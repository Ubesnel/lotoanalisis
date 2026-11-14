# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Marca de sospechosa en las pruebas gratis que ya existían."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['lottery.premium.gift'].search(
        [('origin', '=', 'trial'), ('request_ip', '!=', False)], order='id')._mark_suspect()
