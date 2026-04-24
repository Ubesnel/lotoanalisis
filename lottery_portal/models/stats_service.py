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

    @api.model
    @tools.ormcache()
    def get_hero_stats(self):
        self.env.cr.execute("""
            SELECT
                COUNT(*) AS total_sorteos,
                MIN(date) AS primer_fecha
            FROM lottery_output
        """)
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

    @tools.ormcache()
    def get_last_results_full(self):
        LotteryOutput = self.env['lottery.output'].sudo()

        last_afternoon = LotteryOutput.search(
            [('turn_day', '=', 'afternoon')],
            order='date desc',
            limit=1
        )

        last_evening = LotteryOutput.search(
            [('turn_day', '=', 'evening')],
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
            'extra': str(record.fireball_id.name),
            'numero': str(record.number_id.name).zfill(2),
        }

    @api.model
    @tools.ormcache()
    def get_top_10_general(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_mv""")
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top_10_dia(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_afternoon_mv""")
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top_10_noche(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_evening_mv""")
        return self.env.cr.dictfetchall()

    @tools.ormcache('day')
    def get_ultimas_salidas_por_dia(self, day):
        self.env.cr.execute("""
            SELECT * FROM (
                SELECT * FROM lottery_ultima_salida_dia_semana_mv
                WHERE week_day = %s
                ORDER BY date DESC
                LIMIT 7
            ) sub
            ORDER BY date ASC
        """, (day,))
        return self.env.cr.dictfetchall()

    @tools.ormcache('month', 'year')
    def get_month_year(self, month, year):
        if not month:
            month = str(date.today().month)
        if not year:
            year = date.today().year
        return '%s %s' % (MONTHS_DICT[month], year)

    @api.model
    @tools.ormcache('week_code')
    def get_top_10_por_dia_semana(self, week_code):
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
                WHERE week_day = %s
                ORDER BY {field_name} DESC
                LIMIT 10
            """

        self.env.cr.execute(query, (week_code,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_centenas_afternoon(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_dia_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_centenas_evening(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_noche_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_centenas_general(self):
        self.env.cr.execute("""
                SELECT centena, atraso
                FROM lottery_top5_centena_general_mv ORDER BY atraso DESC;                
            """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type')
    def get_top_atrasos_lineas(self, type):
        query = """
            SELECT
                name,
                CASE %s
                    WHEN 'general' THEN general
                    WHEN 'afternoon' THEN afternoon
                    WHEN 'evening' THEN evening
                END AS atraso
            FROM lottery_top_atrasos_lineas_mv
            ORDER BY atraso DESC;
        """
        self.env.cr.execute(query, (type,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type')
    def get_top_atrasos_terminales(self, type):
        query = """
                SELECT
                name,
                CASE %s
                    WHEN 'general' THEN general
                    WHEN 'afternoon' THEN afternoon
                    WHEN 'evening' THEN evening
                END AS atraso
            FROM lottery_top_atrasos_terminales_mv
            ORDER BY atraso DESC;
            """
        self.env.cr.execute(query, (type,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('type', 'groups_code')
    def get_top_atrasos_number_groups(self, type, groups_code):
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
                WHERE group_code = ANY(%s)
                ORDER BY {field_name} DESC
            """

        self.env.cr.execute(query, (groups_code,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_bola_extra_afternoon(self):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_dia_mv ORDER BY atraso DESC;                
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_bola_extra_evening(self):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_noche_mv ORDER BY atraso DESC;                
                                """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top5_bola_extra_general(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_bola_extra_general_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month', 'current_year')
    def get_top_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)

        if not field:
            return []
        query = f"""
                SELECT
                    ln.id,
                    LPAD(ln.name::text, 2, '0') AS name,
                    {field} AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY {field} DESC, ln.id DESC
                    ) AS rank,
                    (
                        SELECT COUNT(*) FROM lottery_output lo
                        WHERE lo.number_id = ln.id
                          AND lo.month = %(month)s::text
                          AND lo.year = %(year)s
                    ) AS salidas_mes_anio,
                    last_info.last_month_date,
                    last_info.last_month_turn,
                    last_info.last_month_week_day
                FROM lottery_number ln
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
                    ORDER BY lo2.date DESC
                    LIMIT 1
                ) last_info ON true
                ORDER BY {field} DESC, ln.id DESC
                LIMIT 30;
            """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month', 'current_year')
    def get_remaining_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)
        if not field:
            return []
        query = f"""
                SELECT
                    ln.id,
                    LPAD(ln.name::text, 2, '0') AS name,
                    {field} AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY {field} DESC, ln.id DESC
                    ) + 30 AS rank,
                    (
                        SELECT COUNT(*) FROM lottery_output lo
                        WHERE lo.number_id = ln.id
                          AND lo.month = %(month)s::text
                          AND lo.year = %(year)s
                    ) AS salidas_mes_anio,
                    last_info.last_month_date,
                    last_info.last_month_turn,
                    last_info.last_month_week_day
                FROM lottery_number ln
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
                    ORDER BY lo2.date DESC
                    LIMIT 1
                ) last_info ON true
                ORDER BY {field} DESC, ln.id DESC
                OFFSET 30 LIMIT 40;
            """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month_filter', 'numbers')
    def get_top_numbers_month_info(self, month_filter, numbers):
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
                  AND number_id=ANY(%s) ORDER BY number_id, date DESC) t
            WHERE years_without_month > 0 ORDER BY years_without_month DESC;
        """
        self.env.cr.execute(query,(month_filter, number_ids,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('month', 'current_year')
    def get_bottom_numbers_month(self, month=None, current_year=None):
        field = MONTH_FIELD_MAP.get(month)

        if not field:
            return []
        query = f"""
                    SELECT
                        ln.id,
                        LPAD(ln.name::text, 2, '0') AS name,
                        {field} AS total,
                        ROW_NUMBER() OVER (
                            ORDER BY {field}, ln.id DESC
                        ) AS rank,
                        (
                            SELECT COUNT(*) FROM lottery_output lo
                            WHERE lo.number_id = ln.id
                              AND lo.month = %(month)s::text
                              AND lo.year = %(year)s
                        ) AS salidas_mes_anio,
                        last_info.last_month_date,
                        last_info.last_month_turn,
                        last_info.last_month_week_day
                    FROM lottery_number ln
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
                        ORDER BY lo2.date DESC
                        LIMIT 1
                    ) last_info ON true
                    ORDER BY {field}, ln.id DESC
                    LIMIT 30;
                """
        self.env.cr.execute(query, {'month': month, 'year': current_year})
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_numbers_all_weekdays(self):
        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, id,
                total_lunes, total_martes, total_miercoles,
                total_jueves, total_viernes, total_sabado, total_domingo
            FROM lottery_number
            ORDER BY id
        """)
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
    @tools.ormcache()
    def get_numbers_all_weeks(self):
        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, id,
                total_semana_1, total_semana_2, total_semana_3, total_semana_4, total_semana_5
            FROM lottery_number
            ORDER BY id
        """)
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
    @tools.ormcache()
    def get_centenas_all_weekdays(self):
        self.env.cr.execute("""
            SELECT week_day, field_type, centena, total_salidas
            FROM lottery_centena_weekday_mv
            ORDER BY week_day, field_type, total_salidas DESC
        """)
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
    @tools.ormcache()
    def get_centenas_all_weeks(self):
        self.env.cr.execute("""
            SELECT week_segment, field_type, centena, total_salidas
            FROM lottery_centena_week_mv
            ORDER BY week_segment, field_type, total_salidas DESC
        """)
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
    @tools.ormcache()
    def get_all_atrasos_lineas(self):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening
            FROM lottery_top_atrasos_lineas_mv
            ORDER BY general DESC
        """)
        rows = self.env.cr.dictfetchall()
        return {
            'general': [{'name': r['name'], 'atraso': r['general']} for r in sorted(rows, key=lambda x: x['general'] or 0, reverse=True)],
            'afternoon': [{'name': r['name'], 'atraso': r['afternoon']} for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening': [{'name': r['name'], 'atraso': r['evening']} for r in sorted(rows, key=lambda x: x['evening'] or 0, reverse=True)],
        }

    @api.model
    @tools.ormcache()
    def get_all_atrasos_terminales(self):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening
            FROM lottery_top_atrasos_terminales_mv
            ORDER BY general DESC
        """)
        rows = self.env.cr.dictfetchall()
        return {
            'general': [{'name': r['name'], 'atraso': r['general']} for r in sorted(rows, key=lambda x: x['general'] or 0, reverse=True)],
            'afternoon': [{'name': r['name'], 'atraso': r['afternoon']} for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening': [{'name': r['name'], 'atraso': r['evening']} for r in sorted(rows, key=lambda x: x['evening'] or 0, reverse=True)],
        }

    @api.model
    @tools.ormcache()
    def get_all_atrasos_parejas(self):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening
            FROM lottery_number_groups_atrasos_mv
            WHERE group_code = 'resta_0'
            ORDER BY general DESC
        """)
        rows = self.env.cr.dictfetchall()
        return {
            'general': [{'name': r['name'], 'atraso': r['general']} for r in sorted(rows, key=lambda x: x['general'] or 0, reverse=True)],
            'afternoon': [{'name': r['name'], 'atraso': r['afternoon']} for r in sorted(rows, key=lambda x: x['afternoon'] or 0, reverse=True)],
            'evening': [{'name': r['name'], 'atraso': r['evening']} for r in sorted(rows, key=lambda x: x['evening'] or 0, reverse=True)],
        }

    @api.model
    @tools.ormcache('day')
    def get_top_numbers_by_week_day(self, day):
        field = WEEKDAY_FIELD_MAP.get(day)

        if not field:
            return []
        query = f"""
                SELECT
                    LPAD(name::text, 2, '0') AS name,
                    {field} AS total,
                    ROW_NUMBER() OVER (
                        ORDER BY {field} desc, id desc
                    ) AS rank
                FROM lottery_number
                ORDER BY {field} desc, id desc
                LIMIT 15;
                """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week')
    def get_top_numbers_by_week(self, week):
        field = WEEK_FIELD_MAP.get(week)

        if not field:
            return []
        query = f"""
                    SELECT
                        LPAD(name::text, 2, '0') AS name,
                        {field} AS total,
                        ROW_NUMBER() OVER (
                            ORDER BY {field} desc, id desc
                        ) AS rank
                    FROM lottery_number
                    ORDER BY {field} desc, id desc
                    LIMIT 15;
                    """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('day')
    def get_bottom_numbers_by_week_day(self, day):
        field = WEEKDAY_FIELD_MAP.get(day)

        if not field:
            return []
        query = f"""
                    SELECT
                        LPAD(name::text, 2, '0') AS name,
                        {field} AS total,
                        ROW_NUMBER() OVER (
                            ORDER BY {field}, id desc
                        ) AS rank
                    FROM lottery_number
                    ORDER BY {field}, id desc
                    LIMIT 15;
                    """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week')
    def get_bottom_numbers_by_week(self, week):
        field = WEEK_FIELD_MAP.get(week)

        if not field:
            return []
        query = f"""
                        SELECT
                            LPAD(name::text, 2, '0') AS name,
                            {field} AS total,
                            ROW_NUMBER() OVER (
                                ORDER BY {field}, id desc
                            ) AS rank
                        FROM lottery_number
                        ORDER BY {field}, id desc
                        LIMIT 15;
                        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('number_id')
    def get_salidas_numeros_despues_numero(self, number_id):
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
            ) lo_actual
            JOIN lottery_output lo_next ON lo_next.id = lo_actual.next_id
            JOIN lottery_number ln_next ON ln_next.id = lo_next.number_id
            WHERE lo_actual.number_id = %s
            GROUP BY ln_next.name
            ORDER BY COUNT(ln_next.name) DESC, ln_next.name
            LIMIT 10
        """, (number_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('number_id')
    def get_salidas_numeros_antes_numero(self, number_id):
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
            ) lo_actual
            JOIN lottery_output lo_prev ON lo_prev.id = lo_actual.prev_id
            JOIN lottery_number ln_prev ON ln_prev.id = lo_prev.number_id
            WHERE lo_actual.number_id = %s
            GROUP BY ln_prev.name
            ORDER BY COUNT(ln_prev.name) DESC, ln_prev.name
            LIMIT 10
        """, (number_id,))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('day', 'field')
    def get_top_centenas_by_week_day(self, day, field):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_weekday_mv
            WHERE week_day = %s AND field_type = %s
            ORDER BY total_salidas DESC
            LIMIT 4
        """, (day, field))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('day', 'field')
    def get_bottom_centenas_by_week_day(self, day, field):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_weekday_mv
            WHERE week_day = %s AND field_type = %s
            ORDER BY total_salidas ASC
            LIMIT 4
        """, (day, field))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'field')
    def get_top_centenas_by_week(self, week, field):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_week_mv
            WHERE week_segment = %s AND field_type = %s
            ORDER BY total_salidas DESC
            LIMIT 4
        """, (week, field))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('week', 'field')
    def get_bottom_centenas_by_week(self, week, field):
        self.env.cr.execute("""
            SELECT centena, total_salidas
            FROM lottery_centena_week_mv
            WHERE week_segment = %s AND field_type = %s
            ORDER BY total_salidas ASC
            LIMIT 4
        """, (week, field))
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top_repeticiones(self):
        query = f"""WITH data AS (select number_id, date,        
              LAG(number_id) OVER (ORDER BY date, CASE WHEN turn_day = 'afternoon' THEN 1 ELSE 2 END) AS prev_number
                FROM lottery_output),
            pegados AS (select number_id, date FROM data WHERE number_id = prev_number)
            select LPAD(ln.name::text, 2, '0') AS name,
                COUNT(*) AS repeticiones,
                TO_CHAR(MAX(p.date), 'DD/MM/YYYY') AS ultima_repeticion    
            FROM pegados p
            JOIN lottery_number ln ON ln.id = p.number_id
            GROUP BY ln.name
            ORDER BY repeticiones desc, ln.name
            LIMIT 15;"""
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache()
    def get_top_pegados(self):
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
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @tools.ormcache('option', 'day')
    def get_top_6_groups(self, option=False, day=False):
        field_map = {'general': 'salidas_atrasadas', 'afternoon': 'salidas_atrasadas_dia',
                     'evening': 'salidas_atrasadas_noche'}
        day_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                     'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
                     'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
                     'do': 'salidas_atrasadas_domingo'}

        field = field_map.get(option, 'salidas_atrasadas')
        field_day = day_map.get(day, 'salidas_atrasadas_lunes')
        query = f"""SELECT id, UPPER(name) as name, salidas_atrasadas, 
        salidas_atrasadas_dia, 
        salidas_atrasadas_noche, 
        {field_day} as salidas_atrasadas_por_dia         
        FROM lottery_group where code not in ('pinta_0', 'pinta_1', 'pinta_2', 'pinta_3', 'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7', 'pinta_8', 'pinta_9')
         ORDER BY {field} DESC LIMIT %s"""
        self.env.cr.execute(query, (5,))
        groups = self.env.cr.dictfetchall()
        return groups

    @tools.ormcache('group', 'orden', 'day')
    def get_info_groups_numbers(self, group, orden, day):
        field_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                     'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves', 'vi': 'salidas_atrasadas_viernes',
                     'sa': 'salidas_atrasadas_sabado', 'do': 'salidas_atrasadas_domingo'
                     }
        field = field_map.get(day)

        numbers = self.env['lottery.number'].search_read(
            [('id', 'in', group.number_ids.ids)],
            ['name', 'total_atrasadas', 'total_atrasadas_dia', 'total_atrasadas_noche', field
             ], order=f'{orden} desc')

        return [{
                'numero': str(n['name']).zfill(2),
                'total_atrasadas': n.get('total_atrasadas', 0),
                'total_atrasadas_dia': n.get('total_atrasadas_dia', 0),
                'total_atrasadas_noche': n.get('total_atrasadas_noche', 0),
                'total_atrasadas_por_dia_semana': n.get(field, 0)}
            for n in numbers
        ]

    @tools.ormcache('option', 'day')
    def get_top_3_pintas(self, option=False, day=False):
        field_map = {'general': 'salidas_atrasadas', 'afternoon': 'salidas_atrasadas_dia',
                     'evening': 'salidas_atrasadas_noche'}
        day_map = {'lu': 'salidas_atrasadas_lunes', 'ma': 'salidas_atrasadas_martes',
                   'mi': 'salidas_atrasadas_miercoles', 'ju': 'salidas_atrasadas_jueves',
                   'vi': 'salidas_atrasadas_viernes', 'sa': 'salidas_atrasadas_sabado',
                   'do': 'salidas_atrasadas_domingo'}

        field = field_map.get(option, 'salidas_atrasadas')
        field_day = day_map.get(day, 'salidas_atrasadas_lunes')
        query = f"""SELECT id, UPPER(name) as name, salidas_atrasadas, 
            salidas_atrasadas_dia, 
            salidas_atrasadas_noche, 
            {field_day} as salidas_atrasadas_por_dia         
            FROM lottery_group where code in ('pinta_0', 'pinta_1', 'pinta_2', 'pinta_3', 'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7', 'pinta_8', 'pinta_9')
             ORDER BY {field} DESC LIMIT %s"""
        self.env.cr.execute(query, (3,))
        groups = self.env.cr.dictfetchall()
        return groups

    @tools.ormcache('group_id', 'day', 'week', 'month', 'limit')
    def get_info_group_numbers_analysis(self, group_id, day, week, month, limit):
        if not group_id or not day or not month or not week:
            return {}

        self.env.cr.execute("""
                SELECT *
                FROM lottery_group_analysis_mv
                WHERE group_id = %s
            """, (group_id,))

        rows = self.env.cr.dictfetchall()

        if not rows:
            return {}

        # 🔹 helpers
        def top(rows, field, n=1, reverse=True):
            return sorted(rows, key=lambda x: x[field] or 0, reverse=reverse)[:n]

        def s(r):
            return {
                "id": r["number_id"],
                "name": r["name"],
            }

        def s_list(lst):
            return [s(x) for x in lst]

        # 🔹 MAPAS DINÁMICOS

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

    @tools.ormcache('group_id', 'turn')
    def get_group_delay_intervals(self, group_id, turn=None):
        where_clause = ""
        params = [group_id]
        if turn:
            where_clause = "where o.turn_day = %s"
            params.append(turn)

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

    @tools.ormcache('group_id', 'turn')
    def get_group_delay_intervals_pintas(self, group_id, turn=None):
        where_clause = ""
        params = [group_id]
        if turn:
            where_clause = "where o.turn_day = %s"
            params.append(turn)
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


