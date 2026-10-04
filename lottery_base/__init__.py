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
    slots, e inicializa el próximo sorteo. Quiniela UY: Lun-Vie todos sus
    turnos + Sábado solo el último (Noche). Resto (Florida, etc.): todos los
    días con todos sus turnos."""
    Slot = env['lottery.sorteo.slot']
    for sorteo in sorteos:
        if sorteo.slot_ids:
            continue
        turnos = sorteo._ordered_turnos()
        if not turnos:
            continue
        if sorteo.source_code == 'quiniela_uy':
            # Lun(0)-Vie(4) todos los turnos, Sábado(5) solo el último.
            slots = [(str(d), t) for d in range(5) for t in turnos]
            slots.append(('5', turnos[-1]))
        else:
            slots = [(str(d), t) for d in range(7) for t in turnos]
        Slot.create([
            {'sorteo_id': sorteo.id, 'dow': d, 'turno_id': t.id} for d, t in slots
        ])
        sorteo._recompute_next_draw()
