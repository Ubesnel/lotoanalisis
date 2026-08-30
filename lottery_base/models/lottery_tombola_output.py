# -*- coding: utf-8 -*-
"""Salida de la Tómbola de la Quiniela Uruguay.

Es un juego aparte de la Quiniela: en el mismo sorteo (turno) se extraen 20
números de dos dígitos de una tómbola física, todos de una sola vez, sin
premios individuales. No tiene relación con `lottery.output` (que modela
salidas de un número por sorteo/premio).

Una fila por número (20 filas por fecha+turno) y no un many2many de 20
números en una sola fila: los atrasos y las salidas por día/mes se calculan
agrupando por número a través del tiempo, y esa consulta es directa contra
una tabla (número, fecha) — exactamente el mismo patrón que ya usa
`lottery.output` para sus propios atrasos. Con un many2many habría que
atravesar la tabla de relación igual, sin ganar nada a cambio.

Sin unique(date, turn_day, number_id): en los primeros meses publicados
(agosto-diciembre de 2006) hay ~29 sorteos donde la página oficial —y el
extracto firmado— repiten un número dentro de los 20, en vez de traer uno
distinto. No hay forma de reconstruir cuál era el número real, así que se
graba tal cual lo publicó la Dirección de Loterías en su momento en lugar de
inventar un valor. Esas fechas quedan disponibles para consultar, pero no
deberían pesar en atrasos/frecuencias: ver `lottery_portal.tombola_stats_start_date`
en Ajustes, que define desde cuándo se calculan las estadísticas.
"""

from odoo import api, fields, models

from .utils import MAPPING_WEEK_DATE, MONTHS, default_today_local


class LotteryTombolaOutput(models.Model):
    _name = 'lottery.tombola.output'
    _description = 'Salida de la Tómbola (Quiniela Uruguay)'
    _order = 'date desc, turn_day desc, id desc'

    date = fields.Date(string='Fecha', default=default_today_local, required=True)
    turn_day = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno del día', required=True, index=True)
    number_id = fields.Many2one('lottery.number', string='Número', required=True, index=True)
    week_day = fields.Selection([('lu', 'Lunes'), ('ma', 'Martes'), ('mi', 'Miércoles'),
                                 ('ju', 'Jueves'), ('vi', 'Viernes'), ('sa', 'Sábado'), ('do', 'Domingo')],
                                string='Día de la semana', index=True, compute='_compute_week_day', store=True)
    year = fields.Integer(string="Año", compute="_compute_year_month", store=True)
    month = fields.Selection(selection=MONTHS, string="Mes", compute="_compute_year_month", store=True)

    def init(self):
        # "Último atraso de este número" y "salidas por mes": el mismo patrón
        # de índice que usa lottery.output para lo mismo.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS lottery_tombola_output_number_date_idx
            ON lottery_tombola_output (number_id, date)
        """)

    @api.depends('date')
    def _compute_year_month(self):
        for record in self:
            if record.date:
                record.year = record.date.year
                record.month = str(record.date.month)
            else:
                record.year = False
                record.month = False

    @api.depends('date')
    def _compute_week_day(self):
        for record in self:
            if record.date:
                record.week_day = MAPPING_WEEK_DATE.get(record.date.weekday())
            else:
                record.week_day = False

    @api.depends('date', 'turn_day', 'number_id.name')
    def _compute_display_name(self):
        turnos = dict(self._fields['turn_day'].selection)
        for record in self:
            date_str = record.date.strftime('%d-%m-%Y') if record.date else ''
            numero = '%02d' % record.number_id.name if record.number_id else ''
            record.display_name = 'Tómbola %s / %s / %s' % (
                date_str, turnos.get(record.turn_day, ''), numero)
