# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop5BolaExtraGeneralMV(models.Model):
    _name = 'lottery.top5.bola.extra.mv'
    _description = 'Lottery Top 5 Bola Extra Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_bola_extra_general_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_bola_extra_general_mv AS
            WITH draws AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY date,
                                 CASE turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                    ) AS draw_num,
                    fireball_id
                FROM lottery_output
                WHERE turn_day IN ('afternoon', 'evening')
                  AND fireball_id IS NOT NULL
            ),
            last_seen AS (
                SELECT fireball_id, MAX(draw_num) AS last_draw_num
                FROM draws
                GROUP BY fireball_id
            ),
            total AS (
                SELECT MAX(draw_num) AS total_draws FROM draws
            )
            SELECT
                n.name AS centena,
                t.total_draws - l.last_draw_num AS atraso
            FROM last_seen l
            JOIN lottery_number n ON n.id = l.fireball_id
            CROSS JOIN total t
            ORDER BY atraso DESC
            LIMIT 4;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_bola_extra_atrasos_mv
            ON lottery_top5_bola_extra_general_mv (atraso DESC);
        """)
