# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError


class LotteryNumber(models.Model):
    _inherit = 'lottery.number'

    number_output_ids = fields.One2many('lottery.output', 'number_id', string='Salidas de número')

    total_salidas = fields.Integer(store=True, index=True)
    total_salidas_dia = fields.Integer(store=True, index=True)
    total_salidas_noche = fields.Integer(store=True, index=True)

    cant_salidas_enero = fields.Integer(store=True, index=True)
    cant_salidas_febrero = fields.Integer(store=True, index=True)
    cant_salidas_marzo = fields.Integer(store=True, index=True)
    cant_salidas_abril = fields.Integer(store=True, index=True)
    cant_salidas_mayo = fields.Integer(store=True, index=True)
    cant_salidas_junio = fields.Integer(store=True, index=True)
    cant_salidas_julio = fields.Integer(store=True, index=True)
    cant_salidas_agosto = fields.Integer(store=True, index=True)
    cant_salidas_septiembre = fields.Integer(store=True, index=True)
    cant_salidas_octubre = fields.Integer(store=True, index=True)
    cant_salidas_noviembre = fields.Integer(store=True, index=True)
    cant_salidas_diciembre = fields.Integer(store=True, index=True)
    total_domingo = fields.Integer(store=True, index=True)
    total_lunes = fields.Integer(store=True, index=True)
    total_martes = fields.Integer(store=True, index=True)
    total_miercoles = fields.Integer(store=True, index=True)
    total_jueves = fields.Integer(store=True, index=True)
    total_viernes = fields.Integer(store=True, index=True)
    total_sabado = fields.Integer(store=True, index=True)
    total_semana_1 = fields.Integer(store=True, index=True)
    total_semana_2 = fields.Integer(store=True, index=True)
    total_semana_3 = fields.Integer(store=True, index=True)
    total_semana_4 = fields.Integer(store=True, index=True)
    total_semana_5 = fields.Integer(store=True, index=True)

    total_atrasadas = fields.Integer(
        string="Atrasos totales",
        default=0,
        index=True
    )

    total_atrasadas_dia = fields.Integer(
        string="Atrasos por la tarde",
        default=0,
        index=True
    )
    total_atrasadas_noche = fields.Integer(
        string="Atrasos por la noche",
        default=0,
        index=True
    )
    salidas_atrasadas_lunes = fields.Integer(string='Atrasos lunes', help='Salidas atrasadas los Lunes', index=True)
    salidas_atrasadas_martes = fields.Integer(string='Atrasos martes', help='Salidas atrasadas los Martes', index=True)
    salidas_atrasadas_miercoles = fields.Integer(string='Atrasos miércoles', help='Salidas atrasadas los Miércoles',
                                                 index=True)
    salidas_atrasadas_jueves = fields.Integer(string='Atrasos jueves', help='Salidas atrasadas los Jueves', index=True)
    salidas_atrasadas_viernes = fields.Integer(string='Atrasos viernes', help='Salidas atrasadas los Viernes',
                                               index=True)
    salidas_atrasadas_sabado = fields.Integer(string='Atrasos sábado', help='Salidas atrasadas los Sábados', index=True)
    salidas_atrasadas_domingo = fields.Integer(string='Atrasos domingo', help='Salidas atrasadas los Domingos',
                                               index=True)

    def cron_recompute_atrasos_full(self):
        sql_query = """
            WITH ranking AS (
                            SELECT 
                                s.number_id,
                                ROW_NUMBER() OVER (
                                    ORDER BY s.date, s.turn_day
                                ) AS orden_global
                            FROM lottery_output s
                        ),
                        ultima_por_numero AS (
                            SELECT 
                                number_id,
                                MAX(orden_global) AS ultima_orden
                            FROM ranking
                            GROUP BY number_id
                        ),
                        ultima_global AS (
                            SELECT MAX(orden_global) AS max_orden
                            FROM ranking
                        )
                        UPDATE lottery_number n
                        SET total_atrasadas = (
                            SELECT 
                                COALESCE(g.max_orden - u.ultima_orden, g.max_orden)
                            FROM ultima_global g
                            LEFT JOIN ultima_por_numero u
                                ON u.number_id = n.id);
            """
        self.env.cr.execute(sql_query)

    def cron_recompute_totales(self):
        sql_query = """
            WITH stats AS (
                SELECT
                    number_id,
                    COUNT(*) AS total_salidas,
                    COUNT(*) FILTER (WHERE turn_day = 'afternoon') AS total_dia,
                    COUNT(*) FILTER (WHERE turn_day = 'evening') AS total_noche,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 1) AS enero,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 2) AS febrero,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 3) AS marzo,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 4) AS abril,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 5) AS mayo,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 6) AS junio,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 7) AS julio,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 8) AS agosto,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 9) AS septiembre,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 10) AS octubre,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 11) AS noviembre,
                    COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 12) AS diciembre,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 0) AS domingo,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 1) AS lunes,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 2) AS martes,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 3) AS miercoles,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 4) AS jueves,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 5) AS viernes,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 6) AS sabado,
                    COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 1 AND 7)  AS semana_1,
                    COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 8 AND 14) AS semana_2,
                    COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 15 AND 21) AS semana_3,
                    COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 22 AND 28) AS semana_4,
                    COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) >= 29) AS semana_5
                FROM lottery_output
                GROUP BY number_id
            )
            UPDATE lottery_number n
            SET
                total_salidas = COALESCE(s.total_salidas, 0),
                total_salidas_dia = COALESCE(s.total_dia, 0),
                total_salidas_noche = COALESCE(s.total_noche, 0),

                cant_salidas_enero = COALESCE(s.enero, 0),
                cant_salidas_febrero = COALESCE(s.febrero, 0),
                cant_salidas_marzo = COALESCE(s.marzo, 0),
                cant_salidas_abril = COALESCE(s.abril, 0),
                cant_salidas_mayo = COALESCE(s.mayo, 0),
                cant_salidas_junio = COALESCE(s.junio, 0),
                cant_salidas_julio = COALESCE(s.julio, 0),
                cant_salidas_agosto = COALESCE(s.agosto, 0),
                cant_salidas_septiembre = COALESCE(s.septiembre, 0),
                cant_salidas_octubre = COALESCE(s.octubre, 0),
                cant_salidas_noviembre = COALESCE(s.noviembre, 0),
                cant_salidas_diciembre = COALESCE(s.diciembre, 0),
                total_domingo = COALESCE(s.domingo, 0),
                total_lunes = COALESCE(s.lunes, 0),
                total_martes = COALESCE(s.martes, 0),
                total_miercoles = COALESCE(s.miercoles, 0),
                total_jueves = COALESCE(s.jueves, 0),
                total_viernes = COALESCE(s.viernes, 0),
                total_sabado = COALESCE(s.sabado, 0),
                total_semana_1 = COALESCE(s.semana_1, 0),
                total_semana_2 = COALESCE(s.semana_2, 0),
                total_semana_3 = COALESCE(s.semana_3, 0),
                total_semana_4 = COALESCE(s.semana_4, 0),
                total_semana_5 = COALESCE(s.semana_5, 0)
            FROM stats s
            WHERE n.id = s.number_id;
        """
        self.env.cr.execute(sql_query)

    def cron_recompute_atrasos_turno(self):
        sql_query = """
                WITH ranking_turno AS (
                    SELECT
                        s.number_id,
                        s.turn_day,
                        ROW_NUMBER() OVER (
                            PARTITION BY s.turn_day
                            ORDER BY s.date, s.id
                        ) AS orden_turno
                    FROM lottery_output s
                ),

                ultima_por_numero_turno AS (
                    SELECT
                        number_id,
                        turn_day,
                        MAX(orden_turno) AS ultima_orden
                    FROM ranking_turno
                    GROUP BY number_id, turn_day
                ),

                ultima_global_turno AS (
                    SELECT
                        turn_day,
                        MAX(orden_turno) AS max_orden
                    FROM ranking_turno
                    GROUP BY turn_day
                ),

                atrasos AS (
                    SELECT
                        n.id AS number_id,

                        COALESCE(
                            (g_dia.max_orden - u_dia.ultima_orden),
                            g_dia.max_orden
                        ) AS atraso_dia,

                        COALESCE(
                            (g_noche.max_orden - u_noche.ultima_orden),
                            g_noche.max_orden
                        ) AS atraso_noche

                    FROM lottery_number n

                    LEFT JOIN ultima_global_turno g_dia
                        ON g_dia.turn_day = 'afternoon'

                    LEFT JOIN ultima_por_numero_turno u_dia
                        ON u_dia.number_id = n.id
                        AND u_dia.turn_day = 'afternoon'

                    LEFT JOIN ultima_global_turno g_noche
                        ON g_noche.turn_day = 'evening'

                    LEFT JOIN ultima_por_numero_turno u_noche
                        ON u_noche.number_id = n.id
                        AND u_noche.turn_day = 'evening'
                )

                UPDATE lottery_number n
                SET
                    total_atrasadas_dia = a.atraso_dia,
                    total_atrasadas_noche = a.atraso_noche
                FROM atrasos a
                WHERE a.number_id = n.id;
            """
        self.env.cr.execute(sql_query)

    def cron_recompute_atrasos_por_dia_semana(self):
        sql_query = """
        WITH dias AS (
            SELECT generate_series(0,6) AS dow
        ),
        atrasos AS (
            SELECT
                n.id AS number_id,
                d.dow,
                -- calcular la cantidad de semanas completas entre la ultima salida del numero y el ultimo dia registrado del sistema
                GREATEST(
                    0,
                    FLOOR(
                        (COALESCE(s.last_system_date, CURRENT_DATE)::date
                         - COALESCE(s.last_number_date, '1900-01-01')::date) / 7
                    )::int
                ) AS atraso
            FROM lottery_number n
            CROSS JOIN dias d
            LEFT JOIN LATERAL (
                SELECT
                    (SELECT MAX(date) FROM lottery_output WHERE EXTRACT(DOW FROM date) = d.dow) AS last_system_date,
                    (SELECT MAX(date) FROM lottery_output WHERE number_id = n.id AND EXTRACT(DOW FROM date) = d.dow) AS last_number_date
            ) s ON TRUE
        ),
        atrasos_pivot AS (
            SELECT
                number_id,
                MAX(CASE WHEN dow = 0 THEN atraso ELSE 0 END) AS salidas_atrasadas_domingo,
                MAX(CASE WHEN dow = 1 THEN atraso ELSE 0 END) AS salidas_atrasadas_lunes,
                MAX(CASE WHEN dow = 2 THEN atraso ELSE 0 END) AS salidas_atrasadas_martes,
                MAX(CASE WHEN dow = 3 THEN atraso ELSE 0 END) AS salidas_atrasadas_miercoles,
                MAX(CASE WHEN dow = 4 THEN atraso ELSE 0 END) AS salidas_atrasadas_jueves,
                MAX(CASE WHEN dow = 5 THEN atraso ELSE 0 END) AS salidas_atrasadas_viernes,
                MAX(CASE WHEN dow = 6 THEN atraso ELSE 0 END) AS salidas_atrasadas_sabado
            FROM atrasos
            GROUP BY number_id
        )
        UPDATE lottery_number n
        SET
            salidas_atrasadas_domingo  = a.salidas_atrasadas_domingo,
            salidas_atrasadas_lunes    = a.salidas_atrasadas_lunes,
            salidas_atrasadas_martes   = a.salidas_atrasadas_martes,
            salidas_atrasadas_miercoles= a.salidas_atrasadas_miercoles,
            salidas_atrasadas_jueves   = a.salidas_atrasadas_jueves,
            salidas_atrasadas_viernes  = a.salidas_atrasadas_viernes,
            salidas_atrasadas_sabado   = a.salidas_atrasadas_sabado
        FROM atrasos_pivot a
        WHERE n.id = a.number_id;
        """
        self.env.cr.execute(sql_query)
