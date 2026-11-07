# -*- coding: utf-8 -*-
"""Predicción Premium del próximo sorteo: la versión reducida de lo que la
app muestra gratis (línea y terminal top, sus números fuertes y las ternas
top). Se arma sola desde Recomendados y la predicción del día y turno; la
app la muestra solo publicada y solo a quien tiene pase Premium."""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .fcm_service import lanzar_push
from .lottery_output import _lista, _mensajes, _push_worker, _sorteo_con_pais, _turno_label

_logger = logging.getLogger(__name__)

DIGITOS = [(str(d), str(d)) for d in range(10)]
# Números fuertes: 3 de la línea top y 3 del terminal top.
NUMEROS_POR_LADO = 3
# Ternas top: centenas por puesto (Súper Mágico, 2º, 3º). 2+2+1 = 5.
TERNAS_TOP_POR_PUESTO = (2, 2, 1)
# Parlés top: los 5 Números con los 5 de la Suerte, primero los cruzados.
PARLES_TOP = 10
# De esos 10, los que van primero y resaltados en la app.
PARLES_DESTACADOS = 5
# Tómbola: cuántos números de la línea tienen que salir para contar como acierto.
MINIMO_TOMBOLA = {3: 3, 4: 3, 5: 3, 6: 3, 7: 3}
# Si cambian, la evaluación se rehace.
ACIERTOS = ('acierto_linea', 'acierto_terminal', 'acierto_fuerte', 'acierto_centena',
            'acierto_terna', 'acierto_parle', 'acierto_tombola')
CAMPOS_EVALUADOS = {'sorteo_id', 'date', 'turno_id', 'linea_top', 'terminal_top', 'number_ids',
                    'centena_top_1', 'centena_top_2', 'terna_ids', 'parle_ids',
                    'tombola_linea_ids'}


