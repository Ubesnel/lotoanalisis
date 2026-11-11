# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Premium ya jugadas: carga los aciertos de Súper Mágico y tablas de 5 y
    10 sin tocar el resto de la evaluación (ni las marcadas a mano)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Premium = env['lottery.prediction.premium'].with_context(evaluacion_auto=True)
    for rec in Premium.search([('evaluada', '=', True), ('output_id', '!=', False)]):
        rec.write(rec._vals_magicos(rec.output_id))
