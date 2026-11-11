# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api

from odoo.addons.lottery_api.models.premium_pass import country_from_ip


def migrate(cr, version):
    """País de los códigos viejos que tienen IP guardada (las pruebas gratis) y de su pase."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    gifts = env['lottery.premium.gift'].search([('country_id', '=', False), ('request_ip', '!=', False)])
    for gift in gifts:
        country = country_from_ip(env, gift.request_ip)
        if not country:
            continue
        gift.country_id = country
        if gift.origin == 'trial' and gift.pass_id and not gift.pass_id.country_id:
            gift.pass_id.write({'country_id': country,
                                'request_ip': gift.pass_id.request_ip or gift.request_ip})
