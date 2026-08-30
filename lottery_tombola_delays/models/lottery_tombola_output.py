# -*- coding: utf-8 -*-
from odoo import models, api


class LotteryTombolaOutput(models.Model):
    _inherit = 'lottery.tombola.output'

    def _trigger_tombola_stats_recompute(self):
        """Dispara el cron de recálculo de estadísticas de Tómbola. No hace
        falta cola dirty: no hay sorteo_id que particionar, el recálculo
        siempre es sobre la tabla completa (100 números) y es barato, así
        que no hay estado que acarrear entre el write y el cron."""
        cron = self.env.ref('lottery_tombola_delays.cron_recompute_pending_tombola_stats',
                            raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._trigger_tombola_stats_recompute()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._trigger_tombola_stats_recompute()
        return res

    def unlink(self):
        res = super().unlink()
        self._trigger_tombola_stats_recompute()
        return res

    @api.model
    def cron_recompute_pending_tombola_stats(self):
        self.env['lottery.tombola.number.stat'].cron_recompute_all()
