# -*- coding: utf-8 -*-
from odoo import models, fields


class LotteryGroup(models.Model):
    _name = 'lottery.group'
    _description = 'Grupos de números'
    _order = 'code'

    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)
    number_ids = fields.Many2many('lottery.number', 'lottery_group_number_rel', 'group_id', 'number_id',
                                  string='Números')
    notes = fields.Text(string='Notas')
    stat_ids = fields.One2many('lottery.group.stat', 'group_id', string='Estadísticas por sorteo')

    _sql_constraints = [
        ('lottery_number_name_unique',
         'unique(name)',
         'El número ya existe, debe ser único.'),
        ('lottery_number_code_unique',
         'unique(code)',
         'El código ya existe, debe ser único.')
    ]
