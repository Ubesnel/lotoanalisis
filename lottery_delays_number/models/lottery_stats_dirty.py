# -*- coding: utf-8 -*-
from odoo import models, fields


class LotteryStatsDirty(models.Model):
    """Cola mínima de sorteos con estadísticas pendientes de recálculo.

    Al guardar una salida solo se inserta una fila acá (transaccional: si el
    guardado se revierte, la marca también) y se dispara el cron
    cron_recompute_pending_stats, que hace el trabajo pesado en un worker de
    cron sin bloquear la respuesta al usuario.
    """
    _name = 'lottery.stats.dirty'
    _description = 'Sorteos con estadísticas pendientes de recálculo'
    _log_access = False

    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                index=True, ondelete='cascade')
