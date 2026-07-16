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
    number_ids = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_rel',
        'prediction_id', 'number_id',
        string='Números a predecir')
    numbers_count = fields.Integer(
        string='Cantidad', compute='_compute_numbers_count', store=True)

    # Se completa automáticamente al registrarse la salida del sorteo:
    # True si el número salido estaba entre los predichos.
    cumplida = fields.Boolean(
        'Se cumplió?', default=False, index=True,
        help='El número que salió en el sorteo estaba entre los números '
             'de esta predicción. Se marca automáticamente al registrar '
             'la salida.')
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
