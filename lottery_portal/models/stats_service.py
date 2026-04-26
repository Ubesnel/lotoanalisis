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
                LIMIT 8
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
            SELECT name, general, afternoon, evening,
                   last_num_general, last_date_general,
                   last_num_afternoon, last_date_afternoon,
                   last_num_evening, last_date_evening,
                   max_delay_num_general, max_delay_val_general, max_delay_date_general,
                   max_delay_num_afternoon, max_delay_val_afternoon, max_delay_date_afternoon,
                   max_delay_num_evening, max_delay_val_evening, max_delay_date_evening
            FROM lottery_top_atrasos_lineas_mv
        """)
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
    @tools.ormcache()
    def get_all_atrasos_terminales(self):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening,
                   last_num_general, last_date_general,
                   last_num_afternoon, last_date_afternoon,
                   last_num_evening, last_date_evening,
                   max_delay_num_general, max_delay_val_general, max_delay_date_general,
                   max_delay_num_afternoon, max_delay_val_afternoon, max_delay_date_afternoon,
                   max_delay_num_evening, max_delay_val_evening, max_delay_date_evening
            FROM lottery_top_atrasos_terminales_mv
        """)
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
    @tools.ormcache()
    def get_weekend_groups(self):
        """Top 5 líneas y terminales que más salen en sábado + domingo."""
        self.env.cr.execute("""
            SELECT grp_type, grp_code, total_general, total_afternoon, total_evening
            FROM lottery_weekend_groups_mv
        """)
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
    @tools.ormcache()
    def get_all_group_sequences(self):
        """Para cada línea/terminal, top 5 grupos que salen más frecuentemente a continuación."""
        from collections import defaultdict

        self.env.cr.execute("""
            SELECT grp_type, from_code, to_code,
                   total_general, total_afternoon, total_evening
            FROM lottery_group_sequences_mv
        """)
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
    @tools.ormcache()
    def get_all_atrasos_parejas(self):
        self.env.cr.execute("""
            SELECT name, general, afternoon, evening, last_date, last_turn,
                   last_date_afternoon, last_date_evening
            FROM lottery_number_groups_atrasos_mv
            WHERE group_code = 'resta_0'
        """)
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

    # ─── Números Calientes ───────────────────────────────────────────────────

    @api.model
    @tools.ormcache('turn_day', 'today_str')
    def get_numeros_calientes(self, turn_day, today_str):
        """
        Ponderación separada: estadísticas GENERALES aplican igual a ambos turnos;
        estadísticas POR TURNO solo suman al turno correspondiente.

        GENERALES (mismo peso tarde y noche):
          C1    22 pts  Top 70 salidores del mes actual
          C7    12 pts  Decena/unidad coincide con dígitos de últimos 3 sorteos
                        (se consideran también los vecinos ±1 de cada número sorteado)
          C8   −12 pts  Penalización por recencia (últimos 5 sorteos):
                        −12 si el número salió exacto, −6 si es ±1 de alguno
                        Score bajo → improbable → cae en lista de fríos
          C2g   10 pts  Top 5 grupos más atrasados — GENERAL
          C3g    9 pts  Top 5 pintas más atrasadas — GENERAL
          C4     7 pts  Más sale en la semana del mes actual
          C5     5 pts  Más sale en el día de la semana actual

        POR TURNO (tarde → afternoon / noche → evening):
          C2t   14 pts  Top 5 grupos más atrasados del turno
          C3t   11 pts  Top 5 pintas más atrasadas del turno
          C6    10 pts  Salidor del mes × atraso del turno

        Máx: ~100 pts  (C8 puede restar hasta 12 pts adicionales)
        """
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        month = today.month
        pg_dow = (today.weekday() + 1) % 7        # Python Mon=0 → PG Mon=1, PG Sun=0
        day = today.day

        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'

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
            SELECT id,
                   LPAD(name::text, 2, '0') AS name,
                   name::int                AS num_int,
                   {month_field}            AS salidas_mes,
                   {dow_field}              AS salidas_dow,
                   {week_field}             AS salidas_semana,
                   {turn_atraso_field}      AS atraso_turno
            FROM lottery_number
        """)
        numbers = {r['id']: r for r in self.env.cr.dictfetchall()}

        def _fetch_group_ids(extra_where=''):
            """Devuelve (general_ids, turn_ids) para grupos o pintas."""
            self.env.cr.execute(f"""
                SELECT group_code,
                       MIN(general)           AS atraso_gen,
                       MIN({turn_mv_field})   AS atraso_turn
                FROM lottery_number_groups_atrasos_mv
                {extra_where}
                GROUP BY group_code
            """)
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
        gen_pinta_ids, turn_pinta_ids = _fetch_group_ids("WHERE group_code LIKE 'pinta_%%'")

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

        # ── C7. Dígitos últimos 3 sorteos + vecinos ±1 ("alante y atras") ──
        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 3
        """)
        digit_set = set()
        for draw in self.env.cr.dictfetchall():
            for delta in (-1, 0, 1):
                nv = draw['num_val'] + delta
                if 0 <= nv <= 99:
                    digit_set.add(nv // 10)
                    digit_set.add(nv % 10)

        # ── C8. Penalización por recencia: exacto o ±1 en últimos 5 sorteos ─
        self.env.cr.execute("""
            SELECT ln.name::int AS num_val
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            ORDER BY lo.date DESC, lo.id DESC
            LIMIT 5
        """)
        recent_nums = {r['num_val'] for r in self.env.cr.dictfetchall()}
        adjacent_nums = {
            adj for n in recent_nums
            for adj in (n - 1, n + 1)
            if 0 <= adj <= 99 and adj not in recent_nums
        }

        # ── Ponderación ──────────────────────────────────────────────────────
        scores = []
        for num_id, n in numbers.items():
            rm  = rank_mes[num_id]
            rd  = rank_dow[num_id]
            rs  = rank_semana[num_id]
            rc6 = rank_c6[num_id]

            # Generales (mismo peso en tarde y noche)
            s1  = 22.0 * (1 - (rm - 1) / 70) if rm <= 70 else 0
            s2g = 10.0 if num_id in gen_group_ids  else 0
            s3g =  9.0 if num_id in gen_pinta_ids  else 0
            s4  =  7.0 * (1 - (rs - 1) / N)
            s5  =  5.0 * (1 - (rd - 1) / N)
            ni  = n['num_int']
            # C7: bonus por coincidencia de dígitos (decena/unidad) con últimos 3 sorteos ±1
            s7  = 12.0 * ((1 if ni // 10 in digit_set else 0) + (1 if ni % 10 in digit_set else 0)) / 2
            # C8: penalización por recencia — baja calientes, hunde fríos
            if ni in recent_nums:
                s8 = -12.0
            elif ni in adjacent_nums:
                s8 = -6.0
            else:
                s8 = 0.0

            # Por turno (solo suma al turno correspondiente)
            s2t = 14.0 if num_id in turn_group_ids else 0
            s3t = 11.0 if num_id in turn_pinta_ids else 0
            s6  = 10.0 * (1 - (rc6 - 1) / N)

            scores.append({
                'name': n['name'],
                'score': round(s1 + s2g + s3g + s4 + s5 + s7 + s8 + s2t + s3t + s6, 1),
            })

        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores

    def _get_calientes_cebs(self, turn_day, pg_dow, week_seg, turn_mv, gen_mv, freq_field_type):
        """
        Algoritmo compartido para centenas y bola extra calientes.
        Combina atraso (turno + general) con frecuencia (día semana + semana del mes).
        Retorna los 4 mejores.
        """
        PG_DOW_CODE = {0: 'do', 1: 'lu', 2: 'ma', 3: 'mi', 4: 'ju', 5: 'vi', 6: 'sa'}
        week_day_code = PG_DOW_CODE[pg_dow]

        # Candidatos: top delayed del turno + top delayed general
        self.env.cr.execute(f"""
            SELECT centena, atraso AS atraso_turn, NULL::int AS atraso_gen FROM {turn_mv}
            UNION
            SELECT centena, NULL::int, atraso FROM {gen_mv}
        """)
        cands = {}
        for r in self.env.cr.dictfetchall():
            name = r['centena']
            if name not in cands:
                cands[name] = {'name': name, 'atraso_turn': 0, 'atraso_gen': 0, 'freq_dow': 0, 'freq_week': 0}
            if r['atraso_turn'] is not None:
                cands[name]['atraso_turn'] = r['atraso_turn'] or 0
            if r['atraso_gen'] is not None:
                cands[name]['atraso_gen'] = r['atraso_gen'] or 0

        if not cands:
            return []

        cand_names = list(cands.keys())

        self.env.cr.execute("""
            SELECT centena, total_salidas FROM lottery_centena_weekday_mv
            WHERE week_day = %s AND field_type = %s AND centena = ANY(%s)
        """, (week_day_code, freq_field_type, cand_names))
        for r in self.env.cr.dictfetchall():
            if r['centena'] in cands:
                cands[r['centena']]['freq_dow'] = r['total_salidas'] or 0

        self.env.cr.execute("""
            SELECT centena, total_salidas FROM lottery_centena_week_mv
            WHERE week_segment = %s AND field_type = %s AND centena = ANY(%s)
        """, (week_seg, freq_field_type, cand_names))
        for r in self.env.cr.dictfetchall():
            if r['centena'] in cands:
                cands[r['centena']]['freq_week'] = r['total_salidas'] or 0

        vals = list(cands.values())
        mx_turn = max((v['atraso_turn'] for v in vals), default=1) or 1
        mx_gen  = max((v['atraso_gen']  for v in vals), default=1) or 1
        mx_dow  = max((v['freq_dow']    for v in vals), default=1) or 1
        mx_week = max((v['freq_week']   for v in vals), default=1) or 1

        for v in vals:
            v['score'] = round(
                50.0 * v['atraso_turn'] / mx_turn +
                30.0 * v['atraso_gen']  / mx_gen  +
                15.0 * v['freq_dow']    / mx_dow  +
                 5.0 * v['freq_week']   / mx_week, 1
            )

        vals.sort(key=lambda x: x['score'], reverse=True)
        return [{'name': v['name']} for v in vals[:4]]

    def _get_frios_cebs(self, turn_day, output_id_field):
        """Devuelve las 4 centenas/bola extra que salieron más recientemente en el turno dado."""
        self.env.cr.execute(f"""
            SELECT n.name AS name
            FROM lottery_output lo
            JOIN lottery_number n ON n.id = lo.{output_id_field}
            WHERE lo.turn_day = %s AND lo.{output_id_field} IS NOT NULL
            GROUP BY lo.{output_id_field}, n.name
            ORDER BY MAX(lo.date) DESC
            LIMIT 4
        """, (turn_day,))
        return [{'name': r['name']} for r in self.env.cr.dictfetchall()]

    @api.model
    @tools.ormcache('today_str')
    def get_calientes_all(self, today_str):
        """Endpoint unificado: números, centenas y bola extra calientes para ambos turnos."""
        from datetime import date as _date
        today = _date.fromisoformat(today_str)
        pg_dow   = (today.weekday() + 1) % 7
        day      = today.day
        week_seg = (
            'sem_1' if day <= 7  else
            'sem_2' if day <= 14 else
            'sem_3' if day <= 21 else
            'sem_4' if day <= 28 else
            'sem_5'
        )

        # Fecha del próximo sorteo = última salida del turno + 1 día
        DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        self.env.cr.execute("""
            SELECT
                MAX(date) FILTER (WHERE turn_day = 'afternoon') + INTERVAL '1 day' AS next_afternoon,
                MAX(date) FILTER (WHERE turn_day = 'evening')   + INTERVAL '1 day' AS next_evening,
                (SELECT turn_day FROM lottery_output ORDER BY date DESC, id DESC LIMIT 1) AS last_turn
            FROM lottery_output
        """)
        row = self.env.cr.dictfetchone() or {}

        def _fmt_date(d):
            if not d:
                return ''
            return '%s %s' % (DAY_NAMES[d.weekday()], d.strftime('%d/%m/%Y'))

        result = {}
        for turn in ('afternoon', 'evening'):
            turn_cen_mv = 'lottery_top5_centena_dia_mv'    if turn == 'afternoon' else 'lottery_top5_centena_noche_mv'
            turn_be_mv  = 'lottery_top5_bola_extra_dia_mv' if turn == 'afternoon' else 'lottery_top5_bola_extra_noche_mv'
            next_date   = row.get('next_' + turn)
            all_scores  = self.get_numeros_calientes(turn, today_str)
            result[turn] = {
                'numbers':         all_scores[:30],
                'numbers_cold':    list(reversed(all_scores[-30:])),
                'centenas':        self._get_calientes_cebs(turn, pg_dow, week_seg, turn_cen_mv, 'lottery_top5_centena_general_mv',    'hundreds_id'),
                'centenas_cold':   self._get_frios_cebs(turn, 'hundreds_id'),
                'bola_extra':      self._get_calientes_cebs(turn, pg_dow, week_seg, turn_be_mv,  'lottery_top5_bola_extra_general_mv', 'fireball_id'),
                'bola_extra_cold': self._get_frios_cebs(turn, 'fireball_id'),
                'next_draw':       _fmt_date(next_date),
            }
        result['last_turn'] = row.get('last_turn') or 'afternoon'
        return result

