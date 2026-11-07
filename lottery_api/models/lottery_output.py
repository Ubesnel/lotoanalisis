# -*- coding: utf-8 -*-
"""Envío manual de push FCM al confirmar una salida desde el formulario.

El envío es manual (botón) y no automático al crear la salida: un error de
carga con un número ganador inválido ya generó falsas expectativas entre los
jugadores dos veces, así que se prefiere depender de una confirmación humana
antes de notificar.
"""

import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models, registry
from odoo.exceptions import UserError

from .fcm_service import PUSH_LANGS, lanzar_push

_logger = logging.getLogger(__name__)

# Campos de la salida que cambian los aciertos de la predicción Premium.
CAMPOS_SALIDA_PREMIUM = {'sorteo_id', 'date', 'turno_id', 'number_id', 'hundreds_id',
                         'premio_2_id', 'premio_3_id'}



def _push_worker(dbname, messages):
    """Envía los push en un hilo aparte, con su propio cursor.

    Se ejecuta fuera del request (post-commit), así el guardado de la salida
    no espera la llamada HTTP a FCM y no se retienen locks durante la red.
    """
    try:
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            FcmService = env['lottery.fcm.service']
            for sorteo_id, title, body, lang in messages:
                try:
                    FcmService.send_push(sorteo_id, title, body, lang)
                except Exception as e:
                    _logger.error(
                        'lottery_api: error enviando push (hilo) sorteo %s: %s',
                        sorteo_id, e
                    )
            # Persiste el cache del token de acceso escrito por send_push.
            cr.commit()
    except Exception as e:
        _logger.error('lottery_api: error en el hilo de push FCM: %s', e)


def _mensajes(rec, sorteo_id):
    """[(sorteo_id, title, body, lang)] del push de `rec`, uno por idioma."""
    return [(sorteo_id, *rec._build_push_message(rec, lang), lang) for lang in PUSH_LANGS]


def _turno_label(sorteo, turno, fecha, lang):
    """Turno con su hora ('Tarde 12:00 PM'); en inglés con su name_en."""
    label = sorteo._turno_con_hora(turno, fecha)
    nombre = turno.name or ''
    if lang == 'en' and turno.name_en and label.startswith(nombre):
        label = turno.name_en + label[len(nombre):]
    return label


# Nombres fijos: el push no depende del idioma del usuario que lo dispara
# (los crons corren como OdooBot) ni de las traducciones de res.country.
PAISES = {
    'US': ('Estados Unidos', 'United States'),
    'DO': ('República Dominicana', 'Dominican Republic'),
    'SX': ('San Martín', 'Sint Maarten'),
    'NI': ('Nicaragua', 'Nicaragua'),
    'HN': ('Honduras', 'Honduras'),
    'SV': ('El Salvador', 'El Salvador'),
    'CR': ('Costa Rica', 'Costa Rica'),
    'UY': ('Uruguay', 'Uruguay'),
}


def _pais(sorteo, lang):
    """País del sorteo en el idioma del push."""
    country = sorteo.country_id
    if not country:
        return ''
    nombres = PAISES.get(country.code or '')
    if nombres:
        return nombres[1] if lang == 'en' else nombres[0]
    lang_odoo = 'en_US' if lang == 'en' else (
        sorteo.env['res.lang'].sudo().search([('code', '=like', 'es%')], limit=1).code
        or sorteo.env.lang)
    return country.with_context(lang=lang_odoo).name or ''


def _premios(out):
    """Números (enteros) de los premios 1, 2 y 3 de la salida."""
    return [n.name for n in (out.number_id, out.premio_2_id, out.premio_3_id) if n]


def _sorteo_con_pais(sorteo, lang):
    """'Tennessee (Estados Unidos)': hay loterías que se llaman igual en
    distintos países."""
    pais = _pais(sorteo, lang)
    return f'{sorteo.name} ({pais})' if pais else sorteo.name


