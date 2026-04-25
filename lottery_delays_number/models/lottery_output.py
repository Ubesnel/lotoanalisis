# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    def _schedule_delays_recompute(self):
        if getattr(self.env.cr, '_lottery_delays_recompute_pending', False):
            return
        self.env.cr._lottery_delays_recompute_pending = True
        registry = self.env.registry
        uid = self.env.uid

        def _run():
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                ln = env['lottery.number']
                ln.cron_recompute_totales()
                ln.cron_recompute_atrasos_full()
                ln.cron_recompute_atrasos_turno()
                ln.cron_recompute_atrasos_por_dia_semana()
                # Actualizar lottery_group con los datos frescos de lottery_number
                env['lottery.group'].cron_recompute_from_sql()
                # Refrescar las vistas materializadas con todos los datos ya actualizados
                cr.execute("SELECT refresh_all_lottery_matviews()")
                cr.commit()
            # Limpiar el caché de Odoo para que la próxima petición lea datos frescos
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                env['lottery.stats.service'].clear_caches()

        self.env.cr.postcommit.add(_run)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self._schedule_delays_recompute()
        return record

    def write(self, vals):
        res = super().write(vals)
        self._schedule_delays_recompute()
        return res

    def unlink(self):
        res = super().unlink()
        self._schedule_delays_recompute()
        return res
