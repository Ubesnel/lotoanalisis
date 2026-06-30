# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryUltimaSalidaPorDiaMV(models.Model):
    _name = 'lottery.ultima.salida.dia.mv'
    _description = 'Lottery Ultima Salida por Día Materialized View'
    _auto = False


    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_ultima_salida_dia_semana_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_ultima_salida_dia_semana_mv AS
            SELECT
            lo.sorteo_id,
            lo.week_day,
            lo.date,
            TO_CHAR(lo.date, 'DD/MM/YYYY') as fecha,
            MAX(CASE WHEN lo.turn_day = 'afternoon' THEN c.name END) AS centena_dia,
            LPAD(MAX(CASE WHEN lo.turn_day = 'afternoon' THEN ln.name::text END), 2, '0') AS numero_dia,
            MAX(CASE WHEN lo.turn_day = 'afternoon' THEN be.name END) AS bola_extra_dia,
            MAX(CASE WHEN lo.turn_day = 'evening' THEN c.name END) AS centena_noche,
            LPAD(MAX(CASE WHEN lo.turn_day = 'evening' THEN ln.name::text END), 2, '0') AS numero_noche,
            MAX(CASE WHEN lo.turn_day = 'evening' THEN be.name END) AS bola_extra_noche
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            JOIN lottery_number c ON c.id = lo.hundreds_id
            LEFT JOIN lottery_number be ON be.id = lo.fireball_id
            GROUP BY lo.sorteo_id, lo.week_day, lo.date;
        """)
