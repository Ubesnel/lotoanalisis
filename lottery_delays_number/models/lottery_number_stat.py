# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryNumberStat(models.Model):
    """Estadísticas generales de un número dentro de un sorteo (todos los
    turnos juntos). Lo que depende del turno vive en una fila por turno en
    `lottery.number.stat.turno` (turno_stat_ids)."""
    _name = 'lottery.number.stat'
    _description = 'Estadísticas de número por sorteo'
    _order = 'sorteo_id, number_name'

    number_id = fields.Many2one('lottery.number', string='Número', required=True,
                                index=True, ondelete='cascade')
    number_name = fields.Integer(related='number_id.name', string='Número', store=True, index=True)
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True, index=True, ondelete='cascade')
    turno_stat_ids = fields.One2many('lottery.number.stat.turno', 'stat_id', string='Por turno')

    total_salidas = fields.Integer(store=True, index=True, help="Total salidas")

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
    ultima_fecha = fields.Date(string='Última salida')
    ultimo_turno_id = fields.Many2one('lottery.turno', string='Turno de la última salida', ondelete='set null')

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
    #  Recálculos SQL (por sorteo)
    # ------------------------------------------------------------------
    def cron_recompute_all(self):
        """Reconstruye TODAS las estadísticas desde cero (refleja borrados/ediciones).
        Las filas por turno se van con el DELETE por el ondelete='cascade'."""
        self.env.cr.execute("DELETE FROM lottery_number_stat;")
        self.env.cr.execute("SELECT DISTINCT sorteo_id FROM lottery_output;")
        for (sorteo_id,) in self.env.cr.fetchall():
            self.recompute_for_sorteo(sorteo_id)

    def recompute_for_sorteo(self, sorteo_id):
        """Actualiza las estadísticas de un sorteo: generales y por turno."""
        p = {'sorteo_id': sorteo_id}
        self._recompute_totales(p)
        self._recompute_atraso_general(p)
        self._recompute_atrasos_dia_semana(p)
        self._sync_number_name()
        # Al final: necesita las filas generales ya creadas para enlazar stat_id.
        self.env['lottery.number.stat.turno']._recompute_for_sorteo(sorteo_id)

    def _recompute_totales(self, p):
        self.env.cr.execute("""
            INSERT INTO lottery_number_stat (
                number_id, sorteo_id, total_salidas,
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
            WHERE sorteo_id = %(sorteo_id)s
            GROUP BY number_id, sorteo_id
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
                total_salidas = EXCLUDED.total_salidas,
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
        """, p)

    def _recompute_atraso_general(self, p):
        """Atraso global del número en el sorteo: cuántos sorteos (de cualquier
        turno, en orden cronológico fecha + secuencia del turno) pasaron desde
        su última salida. Si nunca salió, el total de sorteos. Guarda también
        la fecha y el turno de esa última salida."""
        self.env.cr.execute("""
            WITH ranking AS (
                SELECT
                    s.number_id, s.date, s.turno_id,
                    ROW_NUMBER() OVER (ORDER BY s.date, s.turno_sequence, s.id) AS orden_global
                FROM lottery_output s
                WHERE s.sorteo_id = %(sorteo_id)s
            ),
            ultima_por_numero AS (
                SELECT DISTINCT ON (number_id)
                    number_id, orden_global AS ultima_orden, date, turno_id
                FROM ranking
                ORDER BY number_id, orden_global DESC
            ),
            max_orden AS (SELECT MAX(orden_global) AS val FROM ranking),
            atrasos AS (
                SELECT
                    n.id AS number_id,
                    COALESCE(m.val - u.ultima_orden, m.val, 0) AS total_atrasadas,
                    u.date AS ultima_fecha,
                    u.turno_id AS ultimo_turno_id
                FROM lottery_number n
                CROSS JOIN max_orden m
                LEFT JOIN ultima_por_numero u ON u.number_id = n.id
            )
            INSERT INTO lottery_number_stat (number_id, sorteo_id, total_atrasadas, ultima_fecha, ultimo_turno_id)
            SELECT number_id, %(sorteo_id)s, total_atrasadas, ultima_fecha, ultimo_turno_id FROM atrasos
            ON CONFLICT (number_id, sorteo_id) DO UPDATE SET
                total_atrasadas = EXCLUDED.total_atrasadas,
                ultima_fecha = EXCLUDED.ultima_fecha,
                ultimo_turno_id = EXCLUDED.ultimo_turno_id;
        """, p)

    def _recompute_atrasos_dia_semana(self, p):
        """Atraso en semanas para cada día de la semana."""
        self.env.cr.execute("""
            WITH dias AS (SELECT generate_series(0,6) AS dow),
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
                        (SELECT MIN(date) FROM lottery_output
                          WHERE sorteo_id = %(sorteo_id)s AND EXTRACT(DOW FROM date) = d.dow) AS first_system_date,
                        (SELECT MAX(date) FROM lottery_output
                          WHERE sorteo_id = %(sorteo_id)s AND EXTRACT(DOW FROM date) = d.dow) AS last_system_date,
                        (SELECT MAX(date) FROM lottery_output
                          WHERE number_id = n.id AND sorteo_id = %(sorteo_id)s AND EXTRACT(DOW FROM date) = d.dow) AS last_number_date
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
            INSERT INTO lottery_number_stat (
                number_id, sorteo_id,
                salidas_atrasadas_domingo, salidas_atrasadas_lunes, salidas_atrasadas_martes,
                salidas_atrasadas_miercoles, salidas_atrasadas_jueves, salidas_atrasadas_viernes,
                salidas_atrasadas_sabado
            )
            SELECT
                number_id, %(sorteo_id)s,
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
        """, p)

    def _sync_number_name(self):
        """Rellena number_name en las filas creadas por SQL crudo."""
        self.env.cr.execute("""
            UPDATE lottery_number_stat s
            SET number_name = n.name
            FROM lottery_number n
            WHERE n.id = s.number_id
              AND s.number_name IS DISTINCT FROM n.name;
        """)


