# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryGroupsAnalysisMV(models.Model):
    _name = 'lottery.group.analysis.mv'
    _description = 'Lottery Group Analysis Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_group_analysis_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_group_analysis_mv AS
                SELECT
                    g.id AS group_id,
                    n.id AS number_id,
                    LPAD(n.name::text, 2, '0') AS name,                               
                    n.total_atrasadas,
                    n.total_atrasadas_dia,
                    n.total_atrasadas_noche,
                    n.salidas_atrasadas_lunes,
                    n.salidas_atrasadas_martes,
                    n.salidas_atrasadas_miercoles,
                    n.salidas_atrasadas_jueves,
                    n.salidas_atrasadas_viernes,
                    n.salidas_atrasadas_sabado,
                    n.salidas_atrasadas_domingo,
                    n.total_lunes,                    
                    n.total_martes,
                    n.total_miercoles,
                    n.total_jueves,
                    n.total_viernes,
                    n.total_sabado,
                    n.total_domingo,
                    n.total_semana_1,
                    n.total_semana_2,
                    n.total_semana_3,
                    n.total_semana_4,
                    n.total_semana_5,
                    n.cant_salidas_enero,
                    n.cant_salidas_febrero,
                    n.cant_salidas_marzo,
                    n.cant_salidas_abril,
                    n.cant_salidas_mayo,
                    n.cant_salidas_junio,
                    n.cant_salidas_julio,
                    n.cant_salidas_agosto,
                    n.cant_salidas_septiembre,
                    n.cant_salidas_octubre,
                    n.cant_salidas_noviembre,
                    n.cant_salidas_diciembre
                    FROM lottery_group g
                    JOIN lottery_group_number_rel rel ON rel.group_id = g.id
                    JOIN lottery_number n ON n.id = rel.number_id;
        """)

        self.env.cr.execute("""CREATE INDEX idx_lottery_group_analysis_mv ON lottery_group_analysis_mv (group_id);""")
