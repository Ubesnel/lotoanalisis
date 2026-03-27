from odoo import models, api
import calendar
from datetime import date, datetime
from odoo.addons.lottery_base.models.utils import MONTHS_DICT


class LotteryStatsService(models.AbstractModel):
    _name = 'lottery.stats.service'
    _description = 'Lottery Statistics Service'

    def _top(self, field, limit=30):
        return self.env['lottery.number'].search(
            [],
            order=f"{field} desc",
            limit=limit
        )

    def _bottom(self, field, limit=30):
        return self.env['lottery.number'].search(
            [],
            order=f"{field} asc",
            limit=limit
        )

    def dashboard_data(self):
        return {
            "top_general": self._top("total_salidas", 30),
            "bottom_general": self._bottom("total_salidas", 30),
            "top_dia": self._top("total_salidas_dia", 15),
            "top_noche": self._top("total_salidas_noche", 15),
            "top_atrasados": self._top("total_atrasadas", 15),
        }

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
        query = """
                WITH top10 AS (
                    SELECT id, name, total_atrasadas
                    FROM lottery_number
                    ORDER BY total_atrasadas DESC
                    LIMIT 10
                )
                SELECT                     
                    LPAD(t.name::text, 2, '0') as name,                    
                    TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha,
                    o.turn_day AS ultimo_turno,
                    t.total_atrasadas
                FROM top10 t
                LEFT JOIN LATERAL (
                    SELECT date, turn_day
                    FROM lottery_output
                    WHERE number_id = t.id
                    ORDER BY date DESC
                    LIMIT 1
                ) o ON TRUE
                ORDER BY t.total_atrasadas DESC;
            """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_10_dia(self):
        query = """
            WITH top10 AS (
                SELECT id, name, total_atrasadas_dia
                FROM lottery_number
                ORDER BY total_atrasadas_dia DESC
                LIMIT 10
            )
            SELECT                     
                LPAD(t.name::text, 2, '0') as name,
                t.total_atrasadas_dia as total_atrasadas,
                TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha
            FROM top10 t
            LEFT JOIN LATERAL (
                SELECT date
                FROM lottery_output
                WHERE number_id = t.id
                  AND turn_day = 'afternoon'
                ORDER BY date DESC
                LIMIT 1
            ) o ON TRUE
            ORDER BY t.total_atrasadas_dia DESC;
        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_10_noche(self):
        query = """
            WITH top10 AS (
                SELECT id, name, total_atrasadas_noche
                FROM lottery_number
                ORDER BY total_atrasadas_noche DESC
                LIMIT 10
            )
            SELECT                     
                LPAD(t.name::text, 2, '0') as name,
                t.total_atrasadas_noche as total_atrasadas,
                TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha,
                o.turn_day AS ultimo_turno
            FROM top10 t
            LEFT JOIN LATERAL (
                SELECT date, turn_day
                FROM lottery_output
                WHERE number_id = t.id
                  AND turn_day = 'evening'
                ORDER BY date DESC
                LIMIT 1
            ) o ON TRUE
            ORDER BY t.total_atrasadas_noche DESC;
        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def get_ultimas_salidas_por_dia(self, day):
        query = """
        SELECT
                TO_CHAR(lo.date, 'DD/MM/YYYY') as fecha,
                MAX(CASE WHEN lo.turn_day = 'afternoon' THEN c.name END) AS centena_dia,
                LPAD(MAX(CASE WHEN lo.turn_day = 'afternoon' THEN ln.name::text END), 2, '0') AS numero_dia,
                MAX(CASE WHEN lo.turn_day = 'afternoon' THEN be.name END) AS bola_extra_dia,
                MAX(CASE WHEN lo.turn_day = 'evening' THEN c.name END) AS centena_noche, 
                LPAD(MAX(CASE WHEN lo.turn_day = 'evening' THEN ln.name::text END), 2, '0') AS numero_noche,
                MAX(CASE WHEN lo.turn_day = 'evening' THEN be.name END) AS bola_extra_noche
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            join lottery_number c on (c.id=lo.hundreds_id)
            left join lottery_number be on (be.id=lo.fireball_id)
            WHERE lo.week_day = %s
            GROUP BY lo.date
            ORDER BY lo.date DESC
            LIMIT 8;
        """
        self.env.cr.execute(query, (day,))
        records = self.env.cr.dictfetchall()
        records.sort(key=lambda x: datetime.strptime(x['fecha'], '%d/%m/%Y'))
        return records

    def build_calendar(self, month, year, records):
        cal = calendar.Calendar(firstweekday=0)
        data_by_day = {}
        for r in records:
            day = r.get('date').day
            if day not in data_by_day:
                data_by_day[day] = {'dia': None, 'noche': None}

            if r.get('turn_day') == 'afternoon':
                data_by_day[day]['dia'] = (r.get('centena'), str(r.get('numero')).zfill(2), r.get('bola_extra'))
            else:
                data_by_day[day]['noche'] = (r.get('centena'), str(r.get('numero')).zfill(2), r.get('bola_extra'))

        month_days = cal.monthdayscalendar(year, month)

        result = []

        for week in month_days:
            for day in week:
                if day == 0:
                    result.append({
                        'empty': True
                    })
                else:
                    result.append({
                        'empty': False,
                        'day': day,
                        'dia_numero': data_by_day.get(day, {}).get('dia'),
                        'noche_numero': data_by_day.get(day, {}).get('noche'),
                    })

        return result

    def build_calendar_weeks(self, calendar_build):
        weeks = []

        for i in range(0, len(calendar_build), 7):
            week = calendar_build[i:i + 7]
            if len(week) < 7:
                week += [{'empty': True}] * (7 - len(week))

            weeks.append(week)

        return weeks

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
            WITH top10 AS (
                SELECT id, name, {field_name} AS total_atrasadas
                FROM lottery_number
                ORDER BY {field_name} DESC
                LIMIT 10
            )
            SELECT
                LPAD(t.name::text, 2, '0') as name,
                TO_CHAR(o.date, 'DD/MM/YYYY') AS ultima_fecha,
                o.turn_day AS ultimo_turno,
                t.total_atrasadas
            FROM top10 t
            LEFT JOIN LATERAL (
                SELECT date, turn_day
                FROM lottery_output
                WHERE number_id = t.id
                  AND week_day = %s
                ORDER BY date DESC
                LIMIT 1
            ) o ON TRUE
            ORDER BY t.total_atrasadas DESC;
        """

        self.env.cr.execute(query, (week_code,))
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_centenas_afternoon(self):
        query = """WITH calendar AS (
                    SELECT generate_series(
                        (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                        (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                        interval '1 day'
                    )::date AS draw_date
                ),
            centena_last AS (
                SELECT hundreds_id, MAX(date) AS last_date
                FROM lottery_output
                WHERE turn_day = 'afternoon'
                GROUP BY hundreds_id
            )
            SELECT
                n.name AS centena,
                COUNT(c.draw_date) AS atraso
            FROM centena_last l
            JOIN lottery_number n ON n.id = l.hundreds_id
            JOIN calendar c
                ON c.draw_date > l.last_date
            LEFT JOIN lottery_output lo
                ON lo.hundreds_id = l.hundreds_id
               AND lo.turn_day = 'afternoon'
               AND lo.date = c.draw_date
            WHERE lo.id IS NULL
            GROUP BY n.name
            ORDER BY atraso desc
            limit 5;
                    """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_centenas_evening(self):
        query = """WITH calendar AS (
                        SELECT generate_series(
                            (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'evening'),
                            (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'evening'),
                            interval '1 day'
                        )::date AS draw_date
                    ),
                centena_last AS (
                    SELECT hundreds_id, MAX(date) AS last_date
                    FROM lottery_output
                    WHERE turn_day = 'evening'
                    GROUP BY hundreds_id
                )
                SELECT
                    n.name AS centena,
                    COUNT(c.draw_date) AS atraso
                FROM centena_last l
                JOIN lottery_number n ON n.id = l.hundreds_id
                JOIN calendar c
                    ON c.draw_date > l.last_date
                LEFT JOIN lottery_output lo
                    ON lo.hundreds_id = l.hundreds_id
                   AND lo.turn_day = 'evening'
                   AND lo.date = c.draw_date
                WHERE lo.id IS NULL
                GROUP BY n.name
                ORDER BY atraso desc
                limit 5;
                        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_centenas_general(self):
        query = """WITH turn_order AS (
                    SELECT 'afternoon' AS turn_day, 2 AS order_num
                    UNION ALL
                    SELECT 'evening', 3
                ),
                centena_last AS (   
                    SELECT lo.hundreds_id, lo.date AS last_date, lo.turn_day AS last_turn,
                           t.order_num AS last_turn_order
                    FROM lottery_output lo
                    JOIN turn_order t ON t.turn_day = lo.turn_day
                    WHERE (lo.hundreds_id, lo.date, lo.turn_day) IN (
                        SELECT hundreds_id, date, turn_day
                        FROM (
                            SELECT hundreds_id, date, turn_day,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY hundreds_id
                                       ORDER BY date DESC, 
                                                CASE turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END DESC
                                   ) AS rn
                            FROM lottery_output
                            WHERE turn_day IN ('afternoon','evening')
                        ) sub
                        WHERE rn = 1
                    )
                )
                SELECT
                    n.name AS centena,
                    COUNT(*) AS atraso
                FROM centena_last l
                JOIN lottery_number n ON n.id = l.hundreds_id
                JOIN lottery_output lo
                    ON lo.turn_day IN ('afternoon','evening')
                   AND ((lo.date > l.last_date) 
                        OR (lo.date = l.last_date AND
                            CASE lo.turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END > l.last_turn_order))
                   AND lo.hundreds_id <> l.hundreds_id
                GROUP BY n.name
                ORDER BY atraso DESC
                LIMIT 5;
                            """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_atrasos_lineas(self, type):
        query = """
            WITH params AS (
                    SELECT %s::text AS tipo
                )
            SELECT
                CASE lg.code
                    WHEN 'line_0' THEN '00-09'
                    WHEN 'line_1' THEN '10-19'
                    WHEN 'line_2' THEN '20-29'
                    WHEN 'line_3' THEN '30-39'
                    WHEN 'line_4' THEN '40-49'
                    WHEN 'line_5' THEN '50-59'
                    WHEN 'line_6' THEN '60-69'
                    WHEN 'line_7' THEN '70-79'
                    WHEN 'line_8' THEN '80-89'
                    WHEN 'line_9' THEN '90-99'
                END AS name,
                CASE p.tipo
                    WHEN 'general' THEN lg.salidas_atrasadas
                    WHEN 'afternoon' THEN lg.salidas_atrasadas_dia
                    WHEN 'evening' THEN lg.salidas_atrasadas_noche
                END AS atraso
            FROM lottery_group lg
            CROSS JOIN params p
            WHERE lg.code IN (
                'line_0','line_1','line_2','line_3','line_4',
                'line_5','line_6','line_7','line_8','line_9'
            )
            ORDER BY atraso DESC;
        """
        self.env.cr.execute(query, (type,))
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_atrasos_terminales(self, type):
        query = """
                WITH params AS (
                        SELECT %s::text AS tipo
                    )
                SELECT
                    CASE lg.code
                        WHEN 'terminal_0' THEN '00-90'
                        WHEN 'terminal_1' THEN '01-91'
                        WHEN 'terminal_2' THEN '02-92'
                        WHEN 'terminal_3' THEN '03-93'
                        WHEN 'terminal_4' THEN '04-94'
                        WHEN 'terminal_5' THEN '05-95'
                        WHEN 'terminal_6' THEN '06-96'
                        WHEN 'terminal_7' THEN '07-97'
                        WHEN 'terminal_8' THEN '08-98'
                        WHEN 'terminal_9' THEN '09-99'
                    END AS name,
                    CASE p.tipo
                        WHEN 'general' THEN lg.salidas_atrasadas
                        WHEN 'afternoon' THEN lg.salidas_atrasadas_dia
                        WHEN 'evening' THEN lg.salidas_atrasadas_noche
                    END AS atraso
                FROM lottery_group lg
                CROSS JOIN params p
                WHERE lg.code IN (
                    'terminal_0','terminal_1','terminal_2','terminal_3','terminal_4',
                    'terminal_5','terminal_6','terminal_7','terminal_8','terminal_9'
                )
                ORDER BY atraso DESC;
            """
        self.env.cr.execute(query, (type,))
        return self.env.cr.dictfetchall()

    @api.model
    def get_top_atrasos_number_groups(self, type, groups_code):
        query = """
            WITH params AS (
                SELECT %s::text AS tipo
            )
            SELECT
                LPAD(ln.name::text, 2, '0') as name,                
                CASE p.tipo
                    WHEN 'general' THEN ln.total_atrasadas
                    WHEN 'afternoon' THEN ln.total_atrasadas_dia
                    WHEN 'evening' THEN ln.total_atrasadas_noche
                END AS atraso
            FROM lottery_group lg
            JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
            JOIN lottery_number ln ON ln.id = rel.number_id
            CROSS JOIN params p
            WHERE lg.code = ANY(%s)
            ORDER BY atraso DESC;
                """
        self.env.cr.execute(query, (type, groups_code))
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_bola_extra_afternoon(self):
        query = """WITH calendar AS (
                        SELECT generate_series(
                            (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                            (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'afternoon'),
                            interval '1 day'
                        )::date AS draw_date
                    ),
                centena_last AS (
                    SELECT fireball_id, MAX(date) AS last_date
                    FROM lottery_output
                    WHERE turn_day = 'afternoon'
                    GROUP BY fireball_id
                )
                SELECT
                    n.name AS centena,
                    COUNT(c.draw_date) AS atraso
                FROM centena_last l
                JOIN lottery_number n ON n.id = l.fireball_id
                JOIN calendar c
                    ON c.draw_date > l.last_date
                LEFT JOIN lottery_output lo
                    ON lo.fireball_id = l.fireball_id
                   AND lo.turn_day = 'afternoon'
                   AND lo.date = c.draw_date
                WHERE lo.id IS NULL
                GROUP BY n.name
                ORDER BY atraso desc
                limit 5;
                        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_bola_extra_evening(self):
        query = """WITH calendar AS (
                            SELECT generate_series(
                                (SELECT MIN(date) FROM lottery_output WHERE turn_day = 'evening'),
                                (SELECT MAX(date) FROM lottery_output WHERE turn_day = 'evening'),
                                interval '1 day'
                            )::date AS draw_date
                        ),
                    centena_last AS (
                        SELECT fireball_id, MAX(date) AS last_date
                        FROM lottery_output
                        WHERE turn_day = 'evening'
                        GROUP BY fireball_id
                    )
                    SELECT
                        n.name AS centena,
                        COUNT(c.draw_date) AS atraso
                    FROM centena_last l
                    JOIN lottery_number n ON n.id = l.fireball_id
                    JOIN calendar c
                        ON c.draw_date > l.last_date
                    LEFT JOIN lottery_output lo
                        ON lo.fireball_id = l.fireball_id
                       AND lo.turn_day = 'evening'
                       AND lo.date = c.draw_date
                    WHERE lo.id IS NULL
                    GROUP BY n.name
                    ORDER BY atraso desc
                    limit 5;
                            """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def get_top5_bola_extra_general(self):
        query = """WITH turn_order AS (
                        SELECT 'afternoon' AS turn_day, 2 AS order_num
                        UNION ALL
                        SELECT 'evening', 3
                    ),
                    centena_last AS (   
                        SELECT lo.fireball_id, lo.date AS last_date, lo.turn_day AS last_turn,
                               t.order_num AS last_turn_order
                        FROM lottery_output lo
                        JOIN turn_order t ON t.turn_day = lo.turn_day
                        WHERE (lo.fireball_id, lo.date, lo.turn_day) IN (
                            SELECT fireball_id, date, turn_day
                            FROM (
                                SELECT fireball_id, date, turn_day,
                                       ROW_NUMBER() OVER (
                                           PARTITION BY fireball_id
                                           ORDER BY date DESC, 
                                                    CASE turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END DESC
                                       ) AS rn
                                FROM lottery_output
                                WHERE turn_day IN ('afternoon','evening')
                            ) sub
                            WHERE rn = 1
                        )
                    )
                    SELECT
                        n.name AS centena,
                        COUNT(*) AS atraso
                    FROM centena_last l
                    JOIN lottery_number n ON n.id = l.fireball_id
                    JOIN lottery_output lo
                        ON lo.turn_day IN ('afternoon','evening')
                       AND ((lo.date > l.last_date) 
                            OR (lo.date = l.last_date AND
                                CASE lo.turn_day WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 END > l.last_turn_order))
                       AND lo.fireball_id <> l.fireball_id
                    GROUP BY n.name
                    ORDER BY atraso DESC
                    LIMIT 5;
                                """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()