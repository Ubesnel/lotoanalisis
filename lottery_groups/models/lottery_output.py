# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self.env['lottery.group'].cron_recompute_from_sql()
        return record

    def write(self, vals):
        res = super().write(vals)
        self.env['lottery.group'].cron_recompute_from_sql()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['lottery.group'].cron_recompute_from_sql()
        return res
