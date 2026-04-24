# -*- coding: utf-8 -*-

from odoo import models, tools

class LotteryTop5CentenaDiaMV(models.Model):
    _name = 'lottery.top5.centena.dia.mv'
    _description = 'Lottery Top 5 Centena Dia Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_centena_dia_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_centena_dia_mv AS
            WITH last_seen AS (
                SELECT
                    hundreds_id,
                    (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'afternoon')
                    - MAX(date) AS atraso
                FROM lottery_output
                WHERE turn_day = 'afternoon'
                GROUP BY hundreds_id
            )
            SELECT n.name AS centena, ls.atraso
            FROM last_seen ls
            JOIN lottery_number n ON n.id = ls.hundreds_id
            ORDER BY atraso DESC
            LIMIT 4;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_centena_atrasos_dias_mv
            ON lottery_top5_centena_dia_mv (atraso DESC);
        """)
