# -*- coding: utf-8 -*-

from collections import Counter

from odoo import models, api, tools
import calendar
from datetime import date, datetime
from odoo.addons.lottery_base.models.utils import MONTHS_DICT

MONTH_FIELD_MAP = {
        1: "cant_salidas_enero",
        2: "cant_salidas_febrero",
        3: "cant_salidas_marzo",
        4: "cant_salidas_abril",
        5: "cant_salidas_mayo",
        6: "cant_salidas_junio",
        7: "cant_salidas_julio",
        8: "cant_salidas_agosto",
        9: "cant_salidas_septiembre",
        10: "cant_salidas_octubre",
        11: "cant_salidas_noviembre",
        12: "cant_salidas_diciembre",
    }

WEEKDAY_FIELD_MAP = {
        "lu": "total_lunes",
        "ma": "total_martes",
        "mi": "total_miercoles",
        "ju": "total_jueves",
        "vi": "total_viernes",
        "sa": "total_sabado",
        "do": "total_domingo",
}

WEEK_FIELD_MAP = {
        "sem_1": "total_semana_1",
        "sem_2": "total_semana_2",
        "sem_3": "total_semana_3",
        "sem_4": "total_semana_4",
        "sem_5": "total_semana_5"
}


class LotteryStatsService(models.Model):
    _name = 'lottery.stats.service'
    _description = 'Lottery Statistics Service'

    def clear_caches(self):
        self.env.registry.clear_cache()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_hero_stats(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT
                COUNT(*) AS total_sorteos,
                MIN(date) AS primer_fecha
            FROM lottery_output lo
            WHERE lo.sorteo_id = %(sorteo_id)s
        """, {'sorteo_id': sorteo_id})
        row = self.env.cr.dictfetchone()
        total = row['total_sorteos'] or 0
        primer_fecha = row['primer_fecha'] or date.today()
        hoy = date.today()
        anios = hoy.year - primer_fecha.year - (
            1 if (hoy.month, hoy.day) < (primer_fecha.month, primer_fecha.day) else 0
        )
        if total >= 1000:
            total_fmt = '%dk+' % (total // 1000)
        else:
            total_fmt = str(total)
        return {
            'anios': anios,
            'total_sorteos': total_fmt,
        }

    @tools.ormcache('sorteo_id')
    def get_last_results_full(self, sorteo_id=False):
        LotteryOutput = self.env['lottery.output'].sudo()

        last_afternoon = LotteryOutput.search(
            [('turn_day', '=', 'afternoon'), ('sorteo_id', '=', sorteo_id)],
            order='date desc',
            limit=1
        )

        last_evening = LotteryOutput.search(
            [('turn_day', '=', 'evening'), ('sorteo_id', '=', sorteo_id)],
            order='date desc',
            limit=1
        )

        return {
            'afternoon': self._build_result_dict(last_afternoon),
            'evening': self._build_result_dict(last_evening),
        }

    def _format_date_es(self, date):
        dias = ['LUN.', 'MAR.', 'MIÉ.', 'JUE.', 'VIE.', 'SÁB.', 'DOM.']
        meses = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
                 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

        return "%s %s DE %s DE %s" % (
            dias[date.weekday()],
            str(date.day).zfill(2),
            meses[date.month - 1],
            date.year
        )

    def _build_result_dict(self, record):
        if not record:
            return False

        return {
            'date': self._format_date_es(record.date),
            # Ojo: hundreds_id.name sobre un recordset vacío devuelve 0, no
            # vacío (es un Integer), así que los sorteos sin centena pintaban
            # un "0". Se muestra "-" igual que la bola extra ausente.
            'centena': str(record.hundreds_id.name) if record.hundreds_id else '-',
            'extra': str(record.fireball_id.name) if record.fireball_id else '-',
            'numero': str(record.number_id.name).zfill(2),
        }

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top_10_general(self, sorteo_id=False):
        self.env.cr.execute("""SELECT * FROM lottery_top10_mv WHERE sorteo_id = %s""", (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top_10_dia(self, sorteo_id=False):
        self.env.cr.execute("""SELECT * FROM lottery_top10_afternoon_mv WHERE sorteo_id = %s""", (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top_10_noche(self, sorteo_id=False):
        self.env.cr.execute("""SELECT * FROM lottery_top10_evening_mv WHERE sorteo_id = %s""", (sorteo_id,))
        return self.env.cr.dictfetchall()

    @tools.ormcache('day', 'sorteo_id')
    def get_ultimas_salidas_por_dia(self, day, sorteo_id=False):
        self.env.cr.execute("""
            SELECT * FROM lottery_ultima_salida_dia_semana_mv
            WHERE week_day = %s AND sorteo_id = %s
            ORDER BY date DESC
            LIMIT 10
        """, (day, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    def get_ultimas_salidas_consecutivas(self, sorteo_id=False):
        """Últimas 10 fechas de sorteo consecutivas, excluyendo hoy, orden DESC.
        Sin ormcache para que CURRENT_DATE siempre refleje el día actual."""
        self.env.cr.execute("""
            SELECT date, fecha,
                   centena_dia, numero_dia, bola_extra_dia,
                   centena_noche, numero_noche, bola_extra_noche
            FROM lottery_ultima_salida_dia_semana_mv
            WHERE date < CURRENT_DATE AND sorteo_id = %s
            ORDER BY date DESC
            LIMIT 10
        """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    def get_ultimas_salidas_col1(self, sorteo_id=False):
        """Últimas 10 fechas de sorteo, incluyendo hoy si hay datos registrados, orden DESC.
        Sin ormcache porque usa CURRENT_DATE y debe reflejar el día actual en cada petición."""
        self.env.cr.execute("""
            SELECT date, fecha,
                   centena_dia, numero_dia, bola_extra_dia,
                   centena_noche, numero_noche, bola_extra_noche
            FROM lottery_ultima_salida_dia_semana_mv
            WHERE date <= CURRENT_DATE AND sorteo_id = %s
            ORDER BY date DESC
            LIMIT 10
        """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @tools.ormcache('month', 'year', 'sorteo_id')
    def get_month_year(self, month, year, sorteo_id=False):
        if not month:
            month = str(date.today().month)
        if not year:
            year = date.today().year
        return '%s %s' % (MONTHS_DICT[month], year)

    @api.model
    @tools.ormcache('week_code', 'sorteo_id')
    def get_top_10_por_dia_semana(self, week_code, sorteo_id=False):
        field_map = {
            'lu': 'salidas_atrasadas_lunes',
            'ma': 'salidas_atrasadas_martes',
            'mi': 'salidas_atrasadas_miercoles',
            'ju': 'salidas_atrasadas_jueves',
            'vi': 'salidas_atrasadas_viernes',
            'sa': 'salidas_atrasadas_sabado',
            'do': 'salidas_atrasadas_domingo',
        }
        field_name = field_map.get(week_code)
        if not field_name:
            return []
        query = f"""
                SELECT
                    name,
                    TO_CHAR(date, 'DD/MM/YYYY') AS ultima_fecha,
                    turn_day AS ultimo_turno,
                    {field_name} AS total_atrasadas
                FROM lottery_top10_dia_semana_mv
                WHERE week_day = %s AND sorteo_id = %s
                ORDER BY {field_name} DESC
                LIMIT 10
            """

        self.env.cr.execute(query, (week_code, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_centenas_afternoon(self, sorteo_id=False):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_dia_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
                    """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_centenas_evening(self, sorteo_id=False):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_noche_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
                    """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_centenas_general(self, sorteo_id=False):
        self.env.cr.execute("""
                SELECT centena, atraso
                FROM lottery_top5_centena_general_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
            """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type', 'sorteo_id')
    def get_top_atrasos_lineas(self, type, sorteo_id=False):
        query = """
            SELECT
                name,
                CASE %s
                    WHEN 'general' THEN general
                    WHEN 'afternoon' THEN afternoon
                    WHEN 'evening' THEN evening
                END AS atraso
            FROM lottery_top_atrasos_lineas_mv
            WHERE sorteo_id = %s
            ORDER BY atraso DESC;
        """
        self.env.cr.execute(query, (type, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type', 'sorteo_id')
    def get_top_atrasos_terminales(self, type, sorteo_id=False):
        query = """
                SELECT
                name,
                CASE %s
                    WHEN 'general' THEN general
                    WHEN 'afternoon' THEN afternoon
                    WHEN 'evening' THEN evening
                END AS atraso
            FROM lottery_top_atrasos_terminales_mv
            WHERE sorteo_id = %s
            ORDER BY atraso DESC;
            """
        self.env.cr.execute(query, (type, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type', 'groups_code', 'sorteo_id')
    def get_top_atrasos_number_groups(self, type, groups_code, sorteo_id=False):
        field_map = {
            'general': 'general',
            'afternoon': 'afternoon',
            'evening': 'evening',
        }
        field_name = field_map.get(type)
        if not field_name:
            return []
        query = f"""
                SELECT
                    name,
                    {field_name} AS atraso
                FROM lottery_number_groups_atrasos_mv
                WHERE group_code = ANY(%s) AND sorteo_id = %s
                ORDER BY {field_name} DESC
            """

        self.env.cr.execute(query, (groups_code, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_bola_extra_afternoon(self, sorteo_id=False):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_dia_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
                            """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_bola_extra_evening(self, sorteo_id=False):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_noche_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
                                """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top5_bola_extra_general(self, sorteo_id=False):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_bola_extra_general_mv WHERE sorteo_id = %s ORDER BY atraso DESC;
                    """, (sorteo_id,))
        return self.env.cr.dictfetchall()

    def _month_numbers_cte(self, field, sorteo_id=False):
        """CTE base compartida para las 3 tablas de números por mes.

        - total = total_historico - salidas_mes_anio  (congelado: excluye año actual)
        - global_rank: partición única 1-100, sin solapamiento entre tablas
        """
        return f"""
            WITH base AS (
                SELECT
                    ln.id,
                    LPAD(ln.name::text, 2, '0') AS name,
                    lns.{field} AS total_historico,
                    COALESCE((
                        SELECT COUNT(*) FROM lottery_output lo
                        WHERE lo.number_id = ln.id
                          AND lo.month = %(month)s::text
                          AND lo.year = %(year)s
                          AND lo.sorteo_id = %(sorteo_id)s
                    ), 0) AS salidas_mes_anio,
                    last_info.last_month_date,
                    last_info.last_month_turn,
                    last_info.last_month_week_day
                FROM lottery_number_stat lns
                JOIN lottery_number ln ON ln.id = lns.number_id
                LEFT JOIN LATERAL (
                    SELECT
                        TO_CHAR(lo2.date, 'DD/MM/YYYY') AS last_month_date,
                        lo2.turn_day AS last_month_turn,
                        CASE lo2.week_day
                            WHEN 'lu' THEN 'Lun'
                            WHEN 'ma' THEN 'Mar'
                            WHEN 'mi' THEN 'Mié'
                            WHEN 'ju' THEN 'Jue'
                            WHEN 'vi' THEN 'Vie'
                            WHEN 'sa' THEN 'Sáb'
                            WHEN 'do' THEN 'Dom'
                            ELSE lo2.week_day
                        END AS last_month_week_day
                    FROM lottery_output lo2
                    WHERE lo2.number_id = ln.id
                      AND lo2.month = %(month)s::text
                      AND lo2.sorteo_id = %(sorteo_id)s
                    ORDER BY lo2.date DESC
                    LIMIT 1
                ) last_info ON true
                WHERE lns.sorteo_id = %(sorteo_id)s
            ),
            ranked AS (
                SELECT
                    id, name, total_historico, salidas_mes_anio,
                    last_month_date, last_month_turn, last_month_week_day,
                    (total_historico - salidas_mes_anio) AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY (total_historico - salidas_mes_anio) DESC, id DESC
                    ) AS global_rank
                FROM base
            )
        """

    @api.model
    @tools.ormcache('month', 'current_year', 'sorteo_id')
    def get_top_numbers_month(self, month=None, current_year=None, sorteo_id=False):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        query = self._month_numbers_cte(field, sorteo_id=sorteo_id) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                global_rank AS rank
            FROM ranked
            WHERE global_rank <= 30
            ORDER BY global_rank;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year, 'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month', 'current_year', 'sorteo_id')
    def get_remaining_numbers_month(self, month=None, current_year=None, sorteo_id=False):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        query = self._month_numbers_cte(field, sorteo_id=sorteo_id) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                global_rank AS rank
            FROM ranked
            WHERE global_rank > 30 AND global_rank <= 70
            ORDER BY global_rank;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year, 'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month_filter', 'numbers', 'sorteo_id')
    def get_top_numbers_month_info(self, month_filter, numbers, sorteo_id=False):
        number_ids = [n.get('id') for n in numbers]
        query = """
            SELECT *
            FROM (
                SELECT DISTINCT ON (number_id)
                    number_id,
                    LPAD(lottery_number.name::text, 2, '0') AS name,
                    TO_CHAR(date, 'DD/MM/YYYY') AS last_date,
                    turn_day,
                    CASE week_day
                        WHEN 'lu' THEN 'Lun'
                        WHEN 'ma' THEN 'Mar'
                        WHEN 'mi' THEN 'Mié'
                        WHEN 'ju' THEN 'Jue'
                        WHEN 'vi' THEN 'Vie'
                        WHEN 'sa' THEN 'Sáb'
                        WHEN 'do' THEN 'Dom'
                        ELSE week_day
                    END AS week_day_label,
                    (EXTRACT(YEAR FROM CURRENT_DATE) - year)::int AS years_without_month
                    FROM lottery_output
                    join lottery_number on (lottery_number.id=lottery_output.number_id)
                WHERE month = %s
                  AND number_id=ANY(%s)
                  AND lottery_output.sorteo_id = %s
                ORDER BY number_id, date DESC) t
            WHERE years_without_month > 0 ORDER BY years_without_month DESC;
        """
        self.env.cr.execute(query, (month_filter, number_ids, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month', 'current_year', 'sorteo_id')
    def get_bottom_numbers_month(self, month=None, current_year=None, sorteo_id=False):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        # rank local 1-30 donde 1 = menos frecuente (compatible con getBallFriosClass)
        query = self._month_numbers_cte(field, sorteo_id=sorteo_id) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                ROW_NUMBER() OVER (ORDER BY total ASC, id DESC) AS rank
            FROM ranked
            WHERE global_rank > 70
            ORDER BY total ASC, id DESC;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year, 'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_ids')
    def get_quiniela_uy_centenas_top_bottom(self, sorteo_ids):
        """Top 3 / bottom 3 centenas que más y menos acompañan a cada número
        00-99 de la Quiniela Uruguay. `sorteo_ids`: tupla de 1 (un premio
        puntual) o de los 20 (ámbito General, los 20 premios juntos).

        Universo completo 100 números x 10 centenas (CROSS JOIN) para que
        una combinación que nunca salió pueda aparecer en "bottom" con 0
        salidas, en vez de quedar afuera por no tener fila en los datos.

        Comparte criterio con lottery.quiniela.uy.ternas.get_centenas_por_numero
        (wizard de Odoo), que solo trae el top; acá se agrega el bottom para
        la app, siguiendo el propio comentario de ese archivo de que el SQL
        se muda a este servicio cuando esto se expone a la app."""
        if not sorteo_ids:
            return {}
        self.env.cr.execute("""
            WITH universo AS (
                SELECT nums.numero, cents.centena
                FROM (SELECT LPAD(g::text, 2, '0') AS numero FROM generate_series(0, 99) g) nums
                CROSS JOIN (SELECT g::text AS centena FROM generate_series(0, 9) g) cents
            ),
            conteo AS (
                SELECT RIGHT(o.complete_number, 2) AS numero,
                       LEFT(o.complete_number, 1) AS centena,
                       COUNT(*) AS veces
                FROM lottery_output o
                WHERE o.sorteo_id IN %(sorteo_ids)s
                  AND o.complete_number IS NOT NULL
                GROUP BY 1, 2
            ),
            combinado AS (
                SELECT u.numero, u.centena, COALESCE(c.veces, 0) AS veces
                FROM universo u
                LEFT JOIN conteo c ON c.numero = u.numero AND c.centena = u.centena
            ),
            ranked AS (
                SELECT numero, centena, veces,
                       ROW_NUMBER() OVER (PARTITION BY numero ORDER BY veces DESC, centena) AS puesto_top,
                       ROW_NUMBER() OVER (PARTITION BY numero ORDER BY veces ASC, centena) AS puesto_bottom
                FROM combinado
            )
            SELECT numero, centena, veces, puesto_top, puesto_bottom
            FROM ranked
            WHERE puesto_top <= 3 OR puesto_bottom <= 3
            ORDER BY numero;
        """, {'sorteo_ids': tuple(sorteo_ids)})

        result = {}
        for row in self.env.cr.dictfetchall():
            entry = result.setdefault(row['numero'], {'top': [], 'bottom': []})
            if row['puesto_top'] <= 3:
                entry['top'].append(
                    {'centena': row['centena'], 'veces': row['veces'], 'rank': row['puesto_top']})
            if row['puesto_bottom'] <= 3:
                entry['bottom'].append(
                    {'centena': row['centena'], 'veces': row['veces'], 'rank': row['puesto_bottom']})
        for entry in result.values():
            entry['top'].sort(key=lambda x: x['rank'])
            entry['bottom'].sort(key=lambda x: x['rank'])
        return result

    @api.model
    def get_combinaciones_scores(self, sorteo_id, target_date, window=15):
        """Puntaje de combinación de los 100 números 00-99, sin recortar.

        Núcleo compartido: `get_combinaciones` lo usa para devolver el TOP N
        al wizard y a la app, y el botón "Completar números" de
        lottery.prediction lo usa para ordenar todo el conjunto de candidatos
        (que puede pasar el tope de 50 del TOP).

        Toma las últimas `window` salidas hasta `target_date` (ambos turnos),
        cuenta la frecuencia de cada dígito 0-9 sobre el número completo
        (centena/decena/unidad) y puntúa cada combinación 00-99 como
        freq(decena) * freq(unidad).

        Devuelve {'outputs': [(fecha, turno, completo), ...] de más reciente
        a más viejo, 'digits': Counter de dígitos, 'scores': {'00': n, ...}}.
        Sin ormcache a propósito: la ventana cambia con cada salida nueva."""
        try:
            window = max(1, min(int(window), 200))
        except (TypeError, ValueError):
            window = 15

        # Últimas `window` salidas hasta la fecha, más reciente primero.
        self.env.cr.execute("""
            SELECT date, turn_day, complete_number
            FROM lottery_output
            WHERE sorteo_id = %s AND date <= %s AND complete_number IS NOT NULL
            ORDER BY date DESC,
                     CASE turn_day WHEN 'evening' THEN 1 ELSE 0 END DESC
            LIMIT %s
        """, (sorteo_id, target_date, window))
        outputs = self.env.cr.fetchall()
        if not outputs:
            return {'outputs': [], 'digits': Counter(), 'scores': {}}

        digs = Counter(d for _, _, n in outputs for d in n)
        scores = {
            f'{dd}{uu}': digs.get(dd, 0) * digs.get(uu, 0)
            for dd in '0123456789' for uu in '0123456789'
        }
        return {'outputs': outputs, 'digits': digs, 'scores': scores}

    @api.model
    def get_combinaciones(self, sorteo_id, target_date, window=15, top=25):
        """N números candidatos por combinación de dígitos (para la app móvil).

        Misma lógica que el wizard lottery.consulta.combinaciones: toma las
        últimas `window` salidas hasta `target_date` (ambos turnos), cuenta la
        frecuencia de cada dígito 0-9 sobre el número completo (centena/decena/
        unidad) y puntúa cada combinación 00-99 como freq(decena)*freq(unidad).
        Devuelve el TOP `top` (default 25, tope 50). Marca 'directo' (el número
        salió ese dd/mm en años anteriores) y 'virado' (su invertido salió ese
        dd/mm). Los grupos de color escalan con el total (~40% hot, ~32% warm,
        resto cool), así con 25 quedan 1-10/11-18/19-25 como el wizard. Datos
        estructurados (sin HTML) para el endpoint REST /consulta-combinaciones.
        NO se cachea a propósito: la ventana cambia con cada salida nueva del
        día (el proxy_cache de 20s de nginx absorbe la repetición)."""
        try:
            top = max(1, min(int(top), 50))
        except (TypeError, ValueError):
            top = 25

        base = self.get_combinaciones_scores(sorteo_id, target_date, window)
        outputs = base['outputs']
        if not outputs:
            return {'window_used': 0, 'top': [],
                    'digits_heat': [], 'window_outputs': []}

        digs = base['digits']
        orden = sorted(base['scores'].items(),
                       key=lambda kv: (-kv[1], kv[0]))[:top]

        # Números (2 cifras) salidos el mismo dd/mm en años anteriores.
        self.env.cr.execute("""
            SELECT DISTINCT RIGHT(complete_number, 2)
            FROM lottery_output
            WHERE sorteo_id = %s
              AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM %s::date)
              AND EXTRACT(DAY FROM date) = EXTRACT(DAY FROM %s::date)
              AND EXTRACT(YEAR FROM date) < EXTRACT(YEAR FROM %s::date)
              AND complete_number IS NOT NULL
        """, (sorteo_id, target_date, target_date, target_date))
        mismos_fecha = {r[0] for r in self.env.cr.fetchall()}

        # Grupos de color proporcionales al total (con 25 → 10/8/7 = wizard).
        n_total = len(orden)
        hot_cut = round(n_total * 0.40)
        warm_cut = round(n_total * 0.72)
        candidatos = [{
            'number': n,
            'score': s,
            'rank': i + 1,
            'group': 'hot' if i < hot_cut else 'warm' if i < warm_cut else 'cool',
            'directo': n in mismos_fecha,
            'virado': n not in mismos_fecha and n[::-1] in mismos_fecha,
        } for i, (n, s) in enumerate(orden)]

        digits_heat = sorted(
            ({'digit': d, 'count': digs.get(d, 0)} for d in '0123456789'),
            key=lambda x: (-x['count'], x['digit']))

        turn_lbl = {'afternoon': 'Tarde', 'evening': 'Noche'}
        window_outputs = [{
            'date': d.strftime('%d/%m'),
            'turn': t,
            'turn_label': turn_lbl.get(t, t),
            'number': n,
        } for d, t, n in outputs]

        return {
            'window_used': len(outputs),
            'top': candidatos,
            'digits_heat': digits_heat,
            'window_outputs': window_outputs,
        }

    @api.model
    @tools.ormcache('month', 'current_year', 'sorteo_id', 'years_top', 'years_mid', 'years_bottom')
    def get_month_overdue_sections(self, month=None, current_year=None, sorteo_id=False,
                                   years_top=2, years_mid=2, years_bottom=4):
        """Números del mes con atraso en años, en 3 secciones por categoría.

        Para cada categoría de /numeros-mes (top=calientes, intermedios,
        bottom=fríos) filtra los números que llevan al menos N años completos
        sin salir en el mes actual, SIN contar el año en curso (es el año a
        evaluar). Ej: estamos en 2026, el 34 salió por última vez en julio
        el 05/07/2023 → 2024 y 2025 sin salir = 2 años → entra con N=2.
        Umbral por categoría: top e intermedios ≥ 2 años, bottom ≥ 4
        (configurables via years_top / years_mid / years_bottom).
        Nunca salió en el mes → también entra.

        Por categoría devuelve:
          all            → Sección 1: todos los que cumplen el umbral
          salieron_anio  → Sección 2: de la 1, los que ya salieron este año
                           en el mes actual (mismo mes, año en curso)
          sin_salir_anio → Sección 3: de la 1, los que no salieron este año en el mes
        """
        categories = {
            'top': (self.get_top_numbers_month(
                month, current_year, sorteo_id=sorteo_id), years_top),
            'intermedios': (self.get_remaining_numbers_month(
                month, current_year, sorteo_id=sorteo_id), years_mid),
            'bottom': (self.get_bottom_numbers_month(
                month, current_year, sorteo_id=sorteo_id), years_bottom),
        }

        # Última salida en este mes en años ANTERIORES al actual, por número
        self.env.cr.execute("""
            SELECT DISTINCT ON (lo.number_id)
                lo.number_id,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS last_month_date,
                lo.year AS last_month_year,
                lo.turn_day AS last_month_turn,
                CASE lo.week_day
                    WHEN 'lu' THEN 'Lun'
                    WHEN 'ma' THEN 'Mar'
                    WHEN 'mi' THEN 'Mié'
                    WHEN 'ju' THEN 'Jue'
                    WHEN 'vi' THEN 'Vie'
                    WHEN 'sa' THEN 'Sáb'
                    WHEN 'do' THEN 'Dom'
                    ELSE lo.week_day
                END AS last_month_week_day
            FROM lottery_output lo
            WHERE lo.sorteo_id = %(sorteo_id)s
              AND lo.month = %(month)s::text
              AND lo.year < %(year)s
            ORDER BY lo.number_id, lo.date DESC
        """, {'sorteo_id': sorteo_id, 'month': month, 'year': current_year})
        prev = {r['number_id']: r for r in self.env.cr.dictfetchall()}

        # Última salida del año ACTUAL en el MES ACTUAL, por número
        self.env.cr.execute("""
            SELECT DISTINCT ON (lo.number_id)
                lo.number_id,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS last_year_date,
                lo.turn_day AS last_year_turn
            FROM lottery_output lo
            WHERE lo.sorteo_id = %(sorteo_id)s
              AND lo.year = %(year)s
              AND lo.month = %(month)s::text
            ORDER BY lo.number_id, lo.date DESC
        """, {'sorteo_id': sorteo_id, 'year': current_year, 'month': month})
        curr = {r['number_id']: r for r in self.env.cr.dictfetchall()}

        result = {}
        for key, (numbers, threshold) in categories.items():
            section_all = []
            for n in numbers:
                p = prev.get(n['id'])
                if p:
                    missed_years = current_year - p['last_month_year'] - 1
                    if missed_years < threshold:
                        continue
                else:
                    missed_years = None  # nunca salió en este mes
                c = curr.get(n['id'])
                section_all.append({
                    'id': n['id'],
                    'name': n['name'],
                    'rank': n['rank'],
                    'total': n['total'],
                    'salidas_mes_anio': n['salidas_mes_anio'],
                    'last_month_date': p['last_month_date'] if p else None,
                    'last_month_turn': p['last_month_turn'] if p else None,
                    'last_month_week_day': p['last_month_week_day'] if p else None,
                    'years_sin_salir_mes': missed_years,
                    'nunca_salio_mes': p is None,
                    'salio_anio_actual': bool(c),
                    'last_year_date': c['last_year_date'] if c else None,
                    'last_year_turn': c['last_year_turn'] if c else None,
                })
            # Más atrasados primero; "nunca salió" encabeza la lista
            section_all.sort(key=lambda i: (
                -(i['years_sin_salir_mes'] if i['years_sin_salir_mes'] is not None else 9999),
                i['rank'],
            ))
            result[key] = {
                'years_threshold': threshold,
                'all': section_all,
                'salieron_anio': [i for i in section_all if i['salio_anio_actual']],
                'sin_salir_anio': [i for i in section_all if not i['salio_anio_actual']],
            }
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_numbers_all_weekdays(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT LPAD(ln.name::text, 2, '0') AS name, ln.id,
                lns.total_lunes, lns.total_martes, lns.total_miercoles,
                lns.total_jueves, lns.total_viernes, lns.total_sabado, lns.total_domingo
            FROM lottery_number_stat lns
            JOIN lottery_number ln ON ln.id = lns.number_id
            WHERE lns.sorteo_id = %(sorteo_id)s
            ORDER BY ln.id
        """, {'sorteo_id': sorteo_id})
        rows = self.env.cr.dictfetchall()
        day_fields = [
            ('lu', 'total_lunes'), ('ma', 'total_martes'), ('mi', 'total_miercoles'),
            ('ju', 'total_jueves'), ('vi', 'total_viernes'), ('sa', 'total_sabado'), ('do', 'total_domingo'),
        ]
        result = {'top': {}, 'bottom': {}}
        for day, field in day_fields:
            desc = sorted(rows, key=lambda x: (x[field] or 0, x['id']), reverse=True)[:15]
            asc = sorted(rows, key=lambda x: (x[field] or 0, -x['id']))[:15]
            result['top'][day] = [{'name': r['name'], 'total': r[field], 'rank': i + 1} for i, r in enumerate(desc)]
            result['bottom'][day] = [{'name': r['name'], 'total': r[field], 'rank': i + 1} for i, r in enumerate(asc)]
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_numbers_all_weeks(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT LPAD(ln.name::text, 2, '0') AS name, ln.id,
                lns.total_semana_1, lns.total_semana_2, lns.total_semana_3, lns.total_semana_4, lns.total_semana_5
            FROM lottery_number_stat lns
            JOIN lottery_number ln ON ln.id = lns.number_id
            WHERE lns.sorteo_id = %(sorteo_id)s
            ORDER BY ln.id
        """, {'sorteo_id': sorteo_id})
        rows = self.env.cr.dictfetchall()
        week_fields = [
            ('sem_1', 'total_semana_1'), ('sem_2', 'total_semana_2'), ('sem_3', 'total_semana_3'),
            ('sem_4', 'total_semana_4'), ('sem_5', 'total_semana_5'),
        ]
        result = {'top': {}, 'bottom': {}}
        for week, field in week_fields:
            desc = sorted(rows, key=lambda x: (x[field] or 0, x['id']), reverse=True)[:15]
            asc = sorted(rows, key=lambda x: (x[field] or 0, -x['id']))[:15]
            result['top'][week] = [{'name': r['name'], 'total': r[field], 'rank': i + 1} for i, r in enumerate(desc)]
            result['bottom'][week] = [{'name': r['name'], 'total': r[field], 'rank': i + 1} for i, r in enumerate(asc)]
        return result

    # ── Tómbola de Quiniela Uruguay (juego aparte, sin sorteo_id) ─────────
    # Sin @tools.ormcache: la tabla lottery_tombola_number_stat tiene 100
    # filas y no hay una MV detrás, así que la query en sí ya es barata; el
    # proxy_cache de nginx delante de estos endpoints (~20s) cubre la
    # repetición sin necesitar que este módulo invalide el ormcache de
    # lottery.stats.service cuando cambian las salidas de Tómbola.

    # Solo líneas y terminales (no pintas/sumas/etc.): son los únicos grupos
    # que interesan para Tómbola. Se reusa el catálogo lottery.group que ya
    # carga lottery_groups (números 0-99, fijo, no depende de sorteo).
    TOMBOLA_GROUP_CODES = ['line_%d' % i for i in range(10)] + ['terminal_%d' % i for i in range(10)]

    def _tombola_top_10(self, order_field, turn_day=None):
        turn_filter = "AND o.turn_day = %(turn_day)s" if turn_day else ""
        self.env.cr.execute(f"""
            SELECT
                lts.number_id AS id,
                LPAD(ln.name::text, 2, '0') AS name,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS ultima_fecha,
                lo.turn_day AS ultimo_turno,
                lts.{order_field} AS total_atrasadas
            FROM lottery_tombola_number_stat lts
            JOIN lottery_number ln ON ln.id = lts.number_id
            LEFT JOIN LATERAL (
                SELECT date, turn_day FROM lottery_tombola_output o
                WHERE o.number_id = lts.number_id {turn_filter}
                ORDER BY date DESC, turn_day DESC
                LIMIT 1
            ) lo ON TRUE
            ORDER BY lts.{order_field} DESC, lts.number_id
            LIMIT 10
        """, {'turn_day': turn_day})
        return self.env.cr.dictfetchall()

    @api.model
    def get_tombola_top_10_general(self):
        return self._tombola_top_10('total_atrasadas')

    @api.model
    def get_tombola_top_10_dia(self):
        return self._tombola_top_10('total_atrasadas_dia', turn_day='afternoon')

    @api.model
    def get_tombola_top_10_noche(self):
        return self._tombola_top_10('total_atrasadas_noche', turn_day='evening')

    @api.model
    def get_tombola_numbers_all_weekdays(self):
        """Top 10 números que más salen en Tómbola, por día de semana
        (lu..sa; sin domingo, no hay sorteo ese día)."""
        day_fields = [
            ('lu', 'total_lunes'), ('ma', 'total_martes'), ('mi', 'total_miercoles'),
            ('ju', 'total_jueves'), ('vi', 'total_viernes'), ('sa', 'total_sabado'),
        ]
        result = {}
        for day, field in day_fields:
            self.env.cr.execute(f"""
                SELECT LPAD(ln.name::text, 2, '0') AS name, lts.{field} AS total
                FROM lottery_tombola_number_stat lts
                JOIN lottery_number ln ON ln.id = lts.number_id
                ORDER BY lts.{field} DESC, lts.number_id
                LIMIT 10
            """)
            result[day] = [dict(r, rank=i + 1) for i, r in enumerate(self.env.cr.dictfetchall())]
        return result

    @api.model
    def get_tombola_numbers_all_weeks(self):
        """Top 10 números que más salen en Tómbola, por semana del mes
        (sem_1..sem_5)."""
        week_fields = [
            ('sem_1', 'total_semana_1'), ('sem_2', 'total_semana_2'), ('sem_3', 'total_semana_3'),
            ('sem_4', 'total_semana_4'), ('sem_5', 'total_semana_5'),
        ]
        result = {}
        for week, field in week_fields:
            self.env.cr.execute(f"""
                SELECT LPAD(ln.name::text, 2, '0') AS name, lts.{field} AS total
                FROM lottery_tombola_number_stat lts
                JOIN lottery_number ln ON ln.id = lts.number_id
                ORDER BY lts.{field} DESC, lts.number_id
                LIMIT 10
            """)
            result[week] = [dict(r, rank=i + 1) for i, r in enumerate(self.env.cr.dictfetchall())]
        return result

    TOMBOLA_GROUPS_TOP_N = 4

    def _tombola_groups_ranking(self, field):
        """Top 4 líneas y top 4 terminales de Tómbola ordenadas por salidas
        (SUMA de sus números), separadas por categoría (no se mezclan entre
        sí: son conjuntos de igual tamaño -10- pero de naturaleza distinta)."""
        self.env.cr.execute(f"""
            SELECT g.code, g.name, SUM(lts.{field}) AS total
            FROM lottery_group_number_rel rel
            JOIN lottery_group g ON g.id = rel.group_id
            JOIN lottery_tombola_number_stat lts ON lts.number_id = rel.number_id
            WHERE g.code = ANY(%(codes)s)
            GROUP BY g.id, g.code, g.name
        """, {'codes': self.TOMBOLA_GROUP_CODES})
        rows = self.env.cr.dictfetchall()
        top_n = self.TOMBOLA_GROUPS_TOP_N
        lineas = sorted((r for r in rows if r['code'].startswith('line_')),
                        key=lambda r: (-r['total'], r['code']))[:top_n]
        terminales = sorted((r for r in rows if r['code'].startswith('terminal_')),
                            key=lambda r: (-r['total'], r['code']))[:top_n]
        return (
            [dict(r, rank=i + 1) for i, r in enumerate(lineas)],
            [dict(r, rank=i + 1) for i, r in enumerate(terminales)],
        )

    @api.model
    def get_tombola_groups_all_weekdays(self):
        """Líneas y terminales de Tómbola que más salen, por día de semana
        (lu..sa; sin domingo, no hay sorteo ese día)."""
        day_fields = [
            ('lu', 'total_lunes'), ('ma', 'total_martes'), ('mi', 'total_miercoles'),
            ('ju', 'total_jueves'), ('vi', 'total_viernes'), ('sa', 'total_sabado'),
        ]
        result = {'lineas': {}, 'terminales': {}}
        for day, field in day_fields:
            lineas, terminales = self._tombola_groups_ranking(field)
            result['lineas'][day] = lineas
            result['terminales'][day] = terminales
        return result

    @api.model
    def get_tombola_groups_all_weeks(self):
        """Líneas y terminales de Tómbola que más salen, por semana del mes
        (sem_1..sem_5)."""
        week_fields = [
            ('sem_1', 'total_semana_1'), ('sem_2', 'total_semana_2'), ('sem_3', 'total_semana_3'),
            ('sem_4', 'total_semana_4'), ('sem_5', 'total_semana_5'),
        ]
        result = {'lineas': {}, 'terminales': {}}
        for week, field in week_fields:
            lineas, terminales = self._tombola_groups_ranking(field)
            result['lineas'][week] = lineas
            result['terminales'][week] = terminales
        return result

    def _tombola_month_numbers_cte(self, field):
        """Copia de _month_numbers_cte para Tómbola: mismo criterio (total =
        histórico del mes en todos los años - lo ya salido este año en el
        mes, ranking global 1-100), sin sorteo_id."""
        return f"""
            WITH base AS (
                SELECT
                    ln.id,
                    LPAD(ln.name::text, 2, '0') AS name,
                    lts.{field} AS total_historico,
                    COALESCE((
                        SELECT COUNT(*) FROM lottery_tombola_output lo
                        WHERE lo.number_id = ln.id
                          AND lo.month = %(month)s::text
                          AND lo.year = %(year)s
                    ), 0) AS salidas_mes_anio,
                    last_info.last_month_date,
                    last_info.last_month_turn,
                    last_info.last_month_week_day
                FROM lottery_tombola_number_stat lts
                JOIN lottery_number ln ON ln.id = lts.number_id
                LEFT JOIN LATERAL (
                    SELECT
                        TO_CHAR(lo2.date, 'DD/MM/YYYY') AS last_month_date,
                        lo2.turn_day AS last_month_turn,
                        CASE lo2.week_day
                            WHEN 'lu' THEN 'Lun'
                            WHEN 'ma' THEN 'Mar'
                            WHEN 'mi' THEN 'Mié'
                            WHEN 'ju' THEN 'Jue'
                            WHEN 'vi' THEN 'Vie'
                            WHEN 'sa' THEN 'Sáb'
                            WHEN 'do' THEN 'Dom'
                            ELSE lo2.week_day
                        END AS last_month_week_day
                    FROM lottery_tombola_output lo2
                    WHERE lo2.number_id = ln.id
                      AND lo2.month = %(month)s::text
                    ORDER BY lo2.date DESC
                    LIMIT 1
                ) last_info ON true
            ),
            ranked AS (
                SELECT
                    id, name, total_historico, salidas_mes_anio,
                    last_month_date, last_month_turn, last_month_week_day,
                    (total_historico - salidas_mes_anio) AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY (total_historico - salidas_mes_anio) DESC, id DESC
                    ) AS global_rank
                FROM base
            )
        """

    @api.model
    def get_tombola_top_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        query = self._tombola_month_numbers_cte(field) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                global_rank AS rank
            FROM ranked
            WHERE global_rank <= 30
            ORDER BY global_rank;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    def get_tombola_remaining_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        query = self._tombola_month_numbers_cte(field) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                global_rank AS rank
            FROM ranked
            WHERE global_rank > 30 AND global_rank <= 70
            ORDER BY global_rank;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    def get_tombola_bottom_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        # rank local 1-30 donde 1 = menos frecuente (compatible con getBallFriosClass)
        query = self._tombola_month_numbers_cte(field) + """
            SELECT
                id, name, total, salidas_mes_anio,
                last_month_date, last_month_turn, last_month_week_day,
                ROW_NUMBER() OVER (ORDER BY total ASC, id DESC) AS rank
            FROM ranked
            WHERE global_rank > 70
            ORDER BY total ASC, id DESC;
        """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    def get_tombola_month_overdue_sections(self, month=None, current_year=None,
                                           years_top=2, years_mid=2, years_bottom=4):
        """Copia de get_month_overdue_sections para Tómbola, sin sorteo_id."""
        categories = {
            'top': (self.get_tombola_top_numbers_month(month, current_year), years_top),
            'intermedios': (self.get_tombola_remaining_numbers_month(month, current_year), years_mid),
            'bottom': (self.get_tombola_bottom_numbers_month(month, current_year), years_bottom),
        }

        # Última salida en este mes en años ANTERIORES al actual, por número
        self.env.cr.execute("""
            SELECT DISTINCT ON (lo.number_id)
                lo.number_id,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS last_month_date,
                lo.year AS last_month_year,
                lo.turn_day AS last_month_turn,
                CASE lo.week_day
                    WHEN 'lu' THEN 'Lun'
                    WHEN 'ma' THEN 'Mar'
                    WHEN 'mi' THEN 'Mié'
                    WHEN 'ju' THEN 'Jue'
                    WHEN 'vi' THEN 'Vie'
                    WHEN 'sa' THEN 'Sáb'
                    WHEN 'do' THEN 'Dom'
                    ELSE lo.week_day
                END AS last_month_week_day
            FROM lottery_tombola_output lo
            WHERE lo.month = %(month)s::text AND lo.year < %(year)s
            ORDER BY lo.number_id, lo.date DESC
        """, {'month': month, 'year': current_year})
        prev = {r['number_id']: r for r in self.env.cr.dictfetchall()}

        # Última salida del año ACTUAL en el MES ACTUAL, por número
        self.env.cr.execute("""
            SELECT DISTINCT ON (lo.number_id)
                lo.number_id,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS last_year_date,
                lo.turn_day AS last_year_turn
            FROM lottery_tombola_output lo
            WHERE lo.year = %(year)s AND lo.month = %(month)s::text
            ORDER BY lo.number_id, lo.date DESC
        """, {'year': current_year, 'month': month})
        curr = {r['number_id']: r for r in self.env.cr.dictfetchall()}

        result = {}
        for key, (numbers, threshold) in categories.items():
            section_all = []
            for n in numbers:
                p = prev.get(n['id'])
                if p:
                    missed_years = current_year - p['last_month_year'] - 1
                    if missed_years < threshold:
                        continue
                else:
                    missed_years = None  # nunca salió en este mes
                c = curr.get(n['id'])
                section_all.append({
                    'id': n['id'],
                    'name': n['name'],
                    'rank': n['rank'],
                    'total': n['total'],
                    'salidas_mes_anio': n['salidas_mes_anio'],
                    'last_month_date': p['last_month_date'] if p else None,
                    'last_month_turn': p['last_month_turn'] if p else None,
                    'last_month_week_day': p['last_month_week_day'] if p else None,
                    'years_sin_salir_mes': missed_years,
                    'nunca_salio_mes': p is None,
                    'salio_anio_actual': bool(c),
                    'last_year_date': c['last_year_date'] if c else None,
                    'last_year_turn': c['last_year_turn'] if c else None,
                })
            # Más atrasados primero; "nunca salió" encabeza la lista
            section_all.sort(key=lambda i: (
                -(i['years_sin_salir_mes'] if i['years_sin_salir_mes'] is not None else 9999),
                i['rank'],
            ))
            result[key] = {
                'years_threshold': threshold,
                'all': section_all,
                'salieron_anio': [i for i in section_all if i['salio_anio_actual']],
                'sin_salir_anio': [i for i in section_all if not i['salio_anio_actual']],
            }
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_centenas_all_weekdays(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT week_day, field_type, centena, total_salidas
            FROM lottery_centena_weekday_mv
            WHERE sorteo_id = %s
            ORDER BY week_day, field_type, total_salidas DESC
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()
        result = {'top_centena': {}, 'bottom_centena': {}, 'top_bola': {}, 'bottom_bola': {}}
        from collections import defaultdict
        grouped = defaultdict(list)
        for r in rows:
            grouped[(r['week_day'], r['field_type'])].append(r)
        for (day, field_type), items in grouped.items():
            key_top = 'top_centena' if field_type == 'hundreds_id' else 'top_bola'
            key_bottom = 'bottom_centena' if field_type == 'hundreds_id' else 'bottom_bola'
            result[key_top][day] = [{'centena': r['centena'], 'total_salidas': r['total_salidas']} for r in items[:4]]
            result[key_bottom][day] = [{'centena': r['centena'], 'total_salidas': r['total_salidas']} for r in reversed(items[-4:])]
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_centenas_all_weeks(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT week_segment, field_type, centena, total_salidas
            FROM lottery_centena_week_mv
            WHERE sorteo_id = %s
            ORDER BY week_segment, field_type, total_salidas DESC
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()
        result = {'top_centena': {}, 'bottom_centena': {}, 'top_bola': {}, 'bottom_bola': {}}
        from collections import defaultdict
        grouped = defaultdict(list)
        for r in rows:
            grouped[(r['week_segment'], r['field_type'])].append(r)
        for (week, field_type), items in grouped.items():
            key_top = 'top_centena' if field_type == 'hundreds_id' else 'top_bola'
            key_bottom = 'bottom_centena' if field_type == 'hundreds_id' else 'bottom_bola'
            result[key_top][week] = [{'centena': r['centena'], 'total_salidas': r['total_salidas']} for r in items[:4]]
            result[key_bottom][week] = [{'centena': r['centena'], 'total_salidas': r['total_salidas']} for r in reversed(items[-4:])]
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_all_atrasos_lineas(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening,
                   last_num_general, last_date_general,
                   last_num_afternoon, last_date_afternoon,
                   last_num_evening, last_date_evening,
                   max_delay_num_general, max_delay_val_general, max_delay_date_general,
                   max_delay_num_afternoon, max_delay_val_afternoon, max_delay_date_afternoon,
                   max_delay_num_evening, max_delay_val_evening, max_delay_date_evening
            FROM lottery_top_atrasos_lineas_mv
            WHERE sorteo_id = %s
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()

        def _row(r, turn):
            return {
                'name': r['name'],
                'atraso': r[turn] or 0,
                'last_num': r[f'last_num_{turn}'],
                'last_date': r[f'last_date_{turn}'],
                'max_delay_num': r[f'max_delay_num_{turn}'],
                'max_delay_val': r[f'max_delay_val_{turn}'],
                'max_delay_date': r[f'max_delay_date_{turn}'],
            }

        return {
            'general':   [_row(r, 'general')   for r in sorted(rows, key=lambda x: x['general'] or 0,   reverse=True)],
            'afternoon': [_row(r, 'afternoon') for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening':   [_row(r, 'evening')   for r in sorted(rows, key=lambda x: x['evening'] or 0,   reverse=True)],
        }

    @api.model
    @tools.ormcache('sorteo_id')
    def get_all_atrasos_terminales(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening,
                   last_num_general, last_date_general,
                   last_num_afternoon, last_date_afternoon,
                   last_num_evening, last_date_evening,
                   max_delay_num_general, max_delay_val_general, max_delay_date_general,
                   max_delay_num_afternoon, max_delay_val_afternoon, max_delay_date_afternoon,
                   max_delay_num_evening, max_delay_val_evening, max_delay_date_evening
            FROM lottery_top_atrasos_terminales_mv
            WHERE sorteo_id = %s
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()

        def _row(r, turn):
            return {
                'name': r['name'],
                'atraso': r[turn] or 0,
                'last_num': r[f'last_num_{turn}'],
                'last_date': r[f'last_date_{turn}'],
                'max_delay_num': r[f'max_delay_num_{turn}'],
                'max_delay_val': r[f'max_delay_val_{turn}'],
                'max_delay_date': r[f'max_delay_date_{turn}'],
            }

        return {
            'general':   [_row(r, 'general')   for r in sorted(rows, key=lambda x: x['general'] or 0,   reverse=True)],
            'afternoon': [_row(r, 'afternoon') for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening':   [_row(r, 'evening')   for r in sorted(rows, key=lambda x: x['evening'] or 0,   reverse=True)],
        }

    @api.model
    @tools.ormcache('sorteo_id')
    def get_weekend_groups(self, sorteo_id=False):
        """Top 5 líneas y terminales que más salen en sábado + domingo."""
        self.env.cr.execute("""
            SELECT grp_type, grp_code, total_general, total_afternoon, total_evening
            FROM lottery_weekend_groups_mv
            WHERE sorteo_id = %s
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()

        def _label(code):
            n = int(code.split('_')[1])
            return f'{n * 10:02d}-{n * 10 + 9:02d}' if code.startswith('line_') else f'{n:02d}→{90 + n:02d}'

        def _top5(type_rows, field):
            ordered = sorted(type_rows, key=lambda x: x[field] or 0, reverse=True)[:5]
            max_val = ordered[0][field] if ordered else 1
            return [
                {
                    'num':   r['grp_code'].split('_')[1],
                    'label': _label(r['grp_code']),
                    'total': r[field] or 0,
                    'pct':   round(100 * (r[field] or 0) / max(max_val, 1)),
                }
                for r in ordered if (r[field] or 0) > 0
            ]

        result = {}
        for grp_type in ('line', 'terminal'):
            type_rows = [r for r in rows if r['grp_type'] == grp_type]
            result[grp_type] = {
                'general':   _top5(type_rows, 'total_general'),
                'afternoon': _top5(type_rows, 'total_afternoon'),
                'evening':   _top5(type_rows, 'total_evening'),
            }
        return result

    @api.model
    @tools.ormcache('day', 'sorteo_id')
    def get_grupos_por_dia(self, day, sorteo_id=False):
        """Top 2 grupos, lineas y terminales mas atrasados por dia usando lottery_group_stat.

        No depende de CURRENT_DATE (a diferencia de get_ultimas_salidas_col1/
        consecutivas): cachear es seguro, igual que su gemelo
        get_top_10_por_dia_semana."""
        field_day_map = {
            'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
            'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
            'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
            'do': 'salidas_atrasadas_domingo',
        }
        field_day = field_day_map.get(day, 'salidas_atrasadas_lunes')

        def _query_top2(code_filter):
            self.env.cr.execute(f"""
                SELECT lg.id, lg.code, UPPER(lg.name) AS name,
                       lgs.salidas_atrasadas,
                       lgs.salidas_atrasadas_dia,
                       lgs.salidas_atrasadas_noche,
                       lgs.{field_day} AS salidas_atrasadas_por_dia
                FROM lottery_group_stat lgs
                JOIN lottery_group lg ON lg.id = lgs.group_id
                WHERE lgs.sorteo_id = %s AND {code_filter}
                ORDER BY lgs.{field_day} DESC
                LIMIT 2
            """, (sorteo_id,))
            return self.env.cr.dictfetchall()

        def _enrich(items):
            for item in items:
                group_obj = self.env['lottery.group'].browse(item['id'])
                num_ids = group_obj.number_ids.ids
                if num_ids:
                    stats = self.env['lottery.number.stat'].search_read(
                        [('number_id', 'in', num_ids), ('sorteo_id', '=', sorteo_id)],
                        ['number_id', field_day],
                        order=f'{field_day} asc',
                    )
                    num_names = {n.id: str(n.name).zfill(2)
                                 for n in self.env['lottery.number'].browse(num_ids)}
                    nums_asc = [
                        {'num': num_names.get(s['number_id'][0], '?'),
                         'delay': s.get(field_day) or 0}
                        for s in stats if s.get('number_id')
                    ]
                    nums_sorted = sorted(nums_asc, key=lambda x: x['num'])
                else:
                    nums_asc = []
                    nums_sorted = []
                item['numbers'] = [n['num'] for n in nums_sorted]
                item['last_on_day'] = nums_asc[0]['num'] if nums_asc else None
                item['most_delayed_on_day'] = nums_asc[-1]['num'] if nums_asc else None
            return items

        # Top 2 grupos (excluye pintas, lineas y terminales)
        # Nota: %% en psycopg2 se convierte en % literal en el SQL enviado a PG
        top_groups = _query_top2(
            "lg.code NOT IN ('pinta_0','pinta_1','pinta_2','pinta_3','pinta_4',"
            "                'pinta_5','pinta_6','pinta_7','pinta_8','pinta_9')"
            " AND lg.code NOT LIKE 'line_%%' AND lg.code NOT LIKE 'terminal_%%'"
        )
        _enrich(top_groups)

        # Top 2 lineas desde lottery_group_stat con codigo line_X
        top_lines = _query_top2("lg.code LIKE 'line_%%'")
        for item in top_lines:
            n = int(item['code'].split('_')[1])
            item['line_num'] = n
            item['name'] = f'Linea {n}'
            item['range'] = f'{n * 10:02d} al {n * 10 + 9:02d}'
        _enrich(top_lines)

        # Top 2 terminales desde lottery_group_stat con codigo terminal_X
        top_terminals = _query_top2("lg.code LIKE 'terminal_%%'")
        for item in top_terminals:
            n = int(item['code'].split('_')[1])
            item['terminal_num'] = n
            item['name'] = f'Terminal {n}'
        _enrich(top_terminals)

        return {
            'groups': top_groups,
            'lines': top_lines,
            'terminals': top_terminals,
        }

    @api.model
    @tools.ormcache('sorteo_id')
    def get_all_group_sequences(self, sorteo_id=False):
        """Para cada línea/terminal, top 5 grupos que salen más frecuentemente a continuación."""
        from collections import defaultdict

        self.env.cr.execute("""
            SELECT grp_type, from_code, to_code,
                   total_general, total_afternoon, total_evening
            FROM lottery_group_sequences_mv
            WHERE sorteo_id = %s
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()

        LINE_RANGES = {f'line_{i}': f'{i * 10:02d}-{i * 10 + 9:02d}' for i in range(10)}

        data = defaultdict(lambda: defaultdict(list))
        for r in rows:
            data[r['grp_type']][r['from_code']].append(r)

        def _label(code):
            n = int(code.split('_')[1])
            if code.startswith('line_'):
                return f'{n * 10:02d}-{n * 10 + 9:02d}'
            return f'{n:02d}→{90 + n:02d}'

        def _top5(rows_list, field):
            ordered = sorted(rows_list, key=lambda x: x[field] or 0, reverse=True)
            top = [r for r in ordered[:5] if (r[field] or 0) > 0]
            max_val = top[0][field] if top else 1
            return [
                {
                    'label':    _label(r['to_code']),
                    'ball_num': r['to_code'].split('_')[1],
                    'total':    r[field] or 0,
                    'pct':      round(100 * (r[field] or 0) / max(max_val, 1)),
                }
                for r in top
            ]

        result = {}
        for grp_type in ('line', 'terminal'):
            result[grp_type] = []
            for i in range(10):
                code = f'{grp_type}_{i}'
                from_rows = data[grp_type].get(code, [])
                result[grp_type].append({
                    'num': str(i),
                    'sublabel': LINE_RANGES[f'line_{i}'] if grp_type == 'line' else f'{i:02d}→{90 + i:02d}',
                    'general':   _top5(from_rows, 'total_general'),
                    'afternoon': _top5(from_rows, 'total_afternoon'),
                    'evening':   _top5(from_rows, 'total_evening'),
                })
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_group_sequences_cross(self, sorteo_id=False):
        """Cross-type sequences between consecutive draws:
           line → next-draw terminal  and  terminal → next-draw line.
           Top 5 per from_code, split by general / afternoon / evening."""
        from collections import defaultdict

        self.env.cr.execute("""
            WITH draw_groups AS (
                SELECT
                    lo.date,
                    lo.turn_day,
                    lg_line.code  AS line_code,
                    lg_term.code  AS term_code,
                    ROW_NUMBER() OVER (
                        PARTITION BY lo.sorteo_id
                        ORDER BY lo.date,
                        CASE lo.turn_day WHEN 'afternoon' THEN 0 ELSE 1 END,
                        lo.id
                    ) AS seq
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                JOIN lottery_group_number_rel rel_l ON rel_l.number_id = ln.id
                JOIN lottery_group lg_line
                    ON lg_line.id = rel_l.group_id AND lg_line.code LIKE 'line_%%'
                JOIN lottery_group_number_rel rel_t ON rel_t.number_id = ln.id
                JOIN lottery_group lg_term
                    ON lg_term.id = rel_t.group_id AND lg_term.code LIKE 'terminal_%%'
                WHERE lo.sorteo_id = %(sorteo_id)s
            ),
            pairs AS (
                SELECT
                    c.line_code  AS line_from,
                    c.term_code  AS term_from,
                    c.turn_day,
                    n.line_code  AS line_to,
                    n.term_code  AS term_to
                FROM draw_groups c
                JOIN draw_groups n ON n.seq = c.seq + 1
            )
            SELECT 'line_to_term' AS cross_type,
                   line_from      AS from_code,
                   term_to        AS to_code,
                   COUNT(*)                                        AS total_general,
                   COUNT(*) FILTER (WHERE turn_day = 'afternoon') AS total_afternoon,
                   COUNT(*) FILTER (WHERE turn_day = 'evening')   AS total_evening
            FROM pairs
            GROUP BY line_from, term_to

            UNION ALL

            SELECT 'term_to_line' AS cross_type,
                   term_from      AS from_code,
                   line_to        AS to_code,
                   COUNT(*)                                        AS total_general,
                   COUNT(*) FILTER (WHERE turn_day = 'afternoon') AS total_afternoon,
                   COUNT(*) FILTER (WHERE turn_day = 'evening')   AS total_evening
            FROM pairs
            GROUP BY term_from, line_to
        """, {'sorteo_id': sorteo_id})
        rows = self.env.cr.dictfetchall()

        data = defaultdict(lambda: defaultdict(list))
        for r in rows:
            data[r['cross_type']][r['from_code']].append(r)

        def _label(code):
            n = int(code.split('_')[1])
            if code.startswith('line_'):
                return f'{n * 10:02d}-{n * 10 + 9:02d}'
            return f'{n:02d}→{90 + n:02d}'

        def _top5(rows_list, field):
            ordered = sorted(rows_list, key=lambda x: x[field] or 0, reverse=True)
            top = [r for r in ordered[:5] if (r[field] or 0) > 0]
            max_val = top[0][field] if top else 1
            return [
                {
                    'label':    _label(r['to_code']),
                    'ball_num': r['to_code'].split('_')[1],
                    'total':    r[field] or 0,
                    'pct':      round(100 * (r[field] or 0) / max(max_val, 1)),
                }
                for r in top
            ]

        result = {}
        for i in range(10):
            line_code = f'line_{i}'
            term_code = f'terminal_{i}'
            result[line_code] = {
                'general':   _top5(data['line_to_term'].get(line_code, []), 'total_general'),
                'afternoon': _top5(data['line_to_term'].get(line_code, []), 'total_afternoon'),
                'evening':   _top5(data['line_to_term'].get(line_code, []), 'total_evening'),
            }
            result[term_code] = {
                'general':   _top5(data['term_to_line'].get(term_code, []), 'total_general'),
                'afternoon': _top5(data['term_to_line'].get(term_code, []), 'total_afternoon'),
                'evening':   _top5(data['term_to_line'].get(term_code, []), 'total_evening'),
            }
        return result

    @api.model
    @tools.ormcache('sorteo_id')
    def get_all_atrasos_parejas(self, sorteo_id=False):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening, last_date, last_turn,
                   last_date_afternoon, last_date_evening
            FROM lottery_number_groups_atrasos_mv
            WHERE group_code = 'resta_0' AND sorteo_id = %s
        """, (sorteo_id,))
        rows = self.env.cr.dictfetchall()

        def _fmt(r, field, turn=None):
            if turn == 'afternoon':
                ld = r['last_date_afternoon'] or ''
                lt = 'afternoon'
            elif turn == 'evening':
                ld = r['last_date_evening'] or ''
                lt = 'evening'
            else:
                ld = r['last_date'] or ''
                lt = r['last_turn'] or ''
            return {
                'name': r['name'],
                'atraso': r[field],
                'last_date': ld,
                'last_turn': lt,
            }

        return {
            'general': [_fmt(r, 'general') for r in sorted(rows, key=lambda x: x['general'] or 0, reverse=True)],
            'afternoon': [_fmt(r, 'afternoon', 'afternoon') for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening': [_fmt(r, 'evening', 'evening') for r in sorted(rows, key=lambda x: x['evening'] or 0, reverse=True)],
        }

    @api.model
    @tools.ormcache('day', 'sorteo_id')
    def get_top_numbers_by_week_day(self, day, sorteo_id=False):
        field = WEEKDAY_FIELD_MAP.get(day)

        if not field:
            return []
        query = f"""
                SELECT
                    LPAD(ln.name::text, 2, '0') AS name,
                    lns.{field} AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY lns.{field} desc, ln.id desc
                    ) AS rank
                FROM lottery_number_stat lns
                JOIN lottery_number ln ON ln.id = lns.number_id
                WHERE lns.sorteo_id = %(sorteo_id)s
                ORDER BY lns.{field} desc, ln.id desc
                LIMIT 15;
                """
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'sorteo_id')
    def get_top_numbers_by_week(self, week, sorteo_id=False):
        field = WEEK_FIELD_MAP.get(week)

        if not field:
            return []
        query = f"""
                    SELECT
                        LPAD(ln.name::text, 2, '0') AS name,
                        lns.{field} AS total,
                        ROW_NUMBER() OVER (
                            ORDER BY lns.{field} desc, ln.id desc
                        ) AS rank
                    FROM lottery_number_stat lns
                    JOIN lottery_number ln ON ln.id = lns.number_id
                    WHERE lns.sorteo_id = %(sorteo_id)s
                    ORDER BY lns.{field} desc, ln.id desc
                    LIMIT 15;
                    """
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('day', 'sorteo_id')
    def get_bottom_numbers_by_week_day(self, day, sorteo_id=False):
        field = WEEKDAY_FIELD_MAP.get(day)

        if not field:
            return []
        query = f"""
                    SELECT
                        LPAD(ln.name::text, 2, '0') AS name,
                        lns.{field} AS total,
                        ROW_NUMBER() OVER (
                            ORDER BY lns.{field}, ln.id desc
                        ) AS rank
                    FROM lottery_number_stat lns
                    JOIN lottery_number ln ON ln.id = lns.number_id
                    WHERE lns.sorteo_id = %(sorteo_id)s
                    ORDER BY lns.{field}, ln.id desc
                    LIMIT 15;
                    """
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'sorteo_id')
    def get_bottom_numbers_by_week(self, week, sorteo_id=False):
        field = WEEK_FIELD_MAP.get(week)

        if not field:
            return []
        query = f"""
                        SELECT
                            LPAD(ln.name::text, 2, '0') AS name,
                            lns.{field} AS total,
                            ROW_NUMBER() OVER (
                                ORDER BY lns.{field}, ln.id desc
                            ) AS rank
                        FROM lottery_number_stat lns
                        JOIN lottery_number ln ON ln.id = lns.number_id
                        WHERE lns.sorteo_id = %(sorteo_id)s
                        ORDER BY lns.{field}, ln.id desc
                        LIMIT 15;
                        """
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_numeros_por_dia_completo(self, day, sorteo_id=False):
        """Top 10 numbers by frequency for a weekday, split by General / Tarde / Noche.
        Includes current delays. No ormcache — delay fields change daily."""
        field_map = {
            'lu': 'total_lunes', 'ma': 'total_martes', 'mi': 'total_miercoles',
            'ju': 'total_jueves', 'vi': 'total_viernes', 'sa': 'total_sabado', 'do': 'total_domingo',
        }
        delay_day_map = {
            'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
            'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
            'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
            'do': 'salidas_atrasadas_domingo',
        }
        day_field = field_map.get(day)
        delay_day_field = delay_day_map.get(day)
        if not day_field:
            return {}

        # General — top 10 by historic frequency on this weekday
        self.env.cr.execute(f"""
            SELECT
                LPAD(ln.name::text, 2, '0') AS name,
                ln.id,
                lns.{day_field} AS total,
                lns.total_atrasadas AS delay_general,
                lns.total_atrasadas_dia AS delay_tarde,
                lns.total_atrasadas_noche AS delay_noche,
                lns.{delay_day_field} AS delay_dia_semana,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS ultima_fecha,
                lo.turn_day AS ultimo_turno
            FROM lottery_number_stat lns
            JOIN lottery_number ln ON ln.id = lns.number_id
            LEFT JOIN LATERAL (
                SELECT date, turn_day FROM lottery_output
                WHERE number_id = ln.id AND week_day = %s
                ORDER BY date DESC LIMIT 1
            ) lo ON true
            WHERE lns.sorteo_id = %s
            ORDER BY lns.{day_field} DESC, ln.id DESC
            LIMIT 10
        """, (day, sorteo_id))
        general = self.env.cr.dictfetchall()

        # Tarde — top 10 by frequency on this weekday + afternoon only
        self.env.cr.execute(f"""
            SELECT
                LPAD(ln.name::text, 2, '0') AS name,
                ln.id,
                COUNT(lo.id) AS total,
                lns.total_atrasadas_dia AS delay_tarde,
                lns.total_atrasadas AS delay_general,
                lns.{delay_day_field} AS delay_dia_semana,
                TO_CHAR(MAX(lo.date), 'DD/MM/YYYY') AS ultima_fecha
            FROM lottery_number ln
            JOIN lottery_output lo ON lo.number_id = ln.id AND lo.sorteo_id = %s
            JOIN lottery_number_stat lns ON lns.number_id = ln.id AND lns.sorteo_id = %s
            WHERE lo.week_day = %s AND lo.turn_day = 'afternoon'
            GROUP BY ln.id, ln.name, lns.total_atrasadas_dia, lns.total_atrasadas, lns.{delay_day_field}
            ORDER BY total DESC, ln.id DESC
            LIMIT 10
        """, (sorteo_id, sorteo_id, day))
        tarde = self.env.cr.dictfetchall()

        # Noche — top 10 by frequency on this weekday + evening only
        self.env.cr.execute(f"""
            SELECT
                LPAD(ln.name::text, 2, '0') AS name,
                ln.id,
                COUNT(lo.id) AS total,
                lns.total_atrasadas_noche AS delay_noche,
                lns.total_atrasadas AS delay_general,
                lns.{delay_day_field} AS delay_dia_semana,
                TO_CHAR(MAX(lo.date), 'DD/MM/YYYY') AS ultima_fecha
            FROM lottery_number ln
            JOIN lottery_output lo ON lo.number_id = ln.id AND lo.sorteo_id = %s
            JOIN lottery_number_stat lns ON lns.number_id = ln.id AND lns.sorteo_id = %s
            WHERE lo.week_day = %s AND lo.turn_day = 'evening'
            GROUP BY ln.id, ln.name, lns.total_atrasadas_noche, lns.total_atrasadas, lns.{delay_day_field}
            ORDER BY total DESC, ln.id DESC
            LIMIT 10
        """, (sorteo_id, sorteo_id, day))
        noche = self.env.cr.dictfetchall()

        return {'general': general, 'tarde': tarde, 'noche': noche}

    @api.model
    @tools.ormcache('number_id', 'sorteo_id')
    def get_salidas_numeros_despues_numero(self, number_id, sorteo_id=False):
        """Top 10 números que más salieron dentro de los 3 sorteos
        siguientes a cada aparición de number_id (ventana ampliada de 1 a 3,
        los 3 offsets pesan igual)."""
        self.env.cr.execute("""
            SELECT
                LPAD(ln_next.name::text, 2, '0') AS name,
                COUNT(ln_next.name) AS cantidad_veces
            FROM (
                SELECT lo.*,
                    LEAD(lo.id, 1) OVER w AS next_id_1,
                    LEAD(lo.id, 2) OVER w AS next_id_2,
                    LEAD(lo.id, 3) OVER w AS next_id_3
                FROM lottery_output lo
                WHERE lo.sorteo_id = %s
                WINDOW w AS (
                    ORDER BY lo.date ASC,
                             CASE lo.turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                )
            ) lo_actual
            CROSS JOIN LATERAL (
                VALUES (lo_actual.next_id_1), (lo_actual.next_id_2), (lo_actual.next_id_3)
            ) AS nxt(next_id)
            JOIN lottery_output lo_next ON lo_next.id = nxt.next_id
            JOIN lottery_number ln_next ON ln_next.id = lo_next.number_id
            WHERE lo_actual.number_id = %s
            GROUP BY ln_next.name
            ORDER BY COUNT(ln_next.name) DESC, ln_next.name
            LIMIT 10
        """, (sorteo_id, number_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('number_id', 'sorteo_id')
    def get_salidas_numeros_antes_numero(self, number_id, sorteo_id=False):
        """Top 10 números que más salieron dentro de los 3 sorteos
        anteriores a cada aparición de number_id (ventana ampliada de 1 a 3,
        los 3 offsets pesan igual)."""
        self.env.cr.execute("""
            SELECT
                LPAD(ln_prev.name::text, 2, '0') AS name,
                COUNT(ln_prev.name) AS cantidad_veces
            FROM (
                SELECT lo.*,
                    LAG(lo.id, 1) OVER w AS prev_id_1,
                    LAG(lo.id, 2) OVER w AS prev_id_2,
                    LAG(lo.id, 3) OVER w AS prev_id_3
                FROM lottery_output lo
                WHERE lo.sorteo_id = %s
                WINDOW w AS (
                    ORDER BY lo.date ASC,
                             CASE lo.turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                )
            ) lo_actual
            CROSS JOIN LATERAL (
                VALUES (lo_actual.prev_id_1), (lo_actual.prev_id_2), (lo_actual.prev_id_3)
            ) AS prv(prev_id)
            JOIN lottery_output lo_prev ON lo_prev.id = prv.prev_id
            JOIN lottery_number ln_prev ON ln_prev.id = lo_prev.number_id
            WHERE lo_actual.number_id = %s
            GROUP BY ln_prev.name
            ORDER BY COUNT(ln_prev.name) DESC, ln_prev.name
            LIMIT 10
        """, (sorteo_id, number_id,))
        return self.env.cr.dictfetchall()

    @api.model
    def get_companion_affinity(self, sorteo_id, fecha_corte=False, turno=False):
        """Afinidad simétrica entre cada par de números 0-99: cuántas veces
        aparecieron uno cerca del otro (dentro de una ventana de 3 sorteos,
        antes o después) hasta fecha_corte inclusive (False = todo el
        historial). Usado por la Tabla LotoAnálisis (lottery.tabla.
        acompanantes) para ubicar los números en la grilla — no es un
        endpoint de alta frecuencia, así que sin ormcache: cada corte de
        fecha es distinto y se pide bajo demanda desde el wizard.

        turno=False → General (mezcla tarde y noche, como siempre).
        turno='afternoon'/'evening' → solo esa secuencia de sorteos
        consecutivos (ventana de 3 dentro del mismo turno, saltando el
        otro).

        Devuelve {(num_a, num_b): peso} con num_a < num_b (cada par una
        sola vez, sumando ambas direcciones)."""
        date_filter = "AND lo.date <= %(fecha_corte)s" if fecha_corte else ""
        turno_filter = "AND lo.turn_day = %(turno)s" if turno else ""
        self.env.cr.execute(f"""
            SELECT ln_a.name AS num_a, ln_b.name AS num_b, COUNT(*) AS peso
            FROM (
                SELECT lo.*,
                    LEAD(lo.number_id, 1) OVER w AS n1,
                    LEAD(lo.number_id, 2) OVER w AS n2,
                    LEAD(lo.number_id, 3) OVER w AS n3,
                    LAG(lo.number_id, 1) OVER w AS p1,
                    LAG(lo.number_id, 2) OVER w AS p2,
                    LAG(lo.number_id, 3) OVER w AS p3
                FROM lottery_output lo
                WHERE lo.sorteo_id = %(sorteo_id)s {date_filter} {turno_filter}
                WINDOW w AS (
                    ORDER BY lo.date ASC,
                             CASE lo.turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                )
            ) lo_actual
            CROSS JOIN LATERAL (
                VALUES (n1), (n2), (n3), (p1), (p2), (p3)
            ) AS nb(neighbor_id)
            JOIN lottery_number ln_a ON ln_a.id = lo_actual.number_id
            JOIN lottery_number ln_b ON ln_b.id = nb.neighbor_id
            WHERE ln_a.name <> ln_b.name
            GROUP BY ln_a.name, ln_b.name
        """, {'sorteo_id': sorteo_id, 'fecha_corte': fecha_corte, 'turno': turno})

        affinity = {}
        for row in self.env.cr.dictfetchall():
            a, b = int(row['num_a']), int(row['num_b'])
            key = (a, b) if a < b else (b, a)
            affinity[key] = affinity.get(key, 0) + row['peso']
        return affinity

    @api.model
    @tools.ormcache('day', 'field', 'sorteo_id')
    def get_top_centenas_by_week_day(self, day, field, sorteo_id=False):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_weekday_mv
            WHERE week_day = %s AND field_type = %s AND sorteo_id = %s
            ORDER BY total_salidas DESC
            LIMIT 4
        """, (day, field, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('day', 'field', 'sorteo_id')
    def get_bottom_centenas_by_week_day(self, day, field, sorteo_id=False):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_weekday_mv
            WHERE week_day = %s AND field_type = %s AND sorteo_id = %s
            ORDER BY total_salidas ASC
            LIMIT 4
        """, (day, field, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'field', 'sorteo_id')
    def get_top_centenas_by_week(self, week, field, sorteo_id=False):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_week_mv
            WHERE week_segment = %s AND field_type = %s AND sorteo_id = %s
            ORDER BY total_salidas DESC
            LIMIT 4
        """, (week, field, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'field', 'sorteo_id')
    def get_bottom_centenas_by_week(self, week, field, sorteo_id=False):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_week_mv
            WHERE week_segment = %s AND field_type = %s AND sorteo_id = %s
            ORDER BY total_salidas ASC
            LIMIT 4
        """, (week, field, sorteo_id))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top_repeticiones(self, sorteo_id=False):
        query = f"""WITH data AS (select number_id, date,
              LAG(number_id) OVER (ORDER BY date, CASE WHEN turn_day = 'afternoon' THEN 1 ELSE 2 END) AS prev_number
                FROM lottery_output WHERE sorteo_id = %(sorteo_id)s),
            pegados AS (select number_id, date FROM data WHERE number_id = prev_number)
            select LPAD(ln.name::text, 2, '0') AS name,
                COUNT(*) AS repeticiones,
                TO_CHAR(MAX(p.date), 'DD/MM/YYYY') AS ultima_repeticion
            FROM pegados p
            JOIN lottery_number ln ON ln.id = p.number_id
            GROUP BY ln.name
            ORDER BY repeticiones desc, ln.name
            LIMIT 15;"""
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_id')
    def get_top_pegados(self, sorteo_id=False):
        query = f"""WITH data AS (
            SELECT
                ln.name::int AS numero,
                lo.date,
                LEAD(ln.name::int) OVER (
                    ORDER BY lo.date,
                    CASE WHEN lo.turn_day = 'afternoon' THEN 1 ELSE 2 END
                ) AS next_numero
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %(sorteo_id)s
        ),
        pegados AS (
            SELECT
                numero,
                date
            FROM data
            WHERE ABS(numero - next_numero) = 1
        )
        SELECT
            LPAD(numero::text, 2, '0') AS name,
            COUNT(*) AS pegadas,
            TO_CHAR(MAX(date), 'DD/MM/YYYY') AS ultima_pegada
        FROM pegados
        GROUP BY numero
        ORDER BY pegadas DESC
        LIMIT 15;"""
        self.env.cr.execute(query, {'sorteo_id': sorteo_id})
        return self.env.cr.dictfetchall()

    @tools.ormcache('option', 'day', 'sorteo_id')
    def get_top_6_groups(self, option=False, day=False, sorteo_id=False):
        field_map = {'general': 'salidas_atrasadas', 'afternoon': 'salidas_atrasadas_dia',
                     'evening': 'salidas_atrasadas_noche'}
        day_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                     'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
                     'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
                     'do': 'salidas_atrasadas_domingo'}

        field = field_map.get(option, 'salidas_atrasadas')
        field_day = day_map.get(day, 'salidas_atrasadas_lunes')
        query = f"""SELECT lg.id, UPPER(lg.name) as name, lgs.salidas_atrasadas,
        lgs.salidas_atrasadas_dia,
        lgs.salidas_atrasadas_noche,
        lgs.{field_day} as salidas_atrasadas_por_dia
        FROM lottery_group_stat lgs
        JOIN lottery_group lg ON lg.id = lgs.group_id
        WHERE lgs.sorteo_id = %s AND lg.code not in ('pinta_0', 'pinta_1', 'pinta_2', 'pinta_3', 'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7', 'pinta_8', 'pinta_9')
         ORDER BY lgs.{field} DESC LIMIT %s"""
        self.env.cr.execute(query, (sorteo_id, 5))
        groups = self.env.cr.dictfetchall()
        return groups

    @tools.ormcache('group', 'orden', 'day', 'sorteo_id')
    def get_info_groups_numbers(self, group, orden, day, sorteo_id=False):
        field_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                     'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves', 'vi': 'salidas_atrasadas_viernes',
                     'sa': 'salidas_atrasadas_sabado', 'do': 'salidas_atrasadas_domingo'
                     }
        field = field_map.get(day)

        stats = self.env['lottery.number.stat'].search_read(
            [('number_id', 'in', group.number_ids.ids), ('sorteo_id', '=', sorteo_id)],
            ['number_id', 'total_atrasadas', 'total_atrasadas_dia', 'total_atrasadas_noche', field
             ], order=f'{orden} desc')

        number_ids = [s['number_id'][0] for s in stats if s.get('number_id')]
        names_by_id = {n.id: n.name for n in self.env['lottery.number'].browse(number_ids)}

        return [{
                'numero': str(names_by_id.get(n['number_id'][0], '')).zfill(2),
                'total_atrasadas': n.get('total_atrasadas', 0),
                'total_atrasadas_dia': n.get('total_atrasadas_dia', 0),
                'total_atrasadas_noche': n.get('total_atrasadas_noche', 0),
                'total_atrasadas_por_dia_semana': n.get(field, 0)}
            for n in stats
        ]

    @tools.ormcache('option', 'day', 'sorteo_id')
    def get_top_3_pintas(self, option=False, day=False, sorteo_id=False):
        field_map = {'general': 'salidas_atrasadas', 'afternoon': 'salidas_atrasadas_dia',
                     'evening': 'salidas_atrasadas_noche'}
        day_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                   'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
                   'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
                   'do': 'salidas_atrasadas_domingo'}

        field = field_map.get(option, 'salidas_atrasadas')
        field_day = day_map.get(day, 'salidas_atrasadas_lunes')
        query = f"""SELECT lg.id, UPPER(lg.name) as name, lgs.salidas_atrasadas,
            lgs.salidas_atrasadas_dia,
            lgs.salidas_atrasadas_noche,
            lgs.{field_day} as salidas_atrasadas_por_dia
            FROM lottery_group_stat lgs
            JOIN lottery_group lg ON lg.id = lgs.group_id
            WHERE lgs.sorteo_id = %s AND lg.code in ('pinta_0', 'pinta_1', 'pinta_2', 'pinta_3', 'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7', 'pinta_8', 'pinta_9')
             ORDER BY lgs.{field} DESC LIMIT %s"""
        self.env.cr.execute(query, (sorteo_id, 3))
        groups = self.env.cr.dictfetchall()
        return groups

    @tools.ormcache('group_id', 'day', 'week', 'month', 'limit', 'sorteo_id')
    def get_info_group_numbers_analysis(self, group_id, day, week, month, limit, sorteo_id=False):
        if not group_id or not day or not month or not week:
            return {}

        self.env.cr.execute("""
                SELECT *
                FROM lottery_group_analysis_mv
                WHERE group_id = %s AND sorteo_id = %s
            """, (group_id, sorteo_id))

        rows = self.env.cr.dictfetchall()

        if not rows:
            return {}

        # ðŸ”¹ helpers
        def top(rows, field, n=1, reverse=True):
            return sorted(rows, key=lambda x: x[field] or 0, reverse=reverse)[:n]

        def s(r):
            return {
                "id": r["number_id"],
                "name": r["name"],
            }

        def s_list(lst):
            return [s(x) for x in lst]

        # ðŸ”¹ MAPAS DINÁMICOS

        month_map = {
            1: "cant_salidas_enero",
            2: "cant_salidas_febrero",
            3: "cant_salidas_marzo",
            4: "cant_salidas_abril",
            5: "cant_salidas_mayo",
            6: "cant_salidas_junio",
            7: "cant_salidas_julio",
            8: "cant_salidas_agosto",
            9: "cant_salidas_septiembre",
            10: "cant_salidas_octubre",
            11: "cant_salidas_noviembre",
            12: "cant_salidas_diciembre",
        }

        week_field = f"total_semana_{week}"

        day_map = {
            "lu": "total_lunes",
            "ma": "total_martes",
            "mi": "total_miercoles",
            "ju": "total_jueves",
            "vi": "total_viernes",
            "sa": "total_sabado",
            "do": "total_domingo",
        }

        day_field = day_map.get(day.lower())

        month_field = month_map.get(month)

        if not all([day_field, month_field, week_field]):
            return {}

        result = {
            "last": s(top(rows, "total_atrasadas", 1, reverse=False)[0]),
            "last_day": s(top(rows, "total_atrasadas_dia", 1, reverse=False)[0]),
            "last_night": s(top(rows, "total_atrasadas_noche", 1, reverse=False)[0]),

            "most_delayed": s_list(top(rows, "total_atrasadas", limit)),
            "most_delayed_day": s_list(top(rows, "total_atrasadas_dia", limit)),
            "most_delayed_night": s_list(top(rows, "total_atrasadas_noche", limit)),

            "day": {
                "most": s_list(top(rows, day_field, limit)),
                "least": s_list(top(rows, day_field, limit, reverse=False)),
            },

            "month": {
                "most": s_list(top(rows, month_field, limit)),
                "least": s_list(top(rows, month_field, limit, reverse=False)),
            },

            "week": {
                "most": s_list(top(rows, week_field, limit)),
                "least": s_list(top(rows, week_field, limit, reverse=False)),
            },

            "day_time": {
                "most": s_list(top(rows, "total_atrasadas_dia", limit, reverse=False)),
                "least": s_list(top(rows, "total_atrasadas_dia", limit)),
            },

            "night_time": {
                "most": s_list(top(rows, "total_atrasadas_noche", limit, reverse=False)),
                "least": s_list(top(rows, "total_atrasadas_noche", limit)),
            },
        }

        return result

    @tools.ormcache('group_id', 'turn', 'sorteo_id')
    def get_group_delay_intervals(self, group_id, turn=None, sorteo_id=False):
        where_clause = "where o.sorteo_id = %s"
        params = [group_id]
        if turn:
            where_clause += " and o.turn_day = %s"
            params.append(sorteo_id)
            params.append(turn)
        else:
            params.append(sorteo_id)

        self.env.cr.execute(f"""
            WITH base AS (
            SELECT
                o.date,
                o.turn_day,
                CASE
                    WHEN rel.number_id IS NOT NULL THEN 1
                    ELSE 0
                END AS hit
            FROM lottery_output o
            LEFT JOIN lottery_group_number_rel rel
                ON rel.number_id = o.number_id
                AND rel.group_id = %s
                {where_clause}
        ),
        
        streaks AS (
            SELECT *,
                SUM(hit) OVER (ORDER BY date, turn_day) AS grp
            FROM base
        ),
        
        atrasos AS (
            SELECT
                grp,
                COUNT(*) AS atraso
            FROM streaks
            WHERE hit = 0
            GROUP BY grp
        )
        
        SELECT            
            COUNT(*) FILTER (WHERE atraso BETWEEN 21 AND 40) AS r_21_40,
            COUNT(*) FILTER (WHERE atraso BETWEEN 41 AND 50) AS r_41_50,
            COUNT(*) FILTER (WHERE atraso BETWEEN 51 AND 60) AS r_51_60,
            COUNT(*) FILTER (WHERE atraso BETWEEN 61 AND 70) AS r_61_70,
            COUNT(*) FILTER (WHERE atraso > 70) AS r_70_plus
        FROM atrasos;
        """, tuple(params))

        return self.env.cr.dictfetchone()

    @tools.ormcache('group_id', 'turn', 'sorteo_id')
    def get_group_delay_intervals_pintas(self, group_id, turn=None, sorteo_id=False):
        where_clause = "where o.sorteo_id = %s"
        params = [group_id]
        if turn:
            where_clause += " and o.turn_day = %s"
            params.append(sorteo_id)
            params.append(turn)
        else:
            params.append(sorteo_id)
        self.env.cr.execute(f"""
                WITH base AS (
                SELECT
                    o.date,
                    o.turn_day,
                    CASE
                        WHEN rel.number_id IS NOT NULL THEN 1
                        ELSE 0
                    END AS hit
                FROM lottery_output o
                LEFT JOIN lottery_group_number_rel rel
                    ON rel.number_id = o.number_id
                    AND rel.group_id = %s
                    {where_clause}
            ),

            streaks AS (
                SELECT *,
                    SUM(hit) OVER (ORDER BY date, turn_day) AS grp
                FROM base
            ),

            atrasos AS (
                SELECT
                    grp,
                    COUNT(*) AS atraso
                FROM streaks
                WHERE hit = 0
                GROUP BY grp
            )

            SELECT            
                COUNT(*) FILTER (WHERE atraso BETWEEN 10 AND 20) AS r_10_20,
                COUNT(*) FILTER (WHERE atraso BETWEEN 21 AND 30) AS r_21_30,
                COUNT(*) FILTER (WHERE atraso BETWEEN 31 AND 40) AS r_31_40,
                COUNT(*) FILTER (WHERE atraso BETWEEN 41 AND 45) AS r_41_45,
                COUNT(*) FILTER (WHERE atraso > 45) AS r_45_plus
            FROM atrasos;
            """, tuple(params))

        return self.env.cr.dictfetchone()

    # ─── Números Calientes ───────────────────────────────────────────────────

    @api.model
    @tools.ormcache('turn_day', 'today_str', 'sorteo_id')
    def get_numeros_calientes(self, turn_day, today_str, sorteo_id=False):
        """
        Ponderación separada: estadísticas GENERALES aplican igual a ambos turnos;
        estadísticas POR TURNO solo suman al turno correspondiente.

        Todos los criterios están en rango 7–15 pts (ratio máx/mín ≤ 2×) para que
        ningún criterio individual domine el ranking.

        GENERALES (mismo peso tarde y noche):
          C1   15 pts  Top 70 salidores del mes actual
          C2   13 pts  Top 5 líneas (decenas) que más siguen a la última sorteada
          C3   11 pts  Top 5 terminales que más siguen al último sorteado
                       +4 pts bonus si coinciden línea Y terminal
          C4   10 pts  Líneas pendientes: sin cumplir el patrón en últimos 4 ciclos
          C5    9 pts  Terminales pendientes: igual lógica que C4
          C6   10 pts  Top 5 grupos más atrasados — GENERAL
          C7    9 pts  Top 5 pintas más atrasadas — GENERAL
          C8    8 pts  Semana del mes: 40 % frecuencia + 60 % atraso acumulado
          C9    7 pts  Día de la semana: 40 % frecuencia + 60 % atraso acumulado
          C13  10 pts  Decena/unidad coincide con dígitos de últimos 3 sorteos ±1
          C14 −20 pts  Penalización por recencia (−20 exacto / −10 reciente / −5 adyacente)
          C15   8 pts  Top 5 líneas en fin de semana  (solo sáb/dom)
          C16   7 pts  Top 5 terminales en fin de semana (solo sáb/dom)
                       +3 pts bonus si coinciden C15 y C16
          C17   5 pts  Presión de fríos: solo bottom-30 del mes, escalado por la
                       proporción de los últimos 6 sorteos que fueron del top-70
                       (0 → sin presión · 5 → todos los recientes eran top-70)

        POR TURNO (tarde → afternoon / noche → evening):
          C10  12 pts  Top 5 grupos más atrasados del turno
          C11  10 pts  Top 5 pintas más atrasadas del turno
          C12   9 pts  Salidor del mes × atraso del turno

        Máx semana:      ~112 pts aprox. (sin penalización, rango comprimido)
        Máx fin de semana: ~130 pts aprox. (+ C15 + C16 + bonus)
        Bottom-30 max C17: +5 pts adicionales cuando cold_pressure = 1.0
        """
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        month = today.month
        pg_dow = (today.weekday() + 1) % 7        # Python Mon=0 → PG Mon=1, PG Sun=0
        day = today.day

        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'

        # ── Resumen de criterios (rango 7–15 pts, ratio ≤ 2×) ──────────────
        # GENERALES:
        #   C1   15 pts  Top 70 salidores del mes actual
        #   C2   13 pts  Top 5 líneas que más siguen a la última línea sorteada
        #   C3   11 pts  Top 5 terminales que más siguen al último terminal
        #                +4 pts bonus si coinciden línea Y terminal
        #   C4   10 pts  Líneas pendientes (sin cumplir en 4 ciclos recientes)
        #   C5    9 pts  Terminales pendientes (ídem)
        #   C6   10 pts  Top 5 grupos más atrasados — GENERAL
        #   C7    9 pts  Top 5 pintas más atrasadas — GENERAL
        #   C8    8 pts  Semana del mes: 40% freq + 60% atraso normalizado
        #   C9    7 pts  Día de la semana: 40% freq + 60% atraso normalizado
        #   C13  10 pts  Dígitos de últimos 3 sorteos ±1
        #   C14 −20 pts  Penalización por recencia (−20/−10/−5)
        #   C15   8 pts  Top 5 líneas en fin de semana   (solo sáb/dom)
        #   C16   7 pts  Top 5 terminales en fin de semana (solo sáb/dom)
        #                +3 pts bonus si coinciden C15 y C16
        #   C17   5 pts  Presión fríos: solo bottom-30, escalado por cold_pressure
        # POR TURNO:
        #   C10  12 pts  Top 5 grupos más atrasados del turno
        #   C11  10 pts  Top 5 pintas más atrasadas del turno
        #   C12   9 pts  Salidor del mes × atraso del turno

        month_field = MONTH_FIELD_MAP[month]
        dow_field = {
            0: 'total_domingo', 1: 'total_lunes', 2: 'total_martes',
            3: 'total_miercoles', 4: 'total_jueves', 5: 'total_viernes', 6: 'total_sabado'
        }[pg_dow]
        week_field = (
            'total_semana_1' if day <= 7 else
            'total_semana_2' if day <= 14 else
            'total_semana_3' if day <= 21 else
            'total_semana_4' if day <= 28 else
            'total_semana_5'
        )
        turn_atraso_field = 'total_atrasadas_dia' if turn_day == 'afternoon' else 'total_atrasadas_noche'
        turn_mv_field = 'afternoon' if turn_day == 'afternoon' else 'evening'

        # ── 1. Todos los números con sus stats ──────────────────────────────
        self.env.cr.execute(f"""
            SELECT ln.id,
                   LPAD(ln.name::text, 2, '0') AS name,
                   ln.name::int                AS num_int,
                   lns.{month_field}            AS salidas_mes,
                   lns.{dow_field}              AS salidas_dow,
                   lns.{week_field}             AS salidas_semana,
                   lns.{turn_atraso_field}      AS atraso_turno
            FROM lottery_number_stat lns
            JOIN lottery_number ln ON ln.id = lns.number_id
            WHERE lns.sorteo_id = %(sorteo_id)s
        """, {'sorteo_id': sorteo_id})
        numbers = {r['id']: r for r in self.env.cr.dictfetchall()}

        def _fetch_group_ids(extra_and=''):
            """Devuelve (general_ids, turn_ids) para grupos o pintas."""
            self.env.cr.execute(f"""
                SELECT group_code,
                       MIN(general)           AS atraso_gen,
                       MIN({turn_mv_field})   AS atraso_turn
                FROM lottery_number_groups_atrasos_mv
                WHERE sorteo_id = %(sorteo_id)s {extra_and}
                GROUP BY group_code
            """, {'sorteo_id': sorteo_id})
            rows = self.env.cr.dictfetchall()
            rows_gen  = sorted(rows, key=lambda r: r['atraso_gen']  or 0, reverse=True)[:5]
            rows_turn = sorted(rows, key=lambda r: r['atraso_turn'] or 0, reverse=True)[:5]
            top_gen  = [r['group_code'] for r in rows_gen]
            top_turn = [r['group_code'] for r in rows_turn]

            def _number_ids(codes):
                if not codes:
                    return set()
                self.env.cr.execute("""
                    SELECT DISTINCT rel.number_id
                    FROM lottery_group lg
                    JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
                    WHERE lg.code = ANY(%s)
                """, (codes,))
                return {r['number_id'] for r in self.env.cr.dictfetchall()}

            return _number_ids(top_gen), _number_ids(top_turn)

        # ── 2. Grupos atrasados (general + turno por separado) ───────────────
        gen_group_ids, turn_group_ids = _fetch_group_ids()

        # ── 3. Pintas atrasadas (general + turno por separado) ───────────────
        gen_pinta_ids, turn_pinta_ids = _fetch_group_ids("AND group_code LIKE 'pinta_%%'")

        # ── Rankings en Python ───────────────────────────────────────────────
        N = max(len(numbers), 1)
        sorted_mes    = sorted(numbers.values(), key=lambda x: x['salidas_mes']    or 0, reverse=True)
        sorted_dow    = sorted(numbers.values(), key=lambda x: x['salidas_dow']    or 0, reverse=True)
        sorted_semana = sorted(numbers.values(), key=lambda x: x['salidas_semana'] or 0, reverse=True)
        sorted_c6     = sorted(numbers.values(),
                               key=lambda x: (x['salidas_mes'] or 0) * (x['atraso_turno'] or 0),
                               reverse=True)

        rank_mes    = {r['id']: i + 1 for i, r in enumerate(sorted_mes)}
        rank_dow    = {r['id']: i + 1 for i, r in enumerate(sorted_dow)}
        rank_semana = {r['id']: i + 1 for i, r in enumerate(sorted_semana)}
        rank_c6     = {r['id']: i + 1 for i, r in enumerate(sorted_c6)}

        # ── C13. Dígitos últimos 3 sorteos + vecinos ±1  (antes C7) ────────
        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 3
        """, (sorteo_id,))
        digit_set = set()
        for draw in self.env.cr.dictfetchall():
            for delta in (-1, 0, 1):
                nv = draw['num_val'] + delta
                if 0 <= nv <= 99:
                    digit_set.add(nv // 10)
                    digit_set.add(nv % 10)

        # ── C14. Penalización por recencia: exacto o ±1 en últimos 5 sorteos ─
        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 5
        """, (sorteo_id,))
        recent_rows = self.env.cr.dictfetchall()
        most_recent_num = recent_rows[0]['num_val'] if recent_rows else None
        recent_nums = {r['num_val'] for r in recent_rows}
        adjacent_nums = {
            adj for n in recent_nums
            for adj in (n - 1, n + 1)
            if 0 <= adj <= 99 and adj not in recent_nums
        }

        # ── C2 + C4. Líneas (decenas) consecutivas y pendientes ─────────────
        # C2: top 5 líneas que más aparecen en el sorteo siguiente a la última línea sorteada
        # C4: de esas top 5, cuántas veces NO se cumplieron en los últimos 4 ciclos (pendientes)
        self.env.cr.execute("""
            WITH ordered AS (
                SELECT
                    (ln.name::int / 10)                          AS linea,
                    ROW_NUMBER() OVER (ORDER BY lo.date, lo.id)  AS rn
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE lo.sorteo_id = %s
            ),
            last_linea AS (
                SELECT linea FROM ordered ORDER BY rn DESC LIMIT 1
            ),
            top_consec AS (
                SELECT nxt.linea AS next_linea, COUNT(*) AS freq
                FROM ordered cur
                JOIN ordered nxt ON nxt.rn = cur.rn + 1
                WHERE cur.linea = (SELECT linea FROM last_linea)
                GROUP BY nxt.linea
                ORDER BY freq DESC
                LIMIT 5
            ),
            last_4_occ AS (
                SELECT rn FROM ordered
                WHERE linea = (SELECT linea FROM last_linea)
                ORDER BY rn DESC
                OFFSET 1 LIMIT 4
            ),
            fulfilled AS (
                SELECT o.linea AS fulfilled_linea, COUNT(*) AS cnt
                FROM ordered o
                JOIN last_4_occ l4 ON o.rn = l4.rn + 1
                WHERE o.linea IN (SELECT next_linea FROM top_consec)
                GROUP BY o.linea
            )
            SELECT
                t.next_linea,
                t.freq,
                (SELECT linea FROM last_linea)   AS last_linea_val,
                COALESCE(f.cnt, 0)               AS count_fulfilled
            FROM top_consec t
            LEFT JOIN fulfilled f ON f.fulfilled_linea = t.next_linea
        """, (sorteo_id,))
        linea_rows = self.env.cr.dictfetchall()
        last_linea_val  = linea_rows[0]['last_linea_val'] if linea_rows else None
        top_lineas      = {r['next_linea']: r for r in linea_rows}
        # fulfilled_lineas: cuántas veces (de 4) ya se cumplió → más cumplida = menos pendiente

        # ── C3 + C5. Terminales (unidades) consecutivos y pendientes ────────
        self.env.cr.execute("""
            WITH ordered AS (
                SELECT
                    (ln.name::int %% 10)                          AS terminal,
                    ROW_NUMBER() OVER (ORDER BY lo.date, lo.id)  AS rn
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE lo.sorteo_id = %s
            ),
            last_terminal AS (
                SELECT terminal FROM ordered ORDER BY rn DESC LIMIT 1
            ),
            top_consec AS (
                SELECT nxt.terminal AS next_terminal, COUNT(*) AS freq
                FROM ordered cur
                JOIN ordered nxt ON nxt.rn = cur.rn + 1
                WHERE cur.terminal = (SELECT terminal FROM last_terminal)
                GROUP BY nxt.terminal
                ORDER BY freq DESC
                LIMIT 5
            ),
            last_4_occ AS (
                SELECT rn FROM ordered
                WHERE terminal = (SELECT terminal FROM last_terminal)
                ORDER BY rn DESC
                OFFSET 1 LIMIT 4
            ),
            fulfilled AS (
                SELECT o.terminal AS fulfilled_terminal, COUNT(*) AS cnt
                FROM ordered o
                JOIN last_4_occ l4 ON o.rn = l4.rn + 1
                WHERE o.terminal IN (SELECT next_terminal FROM top_consec)
                GROUP BY o.terminal
            )
            SELECT
                t.next_terminal,
                t.freq,
                (SELECT terminal FROM last_terminal) AS last_terminal_val,
                COALESCE(f.cnt, 0)                   AS count_fulfilled
            FROM top_consec t
            LEFT JOIN fulfilled f ON f.fulfilled_terminal = t.next_terminal
        """, (sorteo_id,))
        terminal_rows     = self.env.cr.dictfetchall()
        last_terminal_val = terminal_rows[0]['last_terminal_val'] if terminal_rows else None
        top_terminals     = {r['next_terminal']: r for r in terminal_rows}

        # ── Variables auxiliares ─────────────────────────────────────────────
        week_seg_num = (1 if day <= 7 else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)
        is_weekend = pg_dow in (0, 6)   # 0=domingo, 6=sábado

        # ── C9 delay. Atraso de cada número en el día de semana actual ───────
        # Cuántas veces ha ocurrido este weekday desde la última aparición del número
        self.env.cr.execute("""
            WITH dow_draws AS (
                SELECT
                    lo.number_id,
                    ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS dow_rn
                FROM lottery_output lo
                WHERE EXTRACT(DOW FROM lo.date) = %s AND lo.sorteo_id = %s
            ),
            max_rn    AS (SELECT COALESCE(MAX(dow_rn), 1) AS val FROM dow_draws),
            last_app  AS (SELECT number_id, MAX(dow_rn) AS last_rn FROM dow_draws GROUP BY number_id)
            SELECT
                ln.id                                              AS number_id,
                (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_dow
            FROM lottery_number ln
            LEFT JOIN last_app l ON l.number_id = ln.id
        """, (pg_dow, sorteo_id))
        atraso_dow_num    = {r['number_id']: r['atraso_dow'] for r in self.env.cr.dictfetchall()}
        max_atraso_dow    = max(atraso_dow_num.values(), default=1) or 1

        # ── C8 delay. Atraso de cada número en la semana del mes actual ──────
        self.env.cr.execute("""
            WITH seg_draws AS (
                SELECT
                    lo.number_id,
                    ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS seg_rn
                FROM lottery_output lo
                WHERE (CASE
                           WHEN EXTRACT(DAY FROM lo.date) <= 7  THEN 1
                           WHEN EXTRACT(DAY FROM lo.date) <= 14 THEN 2
                           WHEN EXTRACT(DAY FROM lo.date) <= 21 THEN 3
                           WHEN EXTRACT(DAY FROM lo.date) <= 28 THEN 4
                           ELSE 5 END) = %s
                  AND lo.sorteo_id = %s
            ),
            max_rn    AS (SELECT COALESCE(MAX(seg_rn), 1) AS val FROM seg_draws),
            last_app  AS (SELECT number_id, MAX(seg_rn) AS last_rn FROM seg_draws GROUP BY number_id)
            SELECT
                ln.id                                              AS number_id,
                (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_semana
            FROM lottery_number ln
            LEFT JOIN last_app l ON l.number_id = ln.id
        """, (week_seg_num, sorteo_id))
        atraso_semana_num = {r['number_id']: r['atraso_semana'] for r in self.env.cr.dictfetchall()}
        max_atraso_semana = max(atraso_semana_num.values(), default=1) or 1

        # ── C15 + C16. Líneas y terminales de fin de semana (solo sáb/dom) ───
        # Top 5 líneas/terminales por frecuencia en fines de semana + su atraso
        weekend_top_lineas    = {}
        weekend_top_terminals = {}
        max_wd_linea_delay    = 1
        max_wd_terminal_delay = 1

        if is_weekend:
            # Líneas de fin de semana
            self.env.cr.execute("""
                WITH wd AS (
                    SELECT
                        (ln.name::int / 10)                         AS linea,
                        ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE EXTRACT(DOW FROM lo.date) IN (0, 6) AND lo.sorteo_id = %s
                ),
                freq      AS (SELECT linea, COUNT(*) AS freq,
                                     ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS freq_rank
                              FROM wd GROUP BY linea),
                top5      AS (SELECT * FROM freq WHERE freq_rank <= 5),
                max_rn    AS (SELECT COALESCE(MAX(rn), 1) AS val FROM wd),
                last_app  AS (SELECT linea, MAX(rn) AS last_rn FROM wd GROUP BY linea)
                SELECT t.linea, t.freq, t.freq_rank,
                       (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_weekend
                FROM top5 t LEFT JOIN last_app l ON l.linea = t.linea
            """, (sorteo_id,))
            weekend_top_lineas    = {r['linea']: r for r in self.env.cr.dictfetchall()}
            max_wd_linea_delay    = max((v['atraso_weekend'] for v in weekend_top_lineas.values()), default=1) or 1

            # Terminales de fin de semana
            self.env.cr.execute("""
                WITH wd AS (
                    SELECT
                        (ln.name::int %% 10)                         AS terminal,
                        ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE EXTRACT(DOW FROM lo.date) IN (0, 6) AND lo.sorteo_id = %s
                ),
                freq      AS (SELECT terminal, COUNT(*) AS freq,
                                     ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS freq_rank
                              FROM wd GROUP BY terminal),
                top5      AS (SELECT * FROM freq WHERE freq_rank <= 5),
                max_rn    AS (SELECT COALESCE(MAX(rn), 1) AS val FROM wd),
                last_app  AS (SELECT terminal, MAX(rn) AS last_rn FROM wd GROUP BY terminal)
                SELECT t.terminal, t.freq, t.freq_rank,
                       (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_weekend
                FROM top5 t LEFT JOIN last_app l ON l.terminal = t.terminal
            """, (sorteo_id,))
            weekend_top_terminals = {r['terminal']: r for r in self.env.cr.dictfetchall()}
            max_wd_terminal_delay = max((v['atraso_weekend'] for v in weekend_top_terminals.values()), default=1) or 1

        # ── C17: Presión de números fríos ────────────────────────────────────
        # Si los últimos 6 sorteos salieron mayoritariamente del top-70,
        # hay presión estadística para que el siguiente venga del bottom-30.
        # cold_pressure = 1.0 → todos los recientes eran top-70
        # cold_pressure = 0.0 → ninguno era top-70
        top70_ids = {nid for nid, rk in rank_mes.items() if rk <= 70}
        self.env.cr.execute("""
            SELECT lo.number_id
            FROM lottery_output lo
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 6
        """, (sorteo_id,))
        recent_6_ids = [r['number_id'] for r in self.env.cr.dictfetchall()]
        hot_in_recent = sum(1 for nid in recent_6_ids if nid in top70_ids)
        cold_pressure = hot_in_recent / max(len(recent_6_ids), 1)

        # ── Ponderación ──────────────────────────────────────────────────────
        scores = []
        for num_id, n in numbers.items():
            rm  = rank_mes[num_id]
            rd  = rank_dow[num_id]
            rs  = rank_semana[num_id]
            rc6 = rank_c6[num_id]
            ni  = n['num_int']

            ni_linea    = ni // 10   # decena (0-9)
            ni_terminal = ni % 10   # unidad  (0-9)

            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            # TABLA DE PESOS  (todos los criterios en rango 7–15 pts, ratio ≤ 2×)
            # ─────────────────────────────────────────────────────────────────
            #  C1  15 pts  Top 70 salidores del mes                (continuo)
            #  C2  13 pts  Líneas consecutivas                     (continuo)
            #  C3  11 pts  Terminales consecutivos                 (continuo)
            #              +4 pts bonus si coinciden C2 y C3
            #  C4  10 pts  Líneas pendientes                       (continuo)
            #  C5   9 pts  Terminales pendientes                   (continuo)
            #  C6  10 pts  Grupos demorados — GENERAL              (binario)
            #  C7   9 pts  Pintas demoradas — GENERAL              (binario)
            #  C8   8 pts  Semana del mes (freq 40 % + atraso 60 %)(continuo)
            #  C9   7 pts  Día de la semana (freq 40 % + atr. 60 %)(continuo)
            #  C10 12 pts  Grupos demorados — TURNO                (binario)
            #  C11 10 pts  Pintas demoradas — TURNO                (binario)
            #  C12  9 pts  Salidor mes × atraso turno              (continuo)
            #  C13 10 pts  Dígitos últimos 3 sorteos ±1            (semibinario)
            #  C14 -20 pts Penalización recencia (-20/-10/-5/0)    (escalonado)
            #  C15  8 pts  Líneas fin de semana (solo sáb/dom)     (continuo)
            #  C16  7 pts  Terminales fin de semana (solo sáb/dom) (continuo)
            #              +3 pts bonus si coinciden C15 y C16
            # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

            # ── C1: Top 70 salidores del mes ─────────────────────────────────
            s1 = 15.0 * (1 - (rm - 1) / 70) if rm <= 70 else 0

            # ── C2: Líneas consecutivas ───────────────────────────────────────
            # Decaimiento lineal: rank 1 → 13 pts, rank 5 → 2.6 pts
            if ni_linea in top_lineas:
                linea_rank = list(top_lineas.keys()).index(ni_linea) + 1
                s2 = 13.0 * (1 - (linea_rank - 1) / 5)
            else:
                s2 = 0.0

            # ── C3: Terminales consecutivos + bonus coincidencia ─────────────
            # +4 pts si también cumple C2 (línea Y terminal coinciden → doble señal).
            # El bonus es moderado: aporta indicación extra sin dominar el score.
            if ni_terminal in top_terminals:
                term_rank = list(top_terminals.keys()).index(ni_terminal) + 1
                s3 = 11.0 * (1 - (term_rank - 1) / 5)
                if s2 > 0:
                    s3 += 4.0   # coincidencia línea + terminal
            else:
                s3 = 0.0

            # ── C4: Líneas pendientes (no cumplidas en últimos 4 ciclos) ─────
            # pending_ratio = 1.0 → nunca cumplido | 0.0 → siempre cumplido
            if ni_linea in top_lineas:
                fulfilled_linea = top_lineas[ni_linea]['count_fulfilled']
                pending_ratio   = (4 - min(fulfilled_linea, 4)) / 4
                s4_new = 10.0 * pending_ratio
            else:
                s4_new = 0.0

            # ── C5: Terminales pendientes (no cumplidos en últimos 4 ciclos) ─
            if ni_terminal in top_terminals:
                fulfilled_term = top_terminals[ni_terminal]['count_fulfilled']
                pending_ratio  = (4 - min(fulfilled_term, 4)) / 4
                s5_new = 9.0 * pending_ratio
            else:
                s5_new = 0.0

            # ── C6: Grupos demorados — GENERAL ───────────────────────────────
            s6 = 10.0 if num_id in gen_group_ids else 0

            # ── C7: Pintas demoradas — GENERAL ───────────────────────────────
            s7 = 9.0 if num_id in gen_pinta_ids else 0

            # ── C8: Semana del mes — frecuencia + atraso combinados ──────────
            # 40 % frecuencia relativa en la semana del mes actual,
            # 60 % atraso normalizado desde la última aparición en esa semana.
            freq_factor_semana  = 1 - (rs - 1) / N
            delay_factor_semana = atraso_semana_num.get(num_id, 0) / max_atraso_semana
            s8 = 8.0 * (0.4 * freq_factor_semana + 0.6 * delay_factor_semana)

            # ── C9: Día de la semana — frecuencia + atraso combinados ────────
            # Mismo esquema 40/60 que C8 pero para el día de la semana (pg_dow).
            freq_factor_dow  = 1 - (rd - 1) / N
            delay_factor_dow = atraso_dow_num.get(num_id, 0) / max_atraso_dow
            s9 = 7.0 * (0.4 * freq_factor_dow + 0.6 * delay_factor_dow)

            # ── C10: Grupos demorados — TURNO ────────────────────────────────
            s10 = 12.0 if num_id in turn_group_ids else 0

            # ── C11: Pintas demoradas — TURNO ────────────────────────────────
            s11 = 10.0 if num_id in turn_pinta_ids else 0

            # ── C12: Salidor mes × atraso turno ──────────────────────────────
            s12 = 9.0 * (1 - (rc6 - 1) / N)

            # ── C13: Dígitos de últimos 3 sorteos ±1 ─────────────────────────
            # 0 pts si salió exacto recientemente, hasta 10 si ambos dígitos coinciden.
            if ni not in recent_nums:
                s13 = 10.0 * (
                    (1 if ni_linea    in digit_set else 0) +
                    (1 if ni_terminal in digit_set else 0)
                ) / 2
            else:
                s13 = 0.0

            # ── C14: Penalización por recencia ───────────────────────────────
            # Escalonado: −20 si salió exacto, −10 si salió reciente, −5 si adyacente.
            # Se moderó respecto al valor anterior (−30/−12/−6) para no distorsionar
            # el ranking cuando varios criterios positivos empujan el mismo número.
            if ni == most_recent_num:
                s14 = -20.0
            elif ni in recent_nums:
                s14 = -10.0
            elif ni in adjacent_nums:
                s14 = -5.0
            else:
                s14 = 0.0

            # ── C15: Líneas de fin de semana (solo sáb/dom) ───────────────────
            # 40 % frecuencia + 60 % atraso entre las 5 líneas más salidas en fin de semana.
            if is_weekend and ni_linea in weekend_top_lineas:
                wd_l       = weekend_top_lineas[ni_linea]
                freq_wd_l  = 1 - (wd_l['freq_rank'] - 1) / 5
                delay_wd_l = wd_l['atraso_weekend'] / max_wd_linea_delay
                s15 = 8.0 * (0.4 * freq_wd_l + 0.6 * delay_wd_l)
            else:
                s15 = 0.0

            # ── C16: Terminales de fin de semana (solo sáb/dom) + coincidencia ─
            # +3 pts bonus si coincide con C15 (moderado, no domina el score).
            if is_weekend and ni_terminal in weekend_top_terminals:
                wd_t       = weekend_top_terminals[ni_terminal]
                freq_wd_t  = 1 - (wd_t['freq_rank'] - 1) / 5
                delay_wd_t = wd_t['atraso_weekend'] / max_wd_terminal_delay
                s16 = 7.0 * (0.4 * freq_wd_t + 0.6 * delay_wd_t)
                if s15 > 0:
                    s16 += 3.0  # coincidencia línea + terminal de fin de semana
            else:
                s16 = 0.0

            # ── C17: Presión de números fríos ────────────────────────────────
            # Solo aplica al bottom-30 (rm > 70): los menos salidores del mes.
            # El bonus sube a medida que los últimos 6 sorteos fueron del top-70,
            # reflejando la presión para que el próximo salga de ese grupo olvidado.
            # Máx 5 pts (deliberadamente menor que el resto para no elevar en exceso
            # a números que ya tienen poca señal en los demás criterios).
            if rm > 70:
                s17 = 5.0 * cold_pressure
            else:
                s17 = 0.0

            scores.append({
                'name': n['name'],
                'score': round(
                    s1 + s2 + s3 + s4_new + s5_new
                    + s6 + s7 + s8 + s9
                    + s10 + s11 + s12
                    + s13 + s14
                    + s15 + s16
                    + s17,
                    1
                ),
            })

        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores

    # ─── Números Fríos ───────────────────────────────────────────────────────

    @api.model
    @tools.ormcache('turn_day', 'today_str', 'sorteo_id')
    def get_numeros_frios(self, turn_day, today_str, sorteo_id=False):
        """
        Espejo invertido de get_numeros_calientes.
        Parte de los 50 menos salidores del mes y aplica cada criterio al revés:
        - menos salidor reemplaza a más salidor
        - grupos/pintas MÁS recientes (menos demorados) en lugar de más demorados
        - recencia se convierte en BONUS en lugar de penalización
        - líneas/terminales que MENOS siguen en lugar de las que más siguen
        - fin de semana: líneas/terminales que MENOS aparecen

        Todos los pesos son iguales a los de calientes para mantener la simetría.

        GENERALES:
          C1f  15 pts  Bottom 50 menos salidores del mes
          C2f  13 pts  Top 5 líneas que MENOS siguen a la última sorteada
          C3f  11 pts  Top 5 terminales que MENOS siguen al último sorteado
                       +4 pts bonus si coinciden C2f y C3f
          C4f  10 pts  Líneas consistentemente NO cumplidas en últimos 4 ciclos
          C5f   9 pts  Terminales consistentemente NO cumplidas
          C6f  10 pts  Top 5 grupos MENOS atrasados (más recientes) — GENERAL
          C7f   9 pts  Top 3 pintas MENOS atrasadas (más recientes) — GENERAL
          C8f   8 pts  Semana del mes: 40 % menos frecuente + 60 % más reciente
          C9f   7 pts  Día de semana:  40 % menos frecuente + 60 % más reciente
          C13f 10 pts  Dígitos presentes en últimos 3 sorteos (apareció = frío)
          C14f 20 pts  Bonus por recencia (+20 exacto / +10 en últimos 5 sorteos)
          C15f  8 pts  Top 5 líneas que MENOS salen en fin de semana (solo sáb/dom)
          C16f  7 pts  Top 5 terminales que MENOS salen en fin de semana (solo sáb/dom)
                       +3 pts bonus si coinciden C15f y C16f
          C17f  5 pts  Presión calientes: números del top-50 que salieron reciente
        POR TURNO:
          C10f 12 pts  Top 5 grupos MENOS atrasados — TURNO
          C11f 10 pts  Top 3 pintas MENOS atrasadas — TURNO
          C12f  9 pts  Menos salidor mes × menos demorado turno
        """
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        month    = today.month
        pg_dow   = (today.weekday() + 1) % 7
        day      = today.day
        is_weekend   = pg_dow in (0, 6)
        week_seg_num = (1 if day <= 7  else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)

        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'

        month_field = MONTH_FIELD_MAP[month]
        dow_field = {
            0: 'total_domingo', 1: 'total_lunes',   2: 'total_martes',
            3: 'total_miercoles', 4: 'total_jueves', 5: 'total_viernes',
            6: 'total_sabado',
        }[pg_dow]
        week_field = (
            'total_semana_1' if day <= 7  else
            'total_semana_2' if day <= 14 else
            'total_semana_3' if day <= 21 else
            'total_semana_4' if day <= 28 else
            'total_semana_5'
        )
        turn_atraso_field = 'total_atrasadas_dia' if turn_day == 'afternoon' else 'total_atrasadas_noche'
        turn_mv_field     = 'afternoon'           if turn_day == 'afternoon' else 'evening'

        # ── 1. Todos los números ─────────────────────────────────────────────
        self.env.cr.execute(f"""
            SELECT ln.id,
                   LPAD(ln.name::text, 2, '0') AS name,
                   ln.name::int                AS num_int,
                   lns.{month_field}            AS salidas_mes,
                   lns.{dow_field}              AS salidas_dow,
                   lns.{week_field}             AS salidas_semana,
                   lns.{turn_atraso_field}      AS atraso_turno
            FROM lottery_number_stat lns
            JOIN lottery_number ln ON ln.id = lns.number_id
            WHERE lns.sorteo_id = %(sorteo_id)s
        """, {'sorteo_id': sorteo_id})
        numbers = {r['id']: r for r in self.env.cr.dictfetchall()}
        N = max(len(numbers), 1)

        # ── Rankings INVERTIDOS (menos salidor = rank 1) ─────────────────────
        sorted_mes_inv    = sorted(numbers.values(), key=lambda x: x['salidas_mes']    or 0)
        sorted_dow_inv    = sorted(numbers.values(), key=lambda x: x['salidas_dow']    or 0)
        sorted_semana_inv = sorted(numbers.values(), key=lambda x: x['salidas_semana'] or 0)
        # C12f: menos salidor × menos demorado turno → producto ASC
        sorted_c12f = sorted(numbers.values(),
                             key=lambda x: (x['salidas_mes'] or 0) * (x['atraso_turno'] or 0))

        rank_mes_inv    = {r['id']: i + 1 for i, r in enumerate(sorted_mes_inv)}
        rank_dow_inv    = {r['id']: i + 1 for i, r in enumerate(sorted_dow_inv)}
        rank_semana_inv = {r['id']: i + 1 for i, r in enumerate(sorted_semana_inv)}
        rank_c12f       = {r['id']: i + 1 for i, r in enumerate(sorted_c12f)}

        # ── C6f/C7f. Grupos y pintas MENOS atrasados (más recientes) ─────────
        def _fetch_recent_group_ids(extra_and='', limit_gen=5, limit_turn=5):
            self.env.cr.execute(f"""
                SELECT group_code,
                       MIN(general)         AS atraso_gen,
                       MIN({turn_mv_field}) AS atraso_turn
                FROM lottery_number_groups_atrasos_mv
                WHERE sorteo_id = %(sorteo_id)s {extra_and}
                GROUP BY group_code
            """, {'sorteo_id': sorteo_id})
            rows = self.env.cr.dictfetchall()
            # ASC = menos demorado (más reciente)
            rows_gen  = sorted(rows, key=lambda r: r['atraso_gen']  or 0)[:limit_gen]
            rows_turn = sorted(rows, key=lambda r: r['atraso_turn'] or 0)[:limit_turn]

            def _number_ids(codes):
                if not codes:
                    return set()
                self.env.cr.execute("""
                    SELECT DISTINCT rel.number_id
                    FROM lottery_group lg
                    JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
                    WHERE lg.code = ANY(%s)
                """, ([r['group_code'] for r in codes],))
                return {r['number_id'] for r in self.env.cr.dictfetchall()}

            return _number_ids(rows_gen), _number_ids(rows_turn)

        gen_group_ids_f, turn_group_ids_f = _fetch_recent_group_ids(limit_gen=5, limit_turn=5)
        gen_pinta_ids_f, turn_pinta_ids_f = _fetch_recent_group_ids(
            "AND group_code LIKE 'pinta_%%'", limit_gen=3, limit_turn=3)

        # ── C13f/C14f. Recencia ──────────────────────────────────────────────
        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 3
        """, (sorteo_id,))
        digit_set = set()
        for draw in self.env.cr.dictfetchall():
            for delta in (-1, 0, 1):
                nv = draw['num_val'] + delta
                if 0 <= nv <= 99:
                    digit_set.add(nv // 10)
                    digit_set.add(nv % 10)

        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 5
        """, (sorteo_id,))
        recent_rows     = self.env.cr.dictfetchall()
        most_recent_num = recent_rows[0]['num_val'] if recent_rows else None
        recent_nums     = {r['num_val'] for r in recent_rows}

        # ── C2f + C4f. Líneas que MENOS siguen a la última (bottom-5) ────────
        # Se incluyen todas las líneas (0-9) con LEFT JOIN para capturar las que
        # nunca siguieron (freq = 0). Se ordena ASC para elegir las más frías.
        self.env.cr.execute("""
            WITH ordered AS (
                SELECT (ln.name::int / 10)                         AS linea,
                       ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE lo.sorteo_id = %s
            ),
            last_linea    AS (SELECT linea FROM ordered ORDER BY rn DESC LIMIT 1),
            all_lineas    AS (SELECT generate_series(0, 9) AS linea),
            consec_freq   AS (
                SELECT nxt.linea AS next_linea, COUNT(*) AS freq
                FROM ordered cur
                JOIN ordered nxt ON nxt.rn = cur.rn + 1
                WHERE cur.linea = (SELECT linea FROM last_linea)
                GROUP BY nxt.linea
            ),
            bottom_consec AS (
                SELECT al.linea AS next_linea, COALESCE(cf.freq, 0) AS freq
                FROM all_lineas al
                LEFT JOIN consec_freq cf ON cf.next_linea = al.linea
                ORDER BY freq ASC
                LIMIT 5
            ),
            last_4_occ AS (
                SELECT rn FROM ordered
                WHERE linea = (SELECT linea FROM last_linea)
                ORDER BY rn DESC OFFSET 1 LIMIT 4
            ),
            fulfilled AS (
                SELECT o.linea AS fulfilled_linea, COUNT(*) AS cnt
                FROM ordered o
                JOIN last_4_occ l4 ON o.rn = l4.rn + 1
                WHERE o.linea IN (SELECT next_linea FROM bottom_consec)
                GROUP BY o.linea
            )
            SELECT t.next_linea,
                   t.freq,
                   (SELECT linea FROM last_linea) AS last_linea_val,
                   COALESCE(f.cnt, 0)             AS count_fulfilled
            FROM bottom_consec t
            LEFT JOIN fulfilled f ON f.fulfilled_linea = t.next_linea
        """, (sorteo_id,))
        cold_lineas = {r['next_linea']: r for r in self.env.cr.dictfetchall()}

        # ── C3f + C5f. Terminales que MENOS siguen a la última (bottom-5) ─────
        self.env.cr.execute("""
            WITH ordered AS (
                SELECT (ln.name::int %% 10)                         AS terminal,
                       ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE lo.sorteo_id = %s
            ),
            last_terminal AS (SELECT terminal FROM ordered ORDER BY rn DESC LIMIT 1),
            all_terminals AS (SELECT generate_series(0, 9) AS terminal),
            consec_freq   AS (
                SELECT nxt.terminal AS next_terminal, COUNT(*) AS freq
                FROM ordered cur
                JOIN ordered nxt ON nxt.rn = cur.rn + 1
                WHERE cur.terminal = (SELECT terminal FROM last_terminal)
                GROUP BY nxt.terminal
            ),
            bottom_consec AS (
                SELECT at.terminal AS next_terminal, COALESCE(cf.freq, 0) AS freq
                FROM all_terminals at
                LEFT JOIN consec_freq cf ON cf.next_terminal = at.terminal
                ORDER BY freq ASC
                LIMIT 5
            ),
            last_4_occ AS (
                SELECT rn FROM ordered
                WHERE terminal = (SELECT terminal FROM last_terminal)
                ORDER BY rn DESC OFFSET 1 LIMIT 4
            ),
            fulfilled AS (
                SELECT o.terminal AS fulfilled_terminal, COUNT(*) AS cnt
                FROM ordered o
                JOIN last_4_occ l4 ON o.rn = l4.rn + 1
                WHERE o.terminal IN (SELECT next_terminal FROM bottom_consec)
                GROUP BY o.terminal
            )
            SELECT t.next_terminal,
                   t.freq,
                   (SELECT terminal FROM last_terminal) AS last_terminal_val,
                   COALESCE(f.cnt, 0)                   AS count_fulfilled
            FROM bottom_consec t
            LEFT JOIN fulfilled f ON f.fulfilled_terminal = t.next_terminal
        """, (sorteo_id,))
        cold_terminals = {r['next_terminal']: r for r in self.env.cr.dictfetchall()}

        # ── C9f delay. Aparición RECIENTE en día de semana actual ─────────────
        self.env.cr.execute("""
            WITH dow_draws AS (
                SELECT lo.number_id,
                       ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS dow_rn
                FROM lottery_output lo
                WHERE EXTRACT(DOW FROM lo.date) = %s AND lo.sorteo_id = %s
            ),
            max_rn   AS (SELECT COALESCE(MAX(dow_rn), 1) AS val FROM dow_draws),
            last_app AS (SELECT number_id, MAX(dow_rn) AS last_rn FROM dow_draws GROUP BY number_id)
            SELECT ln.id                                               AS number_id,
                   (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0)  AS atraso_dow
            FROM lottery_number ln
            LEFT JOIN last_app l ON l.number_id = ln.id
        """, (pg_dow, sorteo_id))
        atraso_dow_num_f = {r['number_id']: r['atraso_dow'] for r in self.env.cr.dictfetchall()}
        max_atraso_dow_f = max(atraso_dow_num_f.values(), default=1) or 1

        # ── C8f delay. Aparición RECIENTE en semana del mes actual ────────────
        self.env.cr.execute("""
            WITH seg_draws AS (
                SELECT lo.number_id,
                       ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS seg_rn
                FROM lottery_output lo
                WHERE (CASE
                           WHEN EXTRACT(DAY FROM lo.date) <= 7  THEN 1
                           WHEN EXTRACT(DAY FROM lo.date) <= 14 THEN 2
                           WHEN EXTRACT(DAY FROM lo.date) <= 21 THEN 3
                           WHEN EXTRACT(DAY FROM lo.date) <= 28 THEN 4
                           ELSE 5 END) = %s
                  AND lo.sorteo_id = %s
            ),
            max_rn   AS (SELECT COALESCE(MAX(seg_rn), 1) AS val FROM seg_draws),
            last_app AS (SELECT number_id, MAX(seg_rn) AS last_rn FROM seg_draws GROUP BY number_id)
            SELECT ln.id                                               AS number_id,
                   (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0)  AS atraso_semana
            FROM lottery_number ln
            LEFT JOIN last_app l ON l.number_id = ln.id
        """, (week_seg_num, sorteo_id))
        atraso_semana_num_f = {r['number_id']: r['atraso_semana'] for r in self.env.cr.dictfetchall()}
        max_atraso_semana_f = max(atraso_semana_num_f.values(), default=1) or 1

        # ── C15f/C16f. Fin de semana: líneas/terminales que MENOS aparecen ────
        cold_wd_lineas    = {}
        cold_wd_terminals = {}
        max_wd_linea_delay_f    = 1
        max_wd_terminal_delay_f = 1

        if is_weekend:
            # Líneas con MENOR frecuencia en fines de semana (ASC + LEFT JOIN con all)
            self.env.cr.execute("""
                WITH wd AS (
                    SELECT (ln.name::int / 10)                         AS linea,
                           ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE EXTRACT(DOW FROM lo.date) IN (0, 6) AND lo.sorteo_id = %s
                ),
                all_lineas AS (SELECT generate_series(0, 9) AS linea),
                freq   AS (SELECT linea, COUNT(*) AS freq FROM wd GROUP BY linea),
                ranked AS (
                    SELECT al.linea, COALESCE(f.freq, 0) AS freq,
                           ROW_NUMBER() OVER (ORDER BY COALESCE(f.freq, 0) ASC) AS freq_rank
                    FROM all_lineas al LEFT JOIN freq f ON f.linea = al.linea
                ),
                top5    AS (SELECT * FROM ranked WHERE freq_rank <= 5),
                max_rn  AS (SELECT COALESCE(MAX(rn), 1) AS val FROM wd),
                last_app AS (SELECT linea, MAX(rn) AS last_rn FROM wd GROUP BY linea)
                SELECT t.linea, t.freq, t.freq_rank,
                       (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_weekend
                FROM top5 t LEFT JOIN last_app l ON l.linea = t.linea
            """, (sorteo_id,))
            cold_wd_lineas       = {r['linea']: r for r in self.env.cr.dictfetchall()}
            max_wd_linea_delay_f = max((v['atraso_weekend'] for v in cold_wd_lineas.values()), default=1) or 1

            # Terminales con MENOR frecuencia en fines de semana
            self.env.cr.execute("""
                WITH wd AS (
                    SELECT (ln.name::int %% 10)                          AS terminal,
                           ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE EXTRACT(DOW FROM lo.date) IN (0, 6) AND lo.sorteo_id = %s
                ),
                all_terms AS (SELECT generate_series(0, 9) AS terminal),
                freq   AS (SELECT terminal, COUNT(*) AS freq FROM wd GROUP BY terminal),
                ranked AS (
                    SELECT at.terminal, COALESCE(f.freq, 0) AS freq,
                           ROW_NUMBER() OVER (ORDER BY COALESCE(f.freq, 0) ASC) AS freq_rank
                    FROM all_terms at LEFT JOIN freq f ON f.terminal = at.terminal
                ),
                top5    AS (SELECT * FROM ranked WHERE freq_rank <= 5),
                max_rn  AS (SELECT COALESCE(MAX(rn), 1) AS val FROM wd),
                last_app AS (SELECT terminal, MAX(rn) AS last_rn FROM wd GROUP BY terminal)
                SELECT t.terminal, t.freq, t.freq_rank,
                       (SELECT val FROM max_rn) - COALESCE(l.last_rn, 0) AS atraso_weekend
                FROM top5 t LEFT JOIN last_app l ON l.terminal = t.terminal
            """, (sorteo_id,))
            cold_wd_terminals       = {r['terminal']: r for r in self.env.cr.dictfetchall()}
            max_wd_terminal_delay_f = max((v['atraso_weekend'] for v in cold_wd_terminals.values()), default=1) or 1

        # ── C17f. Presión calientes ───────────────────────────────────────────
        # Si los últimos 6 sorteos vinieron mayoritariamente del top-50 (salidores),
        # hay presión para que el siguiente venga de ese mismo grupo → cold signal
        # para los propios números del top-50 (rm_inv > 50).
        bottom50_ids = {nid for nid, rk in rank_mes_inv.items() if rk <= 50}
        self.env.cr.execute("""
            SELECT lo.number_id
            FROM lottery_output lo
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 6
        """, (sorteo_id,))
        recent_6_ids   = [r['number_id'] for r in self.env.cr.dictfetchall()]
        cold_in_recent = sum(1 for nid in recent_6_ids if nid in bottom50_ids)
        # proporción de recientes que NO eran del pool frío → presión sobre los calientes
        hot_pressure   = (len(recent_6_ids) - cold_in_recent) / max(len(recent_6_ids), 1)

        # ── Ponderación ──────────────────────────────────────────────────────
        scores = []
        for num_id, n in numbers.items():
            rm_inv  = rank_mes_inv[num_id]
            rd_inv  = rank_dow_inv[num_id]
            rs_inv  = rank_semana_inv[num_id]
            rc12f   = rank_c12f[num_id]
            ni      = n['num_int']
            ni_linea    = ni // 10
            ni_terminal = ni % 10

            # ── C1f: Bottom 50 menos salidores del mes ────────────────────────
            s1f = 15.0 * (1 - (rm_inv - 1) / 50) if rm_inv <= 50 else 0

            # ── C2f: Líneas que MENOS siguen (rank 1 = la que menos sigue) ────
            if ni_linea in cold_lineas:
                linea_rank_f = list(cold_lineas.keys()).index(ni_linea) + 1
                s2f = 13.0 * (1 - (linea_rank_f - 1) / 5)
            else:
                s2f = 0.0

            # ── C3f: Terminales que MENOS siguen + bonus coincidencia ──────────
            if ni_terminal in cold_terminals:
                term_rank_f = list(cold_terminals.keys()).index(ni_terminal) + 1
                s3f = 11.0 * (1 - (term_rank_f - 1) / 5)
                if s2f > 0:
                    s3f += 4.0   # coincidencia: línea Y terminal son fríos consecutivos
            else:
                s3f = 0.0

            # ── C4f: Líneas consistentemente NO cumplidas ──────────────────────
            # Alta puntuación si el patrón frío se mantuvo (no siguió en ciclos recientes).
            if ni_linea in cold_lineas:
                fulfilled_linea_f = cold_lineas[ni_linea]['count_fulfilled']
                s4f = 10.0 * (4 - min(fulfilled_linea_f, 4)) / 4
            else:
                s4f = 0.0

            # ── C5f: Terminales consistentemente NO cumplidas ──────────────────
            if ni_terminal in cold_terminals:
                fulfilled_term_f = cold_terminals[ni_terminal]['count_fulfilled']
                s5f = 9.0 * (4 - min(fulfilled_term_f, 4)) / 4
            else:
                s5f = 0.0

            # ── C6f: Grupos MENOS atrasados — GENERAL ─────────────────────────
            s6f = 10.0 if num_id in gen_group_ids_f else 0

            # ── C7f: Pintas MENOS atrasadas — GENERAL (top 3) ─────────────────
            s7f = 9.0 if num_id in gen_pinta_ids_f else 0

            # ── C8f: Semana del mes — menos frecuente + más reciente ───────────
            # Para fríos, el factor de recencia se invierte: low atraso = appeared recently = cold.
            freq_factor_semana_f  = 1 - (rs_inv - 1) / N
            recency_factor_semana = 1 - (atraso_semana_num_f.get(num_id, 0) / max_atraso_semana_f)
            s8f = 8.0 * (0.4 * freq_factor_semana_f + 0.6 * recency_factor_semana)

            # ── C9f: Día de semana — menos frecuente + más reciente ────────────
            freq_factor_dow_f  = 1 - (rd_inv - 1) / N
            recency_factor_dow = 1 - (atraso_dow_num_f.get(num_id, 0) / max_atraso_dow_f)
            s9f = 7.0 * (0.4 * freq_factor_dow_f + 0.6 * recency_factor_dow)

            # ── C10f: Grupos MENOS atrasados — TURNO ──────────────────────────
            s10f = 12.0 if num_id in turn_group_ids_f else 0

            # ── C11f: Pintas MENOS atrasadas — TURNO (top 3) ──────────────────
            s11f = 10.0 if num_id in turn_pinta_ids_f else 0

            # ── C12f: Menos salidor mes × menos demorado turno ────────────────
            s12f = 9.0 * (1 - (rc12f - 1) / N)

            # ── C13f: Dígitos presentes en últimos 3 sorteos ──────────────────
            # Inverso de C13 calientes: si la línea/terminal apareció recientemente,
            # es señal de que el número está "quemado" (cold candidate).
            s13f = 10.0 * (
                (1 if ni_linea    in digit_set else 0) +
                (1 if ni_terminal in digit_set else 0)
            ) / 2

            # ── C14f: Recencia como BONUS ──────────────────────────────────────
            # Un número que acaba de salir es el mejor candidato a estar frío.
            # Aplica a TODOS los números (incluidos top-50 salidores) para que
            # un número "caliente" que acaba de salir suba en el ranking de fríos.
            if ni == most_recent_num:
                s14f = 20.0
            elif ni in recent_nums:
                s14f = 10.0
            else:
                s14f = 0.0

            # ── C15f: Líneas que MENOS salen en fin de semana (solo sáb/dom) ──
            if is_weekend and ni_linea in cold_wd_lineas:
                wd_l_f    = cold_wd_lineas[ni_linea]
                freq_wdlf = 1 - (wd_l_f['freq_rank'] - 1) / 5
                rec_wdlf  = 1 - (wd_l_f['atraso_weekend'] / max_wd_linea_delay_f)
                s15f = 8.0 * (0.4 * freq_wdlf + 0.6 * rec_wdlf)
            else:
                s15f = 0.0

            # ── C16f: Terminales que MENOS salen en fin de semana + coincidencia
            if is_weekend and ni_terminal in cold_wd_terminals:
                wd_t_f    = cold_wd_terminals[ni_terminal]
                freq_wdtf = 1 - (wd_t_f['freq_rank'] - 1) / 5
                rec_wdtf  = 1 - (wd_t_f['atraso_weekend'] / max_wd_terminal_delay_f)
                s16f = 7.0 * (0.4 * freq_wdtf + 0.6 * rec_wdtf)
                if s15f > 0:
                    s16f += 3.0
            else:
                s16f = 0.0

            # ── C17f: Presión calientes ────────────────────────────────────────
            # Si los últimos 6 sorteos fueron predominantemente del top-50 salidores,
            # hay presión para que el siguiente también venga de ahí → esos números
            # top-50 reciben un pequeño puntaje frío.
            if rm_inv > 50:   # es del top-50 (caliente por frecuencia del mes)
                s17f = 5.0 * hot_pressure
            else:
                s17f = 0.0

            scores.append({
                'name': n['name'],
                'score': round(
                    s1f + s2f + s3f + s4f + s5f
                    + s6f + s7f + s8f + s9f
                    + s10f + s11f + s12f
                    + s13f + s14f
                    + s15f + s16f
                    + s17f,
                    1
                ),
            })

        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores

    def _query_ceb_stats(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False):
        """
        Consulta unificada para centenas y bola extra (0-9).
        Devuelve una lista de 10 dicts, uno por valor posible, con:
          val, atraso_gen, atraso_turn, consec_freq, month_freq, dow_freq, week_freq
        Se usa tanto para calientes (maximizar) como para frios (invertir).
        """
        field = output_id_field
        self.env.cr.execute(f"""
            WITH all_draws AS (
                SELECT
                    n.name::int                                                          AS val,
                    lo.turn_day,
                    lo.date                                                              AS draw_date,
                    ROW_NUMBER() OVER (ORDER BY lo.date, lo.id)                         AS rn_gen,
                    ROW_NUMBER() OVER (PARTITION BY lo.turn_day ORDER BY lo.date, lo.id) AS rn_turn
                FROM lottery_output lo
                JOIN lottery_number n ON n.id = lo.{field}
                WHERE lo.{field} IS NOT NULL AND lo.sorteo_id = %s
            ),
            last_val      AS (SELECT val FROM all_draws ORDER BY rn_gen DESC LIMIT 1),
            max_rn_gen    AS (SELECT COALESCE(MAX(rn_gen),  1) AS v FROM all_draws),
            max_rn_turn   AS (SELECT COALESCE(MAX(rn_turn), 1) AS v FROM all_draws WHERE turn_day = %s),
            last_gen_app  AS (SELECT val, MAX(rn_gen)  AS last_rn FROM all_draws GROUP BY val),
            last_turn_app AS (SELECT val, MAX(rn_turn) AS last_rn FROM all_draws WHERE turn_day = %s GROUP BY val),
            consec AS (
                SELECT nxt.val AS next_val, COUNT(*) AS freq
                FROM all_draws cur
                JOIN all_draws nxt ON nxt.rn_gen = cur.rn_gen + 1
                WHERE cur.val = (SELECT val FROM last_val)
                GROUP BY nxt.val
            ),
            month_f AS (
                SELECT val, COUNT(*) AS freq FROM all_draws
                WHERE EXTRACT(MONTH FROM draw_date) = %s
                  AND EXTRACT(YEAR  FROM draw_date) = %s
                GROUP BY val
            ),
            dow_f AS (
                SELECT val, COUNT(*) AS freq FROM all_draws
                WHERE EXTRACT(DOW FROM draw_date) = %s
                GROUP BY val
            ),
            week_f AS (
                SELECT val, COUNT(*) AS freq FROM all_draws
                WHERE (CASE
                           WHEN EXTRACT(DAY FROM draw_date) <= 7  THEN 1
                           WHEN EXTRACT(DAY FROM draw_date) <= 14 THEN 2
                           WHEN EXTRACT(DAY FROM draw_date) <= 21 THEN 3
                           WHEN EXTRACT(DAY FROM draw_date) <= 28 THEN 4
                           ELSE 5 END) = %s
                GROUP BY val
            )
            SELECT
                av.val,
                (SELECT v FROM max_rn_gen)  - COALESCE(lg.last_rn, 0)  AS atraso_gen,
                (SELECT v FROM max_rn_turn) - COALESCE(lt.last_rn, 0)  AS atraso_turn,
                COALESCE(c.freq,  0)                                    AS consec_freq,
                COALESCE(mf.freq, 0)                                    AS month_freq,
                COALESCE(df.freq, 0)                                    AS dow_freq,
                COALESCE(wf.freq, 0)                                    AS week_freq
            FROM generate_series(0, 9) av(val)
            LEFT JOIN last_gen_app  lg ON lg.val      = av.val
            LEFT JOIN last_turn_app lt ON lt.val      = av.val
            LEFT JOIN consec        c  ON c.next_val  = av.val
            LEFT JOIN month_f       mf ON mf.val      = av.val
            LEFT JOIN dow_f         df ON df.val      = av.val
            LEFT JOIN week_f        wf ON wf.val      = av.val
        """, (sorteo_id, turn_day, turn_day, month, year, pg_dow, week_seg_num))
        return self.env.cr.dictfetchall()

    def _get_calientes_cebs(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False, rows=None):
        """
        Centenas / bola extra calientes.
        Evalúa los 10 valores posibles (0-9) con 6 criterios ponderados:
          35 % atraso turno   — cuánto lleva sin salir en este turno
          25 % atraso general — cuánto lleva sin salir en cualquier turno
          20 % consecutivo    — con qué frecuencia sigue al último valor sorteado
          10 % frecuencia mes — salidores del mes actual
           7 % frecuencia DOW — salidores en este día de la semana
           3 % frecuencia sem — salidores en esta semana del mes
        Retorna los 4 mejores. Acepta `rows` ya consultadas para no repetir
        la query cuando el llamador puntúa hot/cold/all sobre los mismos datos.
        """
        if rows is None:
            rows = self._query_ceb_stats(turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=sorteo_id)
        if not rows:
            return []

        mx_turn   = max(r['atraso_turn']  for r in rows) or 1
        mx_gen    = max(r['atraso_gen']   for r in rows) or 1
        mx_consec = max(r['consec_freq']  for r in rows) or 1
        mx_month  = max(r['month_freq']   for r in rows) or 1
        mx_dow    = max(r['dow_freq']     for r in rows) or 1
        mx_week   = max(r['week_freq']    for r in rows) or 1

        for r in rows:
            r['score'] = round(
                35.0 * r['atraso_turn'] / mx_turn   +
                25.0 * r['atraso_gen']  / mx_gen    +
                20.0 * r['consec_freq'] / mx_consec +
                10.0 * r['month_freq']  / mx_month  +
                 7.0 * r['dow_freq']    / mx_dow    +
                 3.0 * r['week_freq']   / mx_week,
                1
            )

        rows.sort(key=lambda x: x['score'], reverse=True)
        return [{'name': str(r['val'])} for r in rows[:4]]

    def _get_frios_cebs(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False, rows=None):
        """
        Centenas / bola extra frías.
        Mismos 6 criterios que calientes pero INVERTIDOS:
          35 % recencia turno   — cuánto POCO lleva sin salir (apareció recientemente)
          25 % recencia general — ídem en cualquier turno
          20 % menos seguidor  — el que MENOS sigue al último valor sorteado
          10 % menos salidor mes
           7 % menos salidor DOW
           3 % menos salidor sem
        Retorna los 4 más fríos. Acepta `rows` ya consultadas (ver _get_calientes_cebs).
        """
        if rows is None:
            rows = self._query_ceb_stats(turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=sorteo_id)
        if not rows:
            return []

        mx_turn   = max(r['atraso_turn']  for r in rows) or 1
        mx_gen    = max(r['atraso_gen']   for r in rows) or 1
        mx_consec = max(r['consec_freq']  for r in rows) or 1
        mx_month  = max(r['month_freq']   for r in rows) or 1
        mx_dow    = max(r['dow_freq']     for r in rows) or 1
        mx_week   = max(r['week_freq']    for r in rows) or 1

        for r in rows:
            # Invertir: bajo atraso = reciente = más frío; baja frecuencia = menos salidor = más frío
            r['score'] = round(
                35.0 * (1 - r['atraso_turn'] / mx_turn)   +
                25.0 * (1 - r['atraso_gen']  / mx_gen)    +
                20.0 * (1 - r['consec_freq'] / mx_consec) +
                10.0 * (1 - r['month_freq']  / mx_month)  +
                 7.0 * (1 - r['dow_freq']    / mx_dow)    +
                 3.0 * (1 - r['week_freq']   / mx_week),
                1
            )

        rows.sort(key=lambda x: x['score'], reverse=True)
        return [{'name': str(r['val'])} for r in rows[:4]]

    def _get_all_cebs_scored(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False, rows=None):
        """Todos los valores (centenas o bola extra) con su score caliente, sin recortar.
        Acepta `rows` ya consultadas (ver _get_calientes_cebs)."""
        if rows is None:
            rows = self._query_ceb_stats(turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=sorteo_id)
        if not rows:
            return []
        mx_turn   = max(r['atraso_turn']  for r in rows) or 1
        mx_gen    = max(r['atraso_gen']   for r in rows) or 1
        mx_consec = max(r['consec_freq']  for r in rows) or 1
        mx_month  = max(r['month_freq']   for r in rows) or 1
        mx_dow    = max(r['dow_freq']     for r in rows) or 1
        mx_week   = max(r['week_freq']    for r in rows) or 1
        for r in rows:
            r['score'] = round(
                35.0 * r['atraso_turn'] / mx_turn   +
                25.0 * r['atraso_gen']  / mx_gen    +
                20.0 * r['consec_freq'] / mx_consec +
                10.0 * r['month_freq']  / mx_month  +
                 7.0 * r['dow_freq']    / mx_dow    +
                 3.0 * r['week_freq']   / mx_week,
                1
            )
        rows.sort(key=lambda x: x['score'], reverse=True)
        return [{'name': str(r['val'])} for r in rows]

    @api.model
    @tools.ormcache('today_str', 'sorteo_id')
    def get_calientes_all(self, today_str, sorteo_id=False):
        """Endpoint unificado: números, centenas y bola extra calientes para ambos turnos."""
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        pg_dow       = (today.weekday() + 1) % 7
        day          = today.day
        month        = today.month
        year         = today.year
        week_seg_num = (1 if day <= 7  else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)

        # Fecha del próximo sorteo = última salida del turno + 1 día
        DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        self.env.cr.execute("""
            SELECT
                MAX(date) FILTER (WHERE turn_day = 'afternoon') + INTERVAL '1 day' AS next_afternoon,
                MAX(date) FILTER (WHERE turn_day = 'evening')   + INTERVAL '1 day' AS next_evening,
                (SELECT turn_day FROM lottery_output WHERE sorteo_id = %(sorteo_id)s ORDER BY date DESC, id DESC LIMIT 1) AS last_turn
            FROM lottery_output
            WHERE sorteo_id = %(sorteo_id)s
        """, {'sorteo_id': sorteo_id})
        row = self.env.cr.dictfetchone() or {}

        def _fmt_date(d):
            if not d:
                return ''
            return '%s %s' % (DAY_NAMES[d.weekday()], d.strftime('%d/%m/%Y'))

        def _cut_with_ties(scores_desc, n):
            """Top-n calientes expandido: incluye empates en el límite."""
            if len(scores_desc) <= n:
                return scores_desc
            boundary = scores_desc[n - 1]['score']
            return [s for s in scores_desc if s['score'] >= boundary]

        sorteo = self.env['lottery.sorteo'].browse(sorteo_id)
        uses_fireball = bool(sorteo.uses_fireball)
        uses_hundreds = bool(sorteo.uses_hundreds)
        result = {}
        for turn in ('afternoon', 'evening'):
            result[turn] = self._calientes_for_turn(
                turn, pg_dow, week_seg_num, month, year, today_str,
                sorteo_id, row.get('next_' + turn), _cut_with_ties, _fmt_date,
                uses_fireball, uses_hundreds)
        result['last_turn'] = row.get('last_turn') or 'afternoon'
        return result

    def _calientes_for_turn(self, turn, pg_dow, week_seg_num, month, year,
                            today_str, sorteo_id, next_date, _cut_with_ties, _fmt_date,
                            uses_fireball=True, uses_hundreds=True):
        """Calcula caliente/restante/frío (números, centenas, bola extra) de UN
        solo turno. Reutilizado por get_calientes_all (ambos turnos) y por
        get_calientes_next_turn (solo el próximo turno). Si el sorteo no usa
        bola extra o no usa centena, no las calcula (correcto y más rápido)."""
        all_scores  = self.get_numeros_calientes(turn, today_str, sorteo_id=sorteo_id)
        cold_scores = self.get_numeros_frios(turn, today_str, sorteo_id=sorteo_id)

        # ── Hot top-30 (with tie expansion) ──────────────────────────────
        hot_top   = _cut_with_ties(all_scores, 30)
        hot_names = {s['name'] for s in hot_top}

        # ── Cold top-30 excluding any number already in hot ───────────────
        cold_filtered = [s for s in cold_scores if s['name'] not in hot_names]
        cold_top      = _cut_with_ties(cold_filtered, 30)
        cold_names    = {s['name'] for s in cold_top}

        # ── Remaining: neither hot nor cold ───────────────────────────────
        remaining = [s for s in all_scores if s['name'] not in hot_names
                                            and s['name'] not in cold_names]

        # Centena: solo si el sorteo la usa. Los sorteos de número de 2 dígitos
        # (La Primera, La Suerte, Pick 2) no la tienen, así que se omite.
        # Una sola query por campo: hot/cold/all se puntúan sobre las mismas filas.
        if uses_hundreds:
            cen_rows        = self._query_ceb_stats(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id)
            centenas        = self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id, rows=cen_rows)
            centenas_cold   = self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id, rows=cen_rows)

            hot_cen_names  = {c['name'] for c in centenas}
            cold_cen_names = {c['name'] for c in centenas_cold}

            # Centenas restantes: no clasificadas como calientes ni frías
            all_centenas   = self._get_all_cebs_scored(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id, rows=cen_rows)
            centenas_remaining = [c for c in all_centenas
                                  if c['name'] not in hot_cen_names and c['name'] not in cold_cen_names]
        else:
            centenas = centenas_cold = centenas_remaining = []

        # Bola extra: solo si el sorteo la usa (ej. Florida Pick 3). El resto
        # (Quiniela UY) no la tiene, así que se omite su cálculo.
        if uses_fireball:
            be_rows         = self._query_ceb_stats(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id)
            bola_extra      = self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id, rows=be_rows)
            bola_extra_cold = self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id, rows=be_rows)
            hot_be_names    = {c['name'] for c in bola_extra}
            cold_be_names   = {c['name'] for c in bola_extra_cold}
            all_bola_extra  = self._get_all_cebs_scored(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id, rows=be_rows)
            bola_extra_remaining = [c for c in all_bola_extra if c['name'] not in hot_be_names and c['name'] not in cold_be_names]
        else:
            bola_extra = bola_extra_cold = bola_extra_remaining = []

        return {
            'numbers':              hot_top,
            'numbers_cold':         cold_top,
            'numbers_remaining':    remaining,
            'centenas':             centenas,
            'centenas_cold':        centenas_cold,
            'centenas_remaining':   centenas_remaining,
            'bola_extra':           bola_extra,
            'bola_extra_cold':      bola_extra_cold,
            'bola_extra_remaining': bola_extra_remaining,
            'uses_fireball':        uses_fireball,
            'uses_hundreds':        uses_hundreds,
            'next_draw':            _fmt_date(next_date),
        }

    @api.model
    @tools.ormcache('today_str', 'turn', 'sorteo_id')
    def get_calientes_next_turn(self, today_str, turn, sorteo_id=False):
        """Calcula SOLO el turno del próximo sorteo (fecha + turno vienen del
        campo next_draw del sorteo, fuente única). ~2× más rápido que ambos."""
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        pg_dow       = (today.weekday() + 1) % 7
        day          = today.day
        month        = today.month
        year         = today.year
        week_seg_num = (1 if day <= 7  else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)

        DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        def _fmt_date(d):
            if not d:
                return ''
            return '%s %s' % (DAY_NAMES[d.weekday()], d.strftime('%d/%m/%Y'))

        def _cut_with_ties(scores_desc, n):
            if len(scores_desc) <= n:
                return scores_desc
            boundary = scores_desc[n - 1]['score']
            return [s for s in scores_desc if s['score'] >= boundary]

        if turn not in ('afternoon', 'evening'):
            turn = 'afternoon'
        sorteo = self.env['lottery.sorteo'].browse(sorteo_id)
        uses_fireball = bool(sorteo.uses_fireball)
        uses_hundreds = bool(sorteo.uses_hundreds)

        return {
            'turn':      turn,
            'data':      self._calientes_for_turn(
                turn, pg_dow, week_seg_num, month, year, today_str,
                sorteo_id, today, _cut_with_ties, _fmt_date,
                uses_fireball, uses_hundreds),
        }

    @api.model
    @tools.ormcache('turn', 'today_str', 'sorteo_id')
    def get_validation_sets(self, turn, today_str, sorteo_id=False):
        """Versión liviana para la validación de una salida: calcula SOLO el
        turno indicado y solo los conjuntos hot/cold de números, centenas y
        bola extra (sin el otro turno ni las listas 'remaining'). ~0.4s en frío
        vs. ~1.5s de get_calientes_all."""
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        pg_dow = (today.weekday() + 1) % 7
        day = today.day
        month = today.month
        year = today.year
        week_seg_num = (1 if day <= 7 else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)

        def _cut_with_ties(scores_desc, n):
            if len(scores_desc) <= n:
                return scores_desc
            boundary = scores_desc[n - 1]['score']
            return [s for s in scores_desc if s['score'] >= boundary]

        all_scores = self.get_numeros_calientes(turn, today_str, sorteo_id=sorteo_id)
        cold_scores = self.get_numeros_frios(turn, today_str, sorteo_id=sorteo_id)
        hot_top = _cut_with_ties(all_scores, 30)
        hot_names = {s['name'] for s in hot_top}
        cold_filtered = [s for s in cold_scores if s['name'] not in hot_names]
        cold_top = _cut_with_ties(cold_filtered, 30)

        cen_rows = self._query_ceb_stats(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id)
        be_rows  = self._query_ceb_stats(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id)
        return {
            'numbers':         hot_top,
            'numbers_cold':    cold_top,
            'centenas':        self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id, rows=cen_rows),
            'centenas_cold':   self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id, rows=cen_rows),
            'bola_extra':      self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id, rows=be_rows),
            'bola_extra_cold': self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id, rows=be_rows),
        }

    @api.model
    def get_lineas_terminales_dia_semana(self, wcode, top_n=3, sorteo_id=False):
        """
        Top-N líneas y terminales más atrasadas para un día de semana específico.
        Retorna general, afternoon y evening por separado.

        Estructura de retorno:
        {
          'lineas':     {'general': [...], 'afternoon': [...], 'evening': [...]},
          'terminales': {'general': [...], 'afternoon': [...], 'evening': [...]}
        }
        Cada ítem:
        {
          'name': '00-09', 'delay': 5,
          'numbers': [{'name': '03', 'delay': 4}, ...],  # 10 nums, orden delay DESC
          'max_delay_num': '03', 'max_delay_val': 4,
          'last_num': '07', 'last_date': '20/05/26'
        }
        """
        cr = self.env.cr

        day_col_map = {
            'lu': 'salidas_atrasadas_lunes',
            'ma': 'salidas_atrasadas_martes',
            'mi': 'salidas_atrasadas_miercoles',
            'ju': 'salidas_atrasadas_jueves',
            'vi': 'salidas_atrasadas_viernes',
            'sa': 'salidas_atrasadas_sabado',
            'do': 'salidas_atrasadas_domingo',
        }
        day_col = day_col_map.get(wcode, 'salidas_atrasadas_lunes')

        LINE_NAMES = {i: f'{i*10:02d}-{i*10+9:02d}' for i in range(10)}
        TERM_NAMES = {i: f'{i:02d}-{i+90:02d}' for i in range(10)}

        out = {'lineas': {}, 'terminales': {}}

        for grp_type in ('lineas', 'terminales'):
            is_line  = grp_type == 'lineas'
            name_map = LINE_NAMES if is_line else TERM_NAMES

            # Expresiones SQL seguras (no vienen de input externo)
            grp_expr = ('FLOOR(ln.name::numeric / 10)::int'
                        if is_line else '(ln.name %% 10)::int')
            num_grp  = ('FLOOR(ln.name::numeric / 10)::int'
                        if is_line else '(ln.name %% 10)::int')

            for turn in ('general', 'afternoon', 'evening'):
                t_sql  = f"AND turn_day = '{turn}'"  if turn != 'general' else ''
                tj_sql = f"AND lo.turn_day = '{turn}'" if turn != 'general' else ''

                # ── Paso 1: ranking top-N grupos por atraso ───────────────────
                if turn == 'general':
                    cr.execute(f"""
                        SELECT {grp_expr} AS grp_idx,
                               SUM(ln.{day_col}) AS delay
                        FROM lottery_number ln
                        GROUP BY grp_idx
                        ORDER BY delay DESC
                        LIMIT %s
                    """, [top_n])
                else:
                    cr.execute(f"""
                        WITH all_groups AS (
                            SELECT generate_series(0,9) AS grp_idx
                        ),
                        grp_last AS (
                            SELECT {grp_expr} AS grp_idx, MAX(lo.date) AS last_date
                            FROM lottery_output lo
                            JOIN lottery_number ln ON ln.id = lo.number_id
                            WHERE lo.week_day = %s {tj_sql} AND lo.sorteo_id = %s
                            GROUP BY grp_idx
                        )
                        SELECT
                            ag.grp_idx,
                            CASE
                                WHEN gl.last_date IS NULL THEN
                                    (SELECT COUNT(DISTINCT date) FROM lottery_output
                                     WHERE week_day = %s {t_sql} AND sorteo_id = %s)
                                ELSE
                                    (SELECT COUNT(DISTINCT lo2.date)
                                     FROM lottery_output lo2
                                     WHERE lo2.week_day = %s {t_sql}
                                       AND lo2.sorteo_id = %s
                                       AND lo2.date > gl.last_date)
                            END AS delay
                        FROM all_groups ag
                        LEFT JOIN grp_last gl ON gl.grp_idx = ag.grp_idx
                        ORDER BY delay DESC NULLS LAST
                        LIMIT %s
                    """, [wcode, sorteo_id, wcode, sorteo_id, wcode, sorteo_id, top_n])

                top_rows  = cr.dictfetchall()
                turn_data = []

                for row in top_rows:
                    grp_idx   = row['grp_idx']
                    grp_delay = row['delay'] or 0
                    grp_name  = name_map.get(grp_idx, str(grp_idx))

                    # ── Paso 2: números del grupo con atraso día+turno ────────
                    if turn == 'general':
                        cr.execute(f"""
                            SELECT LPAD(ln.name::text, 2, '0') AS name,
                                   ln.{day_col} AS delay
                            FROM lottery_number ln
                            WHERE {num_grp} = %s
                            ORDER BY ln.{day_col} DESC
                        """, [grp_idx])
                        nums = [{'name': r['name'], 'delay': r['delay'] or 0}
                                for r in cr.dictfetchall()]
                    else:
                        cr.execute(f"""
                            WITH total AS (
                                SELECT COUNT(DISTINCT date) AS cnt
                                FROM lottery_output
                                WHERE week_day = %s {t_sql} AND sorteo_id = %s
                            )
                            SELECT
                                LPAD(ln.name::text, 2, '0') AS name,
                                (SELECT cnt FROM total) - COALESCE((
                                    SELECT COUNT(DISTINCT lo.date)
                                    FROM lottery_output lo
                                    WHERE lo.number_id = ln.id
                                      AND lo.week_day = %s {tj_sql}
                                      AND lo.sorteo_id = %s
                                ), 0) AS delay
                            FROM lottery_number ln
                            WHERE {num_grp} = %s
                            ORDER BY delay DESC
                        """, [wcode, sorteo_id, wcode, sorteo_id, grp_idx])
                        nums = [{'name': r['name'], 'delay': r['delay'] or 0}
                                for r in cr.dictfetchall()]

                    # ── Paso 3: último número del grupo ese día+turno ─────────
                    cr.execute(f"""
                        SELECT LPAD(ln.name::text, 2, '0') AS num,
                               to_char(lo.date, 'DD/MM/YY') AS date
                        FROM lottery_output lo
                        JOIN lottery_number ln ON ln.id = lo.number_id
                        WHERE lo.week_day = %s {tj_sql}
                          AND lo.sorteo_id = %s
                          AND {num_grp} = %s
                        ORDER BY lo.date DESC, lo.id DESC
                        LIMIT 1
                    """, [wcode, sorteo_id, grp_idx])
                    last = cr.dictfetchone() or {}

                    max_num = nums[0] if nums else {}
                    turn_data.append({
                        'name':          grp_name,
                        'grp_idx':       grp_idx,
                        'delay':         grp_delay,
                        'numbers':       nums,
                        'max_delay_num': max_num.get('name', '-'),
                        'max_delay_val': max_num.get('delay', 0),
                        'last_num':      last.get('num', '-'),
                        'last_date':     last.get('date', '-'),
                    })

                out[grp_type][turn] = turn_data

        return out

    # ─── Líneas y Terminales más probables (próximo sorteo) ──────────────────

    @api.model
    @tools.ormcache('turn_day', 'today_str', 'sorteo_id')
    def get_lineas_terminales_probables(self, turn_day, today_str, sorteo_id=False):
        """
        Top 3 líneas y top 3 terminales más probables para el próximo sorteo
        (fecha/turno vienen de sorteo.get_next_draw()). Adaptación a nivel de
        grupo de los criterios de get_numeros_calientes: con solo 10 entidades
        por lado, los criterios puntúan de forma continua por ranking (no por
        magnitud) para que ningún atraso extremo domine el pronóstico.

        ── Criterios (máx ~159 pts, ningún criterio > ~9% del total) ────────
        G1   15 pts  Frecuencia del mes actual (rank 1-10 continuo)
        G2   13 pts  Seguimiento directo: top 5 que siguen a la última del
                     mismo tipo (línea→línea / terminal→terminal)
             +10 pts pendiente: no cumplido en los últimos 4 ciclos
        G3    9 pts  Seguimiento cruzado (último terminal→línea y viceversa)
             +7 pts  pendiente cruzado
             +4 pts  bonus si aparece en top 5 directo Y cruzado
        G4   10 pts  Atraso general (rank, no magnitud)
        G5    9 pts  Cobertura: % de sus números en top-5 grupos/pintas
                     atrasados (general)
        G6    8 pts  Semana del mes: 40% frecuencia + 60% atraso en esa semana
        G7    7 pts  Día de la semana: solo top 5 salidoras del día,
                     40% freq + 60% atraso del día
        G8   12 pts  Atraso del turno del próximo sorteo (rank)
        G9    9 pts  Salidor del mes × atraso del turno (rank)
        G10  10 pts  Dígitos de últimos 3 sorteos (exacto 1.0 / vecino ±1 0.5)
        G11 −10 pts  Recencia: salió en el último sorteo (−10) o en los
                     2 anteriores (−5)
        G12   8 pts  Fin de semana (solo sáb/dom): top 5 weekend,
                     40% freq + 60% atraso weekend
        G13   6 pts  Turno cruzado: top-5 atrasada del turno próximo Y activa
                     en el turno contrario (2+ salidas en últimas 6 → 2/4/6)
        G14   8 pts  Ritmo propio: atraso actual vs MEDIANA histórica de sus
                     intervalos en el turno (pico en ventana 0.9–1.3,
                     baja a 4 si está pasada — evita que una perdida domine)
        G15   7 pts  Dígitos dominantes: top 5 dígitos más repetidos en
                     ambas posiciones en los últimos 12 sorteos
        G16   7 pts  Espejo pendiente: cada XY sorteado espera línea Y y
                     terminal X (pareja NN además línea 0/terminal 0 —
                     bajito/pelón); pendientes en últimos 6 → 3.5 c/u, tope 7
        """
        from datetime import date as _date

        today = _date.fromisoformat(today_str)
        month = today.month
        pg_dow = (today.weekday() + 1) % 7      # PG: 0=domingo … 6=sábado
        day = today.day

        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'
        opposite_turn = 'evening' if turn_day == 'afternoon' else 'afternoon'
        is_weekend = pg_dow in (0, 6)
        week_seg = (1 if day <= 7 else 2 if day <= 14 else
                    3 if day <= 21 else 4 if day <= 28 else 5)

        month_field = MONTH_FIELD_MAP[month]
        dow_name = {0: 'domingo', 1: 'lunes', 2: 'martes', 3: 'miercoles',
                    4: 'jueves', 5: 'viernes', 6: 'sabado'}[pg_dow]
        freq_dow_field = f'total_{dow_name}'
        atraso_dow_field = f'salidas_atrasadas_{dow_name}'
        week_field = f'total_semana_{week_seg}'
        atraso_turn_field = ('salidas_atrasadas_dia' if turn_day == 'afternoon'
                             else 'salidas_atrasadas_noche')

        cr = self.env.cr
        LINE_EXPR = '(ln.name::int / 10)'
        TERM_EXPR = '(ln.name::int %% 10)'
        ORDER_DRAW = ("lo.date, CASE lo.turn_day WHEN 'afternoon' THEN 0 ELSE 1 END, lo.id")

        # ── 1. Stats por grupo desde lottery_group_stat (line_X / terminal_X) ─
        cr.execute(f"""
            SELECT lg.code,
                   lgs.{month_field}        AS freq_mes,
                   lgs.salidas_atrasadas    AS atraso_gen,
                   lgs.{atraso_turn_field}  AS atraso_turno,
                   lgs.{freq_dow_field}     AS freq_dow,
                   lgs.{atraso_dow_field}   AS atraso_dow,
                   lgs.{week_field}         AS freq_semana
            FROM lottery_group_stat lgs
            JOIN lottery_group lg ON lg.id = lgs.group_id
            WHERE lgs.sorteo_id = %s
              AND (lg.code LIKE 'line_%%' OR lg.code LIKE 'terminal_%%')
        """, (sorteo_id,))
        stats = {'line': {}, 'terminal': {}}
        for r in cr.dictfetchall():
            typ, _, idx = r['code'].rpartition('_')
            if typ in stats and idx.isdigit():
                stats[typ][int(idx)] = r

        empty = {
            'next_date': today.strftime('%d/%m/%Y'),
            'next_turn': turn_day,
            'next_turn_label': 'Tarde' if turn_day == 'afternoon' else 'Noche',
            'lineas': [], 'terminales': [], 'cross': [],
        }
        if not stats['line'] or not stats['terminal']:
            return empty

        # ── 2. Últimos sorteos (señales G10/G11/G13/G15/G16) ─────────────────
        cr.execute("""
            SELECT ln.name::int AS num, lo.turn_day
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.sorteo_id = %s
            ORDER BY lo.date DESC,
                     CASE lo.turn_day WHEN 'afternoon' THEN 1 ELSE 0 END,
                     lo.id DESC
            LIMIT 20
        """, (sorteo_id,))
        recent = cr.dictfetchall()          # más reciente primero

        # G10: dígitos de últimos 3 sorteos — exacto 1.0, vecino ±1 0.5
        w_line, w_term = {}, {}
        for d in recent[:3]:
            for digit, wmap in ((d['num'] // 10, w_line), (d['num'] % 10, w_term)):
                wmap[digit] = wmap.get(digit, 0) + 1.0
                for nb in (digit - 1, digit + 1):
                    if 0 <= nb <= 9:
                        wmap[nb] = wmap.get(nb, 0) + 0.5

        # G11: recencia
        last_line = recent[0]['num'] // 10 if recent else None
        last_term = recent[0]['num'] % 10 if recent else None
        near_lines = {d['num'] // 10 for d in recent[1:3]}
        near_terms = {d['num'] % 10 for d in recent[1:3]}

        # G15: dígitos dominantes en últimos 12 sorteos (ambas posiciones)
        digit_count = {}
        for d in recent[:12]:
            for digit in (d['num'] // 10, d['num'] % 10):
                digit_count[digit] = digit_count.get(digit, 0) + 1
        dom_rank = {dig: i + 1 for i, (dig, _cnt) in enumerate(
            sorted(digit_count.items(), key=lambda x: x[1], reverse=True)[:5])}

        # G16: espejo pendiente — XY espera línea Y y terminal X;
        # pareja NN espera además línea 0 y terminal 0 (bajito / pelón)
        window = list(reversed(recent[:6]))   # orden cronológico
        pend_line, pend_term = {}, {}
        for i, d in enumerate(window):
            dec, uni = d['num'] // 10, d['num'] % 10
            later = window[i + 1:]
            expects_l = {uni} | ({0} if dec == uni else set())
            expects_t = {dec} | ({0} if dec == uni else set())
            for tgt in expects_l:
                if not any(x['num'] // 10 == tgt for x in later):
                    pend_line[tgt] = pend_line.get(tgt, 0) + 1
            for tgt in expects_t:
                if not any(x['num'] % 10 == tgt for x in later):
                    pend_term[tgt] = pend_term.get(tgt, 0) + 1

        # G13: actividad en las últimas 6 tiradas del turno contrario
        opp_draws = [d for d in recent if d['turn_day'] == opposite_turn][:6]
        opp_line, opp_term = {}, {}
        for d in opp_draws:
            opp_line[d['num'] // 10] = opp_line.get(d['num'] // 10, 0) + 1
            opp_term[d['num'] % 10] = opp_term.get(d['num'] % 10, 0) + 1

        # ── 3. Seguimientos directo y cruzado (G2/G3) ────────────────────────
        def _followers(from_expr, to_expr):
            """Top 5 valores 'to' que siguen al último valor 'from' sorteado,
            con cuántas veces se cumplió en los últimos 4 ciclos (pendientes)."""
            cr.execute(f"""
                WITH ordered AS (
                    SELECT {from_expr} AS from_g,
                           {to_expr}   AS to_g,
                           ROW_NUMBER() OVER (ORDER BY {ORDER_DRAW}) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE lo.sorteo_id = %s
                ),
                last_g AS (SELECT from_g FROM ordered ORDER BY rn DESC LIMIT 1),
                top_consec AS (
                    SELECT nxt.to_g AS next_g, COUNT(*) AS freq
                    FROM ordered cur
                    JOIN ordered nxt ON nxt.rn = cur.rn + 1
                    WHERE cur.from_g = (SELECT from_g FROM last_g)
                    GROUP BY nxt.to_g
                    ORDER BY freq DESC
                    LIMIT 5
                ),
                last_4_occ AS (
                    SELECT rn FROM ordered
                    WHERE from_g = (SELECT from_g FROM last_g)
                    ORDER BY rn DESC
                    OFFSET 1 LIMIT 4
                ),
                fulfilled AS (
                    SELECT o.to_g AS f_g, COUNT(*) AS cnt
                    FROM ordered o
                    JOIN last_4_occ l4 ON o.rn = l4.rn + 1
                    WHERE o.to_g IN (SELECT next_g FROM top_consec)
                    GROUP BY o.to_g
                )
                SELECT t.next_g, t.freq, COALESCE(f.cnt, 0) AS count_fulfilled
                FROM top_consec t
                LEFT JOIN fulfilled f ON f.f_g = t.next_g
                ORDER BY t.freq DESC
            """, (sorteo_id,))
            return {r['next_g']: {'rank': i + 1, 'fulfilled': r['count_fulfilled']}
                    for i, r in enumerate(cr.dictfetchall())}

        line_direct = _followers(LINE_EXPR, LINE_EXPR)
        line_cross = _followers(TERM_EXPR, LINE_EXPR)
        term_direct = _followers(TERM_EXPR, TERM_EXPR)
        term_cross = _followers(LINE_EXPR, TERM_EXPR)

        # ── 4. Series filtradas: semana del mes (G6) y weekend (G12) ─────────
        def _series_stats(grp_expr, where_extra, extra_params):
            cr.execute(f"""
                WITH s AS (
                    SELECT {grp_expr} AS g,
                           ROW_NUMBER() OVER (ORDER BY {ORDER_DRAW}) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE lo.sorteo_id = %s {where_extra}
                ),
                mx AS (SELECT COALESCE(MAX(rn), 0) AS v FROM s)
                SELECT g, COUNT(*) AS freq,
                       (SELECT v FROM mx) - MAX(rn) AS delay
                FROM s GROUP BY g
            """, (sorteo_id, *extra_params))
            return {r['g']: r for r in cr.dictfetchall()}

        seg_where = """AND (CASE WHEN EXTRACT(DAY FROM lo.date) <= 7  THEN 1
                                 WHEN EXTRACT(DAY FROM lo.date) <= 14 THEN 2
                                 WHEN EXTRACT(DAY FROM lo.date) <= 21 THEN 3
                                 WHEN EXTRACT(DAY FROM lo.date) <= 28 THEN 4
                                 ELSE 5 END) = %s"""
        seg_line = _series_stats(LINE_EXPR, seg_where, (week_seg,))
        seg_term = _series_stats(TERM_EXPR, seg_where, (week_seg,))

        wk_line, wk_term = {}, {}
        if is_weekend:
            wk_where = "AND EXTRACT(DOW FROM lo.date) IN (0, 6)"
            wk_line = _series_stats(LINE_EXPR, wk_where, ())
            wk_term = _series_stats(TERM_EXPR, wk_where, ())

        # ── 5. Ritmo propio (G14): mediana de intervalos en el turno ─────────
        def _rhythm(grp_expr):
            cr.execute(f"""
                WITH s AS (
                    SELECT {grp_expr} AS g,
                           ROW_NUMBER() OVER (ORDER BY lo.date, lo.id) AS rn
                    FROM lottery_output lo
                    JOIN lottery_number ln ON ln.id = lo.number_id
                    WHERE lo.sorteo_id = %s AND lo.turn_day = %s
                ),
                mx   AS (SELECT COALESCE(MAX(rn), 0) AS v FROM s),
                gaps AS (SELECT g,
                                rn - LAG(rn) OVER (PARTITION BY g ORDER BY rn) - 1 AS gap
                         FROM s),
                med  AS (SELECT g,
                                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap) AS med_gap
                         FROM gaps WHERE gap IS NOT NULL GROUP BY g),
                cur  AS (SELECT g, (SELECT v FROM mx) - MAX(rn) AS delay FROM s GROUP BY g)
                SELECT c.g, c.delay, m.med_gap
                FROM cur c LEFT JOIN med m ON m.g = c.g
            """, (sorteo_id, turn_day))
            return {r['g']: r for r in cr.dictfetchall()}

        rhythm_line = _rhythm(LINE_EXPR)
        rhythm_term = _rhythm(TERM_EXPR)

        # ── 6. Cobertura de grupos/pintas atrasados — general (G5) ───────────
        def _delayed_numbers(code_filter):
            cr.execute(f"""
                SELECT group_code, MIN(general) AS atraso
                FROM lottery_number_groups_atrasos_mv
                WHERE sorteo_id = %s {code_filter}
                GROUP BY group_code
                ORDER BY atraso DESC
                LIMIT 5
            """, (sorteo_id,))
            codes = [r['group_code'] for r in cr.dictfetchall()]
            if not codes:
                return set()
            cr.execute("""
                SELECT DISTINCT ln.name::int AS num
                FROM lottery_group lg
                JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
                JOIN lottery_number ln ON ln.id = rel.number_id
                WHERE lg.code = ANY(%s)
            """, (codes,))
            return {r['num'] for r in cr.dictfetchall()}

        delayed_nums = (
            _delayed_numbers("AND group_code NOT LIKE 'pinta_%%' "
                             "AND group_code NOT LIKE 'line_%%' "
                             "AND group_code NOT LIKE 'terminal_%%'")
            | _delayed_numbers("AND group_code LIKE 'pinta_%%'")
        )
        cov_line = {i: sum(1 for n in delayed_nums if n // 10 == i) / 10.0
                    for i in range(10)}
        cov_term = {i: sum(1 for n in delayed_nums if n % 10 == i) / 10.0
                    for i in range(10)}

        # ── 7. Ponderación ────────────────────────────────────────────────────
        def _rank_map(idx_stats, key):
            ordered = sorted(idx_stats, key=lambda i: idx_stats[i].get(key) or 0,
                             reverse=True)
            return {i: pos + 1 for pos, i in enumerate(ordered)}

        def _score_side(idx_stats, direct, cross, seg, wk, rhythm, cov,
                        w_dig, pend, opp_cnt, last_g, near_g):
            n_ent = max(len(idx_stats), 1)
            rank_mes = _rank_map(idx_stats, 'freq_mes')
            rank_gen = _rank_map(idx_stats, 'atraso_gen')
            rank_turn = _rank_map(idx_stats, 'atraso_turno')
            combo = {i: (idx_stats[i].get('freq_mes') or 0)
                        * (idx_stats[i].get('atraso_turno') or 0)
                     for i in idx_stats}
            rank_combo = {i: pos + 1 for pos, i in enumerate(
                sorted(combo, key=lambda i: combo[i], reverse=True))}

            dow_top5 = sorted(idx_stats,
                              key=lambda i: idx_stats[i].get('freq_dow') or 0,
                              reverse=True)[:5]
            dow_rank = {i: pos + 1 for pos, i in enumerate(dow_top5)}
            max_atr_dow = max((idx_stats[i].get('atraso_dow') or 0
                               for i in dow_top5), default=1) or 1

            rank_sem = _rank_map(idx_stats, 'freq_semana')
            max_seg_delay = max((seg.get(i, {}).get('delay') or 0
                                 for i in idx_stats), default=1) or 1

            wk_top5 = sorted(wk, key=lambda i: wk[i]['freq'] or 0, reverse=True)[:5]
            wk_rank = {i: pos + 1 for pos, i in enumerate(wk_top5)}
            max_wk_delay = max((wk[i]['delay'] or 0 for i in wk_top5),
                               default=1) or 1

            top5_turn = {i for i, rk in rank_turn.items() if rk <= 5}

            results = []
            for i in sorted(idx_stats):
                st = idx_stats[i]
                b = {}

                # G1: frecuencia del mes (continuo por rank)
                b['freq_mes'] = 15.0 * (1 - (rank_mes[i] - 1) / n_ent)

                # G2: seguimiento directo + pendiente
                if i in direct:
                    b['seg_directo'] = 13.0 * (1 - (direct[i]['rank'] - 1) / 5)
                    b['seg_directo_pend'] = 10.0 * (4 - min(direct[i]['fulfilled'], 4)) / 4

                # G3: seguimiento cruzado + pendiente + bonus doble señal
                if i in cross:
                    b['seg_cruzado'] = 9.0 * (1 - (cross[i]['rank'] - 1) / 5)
                    b['seg_cruzado_pend'] = 7.0 * (4 - min(cross[i]['fulfilled'], 4)) / 4
                    if i in direct:
                        b['bonus_doble'] = 4.0

                # G4 / G8: atrasos por ranking (no magnitud — una perdida
                # cobra lo mismo que "la más atrasada por poco")
                b['atraso_gen'] = 10.0 * (1 - (rank_gen[i] - 1) / n_ent)
                b['atraso_turno'] = 12.0 * (1 - (rank_turn[i] - 1) / n_ent)

                # G9: salidor del mes × atraso del turno
                b['salidor_x_atraso'] = 9.0 * (1 - (rank_combo[i] - 1) / n_ent)

                # G6: semana del mes — 40% frecuencia + 60% atraso
                f_sem = 1 - (rank_sem[i] - 1) / n_ent
                d_sem = (seg.get(i, {}).get('delay') or 0) / max_seg_delay
                b['semana_mes'] = 8.0 * (0.4 * f_sem + 0.6 * d_sem)

                # G7: día de la semana — solo top 5 salidoras del día
                if i in dow_rank:
                    f_dow = 1 - (dow_rank[i] - 1) / 5
                    d_dow = (st.get('atraso_dow') or 0) / max_atr_dow
                    b['dia_semana'] = 7.0 * (0.4 * f_dow + 0.6 * d_dow)

                # G12: fin de semana (solo sáb/dom)
                if i in wk_rank:
                    f_wk = 1 - (wk_rank[i] - 1) / 5
                    d_wk = (wk[i]['delay'] or 0) / max_wk_delay
                    b['weekend'] = 8.0 * (0.4 * f_wk + 0.6 * d_wk)

                # G10: dígitos de los últimos 3 sorteos (±1 a medio peso)
                if w_dig.get(i):
                    b['digitos_3'] = 10.0 * min(w_dig[i], 2.0) / 2.0

                # G15: dígitos dominantes de los últimos 12 sorteos
                if i in dom_rank:
                    b['digitos_dominantes'] = 7.0 * (1 - (dom_rank[i] - 1) / 5)

                # G16: espejo pendiente (incluye pareja → bajito/pelón)
                if pend.get(i):
                    b['espejo'] = min(3.5 * pend[i], 7.0)

                # G13: turno cruzado — atrasada aquí, calentando en el otro
                if i in top5_turn:
                    k = opp_cnt.get(i, 0)
                    if k >= 4:
                        b['turno_cruzado'] = 6.0
                    elif k == 3:
                        b['turno_cruzado'] = 4.0
                    elif k == 2:
                        b['turno_cruzado'] = 2.0

                # G14: ritmo propio — pico al entrar en su ventana (0.9–1.3
                # de su mediana), baja a 4 si está pasada (la deuda extrema
                # ya cobra en G4/G8)
                rh = rhythm.get(i) or {}
                med_gap = float(rh['med_gap']) if rh.get('med_gap') else 0.0
                if med_gap > 0:
                    ratio = (rh.get('delay') or 0) / med_gap
                    if ratio < 0.5:
                        pts = 0.0
                    elif ratio < 0.9:
                        pts = 8.0 * (ratio - 0.5) / 0.4
                    elif ratio <= 1.3:
                        pts = 8.0
                    else:
                        pts = 4.0
                    if pts:
                        b['ritmo'] = pts

                # G5: cobertura de grupos/pintas atrasados
                if cov.get(i):
                    b['cobertura'] = 9.0 * cov[i]

                # G11: penalización por recencia
                if i == last_g:
                    b['recencia'] = -10.0
                elif i in near_g:
                    b['recencia'] = -5.0

                b = {k: round(v, 1) for k, v in b.items()}
                results.append({
                    'idx': i,
                    'score': round(sum(b.values()), 1),
                    'breakdown': b,
                })
            results.sort(key=lambda x: x['score'], reverse=True)
            return results

        line_scores = _score_side(stats['line'], line_direct, line_cross,
                                  seg_line, wk_line, rhythm_line, cov_line,
                                  w_line, pend_line, opp_line,
                                  last_line, near_lines)
        term_scores = _score_side(stats['terminal'], term_direct, term_cross,
                                  seg_term, wk_term, rhythm_term, cov_term,
                                  w_term, pend_term, opp_term,
                                  last_term, near_terms)

        top_lineas = [{
            'idx': r['idx'],
            'name': f"Línea {r['idx']}",
            'range': f"{r['idx'] * 10:02d} al {r['idx'] * 10 + 9:02d}",
            'score': r['score'],
            'numbers': [f"{r['idx'] * 10 + u:02d}" for u in range(10)],
            'breakdown': r['breakdown'],
        } for r in line_scores[:3]]

        top_terminales = [{
            'idx': r['idx'],
            'name': f"Terminal {r['idx']}",
            'range': f"{r['idx']:02d} al {90 + r['idx']:02d}",
            'score': r['score'],
            'numbers': [f"{d * 10 + r['idx']:02d}" for d in range(10)],
            'breakdown': r['breakdown'],
        } for r in term_scores[:3]]

        # Números de cruce: intersección top-3 líneas × top-3 terminales
        cross_nums = sorted(f"{l['idx'] * 10 + t['idx']:02d}"
                            for l in top_lineas for t in top_terminales)

        return {
            'next_date': today.strftime('%d/%m/%Y'),
            'next_turn': turn_day,
            'next_turn_label': 'Tarde' if turn_day == 'afternoon' else 'Noche',
            'lineas': top_lineas,
            'terminales': top_terminales,
            'cross': cross_nums,
        }

