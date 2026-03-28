# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop5BolaExtraDiaMV(models.Model):
    _name = 'lottery.top5.bola.extra.dia.mv'
    _description = 'Lottery Top 5 Bola Extra Dia Materialized View'
    _auto = False


    def init(self):

        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_bola_extra_dia_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_bola_extra_dia_mv AS
            WITH calendar AS (
                        SELECT generate_series(
                            (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                            (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                            interval '1 day'
                        )::date AS draw_date
                    ),
                centena_last AS (
                    SELECT fireball_id, MAX(date) AS last_date
                    FROM lottery_output
                    WHERE turn_day = 'afternoon'
                    GROUP BY fireball_id
                )
                SELECT
                    n.name AS centena,
                    COUNT(c.draw_date) AS atraso
                FROM centena_last l
                JOIN lottery_number n ON n.id = l.fireball_id
                JOIN calendar c
                    ON c.draw_date > l.last_date
                LEFT JOIN lottery_output lo
                    ON lo.fireball_id = l.fireball_id
                   AND lo.turn_day = 'afternoon'
                   AND lo.date = c.draw_date
                WHERE lo.id IS NULL
                GROUP BY n.name
                ORDER BY atraso desc
                limit 5;
        """)

        self.env.cr.execute("""CREATE INDEX idx_bola_extra_atrasos_dia_mv
                    ON lottery_top5_bola_extra_dia_mv (atraso DESC);""")

