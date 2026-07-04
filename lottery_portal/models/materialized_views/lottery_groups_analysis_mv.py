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
                    ns.sorteo_id,
                    ns.number_id,
                    LPAD(n.name::text, 2, '0') AS name,
                    ns.total_atrasadas, ns.total_atrasadas_dia, ns.total_atrasadas_noche,
                    ns.salidas_atrasadas_lunes, ns.salidas_atrasadas_martes, ns.salidas_atrasadas_miercoles,
                    ns.salidas_atrasadas_jueves, ns.salidas_atrasadas_viernes, ns.salidas_atrasadas_sabado,
                    ns.salidas_atrasadas_domingo,
                    ns.total_lunes, ns.total_martes, ns.total_miercoles, ns.total_jueves,
                    ns.total_viernes, ns.total_sabado, ns.total_domingo,
                    ns.total_semana_1, ns.total_semana_2, ns.total_semana_3, ns.total_semana_4, ns.total_semana_5,
                    ns.cant_salidas_enero, ns.cant_salidas_febrero, ns.cant_salidas_marzo, ns.cant_salidas_abril,
                    ns.cant_salidas_mayo, ns.cant_salidas_junio, ns.cant_salidas_julio, ns.cant_salidas_agosto,
                    ns.cant_salidas_septiembre, ns.cant_salidas_octubre, ns.cant_salidas_noviembre, ns.cant_salidas_diciembre
                FROM lottery_group g
                JOIN lottery_group_number_rel rel ON rel.group_id = g.id
                JOIN lottery_number_stat ns ON ns.number_id = rel.number_id
                JOIN lottery_number n ON n.id = ns.number_id;
        """)

        self.env.cr.execute("""CREATE INDEX idx_lottery_group_analysis_mv ON lottery_group_analysis_mv (group_id, sorteo_id);""")