def _lista(partes, en):
    """['A', 'B', 'C'] → 'A, B y C' / 'A, B and C'."""
    if len(partes) < 2:
        return ''.join(partes)
    return '%s %s %s' % (', '.join(partes[:-1]), 'and' if en else 'y', partes[-1])


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    push_sent = fields.Boolean(string='Notificación enviada', default=False, readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_prediction_validation'):
            self.env['lottery.prediction.premium']._evaluar_salidas(records)
        return records

    def write(self, vals):
        cambia = CAMPOS_SALIDA_PREMIUM.intersection(vals)
        antes = self._claves_prediccion() if cambia else set()
        res = super().write(vals)
        if cambia:
            Premium = self.env['lottery.prediction.premium'].sudo()
            # Al mover la salida de fecha/turno, la predicción vieja queda sin salida.
            Premium.search([('output_id', 'in', self.ids),
                            ('evaluacion_manual', '=', False)])._evaluar_seguro()
            Premium._evaluar_salidas(self)
            self._reevaluar_predicciones(antes | self._claves_prediccion())
        return res

    def unlink(self):
        premiums = self.env['lottery.prediction.premium'].sudo().search(
            [('output_id', 'in', self.ids), ('evaluacion_manual', '=', False)])
        claves = self._claves_prediccion()
        res = super().unlink()
        premiums.exists()._evaluar_seguro()
        self._reevaluar_predicciones(claves)
        return res

    def _claves_prediccion(self):
        return {(r.sorteo_id.id, r.date, r.turno_id.id) for r in self}

    def _reevaluar_predicciones(self, claves):
        """Vuelve a evaluar la predicción normal de esas (sorteo, fecha, turno)
        tras corregir o borrar una salida; sin salida, queda sin evaluar."""
        Prediction = self.env['lottery.prediction'].sudo()
        Output = self.sudo()
        for sorteo_id, date, turno_id in claves:
            dominio = [('sorteo_id', '=', sorteo_id), ('date', '=', date),
                       ('turno_id', '=', turno_id)]
            try:
                with self.env.cr.savepoint():
                    out = Output.search(dominio, limit=1)
                    if out.number_id:
                        out._check_predictions()
                    else:
                        Prediction.search(dominio).write(dict.fromkeys((
                            'cumplida', 'cumplida_30', 'cumplida_20', 'cumplida_10',
                            'cumplida_5', 'cumplida_super_magico', 'verification_date'), False))
            except Exception:  # noqa: BLE001 - no frena la corrección de la salida
                _logger.exception('lottery_api: no se pudo reevaluar la predicción %s', dominio)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación push para esta salida.')
        if not self.sorteo_id.show_in_app:
            raise UserError('Este sorteo no está habilitado para mostrarse en la app.')

        messages = _mensajes(self, self.sorteo_id.id)

        # El envío HTTP se difiere al commit, para no bloquear la UI esperando la red.
        lanzar_push(self.env.cr, _push_worker, (self.env.cr.dbname, messages))
        self.write({
            'push_sent': True,
            'push_sent_date': fields.Datetime.now(),
        })

    def _build_push_message(self, out, lang='es'):
        en = lang == 'en'
        turn_label = _turno_label(out.sorteo_id, out.turno_id, out.date, lang)
        centena = out.hundreds_id.name if out.hundreds_id else ''
        numero = str(out.number_id.name).zfill(2) if out.number_id else ''
        numero_completo = f'{centena}{numero}'

        partes = [
            f'{"Draw" if en else "Turno"}: {turn_label}',
            f'{"Number" if en else "Número"}: {numero_completo}',
        ]

        if out.premio_2_id and out.premio_3_id:
            p2 = str(out.premio_2_id.name).zfill(2)
            p3 = str(out.premio_3_id.name).zfill(2)
            partes.append(f'Runners: {p2} and {p3}' if en else f'Corridos: {p2} y {p3}')

        if out.fireball_id:
            partes.append(f'{"Extra ball" if en else "Bola extra"}: {out.fireball_id.name}')

        # Los aciertos fuertes (Súper Mágico, tabla de 5 y de 10) se
        # festejan; el 20, el 30 y el total se informan sin celebración.
        # La rama genérica de abajo ya arma el texto del 20 y del 30.
        tabla_magicos = self._tabla_numeros_magicos(out)
        if tabla_magicos == 'super':
            partes.append(
                '🎉 Congratulations! The 1st prize was the Super Magic' if en else
                '🎉 ¡Felicitaciones! El Premio 1 fue el Súper Mágico')
        elif tabla_magicos in ('5', '10'):
            partes.append(
                f'🎉 Congratulations! The 1st prize was in the {tabla_magicos} '
                f'Magic Numbers table' if en else
                f'🎉 ¡Felicitaciones! El Premio 1 estuvo en la tabla de '
                f'{tabla_magicos} Números Mágicos')
        elif tabla_magicos == 'general':
            partes.append(
                '🔮 The 1st prize was in the general Magic Numbers table' if en else
                '🔮 El Premio 1 estuvo en la tabla general de Números Mágicos')
        elif tabla_magicos:
            partes.append(
                f'🔮 The 1st prize was in the {tabla_magicos} Magic Numbers table' if en else
                f'🔮 El Premio 1 estuvo en la tabla de {tabla_magicos} Números Mágicos')

        suerte = self._en_numeros_suerte(out)
        if suerte:
            num, fuerte, virado, fecha_suerte = suerte
            dia = fecha_suerte.strftime('%d/%m/%Y')
            if en:
                cual = (f'the strongest of the Lucky Numbers of {dia}' if fuerte
                        else f'one of the Lucky Numbers of {dia}')
                partes.append(
                    f'🔄 The 1st prize matches {num} reversed, {cual}. Flip it and win!'
                    if virado else f'🍀 The 1st prize matches {num} straight, {cual}')
            else:
                cual = (f'el más fuerte de los Números de la Suerte del {dia}' if fuerte
                        else f'uno de los Números de la Suerte del {dia}')
                partes.append(
                    f'🔄 El Premio 1 coincide con el virado del {num}, {cual}. ¡El que vira gana!'
                    if virado else f'🍀 El Premio 1 coincide directo con el {num}, {cual}')

        premium = self._aciertos_premium(out, en)
        if premium:
            partes.append(('⭐ Premium hit! ' if en else '⭐ ¡Premium acertó! ')
                          + ' · '.join(premium))

        # El país va en el título: hay loterías que se llaman igual en
        # distintos países (La Diaria de Honduras y la de Nicaragua).
        sorteo = out.sorteo_id.name
        pais = _pais(out.sorteo_id, lang)
        if pais:
            sorteo = f'{sorteo} ({pais})'
        if en:
            title = f'🎯 {sorteo} result available'
            cierre = '📈 Check the updated analysis for the next draw'
        else:
            title = f'🎯 Resultado {sorteo} disponible'
            cierre = '📈 Consulta el análisis actualizado para el próximo sorteo'
        body = ' · '.join(partes) + '\n' + cierre
        return title, body

    def _aciertos_premium(self, out, en):
        """Lo que acertó la Predicción Premium publicada de esta salida, en
        texto (sin centenas). Lee la evaluación ya guardada."""
        rec = self.env['lottery.prediction.premium'].sudo().search([
            ('sorteo_id', '=', out.sorteo_id.id),
            ('date', '=', out.date),
            ('turno_id', '=', out.turno_id.id),
            ('published', '=', True),
            ('evaluada', '=', True),
        ], limit=1)
        if not rec:
            return []
        num = out.number_id.name if out.number_id else None
        partes = []
        if rec.acierto_linea:
            partes.append(f'{"Top line" if en else "Línea top"} {rec.linea_top}')
        if rec.acierto_terminal:
            partes.append(f'{"Top ending" if en else "Terminal top"} {rec.terminal_top}')
        if rec.acierto_fuerte:
            lado = rec._lado(num) if num is not None else ''
            de = {'linea': ' (top line)' if en else ' de la línea top',
                  'terminal': ' (top ending)' if en else ' del terminal top'}.get(lado, '')
            partes.append(f'{"Strong number" if en else "Número fuerte"} '
                          f'{"%02d" % num if num is not None else ""}{de}'.replace('  ', ' '))
        if rec.acierto_terna:
            partes.append(f'{"Triple" if en else "Terna"} {out.complete_number or ""}'.strip())
        if rec.acierto_parle:
            premios = _premios(out)
            pares = {(min(a, b), max(a, b))
                     for i, a in enumerate(premios) for b in premios[i + 1:]}
            acertados = [p for p in rec.parle_ids if p.numero_1 and p.numero_2 and (
                min(p.numero_1.name, p.numero_2.name),
                max(p.numero_1.name, p.numero_2.name)) in pares]
            acertados.sort(key=lambda p: not p.destacado)
            for p in acertados:
                fuerte = (' strong' if en else ' fuerte') if p.destacado else ''
                partes.append(f'{"Parlay" if en else "Parlé"}{fuerte} '
                              f'{p.numero_1.name:02d}-{p.numero_2.name:02d}')
            if not acertados:
                partes.append('Parlay' if en else 'Parlé')
        if rec.acierto_tombola:
            lineas = rec.tombola_linea_ids.filtered('acertada').ordenadas()
            for t in lineas:
                n = len(t.numeros())
                cuantos = (f'{t.aciertos} of {n}' if en else f'{t.aciertos} de {n}')
                partes.append(f'Tómbola {"of" if en else "de"} {n}: '
                              + (f'{cuantos}!' if en and t.completa else
                                 f'¡{cuantos}!' if t.completa else cuantos))
            if not lineas:
                partes.append('Tómbola')
        return partes

    def _en_numeros_suerte(self, out):
        """(número de la suerte 'NN', es el más fuerte, virado, fecha) si el
        Premio 1 coincide directo o virado (29 ↔ 92) con uno de los Números de
        la Suerte publicados de ese día; None si no. Directo gana sobre
        virado. Un sorteo antes de la hora de corte de Ajustes es del día
        anterior."""
        if not out.number_id or not out.date:
            return None
        params = self.env['ir.config_parameter'].sudo()
        corte = float(params.get_param('lottery_api.suerte_hora') or 6.0)
        dow = str(out.date.weekday())
        slot = out.sorteo_id.slot_ids.filtered(
            lambda sl: sl.dow == dow and sl.turno_id == out.turno_id)[:1]
        fecha = out.date
        if slot and 0 < slot.hora_sorteo < corte:
            fecha -= timedelta(days=1)
        suerte = self.env['lottery.numeros.suerte'].sudo().search([
            ('date', '=', fecha), ('published', '=', True),
        ], limit=1)
        if not suerte:
            return None
        n = out.number_id.name
        virado = (n % 10) * 10 + n // 10
        numeros = {s.name: s for s in suerte.number_ids_5}
        for valor, es_virado in ((n, False), (virado, True)):
            if valor in numeros and not (es_virado and valor == n):
                fuerte = numeros[valor] == suerte.super_magico_id
                return '%02d' % valor, fuerte, es_virado, fecha
        return None

    def _tabla_numeros_magicos(self, out):
        """En qué lista de Números Mágicos estaba el número salido — siempre
        la más chica (más específica) en la que estaba, ya que
        Súper Mágico ⊂ 5 ⊂ 10 ⊂ 20 ⊂ 30 ⊂ Total por construcción (ver
        lottery.prediction.action_completar_numeros y la restricción
        _check_super_magico_en_5).

        Devuelve 'super', '5', '10', '20', '30', 'general' (solo en la lista
        completa de Números a predecir, sin llegar al 20) o None. El caso
        'super' va primero justamente porque el Súper Mágico es uno de los
        5: sin ese chequeo el aviso decía "tabla de 5" y se perdía el
        acierto más fuerte de la predicción.

        Lee los booleanos `cumplida*` que `_check_predictions()` (lottery_portal)
        ya dejó marcados en la predicción al registrar esta salida — no
        recalcula nada. None si no hay predicción publicada para esa fecha/
        turno/sorteo, o si el número no estaba en ninguna lista."""
        prediction = self.env['lottery.prediction'].sudo().search([
            ('sorteo_id', '=', out.sorteo_id.id),
            ('date', '=', out.date),
            ('turno_id', '=', out.turno_id.id),
            ('published', '=', True),
        ], limit=1)
        if not prediction:
            return None
        if prediction.cumplida_super_magico:
            return 'super'
        if prediction.cumplida_5:
            return '5'
        if prediction.cumplida_10:
            return '10'
        if prediction.cumplida_20:
            return '20'
        if prediction.cumplida_30:
            return '30'
        if prediction.cumplida:
            return 'general'
        return None


# Números que saca la Tómbola de Uruguay por turno.
TOMBOLA_TOTAL = 20
# Solo avisa tómbolas recientes: el importador también carga históricos.
TOMBOLA_PUSH_DIAS = 2


def _mejor_tombola(lineas, salidos):
    """(tamaño, aciertos, cuántas líneas) de la mejor tómbola acertada:
    la más grande y, dentro de ese tamaño, la de más aciertos; o None."""
    from .prediction_premium import MINIMO_TOMBOLA
    acertadas = []
    for linea in lineas:
        numeros = linea.numeros()
        aciertos = sum(1 for n in numeros if n in salidos)
        if numeros and aciertos >= MINIMO_TOMBOLA.get(len(numeros), len(numeros)):
            acertadas.append((len(numeros), aciertos))
    if not acertadas:
        return None
    mejor = max(acertadas)
    return mejor[0], mejor[1], acertadas.count(mejor)


def _texto_tombola(mejor, en):
    """'la de 5: 4 de 5' / '2 tómbolas de 3: 3 de 3 cada una'."""
    tamano, aciertos, cuantas = mejor
    if en:
        if cuantas > 1:
            return f'{cuantas} tómbolas of {tamano}: {aciertos} of {tamano} each'
        return f'the one of {tamano}: {aciertos} of {tamano}'
    if cuantas > 1:
        return f'{cuantas} tómbolas de {tamano}: {aciertos} de {tamano} cada una'
    return f'la de {tamano}: {aciertos} de {tamano}'


class LotteryTombolaOutput(models.Model):
    _inherit = 'lottery.tombola.output'

    def _claves(self):
        return {(r.date, r.turno_id.id) for r in self}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_prediction_validation'):
            self.env['lottery.prediction.premium']._evaluar_tombola(records._claves())
            records._push_tombola(records._claves())
        return records

    def write(self, vals):
        claves = self._claves()
        res = super().write(vals)
        if {'date', 'turno_id', 'number_id'}.intersection(vals):
            self.env['lottery.prediction.premium']._evaluar_tombola(claves | self._claves())
            self._push_tombola(self._claves())
        return res

    def _push_tombola(self, claves):
        """Avisa la mejor tómbola acertada (normal y Premium) cuando el turno
        ya tiene los 20 números; una sola vez por predicción."""
        desde = fields.Date.context_today(self) - timedelta(days=TOMBOLA_PUSH_DIAS)
        for date, turno_id in claves:
            if date < desde:
                continue
            try:
                with self.env.cr.savepoint():
                    self._push_tombola_turno(date, turno_id)
            except Exception:  # noqa: BLE001 - no frena la carga de la tómbola
                _logger.exception('lottery_api: no se pudo avisar la tómbola %s %s', date, turno_id)

    def _push_tombola_turno(self, date, turno_id):
        salidas = self.sudo().search([('date', '=', date), ('turno_id', '=', turno_id)])
        salidos = set(salidas.mapped('number_id.name'))
        if len(salidos) < TOMBOLA_TOTAL:
            return
        dominio = [('date', '=', date), ('turno_id', '=', turno_id),
                   ('published', '=', True), ('tombola_linea_ids', '!=', False),
                   ('tombola_push_sent', '=', False), ('sorteo_id.show_in_app', '=', True)]
        normal = self.env['lottery.prediction'].sudo().search(dominio, limit=1)
        premium = self.env['lottery.prediction.premium'].sudo().search(dominio, limit=1)
        mejor_normal = normal and _mejor_tombola(normal.tombola_linea_ids, salidos)
        mejor_premium = premium and _mejor_tombola(premium.tombola_linea_ids, salidos)
        if not (mejor_normal or mejor_premium):
            return
        sorteo = (normal or premium).sorteo_id
        turno = self.env['lottery.turno'].browse(turno_id)
        messages = []
        for lang in PUSH_LANGS:
            en = lang == 'en'
            partes = []
            if mejor_normal:
                partes.append(('🎱 Prediction hit ' if en else '🎱 La predicción acertó ')
                              + _texto_tombola(mejor_normal, en))
            if mejor_premium:
                partes.append(('⭐ Premium hit ' if en else '⭐ Premium acertó ')
                              + _texto_tombola(mejor_premium, en))
            titulo = (f'🎱 Tómbola hit · {_sorteo_con_pais(sorteo, lang)}' if en
                      else f'🎱 ¡Tómbola acertada! · {_sorteo_con_pais(sorteo, lang)}')
            cierre = ('📈 Check the details in the prediction history' if en
                      else '📈 Consulta el detalle en el historial de predicciones')
            body = (_turno_label(sorteo, turno, date, lang) + ' · '
                    + ' · '.join(partes) + '\n' + cierre)
            messages.append((sorteo.id, titulo, body, lang))
        lanzar_push(self.env.cr, _push_worker, (self.env.cr.dbname, messages))
        if normal:
            normal.write({'tombola_push_sent': True})
        if premium:
            premium.write({'tombola_push_sent': True})

    def unlink(self):
        claves = self._claves()
        res = super().unlink()
        self.env['lottery.prediction.premium']._evaluar_tombola(claves)
        return res