class LotteryNumberStatTurno(models.Model):
    """Estadísticas de un número en UN turno de un sorteo: una fila por
    (número, sorteo, turno). Reemplaza a los antiguos campos fijos
    *_dia / *_noche, así un sorteo puede tener cualquier cantidad de turnos.

    Se reconstruye entero por sorteo (DELETE + INSERT) desde
    lottery.number.stat.recompute_for_sorteo; no se edita a mano."""
    _name = 'lottery.number.stat.turno'
    _description = 'Estadísticas de número por sorteo y turno'
    _order = 'sorteo_id, number_name, turno_sequence'
    _log_access = False

    stat_id = fields.Many2one('lottery.number.stat', string='Estadística general',
                              index=True, ondelete='cascade')
    number_id = fields.Many2one('lottery.number', string='Número', required=True,
                                index=True, ondelete='cascade')
    number_name = fields.Integer(string='Número', index=True)
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                index=True, ondelete='cascade')
    turno_id = fields.Many2one('lottery.turno', string='Turno', required=True,
                               index=True, ondelete='cascade')
    turno_sequence = fields.Integer(string='Secuencia del turno', index=True)

    total_salidas = fields.Integer(string='Salidas', index=True,
                                   help="Veces que salió el número en este turno.")
    total_atrasadas = fields.Integer(string='Atraso', index=True,
                                     help="Sorteos de este turno desde la última vez que salió en él. "
                                          "Si nunca salió en el turno, el total de sorteos del turno.")
    ultima_fecha = fields.Date(string='Última salida', help="Última fecha en que salió en este turno.")

    _sql_constraints = [
        ('lottery_number_stat_turno_unique',
         'unique(number_id, sorteo_id, turno_id)',
         'Ya existe una fila de estadísticas para ese número, sorteo y turno.')
    ]

    @api.depends('number_name', 'sorteo_id', 'turno_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.number_name} · {rec.sorteo_id.name or ''} · {rec.turno_id.name or ''}"

    def _recompute_for_sorteo(self, sorteo_id):
        """Reconstruye las filas del sorteo. Turnos considerados: los
        habilitados en el sorteo más cualquiera que tenga salidas (por si se
        deshabilitó un turno con histórico). Cada turno se rankea por separado:
        el atraso cuenta sorteos de ESE turno."""
        p = {'sorteo_id': sorteo_id}
        self.env.cr.execute(
            "DELETE FROM lottery_number_stat_turno WHERE sorteo_id = %(sorteo_id)s;", p)
        self.env.cr.execute("""
            WITH turnos AS (
                SELECT turno_id FROM lottery_sorteo_turno_rel WHERE sorteo_id = %(sorteo_id)s
                UNION
                SELECT DISTINCT turno_id FROM lottery_output WHERE sorteo_id = %(sorteo_id)s
            ),
            ranking AS (
                SELECT
                    s.number_id, s.turno_id, s.date,
                    ROW_NUMBER() OVER (PARTITION BY s.turno_id ORDER BY s.date, s.id) AS orden
                FROM lottery_output s
                WHERE s.sorteo_id = %(sorteo_id)s
            ),
            por_numero AS (
                SELECT number_id, turno_id,
                       COUNT(*) AS salidas, MAX(orden) AS ultima_orden, MAX(date) AS ultima_fecha
                FROM ranking GROUP BY number_id, turno_id
            ),
            por_turno AS (
                SELECT turno_id, MAX(orden) AS max_orden FROM ranking GROUP BY turno_id
            )
            INSERT INTO lottery_number_stat_turno (
                stat_id, number_id, number_name, sorteo_id, turno_id, turno_sequence,
                total_salidas, total_atrasadas, ultima_fecha
            )
            SELECT
                st.id, n.id, n.name, %(sorteo_id)s, t.turno_id, lt.sequence,
                COALESCE(pn.salidas, 0),
                COALESCE(pt.max_orden - pn.ultima_orden, pt.max_orden, 0),
                pn.ultima_fecha
            FROM lottery_number n
            CROSS JOIN turnos t
            JOIN lottery_turno lt ON lt.id = t.turno_id
            LEFT JOIN por_turno pt ON pt.turno_id = t.turno_id
            LEFT JOIN por_numero pn ON pn.number_id = n.id AND pn.turno_id = t.turno_id
            LEFT JOIN lottery_number_stat st ON st.number_id = n.id AND st.sorteo_id = %(sorteo_id)s;
        """, p)
