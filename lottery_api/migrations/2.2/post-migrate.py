# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Evalúa las predicciones Premium que ya tienen salida; las marcadas a
    mano no se tocan."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for rec in env['lottery.prediction.premium'].search([('evaluacion_manual', '=', False)]):
        rec._evaluar_seguro()
