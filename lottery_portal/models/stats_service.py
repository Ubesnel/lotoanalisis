# -*- coding: utf-8 -*-

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
            'centena': str(record.hundreds_id.name),
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
        self.env.cr.execute("""
            SELECT
                LPAD(ln_next.name::text, 2, '0') AS name,
                COUNT(ln_next.name) AS cantidad_veces
            FROM (
                SELECT lo.*,
                    LEAD(lo.id) OVER (
                        ORDER BY lo.date ASC,
                                 CASE lo.turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                    ) AS next_id
                FROM lottery_output lo
                WHERE lo.sorteo_id = %s
            ) lo_actual
            JOIN lottery_output lo_next ON lo_next.id = lo_actual.next_id
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
        self.env.cr.execute("""
            SELECT
                LPAD(ln_prev.name::text, 2, '0') AS name,
                COUNT(ln_prev.name) AS cantidad_veces
            FROM (
                SELECT lo.*,
                    LAG(lo.id) OVER (
                        ORDER BY lo.date ASC,
                                 CASE lo.turn_day WHEN 'afternoon' THEN 1 WHEN 'evening' THEN 2 END
                    ) AS prev_id
                FROM lottery_output lo
                WHERE lo.sorteo_id = %s
            ) lo_actual
            JOIN lottery_output lo_prev ON lo_prev.id = lo_actual.prev_id
            JOIN lottery_number ln_prev ON ln_prev.id = lo_prev.number_id
            WHERE lo_actual.number_id = %s
            GROUP BY ln_prev.name
            ORDER BY COUNT(ln_prev.name) DESC, ln_prev.name
            LIMIT 10
        """, (sorteo_id, number_id,))
        return self.env.cr.dictfetchall()

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

    def _get_calientes_cebs(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False):
        """
        Centenas / bola extra calientes.
        Evalúa los 10 valores posibles (0-9) con 6 criterios ponderados:
          35 % atraso turno   — cuánto lleva sin salir en este turno
          25 % atraso general — cuánto lleva sin salir en cualquier turno
          20 % consecutivo    — con qué frecuencia sigue al último valor sorteado
          10 % frecuencia mes — salidores del mes actual
           7 % frecuencia DOW — salidores en este día de la semana
           3 % frecuencia sem — salidores en esta semana del mes
        Retorna los 4 mejores.
        """
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

    def _get_frios_cebs(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False):
        """
        Centenas / bola extra frías.
        Mismos 6 criterios que calientes pero INVERTIDOS:
          35 % recencia turno   — cuánto POCO lleva sin salir (apareció recientemente)
          25 % recencia general — ídem en cualquier turno
          20 % menos seguidor  — el que MENOS sigue al último valor sorteado
          10 % menos salidor mes
           7 % menos salidor DOW
           3 % menos salidor sem
        Retorna los 4 más fríos.
        """
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

    def _get_all_cebs_scored(self, turn_day, pg_dow, week_seg_num, month, year, output_id_field, sorteo_id=False):
        """Todos los valores (centenas o bola extra) con su score caliente, sin recortar."""
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

        uses_fireball = bool(self.env['lottery.sorteo'].browse(sorteo_id).uses_fireball)
        result = {}
        for turn in ('afternoon', 'evening'):
            result[turn] = self._calientes_for_turn(
                turn, pg_dow, week_seg_num, month, year, today_str,
                sorteo_id, row.get('next_' + turn), _cut_with_ties, _fmt_date, uses_fireball)
        result['last_turn'] = row.get('last_turn') or 'afternoon'
        return result

    def _calientes_for_turn(self, turn, pg_dow, week_seg_num, month, year,
                            today_str, sorteo_id, next_date, _cut_with_ties, _fmt_date,
                            uses_fireball=True):
        """Calcula caliente/restante/frío (números, centenas, bola extra) de UN
        solo turno. Reutilizado por get_calientes_all (ambos turnos) y por
        get_calientes_next_turn (solo el próximo turno). Si el sorteo no usa
        bola extra, no la calcula (correcto y más rápido)."""
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

        centenas        = self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id)
        centenas_cold   = self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id)

        hot_cen_names  = {c['name'] for c in centenas}
        cold_cen_names = {c['name'] for c in centenas_cold}

        # Centenas restantes: no clasificadas como calientes ni frías
        all_centenas   = self._get_all_cebs_scored(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id)

        # Bola extra: solo si el sorteo la usa (ej. Florida Pick 3). El resto
        # (Quiniela UY) no la tiene, así que se omite su cálculo.
        if uses_fireball:
            bola_extra      = self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id)
            bola_extra_cold = self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id)
            hot_be_names    = {c['name'] for c in bola_extra}
            cold_be_names   = {c['name'] for c in bola_extra_cold}
            all_bola_extra  = self._get_all_cebs_scored(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id)
            bola_extra_remaining = [c for c in all_bola_extra if c['name'] not in hot_be_names and c['name'] not in cold_be_names]
        else:
            bola_extra = bola_extra_cold = bola_extra_remaining = []

        return {
            'numbers':              hot_top,
            'numbers_cold':         cold_top,
            'numbers_remaining':    remaining,
            'centenas':             centenas,
            'centenas_cold':        centenas_cold,
            'centenas_remaining':   [c for c in all_centenas   if c['name'] not in hot_cen_names and c['name'] not in cold_cen_names],
            'bola_extra':           bola_extra,
            'bola_extra_cold':      bola_extra_cold,
            'bola_extra_remaining': bola_extra_remaining,
            'uses_fireball':        uses_fireball,
            'next_draw':            _fmt_date(next_date),
        }

    @api.model
    @tools.ormcache('today_str', 'sorteo_id')
    def get_calientes_next_turn(self, today_str, sorteo_id=False):
        """Igual que get_calientes_all pero calcula SOLO el próximo turno a
        jugarse (el opuesto al último registrado). El otro turno no es confiable
        porque cambiará cuando se juegue este. ~2× más rápido."""
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        pg_dow       = (today.weekday() + 1) % 7
        day          = today.day
        month        = today.month
        year         = today.year
        week_seg_num = (1 if day <= 7  else 2 if day <= 14 else
                        3 if day <= 21 else 4 if day <= 28 else 5)

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
            if len(scores_desc) <= n:
                return scores_desc
            boundary = scores_desc[n - 1]['score']
            return [s for s in scores_desc if s['score'] >= boundary]

        last_turn = row.get('last_turn') or 'evening'
        # El próximo turno es el opuesto al último jugado.
        turn = 'evening' if last_turn == 'afternoon' else 'afternoon'
        uses_fireball = bool(self.env['lottery.sorteo'].browse(sorteo_id).uses_fireball)

        return {
            'turn':      turn,
            'last_turn': last_turn,
            'data':      self._calientes_for_turn(
                turn, pg_dow, week_seg_num, month, year, today_str,
                sorteo_id, row.get('next_' + turn), _cut_with_ties, _fmt_date, uses_fireball),
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

        return {
            'numbers':         hot_top,
            'numbers_cold':    cold_top,
            'centenas':        self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id),
            'centenas_cold':   self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'hundreds_id', sorteo_id=sorteo_id),
            'bola_extra':      self._get_calientes_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id),
            'bola_extra_cold': self._get_frios_cebs(turn, pg_dow, week_seg_num, month, year, 'fireball_id', sorteo_id=sorteo_id),
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

