# -*- coding: utf-8 -*-
"""Predicción Premium del próximo sorteo: la versión reducida de lo que la
app muestra gratis (línea y terminal top, sus números fuertes y las ternas
top). Se arma sola desde Recomendados y la predicción del día y turno; la
app la muestra solo publicada y solo a quien tiene pase Premium."""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

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

    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='La app solo muestra las publicadas. Mientras no esté publicada '
             'el cron la recalcula; publicada ya no se toca sola.')
    published_date = fields.Datetime(string='Publicada el', readonly=True, copy=False)

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
        recien_publicadas = self.browse()
        if vals.get('published'):
            recien_publicadas = self.filtered(lambda r: not r.published)
        res = super().write(vals)
        if recien_publicadas:
            recien_publicadas.write({'published_date': fields.Datetime.now()})
        return res

    def _lado(self, num):
        """'linea' / 'terminal' según dónde entra el número, o ''."""
        if self.linea_top and num // 10 == int(self.linea_top):
            return 'linea'
        if self.terminal_top and num % 10 == int(self.terminal_top):
            return 'terminal'
        return ''

    # ── Completar ───────────────────────────────────────────────────────

    def action_completar(self):
        """Línea y terminal top de Recomendados, números fuertes desde la
        predicción del día y ternas top. Precarga: todo queda editable."""
        stats = self.env['lottery.stats.service'].sudo()
        for rec in self:
            data = stats.get_lineas_terminales_probables(
                rec.turno_id.id, str(rec.date), sorteo_id=rec.sorteo_id.id)
            lineas = data.get('lineas') or []
            terminales = data.get('terminales') or []
            rec.write({
                'linea_top': str(lineas[0]['numbers'][0])[0] if lineas else False,
                'terminal_top': str(terminales[0]['numbers'][0])[-1] if terminales else False,
            })
            rec.write({'number_ids': [(6, 0, rec._numeros_fuertes().ids)]})
            rec._completar_ternas()
            rec._completar_parles()
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
        Súper Mágico, después los del 2º número, y así hasta juntar 5."""
        self.ensure_one()
        pred = self.prediction_id
        suerte = self._numeros_suerte()
        if not (pred and self.sorteo_generates_parles and suerte):
            self.write({'parle_ids': [(5, 0, 0)]})
            return
        try:
            parles = pred._parles_premium(suerte, PARLES_TOP)
        except UserError as exc:
            _logger.info('lottery_api: sin parlés top para %s: %s', self.display_name, exc)
            parles = []
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
