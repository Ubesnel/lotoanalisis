# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    sorteo_ids = fields.Many2many('lottery.sorteo', 'lottery_sorteo_users_rel', 'user_id', 'sorteo_id',
                                  string='Sorteos permitidos',
                                  default=lambda self: self.env['lottery.sorteo'].search([]).ids,
                                  help="Sorteos que este usuario puede ver/gestionar. "
                                       "Funciona igual que las compañías permitidas en multicompañía.")

    def write(self, vals):
        res = super().write(vals)
        if 'sorteo_ids' in vals:
            # Las reglas de registro que filtran por sorteo (lottery.output,
            # lottery.number.stat, lottery.group.stat) guardan el dominio YA
            # resuelto: ir.rule._compute_domain está bajo ormcache por usuario,
            # modelo y modo, con la lista de ids adentro. res.users.write solo
            # limpia el caché para los campos de _get_invalidation_fields, y
            # este no está ahí, así que sin esto el cambio recién se ve al
            # reiniciar el servidor: el usuario agrega un sorteo nuevo, guarda,
            # y sus estadísticas siguen invisibles sin ningún aviso.
            self.env.registry.clear_cache()
        return res
