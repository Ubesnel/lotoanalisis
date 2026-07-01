# -*- coding: utf-8 -*-

from . import models
from . import wizard


def post_init_hook(env):
    """Al instalar/actualizar, los usuarios que aún no tienen ningún sorteo
    asignado quedan con acceso a todos (mismo criterio que el default del
    campo, para usuarios que ya existían antes de este módulo)."""
    sorteos = env['lottery.sorteo'].search([])
    sorteo_ids = sorteos.ids
    if not sorteo_ids:
        return
    users_sin_sorteo = env['res.users'].search([('sorteo_ids', '=', False)])
    users_sin_sorteo.write({'sorteo_ids': [(6, 0, sorteo_ids)]})

    _seed_sorteo_calendars(env, sorteos)


def _seed_sorteo_calendars(env, sorteos):
    """Siembra el calendario semanal por defecto de cada sorteo que aún no tenga
    slots, e inicializa el próximo sorteo. Quiniela UY: Lun-Vie ambos turnos +
    Sábado solo noche. Resto (Florida, etc.): todos los días, ambos turnos."""
    Slot = env['lottery.sorteo.slot']
    for sorteo in sorteos:
        if sorteo.slot_ids:
            continue
        if sorteo.source_code == 'quiniela_uy':
            # Lun(0)-Vie(4) tarde+noche, Sábado(5) solo noche.
            slots = [(str(d), t) for d in range(5) for t in ('afternoon', 'evening')]
            slots.append(('5', 'evening'))
        else:
            slots = [(str(d), t) for d in range(7) for t in ('afternoon', 'evening')]
        Slot.create([
            {'sorteo_id': sorteo.id, 'dow': d, 'turn': t} for d, t in slots
        ])
        sorteo._recompute_next_draw()

