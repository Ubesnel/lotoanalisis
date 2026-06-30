# -*- coding: utf-8 -*-

from odoo import models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    def _lottery_fix_home_menu(self):
        """Odoo crea su propio menú "Home" -> "/" al instalar el módulo
        website, sin un xmlid fijo que se pueda heredar/renombrar de forma
        declarativa. Si por instalaciones o actualizaciones sucesivas
        terminan existiendo varios menús de nivel superior apuntando a "/",
        los fusiona dejando uno solo llamado "Inicio"."""
        menus = self.search([('url', '=', '/'), ('name', 'in', ('Home', 'Inicio'))])
        if not menus:
            return
        keep = menus[0]
        keep.write({'name': 'Inicio', 'sequence': 5})
        (menus - keep).unlink()
