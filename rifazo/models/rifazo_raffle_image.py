# -*- coding: utf-8 -*-
from odoo import fields, models


class RifazoRaffleImage(models.Model):
    _name = 'rifazo.raffle.image'
    _description = 'Imagen de rifa'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    raffle_id = fields.Many2one('rifazo.raffle', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char('Descripción')
