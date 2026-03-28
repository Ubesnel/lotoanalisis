# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop10NocheMV(models.Model):
    _name = 'lottery.top10.evening.mv'
    _description = 'Lottery Top 10 Evening Materialized View'
    _auto = False


    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top10_evening_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top10_evening_mv AS
            WITH top10 AS (
                SELECT id, name, total_atrasadas_noche
                FROM lottery_number
                ORDER BY total_atrasadas_noche DESC
                LIMIT 10
                ),
            last_output AS (
                SELECT DISTINCT ON (number_id)
                    number_id,
                    date,
                    turn_day
                FROM lottery_output
                WHERE turn_day = 'evening'
                ORDER BY number_id, date DESC
            )
            SELECT
                LPAD(t.name::text, 2, '0') AS name,
                t.total_atrasadas_noche AS total_atrasadas,
                TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha,
                o.turn_day AS ultimo_turno
            FROM top10 t
            LEFT JOIN last_output o ON o.number_id = t.id
            ORDER BY t.total_atrasadas_noche DESC;
        """)
