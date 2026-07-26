# -*- coding: utf-8 -*-
from odoo import models, fields, api


def _default_sorteo(self):
    return self.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)


class LotteryPrediction(models.Model):
    _name = 'lottery.prediction'
    _description = 'Predicción de números'
    _order = 'date desc, turn_day desc, id desc'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=_default_sorteo,
        help='Sorteo/juego para el que se hace la predicción.')
    date = fields.Date(
        string='Fecha de predicción', required=True, index=True,
        default=lambda self: fields.Date.today(),
        help='Fecha del sorteo para el que se predicen los números.')
    turn_day = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno del día', required=True, index=True)
    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='Solo las predicciones publicadas se envían a la app móvil '
             '(Números Mágicos). Permite prepararlas con anticipación y '
             'publicarlas cuando estén listas.')

    temperature = fields.Selection([
        ('hot',       'Calientes'),
        ('remaining', 'Restantes'),
        ('cold',      'Fríos'),
    ], string='Temperatura', index=True,
        help='Al seleccionar, carga automáticamente los números calientes, '
             'restantes o fríos del último artículo generado para este turno.')

    # ── Números a predecir (listas independientes) ─────────────────────────
    number_ids = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_rel',
        'prediction_id', 'number_id',
        string='Números a predecir')
    number_ids_20 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_20_rel',
        'prediction_id', 'number_id',
        string='20 Números a predecir')
    number_ids_10 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_10_rel',
        'prediction_id', 'number_id',
        string='10 Números a predecir')
    number_ids_5 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_5_rel',
        'prediction_id', 'number_id',
        string='5 Números a predecir')

    numbers_count = fields.Integer(
        string='Cantidad', compute='_compute_numbers_count', store=True)

    # ── Verificación ───────────────────────────────────────────────────────
    cumplida = fields.Boolean(
        'Se cumplió?', default=False, index=True,
        help='El número que salió en el sorteo estaba entre los números '
             'de esta predicción. Se marca automáticamente al registrar '
             'la salida.')
    cumplida_20 = fields.Boolean(
        'Cumplida en 20?', default=False, index=True,
        help='El número salido estaba entre los 20 Números a predecir.')
    cumplida_10 = fields.Boolean(
        'Cumplida en 10?', default=False, index=True,
        help='El número salido estaba entre los 10 Números a predecir.')
    cumplida_5 = fields.Boolean(
        'Cumplida en 5?', default=False, index=True,
        help='El número salido estaba entre los 5 Números a predecir.')
    verification_date = fields.Datetime(
        'Verificada el', readonly=True,
        help='Momento en que se registró la salida y se verificó la '
             'predicción. Vacío = el sorteo aún no se jugó.')

    _sql_constraints = [
        (
            'unique_date_turn_sorteo',
            'unique(date, turn_day, sorteo_id)',
            'Ya existe una predicción registrada para esa fecha, turno y sorteo.'
        )
    ]

    @api.depends('number_ids')
    def _compute_numbers_count(self):
        for rec in self:
            rec.numbers_count = len(rec.number_ids)

    @api.depends('date', 'turn_day', 'sorteo_id.name')
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            turn_label = dict(self._fields['turn_day'].selection).get(rec.turn_day, '')
            sorteo_label = f" / {rec.sorteo_id.name}" if rec.sorteo_id else ''
            rec.display_name = f"{date_str} / {turn_label}{sorteo_label}"

    @api.onchange('temperature', 'turn_day', 'sorteo_id')
    def _onchange_temperature(self):
        if not self.temperature or not self.turn_day or not self.sorteo_id:
            return
        import json as _json
        snapshot_raw = self.sorteo_id.ranking_snapshot
        if not snapshot_raw:
            return
        try:
            snapshot = _json.loads(snapshot_raw)
        except (ValueError, TypeError):
            return
        turn_data = snapshot.get(self.turn_day, {})
        key_map = {
            'hot':       'numbers',
            'cold':      'numbers_cold',
            'remaining': 'numbers_remaining',
        }
        items = turn_data.get(key_map[self.temperature], [])
        names = []
        for item in items:
            raw = item.get('name') if isinstance(item, dict) else str(item)
            try:
                names.append(int(raw))
            except (ValueError, TypeError):
                pass
        if names:
            self.number_ids = self.env['lottery.number'].search([('name', 'in', names)])
        else:
            self.number_ids = self.env['lottery.number']
