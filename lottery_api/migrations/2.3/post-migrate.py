# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Tómbola: 3 aciertos ya es premio en cualquier tamaño. Reevalúa las
    Premium con tómbola que no están marcadas a mano."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for rec in env['lottery.prediction.premium'].search([
            ('evaluacion_manual', '=', False), ('tombola_linea_ids', '!=', False)]):
        rec._evaluar_seguro()
