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
            WITH turn_order AS (
                    SELECT 'afternoon' AS turn_day, 2 AS order_num
                    UNION ALL
                    SELECT 'evening', 3
                ),
                centena_last AS (   
                    SELECT lo.hundreds_id, lo.date AS last_date, lo.turn_day AS last_turn,
                           t.order_num AS last_turn_order
                    FROM lottery_output lo
                    JOIN turn_order t ON t.turn_day = lo.turn_day
                    WHERE (lo.hundreds_id, lo.date, lo.turn_day) IN (
                        SELECT hundreds_id, date, turn_day
                        FROM (
                            SELECT hundreds_id, date, turn_day,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY hundreds_id
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
                JOIN lottery_number n ON n.id = l.hundreds_id
                JOIN lottery_output lo
                    ON lo.turn_day IN ('afternoon','evening')
                   AND ((lo.date > l.last_date) 
                        OR (lo.date = l.last_date AND
                            CASE lo.turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END > l.last_turn_order))
                   AND lo.hundreds_id <> l.hundreds_id
                GROUP BY n.name
                ORDER BY atraso DESC
                LIMIT 4;
        """)

        self.env.cr.execute("""CREATE INDEX idx_centena_atrasos_mv
                    ON lottery_top5_centena_general_mv (atraso DESC);""")

