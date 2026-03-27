# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryNumber(models.Model):
    _name = 'lottery.number'
    _description = 'Números'
    
    name = fields.Integer(string='Número', required=True)
    can_use_hundreds = fields.Boolean(string='Usar en Centena', default=False)


    _sql_constraints = [
        ('lottery_number_name_unique',
         'unique(name)',
         'El número ya existe, debe ser único.')
    ]

    @api.depends('name')
    def _compute_display_name(self):
        for rec in self:
            if rec.name is not None:
                rec.display_name = f"{rec.name}"
            else:
                rec.display_name = ""

