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
            WITH last_seen AS (
                SELECT
                    fireball_id,
                    (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'afternoon')
                    - MAX(date) AS atraso
                FROM lottery_output
                WHERE turn_day = 'afternoon' AND fireball_id IS NOT NULL
                GROUP BY fireball_id
            )
            SELECT n.name AS centena, ls.atraso
            FROM last_seen ls
            JOIN lottery_number n ON n.id = ls.fireball_id
            ORDER BY atraso DESC
            LIMIT 4;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_bola_extra_atrasos_dia_mv
            ON lottery_top5_bola_extra_dia_mv (atraso DESC);
        """)
