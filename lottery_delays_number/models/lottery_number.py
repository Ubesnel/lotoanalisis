# -*- coding: utf-8 -*-
from odoo import models, fields


class LotteryNumber(models.Model):
    _inherit = 'lottery.number'

    number_output_ids = fields.One2many('lottery.output', 'number_id', string='Salidas de número')
    stat_ids = fields.One2many('lottery.number.stat', 'number_id', string='Estadísticas por sorteo')
