# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.addons.lottery_base.models.utils import MONTHS_DICT
import base64
import calendar
import os
from datetime import date, timedelta

WEEKDAYS = [
    ('lu', 'Lunes'),
    ('ma', 'Martes'),
    ('mi', 'Miércoles'),
    ('ju', 'Jueves'),
    ('vi', 'Viernes'),
    ('sa', 'Sábado'),
    ('do', 'Domingo'),
]

WEEKDAY_SHORT = {
    'lu': 'Lun', 'ma': 'Mar', 'mi': 'Mié',
    'ju': 'Jue', 'vi': 'Vie', 'sa': 'Sáb', 'do': 'Dom',
}

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
            today = self._parse_ref_date(None)
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

        category = self.env.ref('lottery_portal.news_category_analisis_mensuales')
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
        .ma-balls-grid { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; padding:8px; }
        .ma-wd-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; }
        .ma-wd-card { border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.09); }
        .ma-wd-hdr { background:linear-gradient(135deg,#6f4a8e,#9b59b6); color:#fff; text-align:center; padding:8px 2px 6px; font-weight:700; font-size:.78rem; letter-spacing:.4px; text-transform:uppercase; }
        .ma-wd-balls { padding:8px 4px 6px; display:flex; flex-wrap:wrap; gap:5px; justify-content:center; background:#faf8ff; min-height:44px; }
        @media(max-width:767px){ .ma-wd-grid { grid-template-columns:repeat(2,1fr); gap:10px; } }
        @media(min-width:768px) and (max-width:1100px){ .ma-wd-grid { grid-template-columns:repeat(4,1fr); } }
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
            f'<div class="ma-balls-grid">'
        )
        for n in top30:
            num_name = n['name']
            num_total = n['total']
            bc = ball_color(n['rank'])
            parts.append(
                f'<span class="ball {bc}" title="Salidas históricas en {month_name}: {num_total}">{num_name}</span>'
            )
        parts.append('</div>')  # ma-balls-grid
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

        # ── Por Día de la Semana (tarjetas) ──────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Top 8 por Día de la Semana</p>'
            '<p class="ma-section-desc">Los 8 números que más han salido en cada día de la semana a lo largo de toda la historia registrada.</p>'
        )
        parts.append('<div class="ma-wd-grid">')
        for code, label in WEEKDAYS:
            nums = weekday_data.get(code, [])
            short = WEEKDAY_SHORT.get(code, label[:3])
            parts.append(
                f'<div class="ma-wd-card">'
                f'<div class="ma-wd-hdr">{short}</div>'
                f'<div class="ma-wd-balls">'
            )
            for pos, n in enumerate(nums, 1):
                bc = ball_color_week(pos)
                parts.append(f'<span class="ball {bc}">{n["name"]}</span>')
            if not nums:
                parts.append('<span class="text-muted small">&#8212;</span>')
            parts.append('</div></div>')
        parts.append('</div>')
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

        category = self.env.ref('lottery_portal.news_category_analisis_mensuales')
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
        .ma-balls-grid { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; padding:8px; }
        .ma-wd-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; }
        .ma-wd-card { border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.09); }
        .ma-wd-hdr { background:linear-gradient(135deg,#6f4a8e,#9b59b6); color:#fff; text-align:center; padding:8px 2px 6px; font-weight:700; font-size:.78rem; letter-spacing:.4px; text-transform:uppercase; }
        .ma-wd-balls { padding:8px 4px 6px; display:flex; flex-wrap:wrap; gap:5px; justify-content:center; background:#faf8ff; min-height:44px; }
        @media(max-width:767px){ .ma-wd-grid { grid-template-columns:repeat(2,1fr); gap:10px; } }
        @media(min-width:768px) and (max-width:1100px){ .ma-wd-grid { grid-template-columns:repeat(4,1fr); } }
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
            f'<div class="ma-balls-grid">'
        )
        for n in bottom30:
            num_name = n['name']
            num_total = n['total']
            bc = ball_color(n['rank'])
            parts.append(
                f'<span class="ball {bc}" title="Salidas históricas en {month_name}: {num_total}">{num_name}</span>'
            )
        parts.append('</div>')  # ma-balls-grid
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

        # ── Por Día de la Semana (tarjetas) ──────────────────────────────
        parts.append('<div class="ma-section">')
        parts.append(
            '<p class="ma-section-title">Menos Salidores por Día de la Semana</p>'
            '<p class="ma-section-desc">Los 8 números que menos han salido en cada día de la semana a lo largo de toda la historia registrada.</p>'
        )
        parts.append('<div class="ma-wd-grid">')
        for code, label in WEEKDAYS:
            nums = weekday_data.get(code, [])
            short = WEEKDAY_SHORT.get(code, label[:3])
            parts.append(
                f'<div class="ma-wd-card">'
                f'<div class="ma-wd-hdr">{short}</div>'
                f'<div class="ma-wd-balls">'
            )
            for pos, n in enumerate(nums, 1):
                bc = ball_color_week(pos)
                parts.append(f'<span class="ball {bc}">{n["name"]}</span>')
            if not nums:
                parts.append('<span class="text-muted small">&#8212;</span>')
            parts.append('</div></div>')
        parts.append('</div>')
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

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_ref_date(self, ref_date):
        """Return a date object from ref_date (str 'YYYY-MM-DD') or today."""
        if ref_date:
            try:
                from datetime import datetime
                return datetime.strptime(ref_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        import pytz
        from datetime import datetime
        tz_name = (
            (self.env.company.partner_id.tz if self.env.company else None)
            or (self.env.user.tz if self.env.user else None)
            or 'America/New_York'
        )
        tz = pytz.timezone(tz_name)
        return datetime.now(tz).date()

    # ─────────────────────────────────────────────────────────────────────────
    # Cron: Grupos más atrasados
    # ─────────────────────────────────────────────────────────────────────────
    def cron_generate_grupos_atrasados(self, ref_date=None):
        """Generate 3 articles (General, Tarde, Noche) for top-5 delayed groups."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        options = [
            ('all',   'General'),
            ('tarde', 'Tarde'),
            ('noche', 'Noche'),
        ]
        for option, label in options:
            try:
                self._generate_grupos_article(today, option, label)
            except Exception as e:
                _logger.error(
                    'cron_generate_grupos_atrasados [%s]: %s', label, e, exc_info=True
                )

    def _generate_grupos_article(self, today, option, label):
        import logging
        _logger = logging.getLogger(__name__)

        svc = self.env['lottery.stats.service'].sudo()
        date_str = today.strftime('%d/%m/%Y')

        _WCODE  = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
        _WLABEL = {'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles',
                   'ju': 'Jueves', 'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo'}
        wcode        = _WCODE[today.weekday()]
        wlabel       = _WLABEL[wcode]
        month_num    = today.month
        month_name   = MONTHS_DICT[str(month_num)]
        week_of_month = min((today.day - 1) // 7 + 1, 5)

        api_option  = {'all': 'general', 'tarde': 'afternoon', 'noche': 'evening'}.get(option, 'general')
        turn_param  = None if option == 'all' else api_option

        # Slug fijo por turno — un único artículo activo por opción, siempre actualizado
        slug  = f'grupos-atrasados-{option}'
        title = f'Top 5 Grupos más atrasados — {label} — {date_str}'
        intro = (f'Análisis detallado de los 5 grupos con mayor atraso acumulado '
                 f'en el turno {label} al {date_str}.')

        groups_raw = svc.get_top_6_groups(api_option, wcode)[:5]
        groups_data = []
        for grp in groups_raw:
            grp_id     = grp['id']
            grp_record = self.env['lottery.group'].browse(grp_id)
            nums = analysis = intervals = None
            try:
                nums = svc.get_info_groups_numbers(grp_record, 'total_atrasadas', wcode)
            except Exception as e:
                _logger.warning('get_info_groups_numbers [%s]: %s', grp_id, e)
            try:
                analysis = svc.get_info_group_numbers_analysis(
                    grp_id, wcode, week_of_month, month_num, 5)
            except Exception as e:
                _logger.warning('get_info_group_numbers_analysis [%s]: %s', grp_id, e)
            try:
                intervals = svc.get_group_delay_intervals(grp_id, turn_param) or {}
            except Exception as e:
                _logger.warning('get_group_delay_intervals [%s]: %s', grp_id, e)
            groups_data.append({
                'grp': grp, 'nums': nums or [], 'analysis': analysis or {}, 'intervals': intervals or {},
            })

        int_ranges = [('21-40', 'r_21_40'), ('41-50', 'r_41_50'),
                      ('51-60', 'r_51_60'), ('61-70', 'r_61_70'), ('>70', 'r_70_plus')]

        html_body = self._build_group_prose_html(
            date_str, option, label, wlabel, month_name, week_of_month,
            groups_data, int_ranges, 'grupos',
        )

        _cover_map = {
            'all':   'grupos top general.png',
            'tarde': 'grupos top tarde.png',
            'noche': 'grupos top noche.png',
        }
        cover = self._load_cover_image(_cover_map.get(option, 'grupos top general.png'))

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        akey = f'grupos_atrasados_{option}'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title': title, 'slug': slug, 'summary': intro,
            'raw_html': html_body, 'is_published': True,
            'article_key': akey,
            'category_id': category.id if category else False,
            'cover_image': cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated grupos article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created grupos article: %s', slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old grupos-atrasados [%s] articles', len(old), option)

    # ─────────────────────────────────────────────────────────────────────────
    # Cron: Pintas más atrasadas
    # ─────────────────────────────────────────────────────────────────────────
    def cron_generate_pintas_atrasadas(self, ref_date=None):
        """Generate 3 articles (General, Tarde, Noche) for top-3 delayed pintas."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        options = [
            ('all',   'General'),
            ('tarde', 'Tarde'),
            ('noche', 'Noche'),
        ]
        for option, label in options:
            try:
                self._generate_pintas_article(today, option, label)
            except Exception as e:
                _logger.error(
                    'cron_generate_pintas_atrasadas [%s]: %s', label, e, exc_info=True
                )

    def _generate_pintas_article(self, today, option, label):
        import logging
        _logger = logging.getLogger(__name__)

        svc = self.env['lottery.stats.service'].sudo()
        date_str = today.strftime('%d/%m/%Y')

        _WCODE  = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
        _WLABEL = {'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles',
                   'ju': 'Jueves', 'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo'}
        wcode        = _WCODE[today.weekday()]
        wlabel       = _WLABEL[wcode]
        month_num    = today.month
        month_name   = MONTHS_DICT[str(month_num)]
        week_of_month = min((today.day - 1) // 7 + 1, 5)

        api_option  = {'all': 'general', 'tarde': 'afternoon', 'noche': 'evening'}.get(option, 'general')
        turn_param  = None if option == 'all' else api_option

        # Slug fijo por turno — un único artículo activo por opción, siempre actualizado
        slug  = f'pintas-atrasadas-{option}'
        title = f'Top 3 Pintas más atrasadas — {label} — {date_str}'
        intro = (f'Análisis detallado de las 3 pintas con mayor atraso acumulado '
                 f'en el turno {label} al {date_str}.')

        pintas_raw = svc.get_top_3_pintas(api_option, wcode)[:3]
        pintas_data = []
        for grp in pintas_raw:
            grp_id     = grp['id']
            grp_record = self.env['lottery.group'].browse(grp_id)
            nums = analysis = intervals = None
            try:
                nums = svc.get_info_groups_numbers(grp_record, 'total_atrasadas', wcode)
            except Exception as e:
                _logger.warning('get_info_groups_numbers pinta [%s]: %s', grp_id, e)
            try:
                analysis = svc.get_info_group_numbers_analysis(
                    grp_id, wcode, week_of_month, month_num, 5)
            except Exception as e:
                _logger.warning('get_info_group_numbers_analysis pinta [%s]: %s', grp_id, e)
            try:
                intervals = svc.get_group_delay_intervals_pintas(grp_id, turn_param) or {}
            except Exception as e:
                _logger.warning('get_group_delay_intervals_pintas [%s]: %s', grp_id, e)
            pintas_data.append({
                'grp': grp, 'nums': nums or [], 'analysis': analysis or {}, 'intervals': intervals or {},
            })

        int_ranges = [('10-20', 'r_10_20'), ('21-30', 'r_21_30'),
                      ('31-40', 'r_31_40'), ('41-45', 'r_41_45'), ('>45', 'r_45_plus')]

        html_body = self._build_group_prose_html(
            date_str, option, label, wlabel, month_name, week_of_month,
            pintas_data, int_ranges, 'pintas',
        )

        _cover_map = {
            'all':   'pintas top general.png',
            'tarde': 'pintas top tarde.png',
            'noche': 'pintas top noche.png',
        }
        cover = self._load_cover_image(_cover_map.get(option, 'pintas top general.png'))

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        akey = f'pintas_atrasadas_{option}'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title': title, 'slug': slug, 'summary': intro,
            'raw_html': html_body, 'is_published': True,
            'article_key': akey,
            'category_id': category.id if category else False,
            'cover_image': cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated pintas article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created pintas article: %s', slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old pintas-atrasadas [%s] articles', len(old), option)

    # ─────────────────────────────────────────────────────────────────────────
    # Shared prose HTML builder for grupos / pintas articles
    # ─────────────────────────────────────────────────────────────────────────
    def _build_group_prose_html(
        self, date_str, option, label, wlabel, month_name, week_of_month,
        items_data, int_ranges, article_type,
    ):
        parts = []

        # ── Inline CSS ────────────────────────────────────────────────────
        parts.append('''<style>
.gp-wrap{font-family:inherit;color:#333;line-height:1.6}
.gp-intro{background:linear-gradient(135deg,#2c3e50,#4a6fa5);color:#fff;
  border-radius:12px;padding:20px 24px;margin-bottom:28px}
.gp-intro h2{margin:0 0 8px;font-size:1.25rem;font-weight:700;color:#fff}
.gp-intro p{margin:0;font-size:.93rem;opacity:.92;line-height:1.65}
.gp-card{border:1px solid #dde3ec;border-radius:12px;margin-bottom:32px;
  overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.07)}
.gp-card-hdr{padding:14px 20px;display:flex;align-items:center;gap:12px;color:#fff;flex-wrap:wrap}
.gp-rank-circle{width:36px;height:36px;border-radius:50%;
  background:rgba(255,255,255,.2);font-weight:800;font-size:1.1rem;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.gp-card-hdr h2{margin:0;font-size:1.1rem;font-weight:700;flex:1;color:#fff !important}
.gp-delay-badges{display:flex;gap:6px;flex-wrap:wrap}
.gp-badge{padding:3px 10px;border-radius:20px;font-size:.74rem;font-weight:700;
  background:rgba(255,255,255,.2)}
.gp-card-body{padding:18px 20px;background:#fff}
.gp-prose{font-size:.92rem;color:#444;margin:0 0 14px;line-height:1.75}
.gp-prose strong{color:#1e293b}
.gp-nums-wrap{margin:14px 0;padding:12px 14px;background:#f8f9ff;border-radius:8px}
.gp-nums-title{font-size:.78rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;color:#666;margin-bottom:10px}
.gp-nums-row{display:flex;flex-wrap:wrap;gap:10px}
.gp-num-item{display:flex;flex-direction:column;align-items:center;gap:4px}
.gp-ball{width:36px;height:36px;border-radius:50%;font-weight:700;font-size:.82rem;
  color:#fff;display:flex;align-items:center;justify-content:center}
.gp-ball-delay{font-size:.68rem;color:#888;font-weight:600}
.gp-info-block{margin-top:12px;padding:12px 16px;border-radius:0 8px 8px 0;border-left:3px solid}
.gp-info-general{background:#f0f4ff;border-color:#6366f1}
.gp-info-tarde{background:#fff7ed;border-color:#f97316}
.gp-info-noche{background:#f0f4ff;border-color:#4f46e5}
.gp-info-day{background:#f0fdf4;border-color:#22c55e}
.gp-info-month{background:#fefce8;border-color:#eab308}
.gp-info-week{background:#fdf4ff;border-color:#a855f7}
.gp-info-intervals{background:#f8fafc;border-color:#94a3b8;border-left-width:3px;border-left-style:solid}
.gp-info-label{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
  color:#888;margin-bottom:5px}
.gp-info-block p{margin:0;font-size:.88rem;color:#374151;line-height:1.7}
.gp-int-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.gp-int-chip{background:#fff;border:1px solid #e2e8f0;border-radius:6px;
  padding:6px 10px;text-align:center;min-width:70px}
.gp-int-chip-val{font-size:1.1rem;font-weight:800;color:#1e293b;display:block}
.gp-int-chip-lbl{font-size:.68rem;color:#94a3b8}
.gp-stats-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.gp-stat{flex:1 1 100px;background:#f1f5f9;border-radius:8px;padding:10px 12px;text-align:center}
.gp-stat-val{font-size:1.4rem;font-weight:800;color:#1e293b}
.gp-stat-lbl{font-size:.72rem;color:#64748b;margin-top:2px}
</style>''')

        # ─ helpers ────────────────────────────────────────────────────────
        def _fmt(lst, limit=3):
            """Return formatted number names from a list of dicts."""
            return ', '.join(
                str(x.get('name', x) if isinstance(x, dict) else x).zfill(2)
                for x in (lst or [])[:limit]
            )

        PALETTES = [
            ('#5b21b6', '#7c3aed'),
            ('#1e3a5f', '#2563eb'),
            ('#14532d', '#16a34a'),
            ('#7f1d1d', '#dc2626'),
            ('#78350f', '#d97706'),
        ]
        BALL_COLORS = [
            '#e74c3c', '#e67e22', '#f59e0b', '#16a34a', '#0891b2',
            '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6', '#84cc16',
        ]

        is_pintas = (article_type == 'pintas')
        entity_name = 'pinta' if is_pintas else 'grupo'
        entity_count = len(items_data)
        turn_desc = {'all': 'todos los turnos', 'tarde': 'el turno Tarde', 'noche': 'el turno Noche'}.get(option, label)

        # ── Intro ─────────────────────────────────────────────────────────
        parts.append('<div class="gp-wrap">')
        parts.append(
            f'<div class="gp-intro">'
            f'<h2>Top {entity_count} {"Pintas" if is_pintas else "Grupos"} '
            f'm&#225;s Atrasados &#8212; {label}</h2>'
            f'<p>Al <strong>{date_str}</strong>, los siguientes {entity_count} '
            f'{"pintas" if is_pintas else "grupos"} de n&#250;meros acumulan el mayor atraso en '
            f'<strong>{turn_desc}</strong> del Pick 3 Florida. '
            f'Hoy es <strong>{wlabel}</strong>, semana {week_of_month} de '
            f'<strong>{month_name}</strong>. El an&#225;lisis incluye la composici&#243;n de cada '
            f'{"pinta" if is_pintas else "grupo"}, el estado de atraso individual de sus n&#250;meros, '
            f'y el comportamiento hist&#243;rico por d&#237;a de la semana, mes y semana del mes.</p>'
            f'</div>'
        )

        for rank, item in enumerate(items_data, 1):
            grp      = item['grp']
            nums     = item['nums']     or []
            analysis = item['analysis'] or {}
            ivs      = item['intervals'] or {}

            dark, light = PALETTES[(rank - 1) % len(PALETTES)]
            grp_name = grp.get('name', f'{entity_name.capitalize()} {rank}')
            atraso_g = grp.get('salidas_atrasadas', 0)
            atraso_t = grp.get('salidas_atrasadas_dia', 0)
            atraso_n = grp.get('salidas_atrasadas_noche', 0)

            # ── Card header ────────────────────────────────────────────────
            parts.append(
                f'<div class="gp-card">'
                f'<div class="gp-card-hdr" style="background:linear-gradient(135deg,{dark},{light})">'
                f'<div class="gp-rank-circle">{rank}</div>'
                f'<h2>{grp_name}</h2>'
                f'<div class="gp-delay-badges">'
                f'<span class="gp-badge">General&#160;{atraso_g}</span>'
                f'<span class="gp-badge">&#9728;&#160;{atraso_t}</span>'
                f'<span class="gp-badge">&#9790;&#160;{atraso_n}</span>'
                f'</div>'
                f'</div>'
                f'<div class="gp-card-body">'
            )

            # ── Stat chips ────────────────────────────────────────────────
            parts.append('<div class="gp-stats-row">')
            for val, lbl in [(atraso_g, 'Atraso General'), (atraso_t, 'Atraso Tarde'), (atraso_n, 'Atraso Noche')]:
                parts.append(
                    f'<div class="gp-stat">'
                    f'<div class="gp-stat-val">{val}</div>'
                    f'<div class="gp-stat-lbl">{lbl}</div>'
                    f'</div>'
                )
            parts.append('</div>')

            # ── Prose 1: overview ─────────────────────────────────────────
            nums_sorted = sorted(nums, key=lambda x: x.get('total_atrasadas', 0), reverse=True)
            num_names   = [n['numero'] for n in nums_sorted]
            most_del    = nums_sorted[0]  if nums_sorted else None
            least_del   = nums_sorted[-1] if nums_sorted else None

            p1 = (
                f'El {entity_name} <strong>{grp_name}</strong> acumula '
                f'<strong>{atraso_g} sorteos consecutivos</strong> sin que ninguno de sus n&#250;meros '
                f'haya aparecido en el combinado general. '
            )
            if num_names:
                p1 += (f'Est&#225; conformado por {len(num_names)} n&#250;meros: '
                       f'<strong>{", ".join(num_names)}</strong>. ')
            if most_del and least_del and most_del['numero'] != least_del['numero']:
                p1 += (
                    f'El n&#250;mero con mayor atraso individual es el '
                    f'<strong>{most_del["numero"]}</strong> '
                    f'({most_del["total_atrasadas"]} sorteos sin salir), '
                    f'mientras que el que apareci&#243; m&#225;s recientemente dentro del '
                    f'{entity_name} fue el <strong>{least_del["numero"]}</strong> '
                    f'(con {least_del["total_atrasadas"]} sorteos de atraso).'
                )
            parts.append(f'<p class="gp-prose">{p1}</p>')

            # ── Prose 2: tarde / noche breakdown ──────────────────────────
            nums_by_tarde = sorted(nums, key=lambda x: x.get('total_atrasadas_dia', 0), reverse=True)
            nums_by_noche = sorted(nums, key=lambda x: x.get('total_atrasadas_noche', 0), reverse=True)
            if nums_by_tarde and nums_by_noche:
                mt = nums_by_tarde[0]
                mn = nums_by_noche[0]
                p2 = (
                    f'En el turno de <strong>Tarde</strong> el {entity_name} lleva '
                    f'<strong>{atraso_t} sorteos</strong> sin aparecer; el n&#250;mero m&#225;s '
                    f'atrasado en ese turno es el <strong>{mt["numero"]}</strong> '
                    f'({mt["total_atrasadas_dia"]} sorteos). '
                    f'En <strong>Noche</strong> acumula <strong>{atraso_n} sorteos</strong> de atraso, '
                    f'siendo el <strong>{mn["numero"]}</strong> el miembro m&#225;s rezagado '
                    f'en ese horario ({mn["total_atrasadas_noche"]} sorteos).'
                )
                parts.append(
                    f'<div class="gp-info-block gp-info-general">'
                    f'<div class="gp-info-label">Atraso por turno</div>'
                    f'<p>{p2}</p></div>'
                )

            # ── Numbers visual grid ───────────────────────────────────────
            if nums_sorted:
                parts.append(
                    '<div class="gp-nums-wrap">'
                    f'<div class="gp-nums-title">N&#250;meros del {entity_name} &#8212; ordenados por atraso</div>'
                    '<div class="gp-nums-row">'
                )
                for ni, n in enumerate(nums_sorted):
                    bc = BALL_COLORS[ni % len(BALL_COLORS)]
                    parts.append(
                        f'<div class="gp-num-item">'
                        f'<div class="gp-ball" style="background:{bc}">{n["numero"]}</div>'
                        f'<div class="gp-ball-delay">{n["total_atrasadas"]}</div>'
                        f'</div>'
                    )
                parts.append('</div></div>')

            # ── Analysis sections (prose) ─────────────────────────────────
            if analysis:
                # Current most delayed & last appeared
                most_delayed_lst  = analysis.get('most_delayed', [])
                most_delayed_t    = analysis.get('most_delayed_day', [])
                most_delayed_n    = analysis.get('most_delayed_night', [])
                last_gen  = analysis.get('last',       {})
                last_day  = analysis.get('last_day',   {})
                last_night= analysis.get('last_night', {})

                if most_delayed_lst and last_gen:
                    top_names  = _fmt(most_delayed_lst, 3)
                    top_t_names = _fmt(most_delayed_t,  2)
                    top_n_names = _fmt(most_delayed_n,  2)
                    last_name  = str(last_gen.get('name', '')).zfill(2)
                    last_d_name = str(last_day.get('name', '')).zfill(2)  if last_day   else '—'
                    last_n_name = str(last_night.get('name', '')).zfill(2) if last_night else '—'
                    parts.append(
                        f'<div class="gp-info-block gp-info-tarde">'
                        f'<div class="gp-info-label">Situaci&#243;n actual de atrasos</div>'
                        f'<p>Los n&#250;meros con mayor atraso acumulado en el {entity_name} son '
                        f'el <strong>{top_names}</strong>. '
                        f'El &#250;ltimo en aparecer de forma general fue el '
                        f'<strong>{last_name}</strong>. '
                        f'En Tarde el m&#225;s rezagado es el <strong>{top_t_names}</strong> '
                        f'y el que sali&#243; m&#225;s recientemente fue el <strong>{last_d_name}</strong>. '
                        f'En Noche los m&#225;s atrasados son <strong>{top_n_names}</strong> '
                        f'y el &#250;ltimo en salir fue el <strong>{last_n_name}</strong>.</p>'
                        f'</div>'
                    )

                # By weekday
                day_most  = analysis.get('day', {}).get('most',  [])
                day_least = analysis.get('day', {}).get('least', [])
                if day_most:
                    most_d_names  = _fmt(day_most,  3)
                    least_d_names = _fmt(day_least, 3)
                    parts.append(
                        f'<div class="gp-info-block gp-info-day">'
                        f'<div class="gp-info-label">Comportamiento los {wlabel}</div>'
                        f'<p>Hist&#243;ricamente los <strong>{wlabel}</strong>, los n&#250;meros '
                        f'm&#225;s activos de este {entity_name} son el '
                        f'<strong>{most_d_names}</strong>. '
                        f'Los que menos aparecen en ese d&#237;a son el '
                        f'<strong>{least_d_names}</strong>. '
                        f'Esto puede ser una referencia &#250;til dado que hoy es {wlabel}.</p>'
                        f'</div>'
                    )

                # By month
                month_most  = analysis.get('month', {}).get('most',  [])
                month_least = analysis.get('month', {}).get('least', [])
                if month_most:
                    most_m_names  = _fmt(month_most,  3)
                    least_m_names = _fmt(month_least, 3)
                    parts.append(
                        f'<div class="gp-info-block gp-info-month">'
                        f'<div class="gp-info-label">En el mes de {month_name}</div>'
                        f'<p>Durante el mes de <strong>{month_name}</strong>, los n&#250;meros '
                        f'del {entity_name} que hist&#243;ricamente m&#225;s han salido son '
                        f'el <strong>{most_m_names}</strong>. '
                        f'Los menos frecuentes en este mes son el <strong>{least_m_names}</strong>. '
                        f'Considerando que estamos en {month_name}, estos datos son especialmente '
                        f'relevantes para el an&#225;lisis actual.</p>'
                        f'</div>'
                    )

                # By week of month
                week_most  = analysis.get('week', {}).get('most',  [])
                week_least = analysis.get('week', {}).get('least', [])
                if week_most:
                    most_w_names  = _fmt(week_most,  3)
                    least_w_names = _fmt(week_least, 3)
                    ordinals = {1: 'primera', 2: 'segunda', 3: 'tercera', 4: 'cuarta', 5: 'quinta'}
                    wlabel_ord = ordinals.get(week_of_month, str(week_of_month))
                    parts.append(
                        f'<div class="gp-info-block gp-info-week">'
                        f'<div class="gp-info-label">Semana {week_of_month} del mes</div>'
                        f'<p>En la <strong>{wlabel_ord} semana del mes</strong> (la actual), '
                        f'los n&#250;meros del {entity_name} que m&#225;s suelen salir son '
                        f'el <strong>{most_w_names}</strong>, mientras que los menos frecuentes '
                        f'en esta franja son el <strong>{least_w_names}</strong>.</p>'
                        f'</div>'
                    )

            # ── Delay intervals (prose + chips) ───────────────────────────
            if ivs:
                total_ep = sum(ivs.get(k, 0) or 0 for _, k in int_ranges)
                if total_ep > 0:
                    # Find most common range
                    max_rng_lbl, max_rng_cnt = int_ranges[0][0], 0
                    for rng_lbl, rng_key in int_ranges:
                        cnt = ivs.get(rng_key, 0) or 0
                        if cnt > max_rng_cnt:
                            max_rng_cnt = cnt
                            max_rng_lbl = rng_lbl

                    last_range_lbl, last_range_key = int_ranges[-1]
                    r_extreme = ivs.get(last_range_key, 0) or 0

                    interp = (
                        f'La franja de atraso m&#225;s frecuente en el historial es de '
                        f'<strong>{max_rng_lbl} sorteos</strong> '
                        f'({max_rng_cnt} {"vez" if max_rng_cnt == 1 else "veces"}). '
                    )
                    if r_extreme > 0:
                        interp += (
                            f'El {entity_name} ha superado la barrera de {last_range_lbl} sorteos '
                            f'consecutivos sin aparecer en <strong>{r_extreme} '
                            f'ocasi&#243;{"n" if r_extreme == 1 else "nes"}</strong>, '
                            f'lo que indica que este nivel de atraso es hist&#243;ricamente posible. '
                        )

                    range_texts = []
                    for rng_lbl, rng_key in int_ranges:
                        v = ivs.get(rng_key, 0) or 0
                        range_texts.append(f'<strong>{v}</strong> veces entre {rng_lbl}')
                    range_prose = ', '.join(range_texts[:-1]) + f' y {range_texts[-1]} sorteos.'

                    parts.append(
                        f'<div class="gp-info-block gp-info-intervals">'
                        f'<div class="gp-info-label">Historial de intervalos de atraso</div>'
                        f'<p>En toda la base de datos hist&#243;rica, este {entity_name} ha acumulado '
                        f'<strong>{total_ep} episodios</strong> de atraso significativo. '
                        f'{interp}La distribuci&#243;n completa: {range_prose}</p>'
                        f'<div class="gp-int-row">'
                    )
                    for rng_lbl, rng_key in int_ranges:
                        v = ivs.get(rng_key, 0) or 0
                        parts.append(
                            f'<div class="gp-int-chip">'
                            f'<span class="gp-int-chip-val">{v}</span>'
                            f'<span class="gp-int-chip-lbl">{rng_lbl} sorteos</span>'
                            f'</div>'
                        )
                    parts.append('</div></div>')

            # close card
            parts.append('</div></div>')

        parts.append('</div>')
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 1: Números más atrasados — General / Tarde / Noche  (cada 5 d)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_numeros_atrasados(self, ref_date=None):
        """Single combined article: top-10 delayed numbers for all 3 turns."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        try:
            self._generate_numeros_atrasados_article(today)
        except Exception as e:
            _logger.error('cron_generate_numeros_atrasados: %s', e, exc_info=True)

    def _generate_numeros_atrasados_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['lottery.stats.service'].sudo()
        date_str = today.strftime('%d/%m/%Y')
        # Slug fijo — un único artículo activo, siempre actualizado
        slug     = 'numeros-atrasados'

        general = svc.get_top_10_general()
        tarde   = svc.get_top_10_dia()
        noche   = svc.get_top_10_noche()

        html_body = self._build_numeros_atrasados_html(date_str, general, tarde, noche)

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        title = f'Top 10 Números más Atrasados — {date_str}'
        intro = f'Ranking de los 10 números con mayor atraso acumulado al {date_str}, en los tres turnos.'

        cover = self._load_cover_image('top 10 numeros atrasados.png')

        akey = 'top_atrasos_general'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'article_key':  akey,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated numeros-atrasados article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created numeros-atrasados article: %s', slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old numeros-atrasados articles', len(old))

    def _build_numeros_atrasados_html(self, date_str, general, tarde, noche):
        parts = []
        parts.append('''<style>
.na-wrap{font-family:inherit;color:#333}
.na-header{background:linear-gradient(135deg,#78350f,#b45309);color:#fff;
  border-radius:10px;padding:18px 22px;margin-bottom:24px}
.na-header h1{margin:0 0 4px;font-size:1.4rem;font-weight:700}
.na-header .na-meta{font-size:.85rem;opacity:.85}
.na-section{margin-bottom:32px}
.na-section-title{font-size:1rem;font-weight:700;color:#fff;
  padding:10px 16px;border-radius:8px 8px 0 0;margin:0}
.na-table{width:100%;border-collapse:collapse;border:1px solid #dde3ec;border-top:none}
.na-table th{background:#f3f4f6;font-size:.78rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.5px;color:#555;
  padding:8px 12px;border-bottom:2px solid #dde3ec;text-align:left}
.na-table td{padding:8px 12px;border-bottom:1px solid #eef0f5;font-size:.9rem}
.na-table tr:last-child td{border-bottom:none}
.na-table tr:hover td{background:#fafbff}
.na-ball-sm{width:28px;height:28px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;
  font-weight:700;font-size:.8rem;color:#fff}
.na-rank{font-weight:700;color:#94a3b8;font-size:.85rem;text-align:center}
.na-atraso{font-weight:700;font-size:1rem}
.na-turn-tag{display:inline-block;padding:2px 7px;border-radius:4px;
  font-size:.72rem;font-weight:600;color:#fff}
.na-turn-afternoon{background:#f59e0b}
.na-turn-evening{background:#6366f1}
</style>''')

        parts.append('<div class="na-wrap">')
        parts.append(
            f'<div class="na-header">'
            f'<h1>Top 10 Números más Atrasados</h1>'
            f'<div class="na-meta">Generado el {date_str} &nbsp;&middot;&nbsp; General · Tarde · Noche</div>'
            f'</div>'
        )

        SECTIONS = [
            ('General',    '#2c3e50',  '#4a6fa5',  general),
            ('Tarde',      '#92400e',  '#d97706',  tarde),
            ('Noche',      '#312e81',  '#4f46e5',  noche),
        ]
        BALL_BG = ['#e74c3c','#e67e22','#f1c40f','#2ecc71','#1abc9c',
                   '#3498db','#9b59b6','#34495e','#e91e63','#00bcd4']

        for sec_title, dark, light, rows in SECTIONS:
            parts.append(f'<div class="na-section">')
            parts.append(
                f'<div class="na-section-title" '
                f'style="background:linear-gradient(135deg,{dark},{light})">'
                f'{sec_title}</div>'
            )
            parts.append(
                '<table class="na-table">'
                '<thead><tr>'
                '<th>#</th><th>Número</th><th>Atraso</th><th>Última salida</th><th>Turno</th>'
                '</tr></thead><tbody>'
            )
            for i, row in enumerate(rows or []):
                bc    = BALL_BG[i % len(BALL_BG)]
                name  = row.get('name', '??')
                atraso = row.get('total_atrasadas', 0)
                fecha = row.get('ultima_fecha', '—')
                turno = row.get('ultimo_turno', '')
                tag_cls = 'na-turn-afternoon' if turno == 'afternoon' else 'na-turn-evening'
                tag_lbl = 'Tarde' if turno == 'afternoon' else ('Noche' if turno == 'evening' else '—')
                parts.append(
                    f'<tr>'
                    f'<td class="na-rank">{i + 1}</td>'
                    f'<td><span class="na-ball-sm" style="background:{bc}">{name}</span></td>'
                    f'<td class="na-atraso" style="color:{dark}">{atraso}</td>'
                    f'<td>{fecha}</td>'
                    f'<td><span class="na-turn-tag {tag_cls}">{tag_lbl}</span></td>'
                    f'</tr>'
                )
            parts.append('</tbody></table></div>')

        parts.append('</div>')
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 2: Números más atrasados por día de la semana  (diario)
    # ═════════════════════════════════════════════════════════════════════════
    _WEEKDAY_CODE = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
    _WEEKDAY_ES   = {
        'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles',
        'ju': 'Jueves', 'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo',
    }

    def cron_generate_numeros_dia_semana(self, ref_date=None):
        """Generate one article per run for the last imported draw's weekday."""
        import logging
        _logger = logging.getLogger(__name__)
        if ref_date:
            target_day = self._parse_ref_date(ref_date)
        else:
            self.env.cr.execute("SELECT MAX(date) AS d FROM lottery_output")
            row = self.env.cr.dictfetchone()
            target_day = row['d'] if row and row.get('d') else self._parse_ref_date(None) - timedelta(days=1)
        try:
            self._generate_numeros_dia_semana_article(target_day)
        except Exception as e:
            _logger.error('cron_generate_numeros_dia_semana: %s', e, exc_info=True)

    def _generate_numeros_dia_semana_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc           = self.env['lottery.stats.service'].sudo()
        wday          = today.weekday()                         # 0=Mon…6=Sun
        wcode         = self._WEEKDAY_CODE[wday]
        wlabel        = self._WEEKDAY_ES[wcode]
        # today = ayer del cron → today + 1 = fecha real de generación (timezone-aware)
        generated_str = (today + timedelta(days=1)).strftime('%d/%m/%Y')
        # Un único artículo por día de semana — sin fecha en el slug
        slug          = f'numeros-atrasados-{wcode}'

        rows = svc.get_top_10_por_dia_semana(wcode)

        # Enrich each row with day/night counts
        enriched = []
        for row in rows:
            num_name = row.get('name', '')
            num_rec  = self.env['lottery.number'].sudo().search(
                [('name', '=', int(num_name))], limit=1
            )
            dia_count = noche_count = 0
            if num_rec:
                dia_count   = num_rec.total_salidas_dia   or 0
                noche_count = num_rec.total_salidas_noche or 0
            enriched.append({
                **row,
                'dia_count':   dia_count,
                'noche_count': noche_count,
            })

        html_body = self._build_numeros_dia_semana_html(
            generated_str, wlabel, wcode, enriched
        )

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        title = f'Números más atrasados los {wlabel} — {generated_str}'
        intro = (f'Análisis de los 10 números con mayor atraso acumulado '
                 f'los {wlabel}, con tendencia día/noche.')

        _cover_map = {
            'lu': 'atraso numeros lunes.png',
            'ma': 'atraso numeros martes.png',
            'mi': 'atraso numeros miercoles.png',
            'ju': 'atraso numeros jueves.png',
            'vi': 'atraso numeros viernes.png',
            'sa': 'atraso numeros sabado.png',
            'do': 'atraso numeros domingo.png',
        }
        cover = self._load_cover_image(_cover_map.get(wcode, 'atraso numeros lunes.png'))

        from odoo import fields as odoo_fields
        akey = f'atraso_dia_{wcode}'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'publish_date': odoo_fields.Datetime.now(),
            'is_published': True,
            'article_key':  akey,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated dia-semana article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created dia-semana article: %s', slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old dia-semana articles for %s', len(old), wcode)

    def _build_numeros_dia_semana_html(self, date_str, wlabel, wcode, rows):
        parts = []
        parts.append('''<style>
.nd-wrap{font-family:inherit;color:#333}
.nd-header{background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;
  border-radius:10px;padding:18px 22px;margin-bottom:24px}
.nd-header h1{margin:0 0 4px;font-size:1.4rem;font-weight:700}
.nd-header .nd-meta{font-size:.85rem;opacity:.85}
.nd-card{border:1px solid #dde3ec;border-radius:10px;margin-bottom:20px;
  overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,.06)}
.nd-card-hdr{padding:11px 16px;display:flex;align-items:center;gap:10px;
  background:linear-gradient(135deg,#1e3a5f,#2563eb)}
.nd-card-hdr .nd-rank{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);
  border-radius:5px;padding:2px 7px;font-weight:700;font-size:.78rem;
  color:rgba(255,255,255,.85);flex-shrink:0;letter-spacing:.4px}
.nd-card-hdr .nd-ball{width:34px;height:34px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:.85rem;color:#fff;flex-shrink:0}
.nd-card-hdr .nd-name{font-weight:700;font-size:1rem;color:#fff}
.nd-card-hdr .nd-atraso{margin-left:auto;font-size:.85rem;color:rgba(255,255,255,.8)}
.nd-card-body{padding:14px 16px;background:#fff}
.nd-dn-row{display:flex;gap:8px;margin-bottom:14px}
.nd-dn-box{flex:1;border-radius:8px;padding:10px;text-align:center}
.nd-dn-box .nd-dn-val{font-size:1.3rem;font-weight:700}
.nd-dn-box .nd-dn-lbl{font-size:.72rem;color:#666;margin-top:2px}
.nd-dn-day{background:#fff7ed;border:1px solid #fed7aa}
.nd-dn-day .nd-dn-val{color:#c2410c}
.nd-dn-night{background:#eef2ff;border:1px solid #c7d2fe}
.nd-dn-night .nd-dn-val{color:#4338ca}
.nd-dn-badge{display:inline-block;margin-top:4px;padding:2px 8px;border-radius:10px;
  font-size:.7rem;font-weight:700;color:#fff}
.nd-badge-day{background:#f97316}
.nd-badge-night{background:#6366f1}
.nd-last-row{font-size:.78rem;color:#777;margin-top:10px}
</style>''')

        BALL_BG = ['#e74c3c','#e67e22','#f59e0b','#16a34a','#0891b2',
                   '#3b82f6','#8b5cf6','#ec4899','#14b8a6','#84cc16']

        parts.append(
            f'<div class="nd-wrap">'
            f'<div class="nd-header">'
            f'<h1>Números más atrasados los {wlabel}</h1>'
            f'<div class="nd-meta">Generado el {date_str} &nbsp;&middot;&nbsp; '
            f'Día de la semana: {wlabel}</div>'
            f'</div>'
        )

        for i, row in enumerate(rows or []):
            bc         = BALL_BG[i % len(BALL_BG)]
            name       = row.get('name', '??')
            atraso     = row.get('total_atrasadas', 0)
            ultima     = row.get('ultima_fecha', '—')
            turno      = row.get('ultimo_turno', '')
            dia_count  = row.get('dia_count', 0)
            noche_count= row.get('noche_count', 0)

            tag_lbl = 'Tarde' if turno == 'afternoon' else ('Noche' if turno == 'evening' else '—')
            dominant = 'Más tarde' if dia_count >= noche_count else 'Más noche'
            dom_cls  = 'nd-badge-day' if dia_count >= noche_count else 'nd-badge-night'

            parts.append(
                f'<div class="nd-card">'
                f'<div class="nd-card-hdr">'
                f'<div class="nd-rank">#{i + 1}</div>'
                f'<div class="nd-ball" style="background:{bc}">{name}</div>'
                f'<span class="nd-name">Número {name}</span>'
                f'<span class="nd-atraso">Atraso: <strong>{atraso}</strong> &nbsp;·&nbsp; Últ: {ultima} ({tag_lbl})</span>'
                f'</div>'
                f'<div class="nd-card-body">'
            )

            # Day / Night breakdown
            parts.append(
                f'<div class="nd-dn-row">'
                f'<div class="nd-dn-box nd-dn-day">'
                f'<div class="nd-dn-val">{dia_count}</div>'
                f'<div class="nd-dn-lbl">Salidas Tarde</div>'
                f'</div>'
                f'<div class="nd-dn-box nd-dn-night">'
                f'<div class="nd-dn-val">{noche_count}</div>'
                f'<div class="nd-dn-lbl">Salidas Noche</div>'
                f'</div>'
                f'<div style="display:flex;align-items:center;padding:0 4px">'
                f'<span class="nd-dn-badge {dom_cls}">{dominant}</span>'
                f'</div>'
                f'</div>'
            )

            parts.append('</div></div>')  # card-body + card

        parts.append('</div>')
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 3a: Secuencias de Líneas  (mensual)
    # ARTÍCULO 3b: Secuencias de Terminales  (mensual)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_secuencias_lineas(self, ref_date=None):
        """Monthly cron: article with line-sequence analysis (lines → next lines + terminals)."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        try:
            self._generate_secuencias_tipo_article(today, 'line')
        except Exception as e:
            _logger.error('cron_generate_secuencias_lineas: %s', e, exc_info=True)

    def cron_generate_secuencias_terminales(self, ref_date=None):
        """Monthly cron: article with terminal-sequence analysis (terminals → next lines + terminals)."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        try:
            self._generate_secuencias_tipo_article(today, 'terminal')
        except Exception as e:
            _logger.error('cron_generate_secuencias_terminales: %s', e, exc_info=True)

    def _generate_secuencias_tipo_article(self, today, grp_type):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['lottery.stats.service'].sudo()
        date_str = today.strftime('%d/%m/%Y')
        # Slug fijo por tipo — un único artículo activo, siempre actualizado
        slug     = f'secuencias-{grp_type}s'

        data       = svc.get_all_group_sequences()
        cross_data = svc.get_group_sequences_cross()

        html_body = self._build_secuencias_tipo_html(grp_type, date_str, data, cross_data)

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )

        if grp_type == 'line':
            tipo_lbl = 'Líneas'
            intro = (
                f'Para cada línea (00-09 a 90-99): top 5 líneas y terminales que aparecen '
                f'con mayor frecuencia en el sorteo siguiente. '
                f'General, Tarde y Noche. Análisis al {date_str}.'
            )
        else:
            tipo_lbl = 'Terminales'
            intro = (
                f'Para cada terminal (0 al 9): top 5 líneas y terminales que aparecen '
                f'con mayor frecuencia en el sorteo siguiente. '
                f'General, Tarde y Noche. Análisis al {date_str}.'
            )

        title = f'Secuencias de {tipo_lbl} — Pick 3 Florida'

        cover_file = 'secuencias lineas.png' if grp_type == 'line' else 'secuencias terminales.png'
        cover = self._load_cover_image(cover_file)

        akey = f'secuencias_{grp_type}'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'article_key':  akey,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated secuencias-%s article: %s', grp_type, slug)
        else:
            existing = self.create(vals)
            _logger.info('Created secuencias-%s article: %s', grp_type, slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old secuencias-%s articles', len(old), grp_type)

    def _build_secuencias_tipo_html(self, grp_type, date_str, data, cross_data=None):
        """Builder shared by both sequence articles (lines / terminals).

        grp_type = 'line'  → renders the 10 líneas entries
        grp_type = 'terminal' → renders the 10 terminales entries

        Same-type sequences (line→line or terminal→terminal) come from
        get_all_group_sequences() — identical source to the stats page.
        Cross-type sequences come from get_group_sequences_cross().
        """
        cross_data = cross_data or {}

        LINE_DARK,  LINE_LIGHT  = '#0d6e3b', '#198754'
        TERM_DARK,  TERM_LIGHT  = '#1e3a5f', '#2563eb'
        BALL_BG = ['#e74c3c', '#f59e0b', '#16a34a', '#2563eb', '#8b5cf6',
                   '#ec4899', '#0891b2', '#d97706', '#15803d', '#7c3aed']

        def _bc(num):
            try:
                return BALL_BG[int(num) % len(BALL_BG)]
            except (ValueError, TypeError):
                return BALL_BG[0]

        TURNS = [
            ('general',   'General', 'fa-globe'),
            ('afternoon', 'Tarde',   'fa-sun-o'),
            ('evening',   'Noche',   'fa-moon-o'),
        ]

        if grp_type == 'line':
            HDR_DARK, HDR_LIGHT = LINE_DARK, LINE_LIGHT
            tipo_lbl   = 'Líneas Consecutivas'
            tipo_icon  = 'fa-th-list'
            entry_pfx  = 'Línea'
        else:
            HDR_DARK, HDR_LIGHT = TERM_DARK, TERM_LIGHT
            tipo_lbl  = 'Terminales Consecutivos'
            tipo_icon = 'fa-hashtag'
            entry_pfx = 'Terminal'

        # ── inner helpers ────────────────────────────────────────────────────
        def _items_html(top5):
            if not top5:
                return '<span style="font-size:.75rem;color:#aaa">Sin datos</span>'
            html = ''
            for item in top5:
                n   = item.get('ball_num', '0')
                lbl = item.get('label', '')
                tot = item.get('total', 0)
                html += (
                    f'<div class="sgt-item">'
                    f'<div class="sgt-item-ball" style="background:{_bc(n)}">{n}</div>'
                    f'<span class="sgt-item-lbl">{lbl}</span>'
                    f'<span class="sgt-item-cnt">&times;{tot}</span>'
                    f'</div>'
                )
            return html

        def _prose(from_label, next_label_pl, top5_general, top5_afternoon, top5_evening):
            """Return a short prose paragraph for a block."""
            def _fmt(lst, n=3):
                return ', '.join(
                    f'<strong>{x["label"]}</strong>&nbsp;({x["total"]})'
                    for x in lst[:n]
                ) if lst else '—'
            lines = []
            if top5_general:
                lines.append(
                    f'Cuando sale {from_label}, los {next_label_pl} que más '
                    f'aparecen en el siguiente sorteo son: '
                    f'{_fmt(top5_general)} (General), '
                    f'{_fmt(top5_afternoon)} (Tarde), '
                    f'{_fmt(top5_evening)} (Noche).'
                )
            return ' '.join(lines)

        def _block_html(block_title, blk_dark, blk_light, entry_data, from_label, next_lbl_pl):
            g = entry_data.get('general',   [])
            a = entry_data.get('afternoon', [])
            e = entry_data.get('evening',   [])
            html = (
                f'<div class="sgt-block">'
                f'<span class="sgt-block-title" '
                f'style="background:{blk_dark}22;color:{blk_dark}">'
                f'{block_title}</span>'
            )
            for turn_key, turn_lbl, _ in TURNS:
                top5 = entry_data.get(turn_key, [])
                if not top5:
                    continue
                html += (
                    f'<div class="sgt-turn-row">'
                    f'<div class="sgt-turn-lbl">{turn_lbl}</div>'
                    f'<div class="sgt-items">{_items_html(top5)}</div>'
                    f'</div>'
                )
            prose = _prose(from_label, next_lbl_pl, g, a, e)
            if prose:
                html += f'<div class="sgt-prose">{prose}</div>'
            html += '</div>'
            return html

        # ── CSS ──────────────────────────────────────────────────────────────
        parts = []
        parts.append('''<style>
.sgt-wrap{font-family:inherit;color:#333}
.sgt-header{border-radius:12px;padding:20px 24px;margin-bottom:24px;color:#fff}
.sgt-header h1{margin:0 0 5px;font-size:1.45rem;font-weight:800;color:#fff}
.sgt-header .sgt-meta{font-size:.85rem;opacity:.85}
.sgt-section-hdr{border-radius:10px;padding:11px 18px;margin:0 0 18px;
  display:flex;align-items:center;gap:10px}
.sgt-section-hdr h2{margin:0;font-size:1.1rem;font-weight:700;color:#fff}
.sgt-section-hdr i{color:#fff;font-size:1rem}
.sgt-entries{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
  gap:16px;margin-bottom:24px}
.sgt-card{border:1px solid #dde3ec;border-radius:10px;overflow:hidden;
  box-shadow:0 2px 6px rgba(0,0,0,.06)}
.sgt-card-hdr{padding:10px 16px;font-weight:700;font-size:.95rem;
  color:#fff;display:flex;align-items:center;gap:9px}
.sgt-card-hdr .sgt-src-ball{width:32px;height:32px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:.72rem;font-weight:700;color:#fff;flex-shrink:0;
  border:2px solid rgba(255,255,255,.4)}
.sgt-card-body{padding:12px 14px;background:#fff}
.sgt-block{margin-bottom:14px;padding-bottom:13px;
  border-bottom:1px solid #edf0f5}
.sgt-block:last-child{margin-bottom:0;padding-bottom:0;border-bottom:none}
.sgt-block-title{font-size:.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.6px;margin-bottom:9px;padding:3px 9px;border-radius:4px;
  display:inline-block}
.sgt-turn-row{margin-bottom:7px}
.sgt-turn-lbl{font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.4px;color:#94a3b8;margin-bottom:4px}
.sgt-items{display:flex;flex-wrap:wrap;gap:5px}
.sgt-item{display:flex;align-items:center;gap:5px;background:#f5f7fb;
  border-radius:7px;padding:4px 8px;font-size:.78rem}
.sgt-item-ball{width:22px;height:22px;border-radius:50%;font-size:.62rem;
  font-weight:700;color:#fff;
  display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.sgt-item-lbl{color:#374151;font-weight:600}
.sgt-item-cnt{color:#94a3b8;font-size:.7rem}
.sgt-prose{background:#f0f4ff;border-left:3px solid #6366f1;
  border-radius:0 6px 6px 0;padding:9px 13px;margin-top:9px;
  font-size:.82rem;color:#1e293b;line-height:1.65}
.sgt-prose strong{color:#4338ca}
@media(max-width:600px){.sgt-entries{grid-template-columns:1fr}}
</style>''')

        parts.append('<div class="sgt-wrap">')
        parts.append(
            f'<div class="sgt-header" '
            f'style="background:linear-gradient(135deg,{HDR_DARK},{HDR_LIGHT})">'
            f'<h1><i class="fa {tipo_icon} me-2"></i>Secuencias de {tipo_lbl}</h1>'
            f'<div class="sgt-meta">Pick 3 Florida &nbsp;·&nbsp; '
            f'Generado el {date_str} &nbsp;·&nbsp; '
            f'Top 5 siguientes — General, Tarde y Noche</div>'
            f'</div>'
        )

        parts.append(
            f'<div class="sgt-section-hdr" '
            f'style="background:linear-gradient(135deg,{HDR_DARK},{HDR_LIGHT})">'
            f'<i class="fa {tipo_icon}"></i>'
            f'<h2>{tipo_lbl}</h2>'
            f'</div>'
        )
        parts.append('<div class="sgt-entries">')

        for entry in data.get(grp_type, []):
            num      = entry.get('num', '?')
            sublabel = entry.get('sublabel', '')
            cross    = cross_data.get(f'{grp_type}_{num}', {})
            from_label = f'la {entry_pfx.lower()} <strong>{sublabel}</strong>'

            same_data = {
                'general':   entry.get('general', []),
                'afternoon': entry.get('afternoon', []),
                'evening':   entry.get('evening', []),
            }

            parts.append(
                f'<div class="sgt-card">'
                f'<div class="sgt-card-hdr" '
                f'style="background:linear-gradient(135deg,{HDR_DARK},{HDR_LIGHT})">'
                f'<div class="sgt-src-ball" style="background:rgba(255,255,255,.2)">'
                f'{num}</div>'
                f'{entry_pfx} {num} &nbsp;'
                f'<span style="font-weight:400;font-size:.82rem;opacity:.85">'
                f'({sublabel})</span>'
                f'</div>'
                f'<div class="sgt-card-body">'
            )

            if grp_type == 'line':
                # 1) Lines that follow (same-type — same as stats page)
                parts.append(_block_html(
                    'Líneas que siguen',
                    LINE_DARK, LINE_LIGHT,
                    same_data,
                    from_label,
                    'líneas',
                ))
                # 2) Terminals that follow (cross-type)
                parts.append(_block_html(
                    'Terminales que siguen',
                    TERM_DARK, TERM_LIGHT,
                    cross,
                    from_label,
                    'terminales',
                ))
            else:
                # 1) Lines that follow (cross-type)
                parts.append(_block_html(
                    'Líneas que siguen',
                    LINE_DARK, LINE_LIGHT,
                    cross,
                    from_label,
                    'líneas',
                ))
                # 2) Terminals that follow (same-type — same as stats page)
                parts.append(_block_html(
                    'Terminales que siguen',
                    TERM_DARK, TERM_LIGHT,
                    same_data,
                    from_label,
                    'terminales',
                ))

            parts.append('</div></div>')  # sgt-card-body + sgt-card

        parts.append('</div>')  # sgt-entries
        parts.append('</div>')  # sgt-wrap
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 4: Sábado + Domingo · Grupos más frecuentes  (mensual)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_fin_de_semana_grupos(self, ref_date=None, force=False):
        """Weekly cron (Saturday): article with the most frequent line/terminal groups
        on Saturdays and Sundays. Runs in the early hours of Saturday so it includes
        Friday's draws and is ready for the coming weekend.

        Pass force=True to execute immediately regardless of the scheduled day,
        e.g. from the cron UI: model.cron_generate_fin_de_semana_grupos(force=True)
        """
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)

        # Guard: only run on Saturdays unless forced.
        if not force and today.weekday() != 5:
            _logger.info(
                'cron_generate_fin_de_semana_grupos skipped — %s is not Saturday. '
                'Use force=True to override.', today
            )
            return

        try:
            self._generate_fin_de_semana_grupos_article(today)
        except Exception as e:
            _logger.error('cron_generate_fin_de_semana_grupos: %s', e, exc_info=True)

    def _generate_fin_de_semana_grupos_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['lottery.stats.service'].sudo()
        date_str = today.strftime('%d/%m/%Y')
        # Slug fijo — un único artículo activo, siempre actualizado
        slug     = 'grupos-fin-semana'

        data = svc.get_weekend_groups()
        html_body = self._build_fin_de_semana_grupos_html(date_str, data)

        category = self.env.ref(
            'lottery_portal.news_category_analisis_mensuales', raise_if_not_found=False
        )
        title = 'Grupos más frecuentes los Sábados y Domingos — Pick 3 Florida'
        intro = (
            f'Top 5 grupos de líneas y terminales con mayor frecuencia histórica '
            f'los sábados y domingos en el Pick 3 Florida. '
            f'General, Tarde y Noche. Análisis al {date_str}.'
        )

        cover = self._load_cover_image('grupos fin semana.png')

        akey = 'fin_semana_grupos'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'article_key':  akey,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated fin-semana article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created fin-semana article: %s', slug)

        # Eliminar versiones anteriores por clave (evita conflictos de slug)
        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old fin-semana articles', len(old))

    def _build_fin_de_semana_grupos_html(self, date_str, data):
        """Build the weekend groups article with prose + bar layout."""

        LINE_DARK,  LINE_LIGHT  = '#7c2d12', '#ea580c'
        TERM_DARK,  TERM_LIGHT  = '#1e3a5f', '#2563eb'
        BALL_BG = ['#e74c3c', '#f59e0b', '#16a34a', '#2563eb', '#8b5cf6',
                   '#ec4899', '#0891b2', '#d97706', '#15803d', '#7c3aed']

        def _bc(num):
            try:
                return BALL_BG[int(num) % len(BALL_BG)]
            except (ValueError, TypeError):
                return BALL_BG[0]

        TURNS = [
            ('general',   'General', '#374151', '#6b7280', 'fa-globe'),
            ('afternoon', 'Tarde',   '#92400e', '#d97706', 'fa-sun-o'),
            ('evening',   'Noche',   '#312e81', '#4f46e5', 'fa-moon-o'),
        ]

        TYPE_CFG = [
            ('line',     'Líneas',     'línea',     LINE_DARK, LINE_LIGHT, 'fa-th-list'),
            ('terminal', 'Terminales', 'terminal',  TERM_DARK, TERM_LIGHT, 'fa-hashtag'),
        ]

        parts = []
        parts.append('''<style>
.fwg-wrap{font-family:inherit;color:#333}
.fwg-header{background:linear-gradient(135deg,#78350f,#f59e0b);color:#fff;
  border-radius:12px;padding:20px 24px;margin-bottom:24px}
.fwg-header h1{margin:0 0 5px;font-size:1.45rem;font-weight:800;color:#fff}
.fwg-header .fwg-meta{font-size:.85rem;opacity:.85}
.fwg-type-section{margin-bottom:32px}
.fwg-type-hdr{border-radius:10px;padding:11px 18px;margin-bottom:18px;
  display:flex;align-items:center;gap:10px}
.fwg-type-hdr h2{margin:0;font-size:1.1rem;font-weight:700;color:#fff}
.fwg-type-hdr i{color:#fff;font-size:1rem}
.fwg-turn-blocks{display:flex;flex-direction:column;gap:14px}
.fwg-turn-block{border:1px solid #dde3ec;border-radius:10px;overflow:hidden;
  box-shadow:0 2px 6px rgba(0,0,0,.05)}
.fwg-turn-hdr{padding:9px 16px;font-weight:700;font-size:.9rem;color:#fff;
  display:flex;align-items:center;gap:8px}
.fwg-turn-hdr i{opacity:.9}
.fwg-turn-body{padding:14px 16px;background:#fff}
.fwg-bars{display:flex;flex-direction:column;gap:8px;margin-bottom:12px}
.fwg-bar-row{display:flex;align-items:center;gap:10px}
.fwg-rank{background:rgba(0,0,0,.07);border:1px solid rgba(0,0,0,.1);
  border-radius:5px;padding:2px 7px;font-weight:700;font-size:.72rem;
  color:#666;flex-shrink:0}
.fwg-ball{width:32px;height:32px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.8rem;color:#fff;flex-shrink:0}
.fwg-bar-wrap{flex:1;min-width:0}
.fwg-bar-lbl{font-size:.78rem;color:#64748b;margin-bottom:3px}
.fwg-bar-bg{background:#e2e8f0;border-radius:4px;height:8px}
.fwg-bar-fill{height:8px;border-radius:4px}
.fwg-cnt{font-weight:700;font-size:.9rem;color:#1e293b;width:44px;
  text-align:right;flex-shrink:0}
.fwg-prose{background:#fff7ed;border-left:4px solid #f59e0b;
  border-radius:0 8px 8px 0;padding:11px 15px;
  font-size:.88rem;color:#1e293b;line-height:1.65}
.fwg-prose strong{color:#92400e}
@media(max-width:600px){
  .fwg-cnt{width:32px;font-size:.8rem}
  .fwg-ball{width:26px;height:26px;font-size:.7rem}
}
</style>''')

        parts.append('<div class="fwg-wrap">')
        parts.append(
            f'<div class="fwg-header">'
            f'<h1><i class="fa fa-calendar-o me-2"></i>'
            f'Grupos m&aacute;s frecuentes — S&aacute;bados y Domingos</h1>'
            f'<div class="fwg-meta">Pick 3 Florida &nbsp;·&nbsp; '
            f'Actualizado: {date_str} &nbsp;·&nbsp; '
            f'Top 5 grupos · General, Tarde y Noche</div>'
            f'</div>'
        )

        for grp_key, grp_lbl, grp_sing, dark, light, icon in TYPE_CFG:
            type_data = data.get(grp_key, {})

            parts.append(
                f'<div class="fwg-type-section">'
                f'<div class="fwg-type-hdr" '
                f'style="background:linear-gradient(135deg,{dark},{light})">'
                f'<i class="fa {icon}"></i>'
                f'<h2>{grp_lbl} m&aacute;s frecuentes en fin de semana</h2>'
                f'</div>'
                f'<div class="fwg-turn-blocks">'
            )

            for turn_key, turn_lbl, t_dark, t_light, t_icon in TURNS:
                top5 = type_data.get(turn_key, [])
                if not top5:
                    continue
                max_val = max((x.get('total', 0) or 0 for x in top5), default=1) or 1

                parts.append(
                    f'<div class="fwg-turn-block">'
                    f'<div class="fwg-turn-hdr" '
                    f'style="background:linear-gradient(135deg,{t_dark},{t_light})">'
                    f'<i class="fa {t_icon}"></i>{turn_lbl}'
                    f'</div>'
                    f'<div class="fwg-turn-body">'
                    f'<div class="fwg-bars">'
                )

                for i, item in enumerate(top5):
                    num   = item.get('num', '?')
                    lbl   = item.get('label', num)
                    total = item.get('total', 0) or 0
                    pct   = round(100 * total / max_val)
                    bc    = _bc(num)

                    parts.append(
                        f'<div class="fwg-bar-row">'
                        f'<span class="fwg-rank">#{i + 1}</span>'
                        f'<div class="fwg-ball" style="background:{bc}">{num}</div>'
                        f'<div class="fwg-bar-wrap">'
                        f'<div class="fwg-bar-lbl">{grp_sing.capitalize()} {lbl}</div>'
                        f'<div class="fwg-bar-bg">'
                        f'<div class="fwg-bar-fill" '
                        f'style="width:{pct}%;background:{light}"></div>'
                        f'</div>'
                        f'</div>'
                        f'<span class="fwg-cnt">{total}&times;</span>'
                        f'</div>'
                    )

                parts.append('</div>')  # fwg-bars

                # Prose for this turn
                def _fmt(lst, n=5):
                    return ', '.join(
                        f'<strong>{x["label"]}</strong> ({x["total"]})'
                        for x in lst[:n]
                    )

                prose = (
                    f'Los grupos de {grp_lbl.lower()} que m&aacute;s salen '
                    f'hist&oacute;ricamente los s&aacute;bados y domingos '
                    f'({turn_lbl}) son: {_fmt(top5)}.'
                )
                parts.append(f'<div class="fwg-prose">{prose}</div>')
                parts.append('</div></div>')  # fwg-turn-body + fwg-turn-block

            parts.append('</div></div>')  # fwg-turn-blocks + fwg-type-section

        parts.append('</div>')  # fwg-wrap
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 7: Números más salidores por día de la semana (diario)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_numeros_salidores_dia(self, ref_date=None):
        """Daily cron: generates/updates one article per weekday with the
        top-10 most-frequent numbers for that weekday (general, tarde, noche)
        plus their current delay stats."""
        import logging
        _logger = logging.getLogger(__name__)
        if ref_date:
            target_day = self._parse_ref_date(ref_date)
        else:
            self.env.cr.execute("SELECT MAX(date) AS d FROM lottery_output")
            row = self.env.cr.dictfetchone()
            target_day = row['d'] if row and row.get('d') else self._parse_ref_date(None) - timedelta(days=1)
        try:
            self._generate_numeros_salidores_dia_article(target_day)
        except Exception as e:
            _logger.error('cron_generate_numeros_salidores_dia: %s', e, exc_info=True)

    def _generate_numeros_salidores_dia_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        _WCODE = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
        _WLABEL = {
            'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles',
            'ju': 'Jueves', 'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo',
        }
        _cover_map = {
            'lu': 'mas salidores lunes.png',
            'ma': 'mas salidores martes.png',
            'mi': 'mas salidores miercoles.png',
            'ju': 'mas salidores jueves.png',
            'vi': 'mas salidores viernes.png',
            'sa': 'mas salidores sabado.png',
            'do': 'mas salidores domingo.png',
        }

        wcode         = _WCODE[today.weekday()]
        wlabel        = _WLABEL[wcode]
        # today = ayer del cron → today + 1 = fecha real de generación (timezone-aware)
        generated_str = (today + timedelta(days=1)).strftime('%d/%m/%Y')
        slug          = f'numeros-salidores-{wcode}'

        svc  = self.env['lottery.stats.service'].sudo()
        data = svc.get_top_numeros_por_dia_completo(wcode)

        html_body = self._build_numeros_salidores_dia_html(generated_str, wlabel, wcode, data)
        cover     = self._load_cover_image(_cover_map.get(wcode, 'atraso numeros lunes.png'))

        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        title = f'Números más salidores los {wlabel} — Pick 3 Florida'
        intro = (
            f'Top 10 números con mayor frecuencia histórica los {wlabel} en el '
            f'Pick 3 Florida, con análisis por turno (Tarde y Noche) y sus '
            f'atrasos actuales. Actualizado al {generated_str}.'
        )

        from odoo import fields as odoo_fields
        akey = f'salidores_dia_{wcode}'
        existing = self.search([('article_key', '=', akey)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'publish_date': odoo_fields.Datetime.now(),
            'is_published': True,
            'article_key':  akey,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated numeros-salidores article: %s', slug)
        else:
            existing = self.create(vals)
            _logger.info('Created numeros-salidores article: %s', slug)

    def _build_numeros_salidores_dia_html(self, date_str, wlabel, wcode, data):
        """HTML builder for the 'números más salidores por día' article."""

        BALL_COLORS = [
            '#e74c3c', '#f59e0b', '#16a34a', '#2563eb', '#8b5cf6',
            '#ec4899', '#0891b2', '#d97706', '#15803d', '#7c3aed',
        ]

        def ball_color(name):
            try:
                return BALL_COLORS[int(name) % len(BALL_COLORS)]
            except (ValueError, TypeError):
                return BALL_COLORS[0]

        def delay_color(val):
            val = val or 0
            if val <= 5:
                return '#16a34a'
            if val <= 15:
                return '#d97706'
            return '#dc2626'

        def delay_label(val):
            val = val or 0
            if val == 0:
                return 'Al día'
            if val == 1:
                return '1 sorteo'
            return f'{val} sorteos'

        SECTIONS = [
            ('general', 'General', '#1e3a5f', '#2563eb', 'delay_general', 'fa-globe'),
            ('tarde',   'Tarde',   '#92400e', '#d97706', 'delay_tarde',   'fa-sun-o'),
            ('noche',   'Noche',   '#312e81', '#4f46e5', 'delay_noche',   'fa-moon-o'),
        ]

        parts = []
        parts.append('''<style>
.nsd-wrap{font-family:inherit;color:#333}
.nsd-header{background:linear-gradient(135deg,#4c1d95,#7c3aed);color:#fff;
  border-radius:12px;padding:20px 24px;margin-bottom:24px}
.nsd-header h1{margin:0 0 6px;font-size:1.5rem;font-weight:800;color:#fff}
.nsd-header .nsd-meta{font-size:.85rem;opacity:.85}
.nsd-section{margin-bottom:28px}
.nsd-sec-hdr{display:flex;align-items:center;gap:10px;
  border-radius:10px;padding:11px 18px;margin-bottom:14px}
.nsd-sec-hdr i{font-size:1rem;opacity:.9;color:#fff}
.nsd-sec-hdr h2{margin:0;font-size:1.1rem;font-weight:700;color:#fff}
.nsd-bars{display:flex;flex-direction:column;gap:7px}
.nsd-bar-row{display:flex;align-items:center;gap:10px;
  background:#f8f9fb;border-radius:8px;padding:8px 12px}
.nsd-rank{background:rgba(0,0,0,.07);border:1px solid rgba(0,0,0,.1);
  border-radius:5px;padding:2px 7px;font-weight:700;font-size:.72rem;
  color:#666;flex-shrink:0;letter-spacing:.3px}
.nsd-ball{width:34px;height:34px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.88rem;color:#fff;flex-shrink:0}
.nsd-bar-wrap{flex:1;min-width:0}
.nsd-bar-label{font-size:.78rem;color:#64748b;margin-bottom:3px}
.nsd-bar-bg{background:#e2e8f0;border-radius:4px;height:8px}
.nsd-bar-fill{height:8px;border-radius:4px}
.nsd-freq{font-weight:700;font-size:.9rem;color:#1e293b;width:52px;
  text-align:right;flex-shrink:0}
.nsd-delay-badge{border-radius:6px;padding:3px 9px;font-size:.76rem;
  font-weight:700;color:#fff;flex-shrink:0;white-space:nowrap}
.nsd-date-small{font-size:.72rem;color:#94a3b8;flex-shrink:0;white-space:nowrap}
.nsd-prose{background:#f0f4ff;border-left:4px solid #6366f1;
  border-radius:0 8px 8px 0;padding:14px 18px;margin-top:10px;
  font-size:.92rem;color:#1e293b;line-height:1.65}
.nsd-prose strong{color:#4338ca}
@media(max-width:600px){
  .nsd-date-small{display:none}
  .nsd-freq{width:38px;font-size:.8rem}
  .nsd-ball{width:28px;height:28px;font-size:.75rem}
  .nsd-delay-badge{font-size:.68rem;padding:2px 6px}
}
</style>''')

        parts.append('<div class="nsd-wrap">')
        parts.append(
            f'<div class="nsd-header">'
            f'<h1><i class="fa fa-star me-2"></i>Números más salidores los {wlabel}</h1>'
            f'<div class="nsd-meta">Pick 3 Florida &nbsp;·&nbsp; '
            f'Actualizado: {date_str} &nbsp;·&nbsp; '
            f'Top 10 por turno con atrasos actuales</div>'
            f'</div>'
        )

        for section_key, section_lbl, dark, light, delay_field, icon in SECTIONS:
            rows = data.get(section_key, [])
            if not rows:
                continue

            max_total = max((r.get('total', 0) or 0 for r in rows), default=1) or 1

            parts.append(
                f'<div class="nsd-section">'
                f'<div class="nsd-sec-hdr" '
                f'style="background:linear-gradient(135deg,{dark},{light})">'
                f'<i class="fa {icon}"></i>'
                f'<h2>{section_lbl}</h2>'
                f'</div>'
                f'<div class="nsd-bars">'
            )

            for i, row in enumerate(rows):
                name   = row.get('name', '??')
                total  = row.get('total', 0) or 0
                delay  = row.get(delay_field, 0) or 0
                ultima = row.get('ultima_fecha') or '—'
                pct    = round(100 * total / max_total)
                bc     = ball_color(name)
                dc     = delay_color(delay)
                dlbl   = delay_label(delay)

                parts.append(
                    f'<div class="nsd-bar-row">'
                    f'<span class="nsd-rank">#{i + 1}</span>'
                    f'<div class="nsd-ball" style="background:{bc}">{name}</div>'
                    f'<div class="nsd-bar-wrap">'
                    f'<div class="nsd-bar-label">Número {name}</div>'
                    f'<div class="nsd-bar-bg">'
                    f'<div class="nsd-bar-fill" '
                    f'style="width:{pct}%;background:{light}"></div>'
                    f'</div>'
                    f'</div>'
                    f'<span class="nsd-freq">{total}&times;</span>'
                    f'<span class="nsd-delay-badge" style="background:{dc}" '
                    f'title="Atraso actual">&#9201; {dlbl}</span>'
                    f'<span class="nsd-date-small">'
                    f'&Uacute;lt.&nbsp;{wlabel[:3]}: {ultima}</span>'
                    f'</div>'
                )

            parts.append('</div>')  # nsd-bars

            # Prose interpretation block
            most_delayed  = max(rows, key=lambda r: r.get(delay_field, 0) or 0)
            least_delayed = min(rows, key=lambda r: r.get(delay_field, 0) or 0)
            top1 = rows[0]

            md_name  = most_delayed.get('name', '??')
            md_delay = most_delayed.get(delay_field, 0) or 0
            ld_name  = least_delayed.get('name', '??')
            ld_delay = least_delayed.get(delay_field, 0) or 0
            t1_name  = top1.get('name', '??')
            t1_total = top1.get('total', 0) or 0

            section_ctx = {
                'general': f'los {wlabel}',
                'tarde':   f'en la Tarde de los {wlabel}',
                'noche':   f'en la Noche de los {wlabel}',
            }[section_key]
            delay_ctx = {
                'general': 'atraso general',
                'tarde':   'atraso en Tarde',
                'noche':   'atraso en Noche',
            }[section_key]

            prose = (
                f'El número más frecuente {section_ctx} es el '
                f'<strong>{t1_name}</strong>, con {t1_total} apariciones históricas. '
                f'Entre los 10 más salidores, el de mayor {delay_ctx} actualmente '
                f'es el <strong>{md_name}</strong> ({delay_label(md_delay)} sin salir)'
            )
            if md_name != ld_name:
                prose += (
                    f', mientras que el <strong>{ld_name}</strong> es el más reciente '
                    f'({delay_label(ld_delay)}).'
                )
            else:
                prose += '.'
            parts.append(f'<div class="nsd-prose">{prose}</div>')

            parts.append('</div>')  # nsd-section

        parts.append('</div>')  # nsd-wrap
        return ''.join(parts)
