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

    def _mark_stats_dirty(self, sorteo_ids):
        """Marca los sorteos afectados como pendientes de recálculo y dispara
        el cron que hace el trabajo pesado. Dentro del request solo se inserta
        una fila liviana por sorteo (transaccional: si el guardado se revierte,
        la marca también), así el usuario no espera por los recálculos.

        Los callbacks de cr.postcommit corren en el MISMO hilo del request
        (después del COMMIT pero antes de responder al navegador), por eso el
        esquema anterior seguía siendo lento para el usuario."""
        if not sorteo_ids:
            return
        cr = self.env.cr
        marked = getattr(cr, '_lottery_dirty_sorteos', None)
        if marked is None:
            marked = set()
            cr._lottery_dirty_sorteos = marked
        new_ids = set(sorteo_ids) - marked
        if not new_ids:
            return
        marked.update(new_ids)
        self.env['lottery.stats.dirty'].sudo().create(
            [{'sorteo_id': sid} for sid in new_ids])
        cron = self.env.ref('lottery_delays_number.cron_recompute_pending_stats',
                            raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    @api.model
    def cron_recompute_pending_stats(self):
        """Procesa los sorteos marcados como sucios: recalcula los stats
        incrementales, marca las MV para refresh, recalcula el ranking
        snapshot y limpia cachés. Mismo pipeline y orden que el antiguo
        callback post-commit, pero en un worker de cron (disparado por
        _trigger al guardar; el intervalo del cron es solo red de seguridad)."""
        dirty = self.env['lottery.stats.dirty'].sudo().search([])
        if not dirty:
            return
        sorteo_ids = set(dirty.mapped('sorteo_id').ids)
        dirty.unlink()

        NumberStat = self.env['lottery.number.stat']
        for sid in sorteo_ids:
            NumberStat.recompute_for_sorteo(sid)
        # lottery_groups puede no estar instalado (dependencia opcional).
        if 'lottery.group.stat' in self.env:
            GroupStat = self.env['lottery.group.stat']
            for sid in sorteo_ids:
                GroupStat.recompute_for_sorteo(sid)

        self.env['ir.config_parameter'].sudo().set_param(MV_DIRTY_PARAM, '1')
        # Publica stats y el consumo de la cola antes del refresh largo de MVs,
        # para no retener locks sobre las MVs más de lo necesario.
        self.env.cr.commit()

        # Partes provistas por lottery_portal (dependencia opcional): refresh
        # de MVs y luego ranking snapshot, EN ESE ORDEN, para que el snapshot
        # lea MVs consistentes con las stats recién calculadas (equivale a lo
        # que garantizaba el antiguo trigger SQL trg_refresh_lottery, pero sin
        # bloquear el guardado del usuario).
        try:
            if hasattr(self, 'refresh_materialized_views'):
                self.cron_refresh_materialized_views()
                self.env.cr.commit()
            if 'lottery.stats.service' in self.env:
                self.env['lottery.stats.service'].clear_caches()
            sorteos = self.env['lottery.sorteo'].browse(list(sorteo_ids))
            if hasattr(sorteos, 'compute_ranking_snapshot'):
                sorteos.compute_ranking_snapshot()
        except Exception:
            _logger.exception('Error refrescando MVs/ranking de lottery (cron)')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._mark_stats_dirty({r.sorteo_id.id for r in records if r.sorteo_id})
        return records

    def write(self, vals):
        res = super().write(vals)
        self._mark_stats_dirty({r.sorteo_id.id for r in self if r.sorteo_id})
        return res

    def unlink(self):
        sorteo_ids = {r.sorteo_id.id for r in self if r.sorteo_id}
        res = super().unlink()
        self._mark_stats_dirty(sorteo_ids)
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
