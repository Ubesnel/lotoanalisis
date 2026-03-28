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
            WITH calendar AS (
                        SELECT generate_series(
                            (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'evening'),
                            (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'evening'),
                            interval '1 day'
                        )::date AS draw_date
                    ),
                centena_last AS (
                    SELECT hundreds_id, MAX(date) AS last_date
                    FROM lottery_output
                    WHERE turn_day = 'evening'
                    GROUP BY hundreds_id
                )
                SELECT
                    n.name AS centena,
                    COUNT(c.draw_date) AS atraso
                FROM centena_last l
                JOIN lottery_number n ON n.id = l.hundreds_id
                JOIN calendar c
                    ON c.draw_date > l.last_date
                LEFT JOIN lottery_output lo
                    ON lo.hundreds_id = l.hundreds_id
                   AND lo.turn_day = 'evening'
                   AND lo.date = c.draw_date
                WHERE lo.id IS NULL
                GROUP BY n.name
                ORDER BY atraso desc
                limit 5;
        """)

        self.env.cr.execute("""CREATE INDEX idx_centena_atrasos_noche_mv
                    ON lottery_top5_centena_noche_mv (atraso DESC);""")

