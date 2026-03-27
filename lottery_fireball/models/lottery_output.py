# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError

class FireballLotteryOutput(models.Model):
    _inherit = 'lottery.output'

    fireball_id = fields.Many2one('lottery.number', string='Bola extra', domain="[('can_use_hundreds','=',True)]", index=True)

    @api.constrains('date')
    def _check_fireball_id(self):
        limit_date = date(2021, 1, 18)
        for record in self:
            if record.date >= limit_date and not record.fireball_id:
                    raise ValidationError(
                        "Debe registrar un valor para la Bola extra."
                    )


