# -*- coding: utf-8 -*-

from odoo import models, tools

class LotteryTop5CentenaNocheMV(models.Model):
    _name = 'lottery.top5.centena.noche.mv'
    _description = 'Lottery Top 5 Centena Noche Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_centena_noche_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_centena_noche_mv AS
            WITH last_seen AS (
                SELECT
                    hundreds_id,
                    (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'evening')
                    - MAX(date) AS atraso
                FROM lottery_output
                WHERE turn_day = 'evening'
                GROUP BY hundreds_id
            )
            SELECT n.name AS centena, ls.atraso
            FROM last_seen ls
            JOIN lottery_number n ON n.id = ls.hundreds_id
            ORDER BY atraso DESC
            LIMIT 4;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_centena_atrasos_noche_mv
            ON lottery_top5_centena_noche_mv (atraso DESC);
        """)
