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
        self.refresh_materialized_views()

    def refresh_materialized_views(self):
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top10_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top10_afternoon_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top10_evening_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_ultima_salida_dia_semana_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_centena_general_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_centena_dia_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_centena_noche_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top_atrasos_lineas_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top_atrasos_terminales_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_general_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_dia_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_noche_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top10_dia_semana_mv""")
        self.env.cr.execute("""REFRESH MATERIALIZED VIEW lottery_top_atrasos_number_groups_mv""")


