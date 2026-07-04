# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.addons.lottery_base import _seed_sorteo_calendars


def migrate(cr, version):
    """En upgrades (donde post_init_hook no corre) siembra el calendario y el
    próximo sorteo de los sorteos que aún no tienen slots."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_sorteo_calendars(env, env['lottery.sorteo'].search([]))
