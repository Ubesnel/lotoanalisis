# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Turno Tarde del día; el resto se considera turno Noche. Todos los sorteos
# (Florida, Quiniela UY, futuros) comparten el mismo vocabulario de turno_day.
EARLY_TURNS = ('afternoon',)


class LotteryNumberStat(models.Model):
    _name = 'lottery.number.stat'
    _description = 'Estadísticas de número por sorteo'
    _order = 'sorteo_id, number_name'

    number_id = fields.Many2one('lottery.number', string='Número', required=True,
                                index=True, ondelete='cascade')
    number_name = fields.Integer(related='number_id.name', string='Número', store=True, index=True)
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True, index=True, ondelete='cascade')

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

    total_domingo = fields.Integer(store=True, index=True)
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
    salidas_atrasadas_domingo = fields.Integer(string='Atrasos domingo', index=True)

    _sql_constraints = [
        ('lottery_number_stat_number_sorteo_unique',
         'unique(number_id, sorteo_id)',
         'Ya existe una fila de estadísticas para ese número y sorteo.')
    ]

    @api.depends('number_id', 'sorteo_id')
    def _compute_display_name(self):
        for rec in self:
            numero = f"{rec.number_id.name}" if rec.number_id else ''
            sorteo = rec.sorteo_id.name or ''
            rec.display_name = f"{numero} · {sorteo}"

    # ------------------------------------------------------------------
    #  Recálculos SQL (particionados por sorteo, con upsert ON CONFLICT)
    # ------------------------------------------------------------------
    def cron_recompute_totales(self):
        self.env.cr.execute("""
            INSERT INTO lottery_number_stat (
                number_id, sorteo_id,
                total_salidas, total_salidas_dia, total_salidas_noche,
                cant_salidas_enero, cant_salidas_febrero, cant_salidas_marzo, cant_salidas_abril,
                cant_salidas_mayo, cant_salidas_junio, cant_salidas_julio, cant_salidas_agosto,
                cant_salidas_septiembre, cant_salidas_octubre, cant_salidas_noviembre, cant_salidas_diciembre,
                total_domingo, total_lunes, total_martes, total_miercoles,
                total_jueves, total_viernes, total_sabado,
                total_semana_1, total_semana_2, total_semana_3, total_semana_4, total_semana_5
            )
            SELECT
                number_id, sorteo_id,
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
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM date) = 0),
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
            FROM lottery_output
            GROUP BY number_id, sorteo_id
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
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
                total_domingo = EXCLUDED.total_domingo,
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
        """, {'early_turns': list(EARLY_TURNS)})
        self._sync_number_name()

    def cron_recompute_atrasos_full(self):
        """Atraso global del número dentro de cada sorteo."""
        self.env.cr.execute("""
            WITH ranking AS (
                SELECT
                    s.number_id, s.sorteo_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.sorteo_id
                        ORDER BY s.date, CASE WHEN s.turn_day = ANY(%(early_turns)s) THEN 0 ELSE 1 END, s.id
                    ) AS orden_global
                FROM lottery_output s
            ),
            ultima_por_numero AS (
                SELECT number_id, sorteo_id, MAX(orden_global) AS ultima_orden
                FROM ranking GROUP BY number_id, sorteo_id
            ),
            ultima_global AS (
                SELECT sorteo_id, MAX(orden_global) AS max_orden
                FROM ranking GROUP BY sorteo_id
            ),
            grid AS (
                SELECT n.id AS number_id, g.sorteo_id, g.max_orden
                FROM lottery_number n
                CROSS JOIN ultima_global g
            ),
            atrasos AS (
                SELECT
                    grid.number_id, grid.sorteo_id,
                    COALESCE(grid.max_orden - u.ultima_orden, grid.max_orden) AS total_atrasadas
                FROM grid
                LEFT JOIN ultima_por_numero u
                    ON u.number_id = grid.number_id AND u.sorteo_id = grid.sorteo_id
            )
            INSERT INTO lottery_number_stat (number_id, sorteo_id, total_atrasadas)
            SELECT number_id, sorteo_id, COALESCE(total_atrasadas, 0) FROM atrasos
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
                total_atrasadas = EXCLUDED.total_atrasadas;
        """, {'early_turns': list(EARLY_TURNS)})
        self._sync_number_name()

    def cron_recompute_atrasos_turno(self):
        """Atraso del número por turno (Tarde/Noche) dentro de cada sorteo:
        cuántos sorteos de ESE turno pasaron desde la última vez que el
        número salió específicamente en ese turno. Si nunca salió en ese
        turno, el atraso es el total histórico de ese turno (no hay anclaje
        posible). Cada turno se rankea por separado."""
        self.env.cr.execute("""
            WITH ranking_turno AS (
                SELECT
                    s.number_id, s.sorteo_id, s.turn_day,
                    (s.turn_day = ANY(%(early_turns)s)) AS es_tarde,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.sorteo_id, (s.turn_day = ANY(%(early_turns)s))
                        ORDER BY s.date, s.id
                    ) AS orden_turno
                FROM lottery_output s
            ),
            ultima_por_numero_turno AS (
                SELECT number_id, sorteo_id, es_tarde, MAX(orden_turno) AS ultima_orden
                FROM ranking_turno GROUP BY number_id, sorteo_id, es_tarde
            ),
            ultima_global_turno AS (
                SELECT sorteo_id, es_tarde, MAX(orden_turno) AS max_orden
                FROM ranking_turno GROUP BY sorteo_id, es_tarde
            ),
            grid AS (
                SELECT n.id AS number_id, srt.sorteo_id
                FROM lottery_number n
                CROSS JOIN (SELECT DISTINCT sorteo_id FROM lottery_output) srt
            ),
            atrasos AS (
                SELECT
                    grid.number_id, grid.sorteo_id,
                    COALESCE(gv.max_orden - uv.ultima_orden, gv.max_orden, 0) AS atraso_dia,
                    COALESCE(gn.max_orden - un.ultima_orden, gn.max_orden, 0) AS atraso_noche
                FROM grid
                LEFT JOIN ultima_global_turno gv
                    ON gv.sorteo_id = grid.sorteo_id AND gv.es_tarde = TRUE
                LEFT JOIN ultima_por_numero_turno uv
                    ON uv.number_id = grid.number_id AND uv.sorteo_id = grid.sorteo_id AND uv.es_tarde = TRUE
                LEFT JOIN ultima_global_turno gn
                    ON gn.sorteo_id = grid.sorteo_id AND gn.es_tarde = FALSE
                LEFT JOIN ultima_por_numero_turno un
                    ON un.number_id = grid.number_id AND un.sorteo_id = grid.sorteo_id AND un.es_tarde = FALSE
            )
            INSERT INTO lottery_number_stat (number_id, sorteo_id, total_atrasadas_dia, total_atrasadas_noche)
            SELECT number_id, sorteo_id, atraso_dia, atraso_noche FROM atrasos
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
                total_atrasadas_dia = EXCLUDED.total_atrasadas_dia,
                total_atrasadas_noche = EXCLUDED.total_atrasadas_noche;
        """, {'early_turns': list(EARLY_TURNS)})
        self._sync_number_name()

    def cron_recompute_atrasos_por_dia_semana(self):
        """Atraso en semanas para cada día de la semana, dentro de cada sorteo."""
        self.env.cr.execute("""
            WITH dias AS (SELECT generate_series(0,6) AS dow),
            sorteos AS (SELECT DISTINCT sorteo_id FROM lottery_output),
            atrasos AS (
                SELECT
                    n.id AS number_id, srt.sorteo_id, d.dow,
                    CASE
                        WHEN s.last_system_date IS NULL THEN 0
                        WHEN s.last_number_date IS NULL THEN
                            GREATEST(0, FLOOR((s.last_system_date::date - s.first_system_date::date) / 7)::int + 1)
                        ELSE
                            GREATEST(0, FLOOR((s.last_system_date::date - s.last_number_date::date) / 7)::int)
                    END AS atraso
                FROM lottery_number n
                CROSS JOIN sorteos srt
                CROSS JOIN dias d
                LEFT JOIN LATERAL (
                    SELECT
                        (SELECT MIN(date) FROM lottery_output
                          WHERE sorteo_id = srt.sorteo_id AND EXTRACT(DOW FROM date) = d.dow) AS first_system_date,
                        (SELECT MAX(date) FROM lottery_output
                          WHERE sorteo_id = srt.sorteo_id AND EXTRACT(DOW FROM date) = d.dow) AS last_system_date,
                        (SELECT MAX(date) FROM lottery_output
                          WHERE number_id = n.id AND sorteo_id = srt.sorteo_id AND EXTRACT(DOW FROM date) = d.dow) AS last_number_date
                ) s ON TRUE
            ),
            atrasos_pivot AS (
                SELECT
                    number_id, sorteo_id,
                    MAX(CASE WHEN dow = 0 THEN atraso ELSE 0 END) AS salidas_atrasadas_domingo,
                    MAX(CASE WHEN dow = 1 THEN atraso ELSE 0 END) AS salidas_atrasadas_lunes,
                    MAX(CASE WHEN dow = 2 THEN atraso ELSE 0 END) AS salidas_atrasadas_martes,
                    MAX(CASE WHEN dow = 3 THEN atraso ELSE 0 END) AS salidas_atrasadas_miercoles,
                    MAX(CASE WHEN dow = 4 THEN atraso ELSE 0 END) AS salidas_atrasadas_jueves,
                    MAX(CASE WHEN dow = 5 THEN atraso ELSE 0 END) AS salidas_atrasadas_viernes,
                    MAX(CASE WHEN dow = 6 THEN atraso ELSE 0 END) AS salidas_atrasadas_sabado
                FROM atrasos
                GROUP BY number_id, sorteo_id
            )
            INSERT INTO lottery_number_stat (
                number_id, sorteo_id,
                salidas_atrasadas_domingo, salidas_atrasadas_lunes, salidas_atrasadas_martes,
                salidas_atrasadas_miercoles, salidas_atrasadas_jueves, salidas_atrasadas_viernes,
                salidas_atrasadas_sabado
            )
            SELECT
                number_id, sorteo_id,
                salidas_atrasadas_domingo, salidas_atrasadas_lunes, salidas_atrasadas_martes,
                salidas_atrasadas_miercoles, salidas_atrasadas_jueves, salidas_atrasadas_viernes,
                salidas_atrasadas_sabado
            FROM atrasos_pivot
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
                salidas_atrasadas_domingo = EXCLUDED.salidas_atrasadas_domingo,
                salidas_atrasadas_lunes = EXCLUDED.salidas_atrasadas_lunes,
                salidas_atrasadas_martes = EXCLUDED.salidas_atrasadas_martes,
                salidas_atrasadas_miercoles = EXCLUDED.salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves = EXCLUDED.salidas_atrasadas_jueves,
                salidas_atrasadas_viernes = EXCLUDED.salidas_atrasadas_viernes,
                salidas_atrasadas_sabado = EXCLUDED.salidas_atrasadas_sabado;
        """)
        self._sync_number_name()

    def _sync_number_name(self):
        """Rellena number_name en las filas creadas por SQL crudo."""
        self.env.cr.execute("""
            UPDATE lottery_number_stat s
            SET number_name = n.name
            FROM lottery_number n
            WHERE n.id = s.number_id
              AND s.number_name IS DISTINCT FROM n.name;
        """)

    def cron_recompute_all(self):
        """Reconstruye TODAS las estadísticas desde cero (refleja borrados/ediciones)."""
        self.env.cr.execute("DELETE FROM lottery_number_stat;")
        self.cron_recompute_totales()
        self.cron_recompute_atrasos_full()
        self.cron_recompute_atrasos_turno()
        self.cron_recompute_atrasos_por_dia_semana()
