# -*- coding: utf-8 -*-
from odoo import models, api


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self._after_change()
        return record

    def write(self, vals):
        res = super().write(vals)
        self._after_change()
        return res

    def unlink(self):
        res = super().unlink()
        self._after_change()
        return res

    def _after_change(self):
        self.env['lottery.group'].cron_recompute_from_sql()
        self.env['lottery.stats.service'].clear_caches()


