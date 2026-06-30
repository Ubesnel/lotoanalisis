# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop5BolaExtraNocheMV(models.Model):
    _name = 'lottery.top5.bola.extra.noche.mv'
    _description = 'Lottery Top 5 Bola Extra Noche Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top5_bola_extra_noche_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top5_bola_extra_noche_mv AS
            WITH last_seen AS (
                SELECT
                    sorteo_id, fireball_id,
                    (SELECT MAX(date) FROM lottery_output lo2
                     WHERE lo2.turn_day = 'evening' AND lo2.fireball_id IS NOT NULL
                       AND lo2.sorteo_id = lo.sorteo_id) - MAX(lo.date) AS atraso
                FROM lottery_output lo
                WHERE lo.turn_day = 'evening' AND lo.fireball_id IS NOT NULL
                GROUP BY sorteo_id, fireball_id
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY sorteo_id ORDER BY atraso DESC) AS rn
                FROM last_seen
            )
            SELECT sorteo_id, n.name AS centena, r.atraso
            FROM ranked r
            JOIN lottery_number n ON n.id = r.fireball_id
            WHERE r.rn <= 4
            ORDER BY sorteo_id, atraso DESC;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_bola_extra_atrasos_noche_mv
            ON lottery_top5_bola_extra_noche_mv (sorteo_id, atraso DESC);
        """)
