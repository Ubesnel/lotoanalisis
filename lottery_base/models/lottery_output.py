# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from .utils import MAPPING_WEEK_DATE, MONTHS


class LotteryOutput(models.Model):
    _name = 'lottery.output'
    _description = 'Salida de Números'
    _order = 'date desc'

    number_id = fields.Many2one('lottery.number', string='Número', required=True, index=True)
    hundreds_id = fields.Many2one('lottery.number', string='Centena', required=True,
                                  domain="[('can_use_hundreds','=',True)]", index=True)
    date = fields.Date(string='Fecha', default=lambda self: fields.Date.today(), required=True)
    turn_day = fields.Selection([('afternoon', 'Tarde'), ('evening', 'Noche')], string='Turno del día', required=True,
                                index=True)
    complete_number = fields.Char(string='Número completo', compute='_compute_complete_number', store=True)
    week_day = fields.Selection([('lu', 'Lunes'), ('ma', 'Martes'), ('mi', 'Miércoles'),
                                 ('ju', 'Jueves'), ('vi', 'Viernes'), ('sa', 'Sábado'), ('do', 'Domingo')],
                                string='Día de la semana', index=True, compute='_compute_week_day', store=True)
    year = fields.Integer(string="Año", compute="_compute_year_month", store=True)
    month = fields.Selection(selection=MONTHS, string="Mes", compute="_compute_year_month", store=True)

    @api.depends('date')
    def _compute_year_month(self):
        for record in self:
            if record.date:
                record.year = record.date.year
                record.month = str(record.date.month)
            else:
                record.year = False
                record.month = False

    _sql_constraints = [
        (
            'unique_date_turn',
            'unique(date, turn_day)',
            'Ya existe una salida registrada para esa fecha y turno.'
        )
    ]

    @api.depends('date', 'turn_day', 'hundreds_id.name', 'number_id')
    def _compute_display_name(self):
        for record in self:
            date_str = record.date.strftime('%d-%m-%Y') if record.date else ''
            turn_label = dict(self._fields['turn_day'].selection).get(record.turn_day, '')
            centena = f"{record.hundreds_id.name}" if record.hundreds_id else ''
            numero = f"{record.number_id.name:02d}" if record.number_id else ''
            combinado = f"{centena}{numero}"
            record.display_name = f"{date_str} / {turn_label} / {combinado}"

    @api.constrains('date', 'turn_day')
    def _check_evening_requires_afternoon(self):
        limit_date = date(2008, 5, 19)
        for record in self:
            if record.date >= limit_date and record.turn_day == 'evening':
                afternoon_exists = self.search_count([
                    ('date', '=', record.date),
                    ('turn_day', '=', 'afternoon'),
                    ('id', '!=', record.id),
                ])
                if not afternoon_exists:
                    raise ValidationError(
                        "No se puede registrar una salida de Noche si no existe previamente una salida de Tarde para la misma fecha."
                    )

    @api.constrains('date', 'turn_day')
    def _check_afternoon_requires_evening(self):

        for record in self:
            if record.date and record.turn_day == 'afternoon':
                fecha_anterior = record.date - timedelta(days=1)
                evening_exists = self.search_count([
                    ('date', '=', fecha_anterior),
                    ('turn_day', '=', 'evening'),
                    ('id', '!=', record.id),
                ])
                if not evening_exists:
                    raise ValidationError(
                        "No se puede registrar una salida de Tarde si no existe previamente una salida de Noche para el día anterior."
                    )

    @api.depends('hundreds_id', 'number_id')
    def _compute_complete_number(self):
        for record in self:
            if record.hundreds_id and record.number_id:
                record.complete_number = f"{record.hundreds_id.name}{record.number_id.name:02d}"
            else:
                record.complete_number = ""

    @api.depends('date')
    def _compute_week_day(self):
        for output in self:
            if output.date:
                output.week_day = MAPPING_WEEK_DATE.get(output.date.weekday())
            else:
                output.week_day = False
