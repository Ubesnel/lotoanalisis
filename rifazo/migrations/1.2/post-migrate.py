# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Las solicitudes anteriores a efectivo/gratis eran todas por transferencia.
    env = api.Environment(cr, SUPERUSER_ID, {'tracking_disable': True})
    env['rifazo.request'].search([
        ('payment_method', '=', False),
        ('submitted_date', '!=', False),
    ]).write({'payment_method': 'transfer'})
