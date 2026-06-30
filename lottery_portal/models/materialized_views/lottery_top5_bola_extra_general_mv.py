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
                    sorteo_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY sorteo_id
                        ORDER BY date,
                                 CASE turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                    ) AS draw_num,
                    fireball_id
                FROM lottery_output
                WHERE turn_day IN ('afternoon', 'evening')
                  AND fireball_id IS NOT NULL
            ),
            last_seen AS (
                SELECT sorteo_id, fireball_id, MAX(draw_num) AS last_draw_num
                FROM draws
                GROUP BY sorteo_id, fireball_id
            ),
            total AS (
                SELECT sorteo_id, MAX(draw_num) AS total_draws FROM draws GROUP BY sorteo_id
            ),
            atrasos AS (
                SELECT
                    l.sorteo_id,
                    n.name AS centena,
                    t.total_draws - l.last_draw_num AS atraso
                FROM last_seen l
                JOIN lottery_number n ON n.id = l.fireball_id
                JOIN total t ON t.sorteo_id = l.sorteo_id
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY sorteo_id ORDER BY atraso DESC) AS rn
                FROM atrasos
            )
            SELECT sorteo_id, centena, atraso
            FROM ranked
            WHERE rn <= 4
            ORDER BY sorteo_id, atraso DESC;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_bola_extra_atrasos_mv
            ON lottery_top5_bola_extra_general_mv (sorteo_id, atraso DESC);
        """)
