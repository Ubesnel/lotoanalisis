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
            WITH turn_order AS (
                        SELECT 'afternoon' AS turn_day, 2 AS order_num
                        UNION ALL
                        SELECT 'evening', 3
                    ),
                    centena_last AS (   
                        SELECT lo.fireball_id, lo.date AS last_date, lo.turn_day AS last_turn,
                               t.order_num AS last_turn_order
                        FROM lottery_output lo
                        JOIN turn_order t ON t.turn_day = lo.turn_day
                        WHERE (lo.fireball_id, lo.date, lo.turn_day) IN (
                            SELECT fireball_id, date, turn_day
                            FROM (
                                SELECT fireball_id, date, turn_day,
                                       ROW_NUMBER() OVER (
                                           PARTITION BY fireball_id
                                           ORDER BY date DESC, 
                                                    CASE turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END DESC
                                       ) AS rn
                                FROM lottery_output
                                WHERE turn_day IN ('afternoon','evening')
                            ) sub
                            WHERE rn = 1
                        )
                    )
                    SELECT
                        n.name AS centena,
                        COUNT(*) AS atraso
                    FROM centena_last l
                    JOIN lottery_number n ON n.id = l.fireball_id
                    JOIN lottery_output lo
                        ON lo.turn_day IN ('afternoon','evening')
                       AND ((lo.date > l.last_date) 
                            OR (lo.date = l.last_date AND
                                CASE lo.turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END > l.last_turn_order))
                       AND lo.fireball_id <> l.fireball_id
                    GROUP BY n.name
                    ORDER BY atraso DESC
                    LIMIT 5;
        """)

        self.env.cr.execute("""CREATE INDEX idx_bola_extra_atrasos_mv
                    ON lottery_top5_bola_extra_general_mv (atraso DESC);""")

