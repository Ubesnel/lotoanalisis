# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryTop10DiaSemanaMV(models.Model):
    _name = 'lottery.top10.dia.semana.mv'
    _description = 'Lottery Top 10 Dia Semana Materialized View'
    _auto = False


    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top10_dia_semana_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top10_dia_semana_mv AS
            WITH base AS (
            SELECT
                id,
                name,
                salidas_atrasadas_lunes,
                salidas_atrasadas_martes,
                salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves,
                salidas_atrasadas_viernes,
                salidas_atrasadas_sabado,
                salidas_atrasadas_domingo
            FROM lottery_number
        ),        
        last_output AS (
            SELECT DISTINCT ON (number_id, week_day)
                number_id,
                week_day,
                date,
                turn_day
            FROM lottery_output
            ORDER BY number_id, week_day, date DESC
        )
        SELECT
            b.id,
            LPAD(b.name::text, 2, '0') AS name,
            lo.week_day,
            lo.date,
            lo.turn_day,
            b.salidas_atrasadas_lunes,
            b.salidas_atrasadas_martes,
            b.salidas_atrasadas_miercoles,
            b.salidas_atrasadas_jueves,
            b.salidas_atrasadas_viernes,
            b.salidas_atrasadas_sabado,
            b.salidas_atrasadas_domingo
        FROM base b
        LEFT JOIN last_output lo
            ON lo.number_id = b.id;                   
        """)
