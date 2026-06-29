# -*- coding: utf-8 -*-

from . import models
from . import wizard


def post_init_hook(env):
    """Al instalar/actualizar, los usuarios que aún no tienen ningún sorteo
    asignado quedan con acceso a todos (mismo criterio que el default del
    campo, para usuarios que ya existían antes de este módulo)."""
    sorteo_ids = env['lottery.sorteo'].search([]).ids
    if not sorteo_ids:
        return
    users_sin_sorteo = env['res.users'].search([('sorteo_ids', '=', False)])
    users_sin_sorteo.write({'sorteo_ids': [(6, 0, sorteo_ids)]})

