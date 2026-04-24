# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryCentenaWeekdayMV(models.Model):
    _name = 'lottery.centena.weekday.mv'
    _description = 'Lottery Centena and Bola Extra by Weekday Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_centena_weekday_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_centena_weekday_mv AS
            SELECT lo.week_day, 'hundreds_id' AS field_type, ln.name AS centena, COUNT(*) AS total_salidas
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.hundreds_id
            GROUP BY lo.week_day, lo.hundreds_id, ln.name
            UNION ALL
            SELECT lo.week_day, 'fireball_id' AS field_type, ln.name AS centena, COUNT(*) AS total_salidas
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.fireball_id
            WHERE lo.fireball_id IS NOT NULL
            GROUP BY lo.week_day, lo.fireball_id, ln.name;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_centena_weekday_mv
            ON lottery_centena_weekday_mv (week_day, field_type, total_salidas DESC);
        """)