class LotteryPredictionPremium(models.Model):
    _name = 'lottery.prediction.premium'
    _description = 'Predicción Premium'
    _order = 'date desc, turno_sequence desc, id desc'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        ondelete='cascade', domain=[('exclude_from_predictions', '=', False)])
    date = fields.Date(string='Fecha', required=True, index=True)
    turno_id = fields.Many2one(
        'lottery.turno', string='Turno', required=True, index=True,
        ondelete='restrict', domain="[('id', 'in', sorteo_turno_ids)]")
    sorteo_turno_ids = fields.Many2many(
        related='sorteo_id.turno_ids', string='Turnos del sorteo')
    turno_sequence = fields.Integer(
        related='turno_id.sequence', store=True, string='Secuencia del turno')
    sorteo_uses_hundreds = fields.Boolean(
        related='sorteo_id.uses_hundreds', string='Usa centena')
    sorteo_generates_parles = fields.Boolean(
        related='sorteo_id.generates_parles', string='Genera parlés')
    sorteo_code = fields.Char(related='sorteo_id.code', string='Código del sorteo')

    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='La app solo muestra las publicadas. Mientras no esté publicada '
             'el cron la recalcula; publicada ya no se toca sola.')
    published_date = fields.Datetime(string='Publicada el', readonly=True, copy=False)
    push_sent = fields.Boolean(string='Notificación enviada', readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)
    tombola_push_sent = fields.Boolean(
        string='Aviso de tómbola enviado', readonly=True, copy=False,
        help='Se avisó la tómbola acertada al completarse los 20 números.')

    prediction_id = fields.Many2one(
        'lottery.prediction', string='Predicción del día',
        compute='_compute_prediction_id',
        help='Predicción del mismo sorteo, fecha y turno: de ahí salen los '
             'números fuertes y las ternas.')

    linea_top = fields.Selection(DIGITOS, string='Línea top')
    terminal_top = fields.Selection(DIGITOS, string='Terminal top')
    number_ids = fields.Many2many(
        'lottery.number', 'lottery_prediction_premium_number_rel',
        'premium_id', 'number_id', string='Números fuertes',
        help='3 de la línea top y 3 del terminal top.')
    # Las 2 mejores centenas, para que el usuario las combine con otro número.
    centena_top_1 = fields.Selection(DIGITOS, string='Mejor centena')
    centena_top_2 = fields.Selection(DIGITOS, string='2ª mejor centena')
    # Ternas top: Súper Mágico y 2º con las 2 mejores centenas, 3º con la mejor.
    terna_ids = fields.One2many(
        'lottery.prediction.premium.terna', 'premium_id', string='Ternas top')
    parle_ids = fields.One2many(
        'lottery.prediction.premium.parle', 'premium_id', string='Parlés top')
    tombola_linea_ids = fields.One2many(
        'lottery.prediction.premium.tombola', 'premium_id', string='Tómbolas',
        help='Solo Quiniela UY: la primera de cada tamaño (3 a 7) de las '
             'tómbolas de la predicción del día.')

    # Evaluación contra la salida: se marca sola al registrarse la salida.
    # Los aciertos se pueden corregir a mano; eso la deja como manual.
    evaluada = fields.Boolean(string='Evaluada', copy=False, index=True)
    evaluacion_manual = fields.Boolean(
        string='Marcada a mano', copy=False,
        help='Algún acierto se marcó a mano: la evaluación automática ya no '
             'la pisa. El botón Evaluar la vuelve a calcular desde la salida.')
    evaluation_date = fields.Datetime(string='Evaluada el', readonly=True, copy=False)
    output_id = fields.Many2one(
        'lottery.output', string='Salida', readonly=True, copy=False,
        ondelete='set null', index=True)
    resultado = fields.Char(related='output_id.complete_number', string='Resultado')
    acierto_linea = fields.Boolean(string='Acertó línea top', copy=False)
    acierto_terminal = fields.Boolean(string='Acertó terminal top', copy=False)
    acierto_fuerte = fields.Boolean(string='Acertó número fuerte', copy=False)
    acierto_centena = fields.Boolean(string='Acertó centena', copy=False)
    acierto_terna = fields.Boolean(string='Acertó terna', copy=False)
    acierto_parle = fields.Boolean(string='Acertó parlé', copy=False)
    acierto_tombola = fields.Boolean(
        string='Acertó tómbola', copy=False,
        help='Alguna línea llegó al mínimo de números salidos para su tamaño '
             '(3 aciertos en cualquier tamaño: con 3 ya hay premio).')
    acierto_alguno = fields.Boolean(
        string='Algún acierto', compute='_compute_acierto_alguno', store=True, index=True)

    _sql_constraints = [
        ('unique_date_turn_sorteo', 'unique(date, turno_id, sorteo_id)',
         'Ya existe una predicción Premium para esa fecha, turno y sorteo.'),
    ]

    @api.depends('sorteo_id', 'date', 'turno_id')
    def _compute_prediction_id(self):
        Prediction = self.env['lottery.prediction']
        for rec in self:
            if not (rec.sorteo_id and rec.date and rec.turno_id):
                rec.prediction_id = False
                continue
            rec.prediction_id = Prediction.search([
                ('sorteo_id', '=', rec.sorteo_id.id),
                ('date', '=', rec.date),
                ('turno_id', '=', rec.turno_id.id),
            ], limit=1)

    @api.depends(*ACIERTOS)
    def _compute_acierto_alguno(self):
        for rec in self:
            rec.acierto_alguno = any(rec[f] for f in ACIERTOS)

    @api.depends('date', 'turno_id.name', 'sorteo_id.name')
    def _compute_display_name(self):
        for rec in self:
            fecha = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            rec.display_name = ' / '.join(
                p for p in (fecha, rec.turno_id.name, rec.sorteo_id.name) if p)

    @api.constrains('number_ids', 'linea_top', 'terminal_top')
    def _check_numeros_fuertes(self):
        for rec in self:
            if len(rec.number_ids) > 2 * NUMEROS_POR_LADO:
                raise ValidationError(
                    'Los números fuertes son %d como máximo.' % (2 * NUMEROS_POR_LADO))
            for n in rec.number_ids:
                if not rec._lado(int(n.name)):
                    raise ValidationError(
                        'El %02d no es de la línea top ni del terminal top.' % int(n.name))

    def write(self, vals):
        if not self.env.context.get('evaluacion_auto') and set(ACIERTOS).intersection(vals):
            vals = dict(vals, evaluacion_manual=True, evaluada=True)
            if not self.filtered('evaluation_date'):
                vals.setdefault('evaluation_date', fields.Datetime.now())
        recien_publicadas = self.browse()
        if vals.get('published'):
            recien_publicadas = self.filtered(lambda r: not r.published)
        res = super().write(vals)
        if recien_publicadas:
            recien_publicadas.write({'published_date': fields.Datetime.now()})
        if CAMPOS_EVALUADOS.intersection(vals) and not self.env.context.get('evaluacion_auto'):
            self.filtered(lambda r: not r.evaluacion_manual)._evaluar()
        return res

    def _lado(self, num):
        """'linea' / 'terminal' según dónde entra el número, o ''."""
        if self.linea_top and num // 10 == int(self.linea_top):
            return 'linea'
        if self.terminal_top and num % 10 == int(self.terminal_top):
            return 'terminal'
        return ''

    # ── Notificación ────────────────────────────────────────────────────

    def action_send_push_notification(self):
        """Avisa a los suscriptos del sorteo que ya está la Premium."""
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación push para esta predicción Premium.')
        if not self.sorteo_id.show_in_app:
            raise UserError('Este sorteo no está habilitado para mostrarse en la app.')
        if not self.published:
            raise UserError('Esta predicción Premium todavía no está publicada.')
        messages = _mensajes(self, self.sorteo_id.id)
        lanzar_push(self.env.cr, _push_worker, (self.env.cr.dbname, messages))
        self.write({'push_sent': True, 'push_sent_date': fields.Datetime.now()})

    def _build_push_message(self, rec, lang='es'):
        en = lang == 'en'
        turn_label = _turno_label(rec.sorteo_id, rec.turno_id, rec.date, lang)
        fecha = rec.date.strftime('%d/%m/%Y') if rec.date else ''
        sorteo = _sorteo_con_pais(rec.sorteo_id, lang)
        partes = []
        if rec.linea_top or rec.terminal_top:
            partes.append('Most Likely Line & Ending' if en else 'Línea y terminal más probable')
        if rec.parle_ids:
            partes.append('Most Likely Parlays' if en else 'Parlés más probables')
        if rec.terna_ids:
            partes.append('Likely Triples' if en else 'Ternas probables')
        if rec.tombola_linea_ids:
            partes.append('Most Likely Tómbolas' if en else 'Tómbolas más probables')
        contenido = _lista(partes, en)
        if en:
            return f'⭐ Premium prediction available · {sorteo}', (
                f'The Premium prediction for the {fecha} draw ({turn_label}) is now '
                f'in the App' + (f': {contenido}.' if contenido else '.'))
        return f'⭐ Predicción Premium disponible · {sorteo}', (
            f'Ya está en la App la Predicción Premium del sorteo del {fecha} '
            f'({turn_label})' + (f': {contenido}.' if contenido else '.'))

    # ── Evaluación ──────────────────────────────────────────────────────

    def _vals_evaluacion(self, out):
        """Aciertos de esta predicción contra la salida `out`."""
        self.ensure_one()
        num = out.number_id.name if out.number_id else None
        premios = [n.name for n in (out.number_id, out.premio_2_id, out.premio_3_id) if n]
        pares = {(min(a, b), max(a, b)) for i, a in enumerate(premios) for b in premios[i + 1:]}
        centena = str(out.hundreds_id.name) if out.hundreds_id else ''
        vals = {
            'evaluada': True,
            'evaluation_date': fields.Datetime.now(),
            'output_id': out.id,
            'acierto_linea': bool(num is not None and self.linea_top
                                  and num // 10 == int(self.linea_top)),
            'acierto_terminal': bool(num is not None and self.terminal_top
                                     and num % 10 == int(self.terminal_top)),
            'acierto_fuerte': bool(out.number_id and out.number_id in self.number_ids),
            'acierto_centena': bool(centena and centena in (self.centena_top_1, self.centena_top_2)),
            'acierto_terna': bool(out.complete_number
                                  and out.complete_number in self.terna_ids.mapped('terna')),
            'acierto_parle': any(
                (min(p.numero_1.name, p.numero_2.name), max(p.numero_1.name, p.numero_2.name)) in pares
                for p in self.parle_ids if p.numero_1 and p.numero_2),
            'evaluacion_manual': False,
        }
        vals.update(self._vals_tombola())
        return vals

    def _vals_tombola(self):
        """Cuántos números de cada línea salieron en la Tómbola de esa fecha
        y turno; acierta si llega al mínimo de su tamaño."""
        self.ensure_one()
        if not self.tombola_linea_ids:
            return {'acierto_tombola': False}
        lineas = []
        salidos = self._tombola_salidos()
        for linea in self.tombola_linea_ids:
            numeros = linea.numeros()
            aciertos = sum(1 for n in numeros if n in salidos)
            minimo = MINIMO_TOMBOLA.get(len(numeros), len(numeros))
            lineas.append((1, linea.id, {
                'aciertos': aciertos,
                'acertada': bool(numeros) and aciertos >= minimo,
                'completa': bool(numeros) and aciertos == len(numeros),
            }))
        return {'acierto_tombola': any(l[2]['acertada'] for l in lineas),
                'tombola_linea_ids': lineas}

    def _tombola_salidos(self):
        """Números (enteros) de la Tómbola de la misma fecha y turno."""
        self.ensure_one()
        self.env.cr.execute("""
            SELECT n.name FROM lottery_tombola_output t
            JOIN lottery_number n ON n.id = t.number_id
            WHERE t.date = %s AND t.turno_id = %s
        """, (self.date, self.turno_id.id))
        return {r[0] for r in self.env.cr.fetchall()}

    def _vals_sin_evaluar(self):
        vals = dict.fromkeys(
            ('evaluada', 'evaluacion_manual', 'evaluation_date', 'output_id') + ACIERTOS, False)
        vals['tombola_linea_ids'] = [(1, l.id, {'aciertos': 0, 'acertada': False, 'completa': False})
                                     for l in self.tombola_linea_ids]
        return vals

    def action_evaluar(self):
        """Botón: rehace la evaluación desde la salida, aunque esté marcada a mano."""
        self._evaluar()
        return True

    def _evaluar(self):
        """Evalúa contra la salida del mismo sorteo, fecha y turno; sin salida
        queda sin evaluar."""
        Output = self.env['lottery.output'].sudo()
        for rec in self.sudo().with_context(evaluacion_auto=True):
            out = Output.search([
                ('sorteo_id', '=', rec.sorteo_id.id),
                ('date', '=', rec.date),
                ('turno_id', '=', rec.turno_id.id),
            ], limit=1)
            rec.write(rec._vals_evaluacion(out) if out and out.number_id
                      else rec._vals_sin_evaluar())

    def _evaluar_seguro(self):
        """Para los hooks de salidas: un error al evaluar no frena la carga."""
        if not self:
            return
        try:
            with self.env.cr.savepoint():
                self._evaluar()
        except Exception:  # noqa: BLE001
            _logger.exception('lottery_api: no se pudo evaluar la Premium %s', self.ids)

    @api.model
    def _evaluar_salidas(self, outputs):
        """Evalúa las predicciones Premium de esas salidas; las marcadas a
        mano no se tocan."""
        for out in outputs:
            self.sudo().search([
                ('sorteo_id', '=', out.sorteo_id.id),
                ('date', '=', out.date),
                ('turno_id', '=', out.turno_id.id),
                ('evaluacion_manual', '=', False),
            ])._evaluar_seguro()

    @api.model
    def _evaluar_tombola(self, claves):
        """Reevalúa las Premium con tómbola de esas (fecha, turno)."""
        for date, turno_id in claves:
            self.sudo().search([
                ('date', '=', date),
                ('turno_id', '=', turno_id),
                ('tombola_linea_ids', '!=', False),
                ('evaluacion_manual', '=', False),
            ])._evaluar_seguro()

    # ── Completar ───────────────────────────────────────────────────────

    def action_completar(self):
        """Línea y terminal top de Recomendados, números fuertes desde la
        predicción del día y ternas top. Precarga: todo queda editable."""
        stats = self.env['lottery.stats.service'].sudo()
        avisos = []
        for rec in self:
            # Los recomendados guardados en la predicción del día, así coinciden
            # con los que ve todo el mundo; sin ellos, el cálculo en vivo.
            lineas, terminales = (rec.prediction_id.reco_lineas_terminales()
                                  if rec.prediction_id else ([], []))
            if not (lineas and terminales):
                data = stats.get_lineas_terminales_probables(
                    rec.turno_id.id, str(rec.date), sorteo_id=rec.sorteo_id.id)
                lineas = [l['idx'] for l in data.get('lineas') or []]
                terminales = [t['idx'] for t in data.get('terminales') or []]
            rec.write({
                'linea_top': str(lineas[0]) if lineas else False,
                'terminal_top': str(terminales[0]) if terminales else False,
            })
            rec.write({'number_ids': [(6, 0, rec._numeros_fuertes().ids)]})
            rec._completar_ternas()
            aviso = rec._completar_parles()
            if aviso:
                avisos.append(aviso)
            rec._completar_tombolas()
        if avisos:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Parlés sin completar',
                    'message': ' '.join(avisos),
                    'type': 'warning',
                    'sticky': True,
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                },
            }
        return True

    def _numeros_fuertes(self):
        """3 y 3 bajando por Súper Mágico, 5, 10, 20 y 30 de la predicción;
        si no alcanzan, los más atrasados del turno en la línea/terminal.
        El número de cruce cuenta para la línea si todavía tiene lugar."""
        self.ensure_one()
        Number = self.env['lottery.number']
        pred = self.prediction_id
        candidatos = Number
        if pred:
            candidatos = (pred.super_magico_id | pred.number_ids_5 | pred.number_ids_10
                          | pred.number_ids_20 | pred.number_ids_30)
        elegidos = {'linea': Number, 'terminal': Number}

        def _sumar(numeros):
            for n in numeros:
                num = int(n.name)
                for lado in ('linea', 'terminal'):
                    if n in elegidos['linea'] | elegidos['terminal']:
                        break
                    if len(elegidos[lado]) >= NUMEROS_POR_LADO:
                        continue
                    if (lado == 'linea' and self.linea_top and num // 10 == int(self.linea_top)) or \
                            (lado == 'terminal' and self.terminal_top and num % 10 == int(self.terminal_top)):
                        elegidos[lado] |= n
                        break

        _sumar(candidatos)
        if any(len(v) < NUMEROS_POR_LADO for v in elegidos.values()):
            _sumar(self._mas_atrasados())
        return elegidos['linea'] | elegidos['terminal']

    def _mas_atrasados(self):
        """Números de la línea y del terminal top, del más atrasado del turno
        al menos atrasado."""
        self.ensure_one()
        nums = set()
        if self.linea_top:
            nums |= {int(self.linea_top) * 10 + u for u in range(10)}
        if self.terminal_top:
            nums |= {d * 10 + int(self.terminal_top) for d in range(10)}
        if not nums:
            return self.env['lottery.number']
        self.env.cr.execute("""
            SELECT s.number_id
            FROM lottery_number_stat_turno s
            WHERE s.sorteo_id = %s AND s.turno_id = %s AND s.number_name = ANY(%s)
            ORDER BY s.total_atrasadas DESC, s.number_name
        """, (self.sorteo_id.id, self.turno_id.id, list(nums)))
        return self.env['lottery.number'].browse([r[0] for r in self.env.cr.fetchall()])

    def _completar_ternas(self):
        """Ternas top: las 2 mejores centenas con el Súper Mágico y con el 2º
        número, y la mejor con el 3º. En Quiniela UY salen del premio 1."""
        self.ensure_one()
        ternas, centenas = [], []
        pred = self._prediccion_ternas() if self.sorteo_uses_hundreds else False
        if pred:
            centenas = pred.centenas_by_temperature(
                pred.sorteo_id, pred.turno_code, pred.temperature)[:2]
            try:
                ternas = pred._armar_ternas(TERNAS_TOP_POR_PUESTO)
            except UserError as exc:
                _logger.info('lottery_api: sin ternas top para %s: %s', self.display_name, exc)
        self.write({
            'centena_top_1': centenas[0] if centenas else False,
            'centena_top_2': centenas[1] if len(centenas) > 1 else False,
            'terna_ids': [(5, 0, 0)] + [(0, 0, {'terna': t}) for t in ternas],
        })

    def _completar_parles(self):
        """Parlés top: los 5 Números de la predicción del día con los 5 de
        la Suerte, primero los cruzados. Van primero y destacados los del
        Súper Mágico, después los del 2º número, y así hasta juntar 5.
        Devuelve el motivo si quedaron vacíos en un sorteo con parlés."""
        self.ensure_one()
        pred = self.prediction_id
        suerte = self._numeros_suerte()
        if not self.sorteo_generates_parles:
            self.write({'parle_ids': [(5, 0, 0)]})
            return None
        if not (pred and suerte):
            self.write({'parle_ids': [(5, 0, 0)]})
            return ('No hay predicción del día.' if not pred else
                    'No hay Números de la Suerte publicados con fecha hasta el %s.'
                    % self.date.strftime('%d/%m/%Y'))
        try:
            parles = pred._parles_premium(suerte, PARLES_TOP)
        except UserError as exc:
            _logger.info('lottery_api: sin parlés top para %s: %s', self.display_name, exc)
            self.write({'parle_ids': [(5, 0, 0)]})
            return str(exc)
        destacados = []
        for numero in pred._orden_de_los_cinco() if parles else []:
            destacados += [p for p in parles if p not in destacados and numero in (
                p[0].name, p[1].name)]
            if len(destacados) >= PARLES_DESTACADOS:
                break
        destacados = destacados[:PARLES_DESTACADOS]
        orden = destacados + [p for p in parles if p not in destacados]
        self.write({'parle_ids': [(5, 0, 0)] + [
            (0, 0, {'sequence': i, 'numero_1': a.id, 'numero_2': b.id,
                    'destacado': (a, b) in destacados})
            for i, (a, b) in enumerate(orden)]})
        return None

    def _completar_tombolas(self):
        """La primera tómbola de cada tamaño de la predicción del día."""
        self.ensure_one()
        Linea = self.env['lottery.prediction.premium.tombola']
        lineas, tamanos = [], set()
        for linea in self.prediction_id.tombola_linea_ids.sorted('id'):
            numeros = linea.numeros()
            if len(numeros) not in tamanos:
                tamanos.add(len(numeros))
                lineas.append(numeros)
        self.write({'tombola_linea_ids': [(5, 0, 0)] + [
            (0, 0, Linea.vals_numeros(n)) for n in sorted(lineas, key=len)]})

    def _numeros_suerte(self):
        """Los 5 Números de la Suerte publicados más recientes a la fecha."""
        self.ensure_one()
        return self.env['lottery.numeros.suerte'].sudo().search([
            ('published', '=', True),
            ('date', '<=', self.date),
        ], order='date desc', limit=1).number_ids_5

    def _prediccion_ternas(self):
        self.ensure_one()
        sorteo = self.sorteo_id._sorteo_ternas()
        return self.env['lottery.prediction'].search([
            ('sorteo_id', '=', sorteo.id),
            ('date', '=', self.date),
            ('turno_id', '=', self.turno_id.id),
        ], limit=1)

    # ── Cron ────────────────────────────────────────────────────────────

    @api.model
    def _cron_preparar_proximo_sorteo(self):
        """Crea la Predicción Premium del próximo sorteo de cada sorteo de la
        app y recalcula las que todavía no están publicadas. Espera a que
        la predicción normal de ese sorteo, fecha y turno esté publicada."""
        sorteos = self.env['lottery.sorteo'].sudo().search([
            ('show_in_app', '=', True),
            ('exclude_from_predictions', '=', False),
        ])
        Prediction = self.env['lottery.prediction'].sudo()
        for sorteo in sorteos:
            try:
                with self.env.cr.savepoint():
                    date_str, turno = sorteo.get_next_draw()
                    if not turno:
                        continue
                    if not Prediction.search_count([
                        ('sorteo_id', '=', sorteo.id),
                        ('date', '=', date_str),
                        ('turno_id', '=', turno.id),
                        ('published', '=', True),
                    ]):
                        continue
                    rec = self.sudo().search([
                        ('sorteo_id', '=', sorteo.id),
                        ('date', '=', date_str),
                        ('turno_id', '=', turno.id),
                    ], limit=1)
                    if not rec:
                        rec = self.sudo().create({
                            'sorteo_id': sorteo.id, 'date': date_str, 'turno_id': turno.id})
                    if not rec.published:
                        rec.action_completar()
                        if sorteo.auto_premium_publish:
                            rec.published = True
                            if sorteo.show_in_app:
                                rec.action_send_push_notification()
            except Exception:  # noqa: BLE001 - un sorteo no frena a los demás
                _logger.exception('lottery_api: predicción Premium falló (sorteo %s)', sorteo.name)
            self.env.cr.commit()


class LotteryPredictionPremiumTerna(models.Model):
    _name = 'lottery.prediction.premium.terna'
    _description = 'Terna top Premium'
    _order = 'terna'

    premium_id = fields.Many2one(
        'lottery.prediction.premium', string='Predicción Premium',
        required=True, ondelete='cascade', index=True)
    # Char: un Integer se come el 0 a la izquierda (098 → 98).
    terna = fields.Char(string='Terna', required=True, size=3)

    _sql_constraints = [
        ('terna_unique_por_premium', 'unique(premium_id, terna)',
         'Esa terna ya está cargada.'),
    ]

    @api.constrains('terna')
    def _check_terna_formato(self):
        for rec in self:
            if not rec.terna or len(rec.terna) != 3 or not rec.terna.isdigit():
                raise ValidationError('La terna tiene que ser un número de 3 cifras (000-999).')


class LotteryPredictionPremiumParle(models.Model):
    _name = 'lottery.prediction.premium.parle'
    _inherit = 'lottery.parle.mixin'
    _description = 'Parlé top Premium'
    _order = 'sequence, id'

    premium_id = fields.Many2one(
        'lottery.prediction.premium', string='Predicción Premium',
        required=True, ondelete='cascade', index=True)
    destacado = fields.Boolean(
        string='Destacado', help='Va primero y resaltado en la app.')

    _sql_constraints = [
        ('parle_unique_por_premium', 'unique(premium_id, numero_1, numero_2)',
         'Ese parlé ya está cargado.'),
    ]


class LotteryPredictionPremiumTombola(models.Model):
    _name = 'lottery.prediction.premium.tombola'
    _inherit = 'lottery.tombola.linea.mixin'
    _description = 'Tómbola Premium'
    _order = 'id'

    premium_id = fields.Many2one(
        'lottery.prediction.premium', string='Predicción Premium',
        required=True, ondelete='cascade', index=True)
    aciertos = fields.Integer(string='Salieron', readonly=True, copy=False,
                              help='Cuántos de sus números salieron en la Tómbola.')
    acertada = fields.Boolean(string='Acertada', readonly=True, copy=False,
                              help='Llegó a 3 aciertos o más: con 3 ya hay premio.')
    completa = fields.Boolean(string='Completa', readonly=True, copy=False,
                              help='Salieron todos sus números.')

    def ordenadas(self):
        """Las acertadas, de la más significativa a la menos: completas
        primero, después las de más números salidos y las más grandes."""
        return self.sorted(lambda t: (not t.completa, -t.aciertos, -len(t.numeros())))
