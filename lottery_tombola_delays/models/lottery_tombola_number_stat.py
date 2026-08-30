# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Mismo vocabulario de turn_day que lottery.tombola.output: 'afternoon' es
# Tarde, el resto ('evening') es Noche.
EARLY_TURNS = ('afternoon',)

# ir.config_parameter que define desde cuándo cuentan las estadísticas de
# Tómbola (excluye los ~29 sorteos de 2006 con un número repetido en vez de
# uno distinto entre los 20). Definido en lottery_portal, pero se lee acá
# directo por clave para no depender de ese módulo.
TOMBOLA_STATS_START_PARAM = 'lottery_portal.tombola_stats_start_date'
_NO_START_DATE = '1900-01-01'


class LotteryTombolaNumberStat(models.Model):
    _name = 'lottery.tombola.number.stat'
    _description = 'Estadísticas de número de Tómbola'
    _order = 'number_name'

    number_id = fields.Many2one('lottery.number', string='Número', required=True,
                                index=True, ondelete='cascade')
    number_name = fields.Integer(related='number_id.name', string='Número', store=True, index=True)

    total_salidas = fields.Integer(store=True, index=True, help="Total salidas")
    total_salidas_dia = fields.Integer(store=True, index=True, help="Total salidas Tarde")
    total_salidas_noche = fields.Integer(store=True, index=True, help="Total salidas Noche")

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

    # Sin domingo: no hay sorteo de Tómbola ese día.
    total_lunes = fields.Integer(store=True, index=True)
    total_martes = fields.Integer(store=True, index=True)
    total_miercoles = fields.Integer(store=True, index=True)
    total_jueves = fields.Integer(store=True, index=True)
    total_viernes = fields.Integer(store=True, index=True)
    total_sabado = fields.Integer(store=True, index=True)

    total_semana_1 = fields.Integer(store=True, index=True, help="Semana 1 (1 al 7)")
    total_semana_2 = fields.Integer(store=True, index=True, help="Semana 2 (8 al 14)")
    total_semana_3 = fields.Integer(store=True, index=True, help="Semana 3 (15 al 21)")
    total_semana_4 = fields.Integer(store=True, index=True, help="Semana 4 (22 al 28)")
    total_semana_5 = fields.Integer(store=True, index=True, help="Últimos días (29, 30 y 31)")

    total_atrasadas = fields.Integer(string="Atrasos totales", default=0, index=True)
    total_atrasadas_dia = fields.Integer(string="Atrasos Tarde", default=0, index=True)
    total_atrasadas_noche = fields.Integer(string="Atrasos Noche", default=0, index=True)

    salidas_atrasadas_lunes = fields.Integer(string='Atrasos lunes', index=True)
    salidas_atrasadas_martes = fields.Integer(string='Atrasos martes', index=True)
    salidas_atrasadas_miercoles = fields.Integer(string='Atrasos miércoles', index=True)
    salidas_atrasadas_jueves = fields.Integer(string='Atrasos jueves', index=True)
    salidas_atrasadas_viernes = fields.Integer(string='Atrasos viernes', index=True)
    salidas_atrasadas_sabado = fields.Integer(string='Atrasos sábado', index=True)

    _sql_constraints = [
        ('lottery_tombola_number_stat_number_unique',
         'unique(number_id)',
         'Ya existe una fila de estadísticas para ese número.')
    ]

    @api.depends('number_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.number_id.name}" if rec.number_id else ''

    def _start_date(self):
        val = self.env['ir.config_parameter'].sudo().get_param(TOMBOLA_STATS_START_PARAM)
        return val or _NO_START_DATE

    # ------------------------------------------------------------------
    #  Recálculos SQL. Sin sorteo_id: siempre se recalcula la tabla
    #  completa (100 números), es barato (a diferencia de las loterías con
    #  sorteo_id, acá no hace falta un camino rápido "por sorteo").
    # ------------------------------------------------------------------
    def cron_recompute_totales(self):
        p = {'early_turns': list(EARLY_TURNS), 'start_date': self._start_date()}
        self.env.cr.execute("""
            INSERT INTO lottery_tombola_number_stat (
                number_id,
                total_salidas, total_salidas_dia, total_salidas_noche,
                cant_salidas_enero, cant_salidas_febrero, cant_salidas_marzo, cant_salidas_abril,
                cant_salidas_mayo, cant_salidas_junio, cant_salidas_julio, cant_salidas_agosto,
                cant_salidas_septiembre, cant_salidas_octubre, cant_salidas_noviembre, cant_salidas_diciembre,
                total_lunes, total_martes, total_miercoles,
                total_jueves, total_viernes, total_sabado,
                total_semana_1, total_semana_2, total_semana_3, total_semana_4, total_semana_5
            )
            SELECT
                number_id,
                COUNT(*),
                COUNT(*) FILTER (WHERE turn_day = ANY(%(early_turns)s)),
                COUNT(*) FILTER (WHERE turn_day != ALL(%(early_turns)s)),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 1),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 2),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 3),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 4),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 5),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 6),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 7),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 8),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 9),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 10),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 11),
                COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM date) = 12),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 1),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 2),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 3),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 4),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 5),
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 6),
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 1 AND 7),
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 8 AND 14),
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 15 AND 21),
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) BETWEEN 22 AND 28),
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM date) >= 29)
            FROM lottery_tombola_output
            WHERE date >= %(start_date)s
            GROUP BY number_id
            ON CONFLICT (number_id) DO UPDATE SET
                total_salidas = EXCLUDED.total_salidas,
                total_salidas_dia = EXCLUDED.total_salidas_dia,
                total_salidas_noche = EXCLUDED.total_salidas_noche,
                cant_salidas_enero = EXCLUDED.cant_salidas_enero,
                cant_salidas_febrero = EXCLUDED.cant_salidas_febrero,
                cant_salidas_marzo = EXCLUDED.cant_salidas_marzo,
                cant_salidas_abril = EXCLUDED.cant_salidas_abril,
                cant_salidas_mayo = EXCLUDED.cant_salidas_mayo,
                cant_salidas_junio = EXCLUDED.cant_salidas_junio,
                cant_salidas_julio = EXCLUDED.cant_salidas_julio,
                cant_salidas_agosto = EXCLUDED.cant_salidas_agosto,
                cant_salidas_septiembre = EXCLUDED.cant_salidas_septiembre,
                cant_salidas_octubre = EXCLUDED.cant_salidas_octubre,
                cant_salidas_noviembre = EXCLUDED.cant_salidas_noviembre,
                cant_salidas_diciembre = EXCLUDED.cant_salidas_diciembre,
                total_lunes = EXCLUDED.total_lunes,
                total_martes = EXCLUDED.total_martes,
                total_miercoles = EXCLUDED.total_miercoles,
                total_jueves = EXCLUDED.total_jueves,
                total_viernes = EXCLUDED.total_viernes,
                total_sabado = EXCLUDED.total_sabado,
                total_semana_1 = EXCLUDED.total_semana_1,
                total_semana_2 = EXCLUDED.total_semana_2,
                total_semana_3 = EXCLUDED.total_semana_3,
                total_semana_4 = EXCLUDED.total_semana_4,
                total_semana_5 = EXCLUDED.total_semana_5;
        """, p)
        self._sync_number_name()

    def cron_recompute_atrasos_general(self):
        """Atraso general: sorteos consecutivos (eventos date+turn_day, NO
        filas) sin que el número haya salido entre los 20."""
        p = {'early_turns': list(EARLY_TURNS), 'start_date': self._start_date()}
        self.env.cr.execute("""
            WITH draws AS (
                SELECT DISTINCT date, turn_day
                FROM lottery_tombola_output
                WHERE date >= %(start_date)s
            ),
            ranking AS (
                SELECT date, turn_day,
                    ROW_NUMBER() OVER (
                        ORDER BY date, CASE WHEN turn_day = ANY(%(early_turns)s) THEN 0 ELSE 1 END
                    ) AS orden_global
                FROM draws
            ),
            ultima_por_numero AS (
                SELECT o.number_id, MAX(r.orden_global) AS ultima_orden
                FROM lottery_tombola_output o
                JOIN ranking r ON r.date = o.date AND r.turn_day = o.turn_day
                WHERE o.date >= %(start_date)s
                GROUP BY o.number_id
            ),
            max_orden AS (SELECT MAX(orden_global) AS val FROM ranking)
            INSERT INTO lottery_tombola_number_stat (number_id, total_atrasadas)
            SELECT n.id, COALESCE(m.val - u.ultima_orden, m.val, 0)
            FROM lottery_number n
            CROSS JOIN max_orden m
            LEFT JOIN ultima_por_numero u ON u.number_id = n.id
            ON CONFLICT (number_id) DO UPDATE SET
                total_atrasadas = EXCLUDED.total_atrasadas;
        """, p)
        self._sync_number_name()

    def cron_recompute_atrasos_turno(self):
        """Atraso por turno (Tarde/Noche): sorteos consecutivos de ESE turno
        sin que el número haya salido en él."""
        p = {'early_turns': list(EARLY_TURNS), 'start_date': self._start_date()}
        self.env.cr.execute("""
            WITH draws_turno AS (
                SELECT DISTINCT date, turn_day
                FROM lottery_tombola_output
                WHERE date >= %(start_date)s
            ),
            ranking_turno AS (
                SELECT date, turn_day,
                    (turn_day = ANY(%(early_turns)s)) AS es_tarde,
                    ROW_NUMBER() OVER (
                        PARTITION BY (turn_day = ANY(%(early_turns)s)) ORDER BY date
                    ) AS orden_turno
                FROM draws_turno
            ),
            ultima_por_numero_turno AS (
                SELECT o.number_id, rt.es_tarde, MAX(rt.orden_turno) AS ultima_orden
                FROM lottery_tombola_output o
                JOIN ranking_turno rt ON rt.date = o.date AND rt.turn_day = o.turn_day
                WHERE o.date >= %(start_date)s
                GROUP BY o.number_id, rt.es_tarde
            ),
            ultima_global_turno AS (
                SELECT es_tarde, MAX(orden_turno) AS max_orden FROM ranking_turno GROUP BY es_tarde
            )
            INSERT INTO lottery_tombola_number_stat (number_id, total_atrasadas_dia, total_atrasadas_noche)
            SELECT
                n.id,
                COALESCE(gv.max_orden - uv.ultima_orden, gv.max_orden, 0),
                COALESCE(gn.max_orden - un.ultima_orden, gn.max_orden, 0)
            FROM lottery_number n
            LEFT JOIN ultima_global_turno gv ON gv.es_tarde = TRUE
            LEFT JOIN ultima_por_numero_turno uv ON uv.number_id = n.id AND uv.es_tarde = TRUE
            LEFT JOIN ultima_global_turno gn ON gn.es_tarde = FALSE
            LEFT JOIN ultima_por_numero_turno un ON un.number_id = n.id AND un.es_tarde = FALSE
            ON CONFLICT (number_id) DO UPDATE SET
                total_atrasadas_dia = EXCLUDED.total_atrasadas_dia,
                total_atrasadas_noche = EXCLUDED.total_atrasadas_noche;
        """, p)
        self._sync_number_name()

    def cron_recompute_atrasos_por_dia_semana(self):
        """Atraso en semanas para lunes..sábado (sin domingo: no hay sorteo)."""
        p = {'start_date': self._start_date()}
        self.env.cr.execute("""
            WITH dias AS (SELECT generate_series(1,6) AS dow),
            atrasos AS (
                SELECT
                    n.id AS number_id, d.dow,
                    CASE
                        WHEN s.last_system_date IS NULL THEN 0
                        WHEN s.last_number_date IS NULL THEN
                            GREATEST(0, FLOOR((s.last_system_date::date - s.first_system_date::date) / 7)::int + 1)
                        ELSE
                            GREATEST(0, FLOOR((s.last_system_date::date - s.last_number_date::date) / 7)::int)
                    END AS atraso
                FROM lottery_number n
                CROSS JOIN dias d
                LEFT JOIN LATERAL (
                    SELECT
                        (SELECT MIN(date) FROM lottery_tombola_output
                          WHERE date >= %(start_date)s AND EXTRACT(DOW FROM date) = d.dow) AS first_system_date,
                        (SELECT MAX(date) FROM lottery_tombola_output
                          WHERE date >= %(start_date)s AND EXTRACT(DOW FROM date) = d.dow) AS last_system_date,
                        (SELECT MAX(date) FROM lottery_tombola_output
                          WHERE number_id = n.id AND date >= %(start_date)s AND EXTRACT(DOW FROM date) = d.dow) AS last_number_date
                ) s ON TRUE
            ),
            atrasos_pivot AS (
                SELECT
                    number_id,
                    MAX(CASE WHEN dow = 1 THEN atraso ELSE 0 END) AS salidas_atrasadas_lunes,
                    MAX(CASE WHEN dow = 2 THEN atraso ELSE 0 END) AS salidas_atrasadas_martes,
                    MAX(CASE WHEN dow = 3 THEN atraso ELSE 0 END) AS salidas_atrasadas_miercoles,
                    MAX(CASE WHEN dow = 4 THEN atraso ELSE 0 END) AS salidas_atrasadas_jueves,
                    MAX(CASE WHEN dow = 5 THEN atraso ELSE 0 END) AS salidas_atrasadas_viernes,
                    MAX(CASE WHEN dow = 6 THEN atraso ELSE 0 END) AS salidas_atrasadas_sabado
                FROM atrasos
                GROUP BY number_id
            )
            INSERT INTO lottery_tombola_number_stat (
                number_id,
                salidas_atrasadas_lunes, salidas_atrasadas_martes,
                salidas_atrasadas_miercoles, salidas_atrasadas_jueves, salidas_atrasadas_viernes,
                salidas_atrasadas_sabado
            )
            SELECT
                number_id,
                salidas_atrasadas_lunes, salidas_atrasadas_martes,
                salidas_atrasadas_miercoles, salidas_atrasadas_jueves, salidas_atrasadas_viernes,
                salidas_atrasadas_sabado
            FROM atrasos_pivot
            ON CONFLICT (number_id) DO UPDATE SET
                salidas_atrasadas_lunes = EXCLUDED.salidas_atrasadas_lunes,
                salidas_atrasadas_martes = EXCLUDED.salidas_atrasadas_martes,
                salidas_atrasadas_miercoles = EXCLUDED.salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves = EXCLUDED.salidas_atrasadas_jueves,
                salidas_atrasadas_viernes = EXCLUDED.salidas_atrasadas_viernes,
                salidas_atrasadas_sabado = EXCLUDED.salidas_atrasadas_sabado;
        """, p)
        self._sync_number_name()

    def _sync_number_name(self):
        """Rellena number_name en las filas creadas por SQL crudo."""
        self.env.cr.execute("""
            UPDATE lottery_tombola_number_stat s
            SET number_name = n.name
            FROM lottery_number n
            WHERE n.id = s.number_id
              AND s.number_name IS DISTINCT FROM n.name;
        """)

    def cron_recompute_all(self):
        """Reconstruye TODAS las estadísticas de Tómbola desde cero."""
        self.env.cr.execute("DELETE FROM lottery_tombola_number_stat;")
        self.cron_recompute_totales()
        self.cron_recompute_atrasos_general()
        self.cron_recompute_atrasos_turno()
        self.cron_recompute_atrasos_por_dia_semana()
