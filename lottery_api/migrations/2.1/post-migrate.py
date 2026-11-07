# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Evalúa las predicciones Premium que ya tienen salida."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['lottery.prediction.premium'].search([])._evaluar()
