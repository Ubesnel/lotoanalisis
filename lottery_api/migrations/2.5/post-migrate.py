# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Carga los aciertos de todos los Números de la Suerte ya publicados."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['lottery.numeros.suerte'].search([('published', '=', True)])._recalcular_aciertos()
