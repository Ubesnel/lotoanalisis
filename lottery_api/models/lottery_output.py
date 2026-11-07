# -*- coding: utf-8 -*-
"""Envío manual de push FCM al confirmar una salida desde el formulario.

El envío es manual (botón) y no automático al crear la salida: un error de
carga con un número ganador inválido ya generó falsas expectativas entre los
jugadores dos veces, así que se prefiere depender de una confirmación humana
antes de notificar.
"""

import logging

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


def _pais(sorteo, lang):
    """País del sorteo; en_US es el idioma base de res.country."""
    country = sorteo.country_id
    if lang == 'en':
        country = country.with_context(lang='en_US')
    return country.name or ''


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
        res = super().write(vals)
        if CAMPOS_SALIDA_PREMIUM.intersection(vals):
            Premium = self.env['lottery.prediction.premium'].sudo()
            # Al mover la salida de fecha/turno, la predicción vieja queda sin salida.
            Premium.search([('output_id', 'in', self.ids),
                            ('evaluacion_manual', '=', False)])._evaluar_seguro()
            Premium._evaluar_salidas(self)
        return res

    def unlink(self):
        premiums = self.env['lottery.prediction.premium'].sudo().search(
            [('output_id', 'in', self.ids), ('evaluacion_manual', '=', False)])
        res = super().unlink()
        premiums.exists()._evaluar_seguro()
        return res

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


class LotteryTombolaOutput(models.Model):
    _inherit = 'lottery.tombola.output'

    def _claves(self):
        return {(r.date, r.turno_id.id) for r in self}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_prediction_validation'):
            self.env['lottery.prediction.premium']._evaluar_tombola(records._claves())
        return records

    def write(self, vals):
        claves = self._claves()
        res = super().write(vals)
        if {'date', 'turno_id', 'number_id'}.intersection(vals):
            self.env['lottery.prediction.premium']._evaluar_tombola(claves | self._claves())
        return res

    def unlink(self):
        claves = self._claves()
        res = super().unlink()
        self.env['lottery.prediction.premium']._evaluar_tombola(claves)
        return res
