# -*- coding: utf-8 -*-

from odoo import models, tools

class LotteryTopAtrasosLineasMV(models.Model):
    _name = 'lottery.top.atrasos.lineas.mv'
    _description = 'Lottery Top Atrasos Lineas Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top_atrasos_lineas_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top_atrasos_lineas_mv AS
            SELECT
            lg.code,
                CASE lg.code
                    WHEN 'line_0' THEN '00-09'
                    WHEN 'line_1' THEN '10-19'
                    WHEN 'line_2' THEN '20-29'
                    WHEN 'line_3' THEN '30-39'
                    WHEN 'line_4' THEN '40-49'
                    WHEN 'line_5' THEN '50-59'
                    WHEN 'line_6' THEN '60-69'
                    WHEN 'line_7' THEN '70-79'
                    WHEN 'line_8' THEN '80-89'
                    WHEN 'line_9' THEN '90-99'
                END AS name,
            
                lg.salidas_atrasadas AS general,
                lg.salidas_atrasadas_dia AS afternoon,
                lg.salidas_atrasadas_noche AS evening
            
            FROM lottery_group lg
            WHERE lg.code IN (
                'line_0','line_1','line_2','line_3','line_4',
                'line_5','line_6','line_7','line_8','line_9'
            );            
        """)

        self.env.cr.execute("""CREATE INDEX idx_line_atrasos_mv_lineas ON lottery_top_atrasos_lineas_mv (general DESC);""")

