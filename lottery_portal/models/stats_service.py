# -*- coding: utf-8 -*-

from odoo import models, api
import calendar
from datetime import date, datetime
from odoo.addons.lottery_base.models.utils import MONTHS_DICT


class LotteryStatsService(models.AbstractModel):
    _name = 'lottery.stats.service'
    _description = 'Lottery Statistics Service'

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
    def get_top_10_general(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_mv""")
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_10_dia(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_afternoon_mv""")
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_10_noche(self):
        self.env.cr.execute("""SELECT * FROM lottery_top10_evening_mv""")
        return self.env.cr.dictfetchall()

    def get_ultimas_salidas_por_dia(self, day):
        self.env.cr.execute("""
                SELECT *
                FROM lottery_ultima_salida_dia_semana_mv
                WHERE week_day = %s
                ORDER BY date DESC
                LIMIT 8
            """, (day,))
        records = self.env.cr.dictfetchall()
        records.sort(key=lambda x: datetime.strptime(x['fecha'], '%d/%m/%Y'))
        return records

    def get_month_year(self, month, year):
        if not month:
            month = str(date.today().month)
        if not year:
            year = date.today().year
        return '%s %s' % (MONTHS_DICT[month], year)

    @api.model
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
    def get_top5_centenas_afternoon(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_dia_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_centenas_evening(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_centena_noche_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_centenas_general(self):
        self.env.cr.execute("""
                SELECT centena, atraso
                FROM lottery_top5_centena_general_mv ORDER BY atraso DESC;                
            """)
        return self.env.cr.dictfetchall()

    @api.model
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
    def get_top5_bola_extra_afternoon(self):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_dia_mv ORDER BY atraso DESC;                
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_bola_extra_evening(self):
        self.env.cr.execute("""
                                SELECT centena, atraso
                                FROM lottery_top5_bola_extra_noche_mv ORDER BY atraso DESC;                
                                """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_bola_extra_general(self):
        self.env.cr.execute("""
                        SELECT centena, atraso
                        FROM lottery_top5_bola_extra_general_mv ORDER BY atraso DESC;                
                    """)
        return self.env.cr.dictfetchall()