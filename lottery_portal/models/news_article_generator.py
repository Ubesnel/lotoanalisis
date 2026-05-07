# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.addons.lottery_base.models.utils import MONTHS_DICT
import base64
import calendar
import os
from datetime import date

WEEKDAYS = [
    ('lu', 'Lunes'),
    ('ma', 'Martes'),
    ('mi', 'Miércoles'),
    ('ju', 'Jueves'),
    ('vi', 'Viernes'),
    ('sa', 'Sábado'),
    ('do', 'Domingo'),
]

WEEKS = [
    ('sem_1', 'Primera Semana (días 1–7)'),
    ('sem_2', 'Segunda Semana (días 8–14)'),
    ('sem_3', 'Tercera Semana (días 15–21)'),
    ('sem_4', 'Cuarta Semana (días 22–28)'),
    ('sem_5', 'Del 29 al 31'),
]


class NewsArticleGenerator(models.Model):
    _inherit = 'news.article'

    def _load_cover_image(self, filename):
        img_path = os.path.join(
            os.path.dirname(__file__), '..', 'static', 'src', 'img', filename
        )
        img_path = os.path.normpath(img_path)
        if not os.path.exists(img_path):
            return False
        with open(img_path, 'rb') as f:
            return base64.b64encode(f.read())

    @api.model
    def cron_generate_monthly_analysis(self, ref_date=None):
        if ref_date:
            if isinstance(ref_date, str):
                from datetime import datetime
                today = datetime.strptime(ref_date, '%Y-%m-%d').date()
            else:
                today = ref_date
        else:
            today = date.today()
            last_day = calendar.monthrange(today.year, today.month)[1]
            if today.day != last_day:
                return

        cur_month = today.month
        cur_year = today.year

        if cur_month == 12:
            next_month, next_year = 1, cur_year + 1
        else:
            next_month, next_year = cur_month + 1, cur_year

        self._generate_top_article(next_month, next_year)
        self._generate_bottom_article(next_month, next_year)

    def _generate_top_article(self, next_month, next_year):
        month_name = MONTHS_DICT[str(next_month)]
        title = f'Números que más han salido en {month_name} históricamente, análisis para sorteos de {month_name} del año {next_year}'

        existing = self.env['news.article'].sudo().search([('title', '=', title)], limit=1)
        if existing:
            return

        self.env.cr.execute("""
            SELECT COUNT(*) AS total_sorteos, COUNT(DISTINCT year) AS total_anios
            FROM lottery_output WHERE month = %s
        """, (str(next_month),))
        row = self.env.cr.dictfetchone()
        total_sorteos = row['total_sorteos'] or 0
        total_anios = row['total_anios'] or 0

        stats = self.env['lottery.stats.service'].sudo()
        top30 = stats.get_top_numbers_month(next_month, next_year)

        weekday_data = {code: stats.get_top_numbers_by_week_day(code)[:8] for code, _ in WEEKDAYS}

        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, total_salidas_dia AS total
            FROM lottery_number ORDER BY total_salidas_dia DESC, id DESC LIMIT 10
        """)
        top_tarde = self.env.cr.dictfetchall()

        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, total_salidas_noche AS total
            FROM lottery_number ORDER BY total_salidas_noche DESC, id DESC LIMIT 10
        """)
        top_noche = self.env.cr.dictfetchall()

        week_data = {code: stats.get_top_numbers_by_week(code)[:8] for code, _ in WEEKS}

        top30_ausentes = stats.get_top_numbers_month_info(str(next_month), top30)[:5]

        companions = {}
        for num in top30:
            companions[num['name']] = stats.get_salidas_numeros_despues_numero(num['id'])[:5]

        raw_html = self._build_analysis_html(
            month_name=month_name,
            next_year=next_year,
            total_sorteos=total_sorteos,
            total_anios=total_anios,
            top30=top30,
            top30_ausentes=top30_ausentes,
            weekday_data=weekday_data,
            top_tarde=top_tarde,
            top_noche=top_noche,
            week_data=week_data,
            companions=companions,
        )

        category = self.env.ref('lottery_portal.news_category_numeros_salidores_mes')
        cover = self._load_cover_image('numeros salidores mes.png')

        self.env['news.article'].sudo().create({
            'title': title,
            'category_id': category.id,
            'raw_html': raw_html,
            'is_published': False,
            'cover_image': cover or False,
        })

    # ─────────────────────────── HTML builder ───────────────────────────

    def _build_analysis_html(self, month_name, next_year,
                              total_sorteos, total_anios, top30, top30_ausentes,
                              weekday_data, top_tarde, top_noche,
                              week_data, companions):
        parts = []

        def ball_color(rank):
            if rank <= 10:
                return 'ball-red'
            if rank <= 20:
                return 'ball-blue'
            return 'ball-green'

        def ball_color_turn(pos):
            if pos <= 3:
                return 'ball-red'
            if pos <= 7:
                return 'ball-blue'
            return 'ball-green'

        def ball_color_week(pos):
            if pos <= 3:
                return 'ball-red'
            if pos <= 5:
                return 'ball-blue'
            return 'ball-green'

        def ball_color_companion(pos):
            if pos <= 2:
                return 'ball-red'
            if pos == 3:
                return 'ball-blue'
            return 'ball-green'

        # Solo estilos de layout que no existen en dashboard_numbers.css
        css = """
        <style>
        .ma-intro { background: linear-gradient(135deg,#6f4a8e,#9b59b6); color:#fff; border-radius:12px; padding:24px 28px; margin-bottom:28px; }
        .ma-intro h2 { margin:0 0 8px; font-size:1.5rem; font-weight:700; }
        .ma-intro p  { margin:0; font-size:1rem; line-height:1.6; opacity:.92; }
        .ma-section  { margin-bottom:32px; }
        .ma-section-title { font-size:1.15rem; font-weight:700; color:#4a2c6e; border-left:4px solid #9b59b6; padding-left:12px; margin-bottom:8px; }
        .ma-section-desc  { color:#6c6c6c; margin-bottom:14px; font-size:.93rem; }
        .ma-grid-3 { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:14px; }
        .ma-grid-2 { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }
        </style>
        """
        parts.append(css)

        # ── Intro ─────────────────────────────────────────────────────────
        parts.append(
            f'<div class="ma-intro">'            
            f'<p>Se analizaron un total de <strong>{total_sorteos:,}</strong> sorteos registrados '
            f'en el mes de <strong>{month_name}</strong> durante <strong>{total_anios}</strong> años, '
            f'con el objetivo de identificar cuáles fueron los números con mayor cantidad de salidas. '
            f'A continuación se brinda información variada sobre los mismos.</p>'
            f'</div>'
        )

        # ── Top 30 ────────────────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            f'<div class="card shadow border-0">'
            f'<div class="card-header text-white fw-bold num-card-hot d-flex justify-content-between align-items-center">'
            f'<span>&#128293; Números que más salen en {month_name}</span>'
            f'</div>'
            f'<div class="card-body p-2 balls-no-zoom">'
            f'<div style="display:grid;grid-template-columns:repeat(10,1fr);gap:6px;justify-items:center;">'
        )
        for n in top30:
            num_name = n['name']
            num_total = n['total']
            bc = ball_color(n['rank'])
            parts.append(
                f'<span class="ball {bc}" title="Salidas históricas en {month_name}: {num_total}">{num_name}</span>'
            )
        parts.append('</div>')  # grid
        parts.append('</div>')  # card-body
        parts.append('</div>')  # card

        # ── Análisis de ausentes ──────────────────────────────────────────
        turn_label_map = {'afternoon': 'Tarde', 'evening': 'Noche'}
        turn_icon_map  = {'afternoon': 'fa-sun-o', 'evening': 'fa-moon-o'}
        turn_color_map = {'afternoon': '#d97706', 'evening': '#1e3a5f'}

        if top30_ausentes:
            parts.append(
                f'<div class="mt-3">'
                f'<p class="ma-section-title" style="font-size:1rem;">'
                f'<i class="fa fa-clock-o"></i>&nbsp; '
                f'Números del conjunto que más tiempo llevan sin salir en {month_name}</p>'
                f'<p class="ma-section-desc">'
                f'A pesar de ser los más salidores históricos de {month_name}, estos números llevan varios años '
                f'sin aparecer en este mes. Se indica la última fecha registrada, el día de la semana y el turno.</p>'
                f'<div class="stat-rank-list">'
            )
            for i, a in enumerate(top30_ausentes, 1):
                a_name = a.get('name', '—')
                a_date = a.get('last_date', '—')
                a_day  = a.get('week_day_label', '')
                a_turn = a.get('turn_day', '')
                a_years = a.get('years_without_month', 0)
                t_label = turn_label_map.get(a_turn, '—')
                t_icon  = turn_icon_map.get(a_turn, 'fa-circle')
                t_color = turn_color_map.get(a_turn, '#888')
                years_txt = f'{a_years} año{"s" if a_years != 1 else ""}'
                parts.append(
                    f'<div class="stat-rank-item">'
                    f'<span class="stat-rank-pos">#{i}</span>'
                    f'<span class="ball ball-lila stat-rank-ball">{a_name}</span>'
                    f'<div class="stat-rank-info">'
                    f'<span class="stat-rank-count">{years_txt} sin salir</span>'
                    f'<span class="stat-rank-date">'
                    f'<i class="fa fa-calendar-o"></i> {a_date} {a_day}'
                    f'&nbsp;&nbsp;<i class="fa {t_icon}" style="color:{t_color};"></i> {t_label}'
                    f'</span>'
                    f'</div>'
                    f'</div>'
                )
            parts.append('</div>')  # stat-rank-list
            parts.append('</div>')  # mt-3

        parts.append('</div>')  # ma-section

        # ── Por Día de la Semana ──────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Top 8 por Día de la Semana</p>'
            '<p class="ma-section-desc">Los 8 números que más han salido en cada día de la semana a lo largo de toda la historia registrada.</p>'
        )
        parts.append(
            '<div class="card border-0 shadow-sm">'
            '<div class="card-body p-2" style="overflow-x:auto;">'
            '<table class="table table-sm mb-0" style="text-align:center;min-width:520px;">'
            '<thead><tr>'
            '<th style="color:#8c6ca8;font-weight:700;width:28px;">#</th>'
        )
        for _, label in WEEKDAYS:
            parts.append(f'<th style="color:#8c6ca8;font-weight:700;">{label}</th>')
        parts.append('</tr></thead><tbody>')

        for pos in range(1, 9):
            parts.append('<tr>')
            parts.append(f'<td class="stat-rank-pos">#{pos}</td>')
            for code, _ in WEEKDAYS:
                nums = weekday_data.get(code, [])
                if pos <= len(nums):
                    num_name = nums[pos - 1]['name']
                    bc = ball_color_week(pos)
                    parts.append(f'<td><span class="ball {bc}">{num_name}</span></td>')
                else:
                    parts.append('<td>—</td>')
            parts.append('</tr>')

        parts.append('</tbody></table>')
        parts.append('</div></div>')
        parts.append('</div>')

        # ── Tarde y Noche ────────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Más Salidores por Turno</p>'
            '<p class="ma-section-desc">Números con mayor cantidad de apariciones totales según el turno del sorteo, considerando toda la historia disponible.</p>'
        )
        parts.append('<div class="ma-grid-2">')
        for label, icon_class, hdr_bg, icon_color, data in [
            ('Tarde', 'fa-sun-o',  'linear-gradient(135deg,#f59e0b,#d97706)', '#fff', top_tarde),
            ('Noche', 'fa-moon-o', 'linear-gradient(135deg,#1e3a5f,#2d5a8e)', '#fff', top_noche),
        ]:
            groups = [data[:3], data[3:7], data[7:]]
            parts.append(
                f'<div class="card border-0 shadow-sm">'
                f'<div class="card-header py-2 px-3" style="background:{hdr_bg};color:{icon_color};">'
                f'<i class="fa {icon_class}" style="color:{icon_color};"></i>'
                f'<span style="font-weight:700;font-size:.95rem;margin-left:6px;">{label}</span>'
                f'</div>'
                f'<div class="card-body p-2 balls-no-zoom">'
            )
            offset = 1
            for group in groups:
                if group:
                    parts.append('<div style="display:flex;gap:6px;justify-content:space-evenly;margin-bottom:6px;">')
                    for n in group:
                        bc = ball_color_turn(offset)
                        parts.append(f'<span class="ball {bc}" title="#{offset}">{n["name"]}</span>')
                        offset += 1
                    parts.append('</div>')
            parts.append('</div></div>')
        parts.append('</div>')
        parts.append('</div>')

        # ── Por Semana del Mes ────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Más Salidores por Semana del Mes</p>'
            '<p class="ma-section-desc">Los números que más han salido según la semana en la que cae el sorteo. La quinta semana comprende los días 29, 30 y 31.</p>'
        )
        parts.append('<div class="ma-grid-3">')
        for code, label in WEEKS:
            nums = week_data.get(code, [])
            parts.append(
                f'<div class="card border-0 shadow-sm">'
                f'<div class="card-header py-2 px-3" style="background:linear-gradient(135deg,#6f4a8e,#9b59b6);color:#fff;">'
                f'<span style="font-weight:700;font-size:.9rem;">{label}</span>'
                f'</div>'
                f'<div class="card-body p-2 balls-no-zoom">'
            )
            if nums:
                groups = [nums[:3], nums[3:5], nums[5:]]
                offset = 1
                for group in groups:
                    if group:
                        parts.append('<div style="display:flex;gap:6px;justify-content:space-evenly;margin-bottom:6px;">')
                        for n in group:
                            bc = ball_color_week(offset)
                            parts.append(f'<span class="ball {bc}" title="#{offset}">{n["name"]}</span>')
                            offset += 1
                        parts.append('</div>')
            else:
                parts.append('<p class="text-muted small mb-0">Sin datos</p>')
            parts.append('</div></div>')
        parts.append('</div>')
        parts.append('</div>')

        # ── Acompañantes Posteriores ──────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Acompañantes Posteriores de los Números del Mes</p>'
            '<p class="ma-section-desc">Para cada uno de los 30 números más salidores del mes se muestran los '
            '5 números que más frecuentemente han salido inmediatamente después en el historial de sorteos.</p>'
        )
        parts.append('<div class="ma-grid-2">')
        for num in top30:
            name = num['name']
            comps = companions.get(name, [])
            color = ball_color(num['rank'])
            parts.append(
                f'<div class="card border-0 shadow-sm mb-1">'
                f'<div class="card-body py-2 px-3 d-flex align-items-center gap-2 flex-wrap">'
                f'<span class="ball {color}" style="flex-shrink:0;">{name}</span>'
                f'<span class="stat-rank-count me-2">{num["total"]} salidas en {month_name}</span>'
            )
            if comps:
                parts.append('<div class="d-flex gap-2 flex-wrap align-items-center ms-auto">')
                for ci, c in enumerate(comps, 1):
                    c_name = c['name']
                    parts.append(
                        f'<span class="ball {ball_color_companion(ci)}">{c_name}</span>'
                    )
                parts.append('</div>')
            else:
                parts.append('<span class="text-muted small">Sin datos</span>')
            parts.append('</div></div>')
        parts.append('</div>')
        parts.append('</div>')

        return ''.join(parts)

    # ─────────────────────── Bottom article ─────────────────────────────

    def _generate_bottom_article(self, next_month, next_year):
        month_name = MONTHS_DICT[str(next_month)]
        title = f'Números que menos han salido en {month_name} históricamente, análisis para sorteos de {month_name} del año {next_year}'

        existing = self.env['news.article'].sudo().search([('title', '=', title)], limit=1)
        if existing:
            return

        self.env.cr.execute("""
            SELECT COUNT(*) AS total_sorteos, COUNT(DISTINCT year) AS total_anios
            FROM lottery_output WHERE month = %s
        """, (str(next_month),))
        row = self.env.cr.dictfetchone()
        total_sorteos = row['total_sorteos'] or 0
        total_anios = row['total_anios'] or 0

        stats = self.env['lottery.stats.service'].sudo()
        bottom30 = stats.get_bottom_numbers_month(next_month, next_year)

        # Numbers with least time without appearing (recently appeared — could appear again)
        self.env.cr.execute("""
            SELECT DISTINCT ON (number_id)
                LPAD(ln.name::text, 2, '0') AS name,
                lo.date,
                TO_CHAR(lo.date, 'DD/MM/YYYY') AS last_date,
                (CURRENT_DATE - lo.date) AS days_since
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.number_id
            WHERE lo.month = %s
            ORDER BY number_id, lo.date DESC
        """, (str(next_month),))
        all_last = self.env.cr.dictfetchall()
        all_last_sorted = sorted(all_last, key=lambda x: x['days_since'])
        recent5 = all_last_sorted[:5]
        overdue5 = all_last_sorted[-5:][::-1]

        weekday_data = {code: stats.get_bottom_numbers_by_week_day(code)[:8] for code, _ in WEEKDAYS}

        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, total_salidas_dia AS total
            FROM lottery_number ORDER BY total_salidas_dia ASC, id ASC LIMIT 10
        """)
        bottom_tarde = self.env.cr.dictfetchall()

        self.env.cr.execute("""
            SELECT LPAD(name::text, 2, '0') AS name, total_salidas_noche AS total
            FROM lottery_number ORDER BY total_salidas_noche ASC, id ASC LIMIT 10
        """)
        bottom_noche = self.env.cr.dictfetchall()

        week_data = {code: stats.get_bottom_numbers_by_week(code)[:8] for code, _ in WEEKS}

        raw_html = self._build_analysis_bottom_html(
            month_name=month_name,
            next_year=next_year,
            total_sorteos=total_sorteos,
            total_anios=total_anios,
            bottom30=bottom30,
            recent5=recent5,
            overdue5=overdue5,
            weekday_data=weekday_data,
            bottom_tarde=bottom_tarde,
            bottom_noche=bottom_noche,
            week_data=week_data,
        )

        category = self.env.ref('lottery_portal.news_category_numeros_salidores_mes')
        cover = self._load_cover_image('numeros menos salidores mes.png')

        self.env['news.article'].sudo().create({
            'title': title,
            'category_id': category.id,
            'raw_html': raw_html,
            'is_published': False,
            'cover_image': cover or False,
        })

    # ─────────────────────── Bottom HTML builder ────────────────────────

    def _build_analysis_bottom_html(self, month_name, next_year,
                                     total_sorteos, total_anios, bottom30,
                                     recent5, overdue5,
                                     weekday_data, bottom_tarde, bottom_noche,
                                     week_data):
        parts = []

        def ball_color(rank):
            if rank <= 10:
                return 'ball-red'
            if rank <= 20:
                return 'ball-blue'
            return 'ball-green'

        def ball_color_turn(pos):
            if pos <= 3:
                return 'ball-red'
            if pos <= 7:
                return 'ball-blue'
            return 'ball-green'

        def ball_color_week(pos):
            if pos <= 3:
                return 'ball-red'
            if pos <= 5:
                return 'ball-blue'
            return 'ball-green'

        css = """
        <style>
        .ma-intro { background: linear-gradient(135deg,#6f4a8e,#9b59b6); color:#fff; border-radius:12px; padding:24px 28px; margin-bottom:28px; }
        .ma-intro h2 { margin:0 0 8px; font-size:1.5rem; font-weight:700; }
        .ma-intro p  { margin:0; font-size:1rem; line-height:1.6; opacity:.92; }
        .ma-section  { margin-bottom:32px; }
        .ma-section-title { font-size:1.15rem; font-weight:700; color:#4a2c6e; border-left:4px solid #9b59b6; padding-left:12px; margin-bottom:8px; }
        .ma-section-desc  { color:#6c6c6c; margin-bottom:14px; font-size:.93rem; }
        .ma-grid-3 { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:14px; }
        .ma-grid-2 { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }
        </style>
        """
        parts.append(css)

        # ── Intro ─────────────────────────────────────────────────────────
        parts.append(
            f'<div class="ma-intro">'
            f'<p>Se analizaron un total de <strong>{total_sorteos:,}</strong> sorteos registrados '
            f'en el mes de <strong>{month_name}</strong> durante <strong>{total_anios}</strong> años. '
            f'A continuación se presentan los números con <strong>menor</strong> cantidad de apariciones '
            f'históricas en este mes, junto con información sobre su última aparición reciente y los que '
            f'llevan más tiempo sin salir.</p>'
            f'</div>'
        )

        # ── Bottom 30 ─────────────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            f'<div class="card shadow border-0">'
            f'<div class="card-header text-white fw-bold num-card-hot d-flex justify-content-between align-items-center">'
            f'<span>&#128269; Números que menos salen en {month_name}</span>'
            f'</div>'
            f'<div class="card-body p-2 balls-no-zoom">'
            f'<div style="display:grid;grid-template-columns:repeat(10,1fr);gap:6px;justify-items:center;">'
        )
        for n in bottom30:
            num_name = n['name']
            num_total = n['total']
            bc = ball_color(n['rank'])
            parts.append(
                f'<span class="ball {bc}" title="Salidas históricas en {month_name}: {num_total}">{num_name}</span>'
            )
        parts.append('</div>')  # grid
        parts.append('</div>')  # card-body
        parts.append('</div>')  # card

        # ── Menos tiempo sin salir (salieron hace poco) ───────────────────
        if recent5:
            parts.append(
                f'<div class="mt-3">'
                f'<p class="ma-section-title" style="font-size:1rem;">'
                f'<i class="fa fa-history"></i>&nbsp; '
                f'Números del conjunto que menos tiempo llevan sin salir en {month_name}</p>'
                f'<p class="ma-section-desc">'
                f'Aunque son de los que menos salen en este mes, estos números aparecieron hace relativamente poco. '
                f'Su aparición reciente puede ser una señal de actividad.</p>'
                f'<div class="stat-rank-list">'
            )
            for i, a in enumerate(recent5, 1):
                a_name = a.get('name', '—')
                a_date = a.get('last_date', '—')
                days = a.get('days_since', 0)
                parts.append(
                    f'<div class="stat-rank-item">'
                    f'<span class="stat-rank-pos">#{i}</span>'
                    f'<span class="ball ball-lila stat-rank-ball">{a_name}</span>'
                    f'<div class="stat-rank-info">'
                    f'<span class="stat-rank-count">{int(days)} días sin salir en {month_name}</span>'
                    f'<span class="stat-rank-date">'
                    f'<i class="fa fa-calendar-o"></i> Última vez: {a_date}'
                    f'</span>'
                    f'</div>'
                    f'</div>'
                )
            parts.append('</div>')  # stat-rank-list
            parts.append('</div>')  # mt-3

        # ── Más tiempo sin salir (podrían salir pronto) ───────────────────
        if overdue5:
            parts.append(
                f'<div class="mt-3">'
                f'<p class="ma-section-title" style="font-size:1rem;">'
                f'<i class="fa fa-clock-o"></i>&nbsp; '
                f'Números del conjunto que más tiempo llevan sin salir en {month_name}</p>'
                f'<p class="ma-section-desc">'
                f'Estos números no solo son de los menos salidores del mes, sino que además llevan mucho tiempo '
                f'sin aparecer. La combinación de ambos factores puede hacerlos interesantes para el próximo {month_name}.</p>'
                f'<div class="stat-rank-list">'
            )
            for i, a in enumerate(overdue5, 1):
                a_name = a.get('name', '—')
                a_date = a.get('last_date', '—')
                days = a.get('days_since', 0)
                parts.append(
                    f'<div class="stat-rank-item">'
                    f'<span class="stat-rank-pos">#{i}</span>'
                    f'<span class="ball ball-lila stat-rank-ball">{a_name}</span>'
                    f'<div class="stat-rank-info">'
                    f'<span class="stat-rank-count">{int(days)} días sin salir en {month_name}</span>'
                    f'<span class="stat-rank-date">'
                    f'<i class="fa fa-calendar-o"></i> Última vez: {a_date}'
                    f'</span>'
                    f'</div>'
                    f'</div>'
                )
            parts.append('</div>')  # stat-rank-list
            parts.append('</div>')  # mt-3

        parts.append('</div>')  # ma-section

        # ── Por Día de la Semana ──────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Menos Salidores por Día de la Semana</p>'
            '<p class="ma-section-desc">Los 8 números que menos han salido en cada día de la semana a lo largo de toda la historia registrada.</p>'
        )
        parts.append(
            '<div class="card border-0 shadow-sm">'
            '<div class="card-body p-2" style="overflow-x:auto;">'
            '<table class="table table-sm mb-0" style="text-align:center;min-width:520px;">'
            '<thead><tr>'
            '<th style="color:#8c6ca8;font-weight:700;width:28px;">#</th>'
        )
        for _, label in WEEKDAYS:
            parts.append(f'<th style="color:#8c6ca8;font-weight:700;">{label}</th>')
        parts.append('</tr></thead><tbody>')

        for pos in range(1, 9):
            parts.append('<tr>')
            parts.append(f'<td class="stat-rank-pos">#{pos}</td>')
            for code, _ in WEEKDAYS:
                nums = weekday_data.get(code, [])
                if pos <= len(nums):
                    num_name = nums[pos - 1]['name']
                    bc = ball_color_week(pos)
                    parts.append(f'<td><span class="ball {bc}">{num_name}</span></td>')
                else:
                    parts.append('<td>—</td>')
            parts.append('</tr>')

        parts.append('</tbody></table>')
        parts.append('</div></div>')
        parts.append('</div>')

        # ── Tarde y Noche ────────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Menos Salidores por Turno</p>'
            '<p class="ma-section-desc">Números con menor cantidad de apariciones totales según el turno del sorteo, considerando toda la historia disponible.</p>'
        )
        parts.append('<div class="ma-grid-2">')
        for label, icon_class, hdr_bg, icon_color, data in [
            ('Tarde', 'fa-sun-o',  'linear-gradient(135deg,#f59e0b,#d97706)', '#fff', bottom_tarde),
            ('Noche', 'fa-moon-o', 'linear-gradient(135deg,#1e3a5f,#2d5a8e)', '#fff', bottom_noche),
        ]:
            groups = [data[:3], data[3:7], data[7:]]
            parts.append(
                f'<div class="card border-0 shadow-sm">'
                f'<div class="card-header py-2 px-3" style="background:{hdr_bg};color:{icon_color};">'
                f'<i class="fa {icon_class}" style="color:{icon_color};"></i>'
                f'<span style="font-weight:700;font-size:.95rem;margin-left:6px;">{label}</span>'
                f'</div>'
                f'<div class="card-body p-2 balls-no-zoom">'
            )
            offset = 1
            for group in groups:
                if group:
                    parts.append('<div style="display:flex;gap:6px;justify-content:space-evenly;margin-bottom:6px;">')
                    for n in group:
                        bc = ball_color_turn(offset)
                        parts.append(f'<span class="ball {bc}" title="#{offset}">{n["name"]}</span>')
                        offset += 1
                    parts.append('</div>')
            parts.append('</div></div>')
        parts.append('</div>')
        parts.append('</div>')

        # ── Por Semana del Mes ────────────────────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Menos Salidores por Semana del Mes</p>'
            '<p class="ma-section-desc">Los números que menos han salido según la semana en la que cae el sorteo. La quinta semana comprende los días 29, 30 y 31.</p>'
        )
        parts.append('<div class="ma-grid-3">')
        for code, label in WEEKS:
            nums = week_data.get(code, [])
            parts.append(
                f'<div class="card border-0 shadow-sm">'
                f'<div class="card-header py-2 px-3" style="background:linear-gradient(135deg,#6f4a8e,#9b59b6);color:#fff;">'
                f'<span style="font-weight:700;font-size:.9rem;">{label}</span>'
                f'</div>'
                f'<div class="card-body p-2 balls-no-zoom">'
            )
            if nums:
                groups = [nums[:3], nums[3:5], nums[5:]]
                offset = 1
                for group in groups:
                    if group:
                        parts.append('<div style="display:flex;gap:6px;justify-content:space-evenly;margin-bottom:6px;">')
                        for n in group:
                            bc = ball_color_week(offset)
                            parts.append(f'<span class="ball {bc}" title="#{offset}">{n["name"]}</span>')
                            offset += 1
                        parts.append('</div>')
            else:
                parts.append('<p class="text-muted small mb-0">Sin datos</p>')
            parts.append('</div></div>')
        parts.append('</div>')
        parts.append('</div>')

        return ''.join(parts)
