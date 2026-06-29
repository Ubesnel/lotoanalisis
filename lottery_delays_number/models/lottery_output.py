# -*- coding: utf-8 -*-
from odoo import models, api


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
                env['lottery.number.stat'].cron_recompute_all()
                cr.commit()

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
