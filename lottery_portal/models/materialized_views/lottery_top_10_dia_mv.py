# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop10DiaMV(models.Model):
    _name = 'lottery.top10.afternoon.mv'
    _description = 'Lottery Top 10 Afternoon Materialized View'
    _auto = False


    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top10_afternoon_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top10_afternoon_mv AS
            WITH top10 AS (
                SELECT number_id AS id, sorteo_id, total_atrasadas_dia,
                       ROW_NUMBER() OVER (PARTITION BY sorteo_id ORDER BY total_atrasadas_dia DESC) AS rn
                FROM lottery_number_stat
            ),
            last_output AS (
                SELECT DISTINCT ON (number_id, sorteo_id)
                    number_id, sorteo_id, date, turn_day
                FROM lottery_output
                WHERE turn_day = 'afternoon'
                ORDER BY number_id, sorteo_id, date DESC
            )
            SELECT
                t.sorteo_id,
                LPAD(ln.name::text, 2, '0') AS name,
                t.total_atrasadas_dia AS total_atrasadas,
                TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha,
                o.turn_day AS ultimo_turno
            FROM top10 t
            JOIN lottery_number ln ON ln.id = t.id
            LEFT JOIN last_output o ON o.number_id = t.id AND o.sorteo_id = t.sorteo_id
            WHERE t.rn <= 10
            ORDER BY t.sorteo_id, t.total_atrasadas_dia DESC;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_top10_afternoon_mv_sorteo ON lottery_top10_afternoon_mv (sorteo_id, total_atrasadas DESC);
        """)
