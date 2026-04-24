# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop5CentenaGeneralMV(models.Model):
    _name = 'lottery.top5.centena.general.mv'
    _description = 'Lottery Top 5 Centena General Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_centena_general_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_centena_general_mv AS
            WITH draws AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY date,
                                 CASE turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                    ) AS draw_num,
                    hundreds_id
                FROM lottery_output
                WHERE turn_day IN ('afternoon', 'evening')
            ),
            last_seen AS (
                SELECT hundreds_id, MAX(draw_num) AS last_draw_num
                FROM draws
                GROUP BY hundreds_id
            ),
            total AS (
                SELECT MAX(draw_num) AS total_draws FROM draws
            )
            SELECT
                n.name AS centena,
                t.total_draws - l.last_draw_num AS atraso
            FROM last_seen l
            JOIN lottery_number n ON n.id = l.hundreds_id
            CROSS JOIN total t
            ORDER BY atraso DESC
            LIMIT 4;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_centena_atrasos_mv
            ON lottery_top5_centena_general_mv (atraso DESC);
        """)
