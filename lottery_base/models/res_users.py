# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    sorteo_ids = fields.Many2many('lottery.sorteo', 'lottery_sorteo_users_rel', 'user_id', 'sorteo_id',
                                  string='Sorteos permitidos',
                                  default=lambda self: self.env['lottery.sorteo'].search([]).ids,
                                  help="Sorteos que este usuario puede ver/gestionar. "
                                       "Funciona igual que las compañías permitidas en multicompañía.")
