# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

# Flag que indica que las vistas materializadas quedaron desactualizadas y un
# cron debe refrescarlas. El refresh de MV cuesta ~26s y no se puede filtrar
# por sorteo, por eso se difiere fuera del request del usuario.
MV_DIRTY_PARAM = 'lottery.mv_dirty'
# Timestamp (UTC, str) del último refresh exitoso de las vistas materializadas.
MV_LAST_REFRESH_PARAM = 'lottery.mv_last_refresh'


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    def _schedule_stats_recompute(self, sorteo_ids):
        """Acumula los sorteos afectados y registra UN solo callback post-commit
        que recomputa los stats incrementales (rápido) y marca las MV como
        sucias. Al correr post-commit se ejecuta una única vez con el estado
        final de la transacción (correcto también para importaciones en lote)."""
        cr = self.env.cr
        pending = getattr(cr, '_lottery_pending_sorteos', None)
        if pending is None:
            pending = set()
            cr._lottery_pending_sorteos = pending
            registry = self.env.registry
            uid = self.env.uid

            def _run():
                try:
                    with registry.cursor() as newcr:
                        env = api.Environment(newcr, uid, {})
                        NumberStat = env['lottery.number.stat']
                        GroupStat = env['lottery.group.stat']
                        for sid in pending:
                            NumberStat.recompute_for_sorteo(sid)
                            GroupStat.recompute_for_sorteo(sid)
                        env['ir.config_parameter'].sudo().set_param(MV_DIRTY_PARAM, '1')
                        env['lottery.stats.service'].clear_caches()
                        newcr.commit()
                except Exception:
                    _logger.exception('Error recomputando stats de lottery (post-commit)')

            cr.postcommit.add(_run)
        pending.update(sorteo_ids)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.sorteo_id:
            self._schedule_stats_recompute([record.sorteo_id.id])
        return record

    def write(self, vals):
        res = super().write(vals)
        sorteo_ids = {r.sorteo_id.id for r in self if r.sorteo_id}
        if sorteo_ids:
            self._schedule_stats_recompute(sorteo_ids)
        return res

    def unlink(self):
        sorteo_ids = {r.sorteo_id.id for r in self if r.sorteo_id}
        res = super().unlink()
        if sorteo_ids:
            self._schedule_stats_recompute(sorteo_ids)
        return res

    @api.model
    def cron_refresh_materialized_views(self):
        """Refresca las vistas materializadas solo si hay cambios pendientes.
        Pensado para un ir.cron frecuente (cada 1 minuto)."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param(MV_DIRTY_PARAM) != '1':
            return
        # Limpiar el flag ANTES de refrescar: si llega un cambio durante el
        # refresh, volverá a marcar dirty y se procesará en el próximo ciclo.
        ICP.set_param(MV_DIRTY_PARAM, '0')
        self._refresh_and_stamp()

    @api.model
    def action_force_refresh_materialized_views(self):
        """Fuerza el refresh de las MV ahora mismo (botón en Ajustes)."""
        self.env['ir.config_parameter'].sudo().set_param(MV_DIRTY_PARAM, '0')
        self._refresh_and_stamp()

    @api.model
    def _refresh_and_stamp(self):
        self.refresh_materialized_views()
        self.env['ir.config_parameter'].sudo().set_param(
            MV_LAST_REFRESH_PARAM, fields.Datetime.to_string(fields.Datetime.now()))
        self.env['lottery.stats.service'].clear_caches()
