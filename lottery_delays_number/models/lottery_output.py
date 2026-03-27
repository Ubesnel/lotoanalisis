# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self.env['lottery.number'].cron_recompute_totales()
        self.env['lottery.number'].cron_recompute_atrasos_full()
        self.env['lottery.number'].cron_recompute_atrasos_turno()
        self.env['lottery.number'].cron_recompute_atrasos_por_dia_semana()
        return record

    def write(self, vals):
        res = super().write(vals)
        self.env['lottery.number'].cron_recompute_totales()
        self.env['lottery.number'].cron_recompute_atrasos_full()
        self.env['lottery.number'].cron_recompute_atrasos_turno()
        self.env['lottery.number'].cron_recompute_atrasos_por_dia_semana()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['lottery.number'].cron_recompute_totales()
        self.env['lottery.number'].cron_recompute_atrasos_full()
        self.env['lottery.number'].cron_recompute_atrasos_turno()
        self.env['lottery.number'].cron_recompute_atrasos_por_dia_semana()
        return res
