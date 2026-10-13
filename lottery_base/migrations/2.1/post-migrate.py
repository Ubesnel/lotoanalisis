# -*- coding: utf-8 -*-
"""La Diaria (Honduras) pasa a los turnos por horario (11:00 AM, 3:00 PM,
9:00 PM) en lugar de Mañana/Tarde/Noche.

El sorteo está en un bloque noupdate, así que en una base donde ya existe el
-u no le cambia los turnos: lo hace esta migración. Corre después de cargar la
data, cuando los turnos nuevos ya están creados.

Solo aplica si el sorteo todavía no tiene salidas ni predicciones: con datos
cargados habría que mover cada registro de turno y recalcular atrasos, y eso
no se hace a ciegas. En ese caso deja todo como está y lo avisa en el log."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

NUEVOS = ['lottery_base.turno_h1100', 'lottery_base.turno_h1500', 'lottery_base.turno_h2100']


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    sorteo = env.ref('lottery_base.sorteo_la_diaria', raise_if_not_found=False)
    if not sorteo:
        return
    turnos = env['lottery.turno']
    for xmlid in NUEVOS:
        turnos |= env.ref(xmlid)
    if sorteo.turno_ids == turnos:
        return

    salidas = env['lottery.output'].search_count([('sorteo_id', '=', sorteo.id)])
    predicciones = 0
    if 'lottery.prediction' in env:
        predicciones = env['lottery.prediction'].search_count([('sorteo_id', '=', sorteo.id)])
    if salidas or predicciones:
        _logger.warning('La Diaria tiene %d salidas y %d predicciones: no se cambian sus '
                        'turnos a los de horario. Hay que migrarlos a mano.',
                        salidas, predicciones)
        return

    sorteo.slot_ids.unlink()
    sorteo.with_context(recomputing_next_draw=True).write({
        'turno_ids': [(6, 0, turnos.ids)],
        'next_draw_date': False,
        'next_draw_turno_id': False,
        'next_draw_manual': False,
    })
    _logger.info('La Diaria: turnos cambiados a %s.', ', '.join(turnos.mapped('name')))
