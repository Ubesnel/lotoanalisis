# -*- coding: utf-8 -*-

from odoo import models, tools

class LotteryTopAtrasosTerminalesMV(models.Model):
    _name = 'lottery.top.atrasos.terminales.mv'
    _description = 'Lottery Top Atrasos Terminales Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top_atrasos_terminales_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top_atrasos_terminales_mv AS
            SELECT
            lg.code,
                CASE lg.code
                    WHEN 'terminal_0' THEN '00-90'
                    WHEN 'terminal_1' THEN '01-91'
                    WHEN 'terminal_2' THEN '02-92'
                    WHEN 'terminal_3' THEN '03-93'
                    WHEN 'terminal_4' THEN '04-94'
                    WHEN 'terminal_5' THEN '05-95'
                    WHEN 'terminal_6' THEN '06-96'
                    WHEN 'terminal_7' THEN '07-97'
                    WHEN 'terminal_8' THEN '08-98'
                    WHEN 'terminal_9' THEN '09-99'
                END AS name,
            
                lg.salidas_atrasadas AS general,
                lg.salidas_atrasadas_dia AS afternoon,
                lg.salidas_atrasadas_noche AS evening
            
            FROM lottery_group lg
            WHERE lg.code IN (
                'terminal_0','terminal_1','terminal_2','terminal_3','terminal_4',
                'terminal_5','terminal_6','terminal_7','terminal_8','terminal_9'
            );            
        """)

        self.env.cr.execute("""CREATE INDEX idx_line_atrasos_mv_terminales ON lottery_top_atrasos_terminales_mv (general DESC);""")

