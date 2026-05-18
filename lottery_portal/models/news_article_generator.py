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
        from datetime import date
        return date.today()

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

        svc = self.env['stats.service']
        date_str  = today.strftime('%d/%m/%Y')
        day_code  = today.strftime('%A').lower()[:3]
        month_num = today.month
        week_num  = today.isocalendar()[1]

        _DAY_MAP = {
            'mon': 'lunes', 'tue': 'martes', 'wed': 'miercoles',
            'thu': 'jueves', 'fri': 'viernes', 'sat': 'sabado', 'sun': 'domingo',
        }
        day_es = _DAY_MAP.get(day_code, '')

        raw = svc.get_top_6_groups(option, day_es)
        groups_data = (raw or [])[:5]

        int_cfg = {
            'ranges': [
                ('21-40', 'r_21_40'),
                ('41-50', 'r_41_50'),
                ('51-60', 'r_51_60'),
                ('61-70', 'r_61_70'),
                ('+70',   'r_70_plus'),
            ],
            'method': 'get_group_delay_intervals',
        }

        title_ctx = f'Top 5 Grupos más atrasados — {label}'
        slug      = f'grupos-atrasados-{option}-{today.strftime("%Y-%m-%d")}'[:100]

        html_body = self._build_group_article_html(
            title_ctx, date_str, today, option, day_es,
            month_num, week_num, groups_data, int_cfg,
        )

        category = self.env.ref(
            'lottery_portal.news_category_grupos_atrasados', raise_if_not_found=False
        )

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title_ctx,
            'slug':         slug,
            'summary':      f'Análisis de los 5 grupos más atrasados ({label}) al {date_str}.',
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated grupos article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created grupos article: %s', slug)

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

        svc = self.env['stats.service']
        date_str  = today.strftime('%d/%m/%Y')
        day_code  = today.strftime('%A').lower()[:3]
        month_num = today.month
        week_num  = today.isocalendar()[1]

        _DAY_MAP = {
            'mon': 'lunes', 'tue': 'martes', 'wed': 'miercoles',
            'thu': 'jueves', 'fri': 'viernes', 'sat': 'sabado', 'sun': 'domingo',
        }
        day_es = _DAY_MAP.get(day_code, '')

        raw = svc.get_top_3_pintas(option, day_es)
        groups_data = (raw or [])[:3]

        int_cfg = {
            'ranges': [
                ('10-20', 'r_10_20'),
                ('21-30', 'r_21_30'),
                ('31-40', 'r_31_40'),
                ('41-45', 'r_41_45'),
                ('+45',   'r_45_plus'),
            ],
            'method': 'get_group_delay_intervals_pintas',
        }

        title_ctx = f'Top 3 Pintas más atrasadas — {label}'
        slug      = f'pintas-atrasadas-{option}-{today.strftime("%Y-%m-%d")}'[:100]

        html_body = self._build_group_article_html(
            title_ctx, date_str, today, option, day_es,
            month_num, week_num, groups_data, int_cfg,
        )

        category = self.env.ref(
            'lottery_portal.news_category_pintas_atrasadas', raise_if_not_found=False
        )

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title_ctx,
            'slug':         slug,
            'summary':      f'Análisis de las 3 pintas más atrasadas ({label}) al {date_str}.',
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated pintas article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created pintas article: %s', slug)

    # ─────────────────────────────────────────────────────────────────────────
    # Shared HTML builder for grupos / pintas articles
    # ─────────────────────────────────────────────────────────────────────────
    def _build_group_article_html(
        self, title_ctx, date_str, today, option, day_es,
        month_num, week_num, groups_data, int_cfg,
    ):
        svc = self.env['stats.service']
        parts = []

        # ── Inline CSS ────────────────────────────────────────────────────
        parts.append('''<style>
.ga-wrap{font-family:inherit;color:#333}
.ga-header{background:linear-gradient(135deg,#2c3e50,#4a6fa5);color:#fff;
  border-radius:10px;padding:18px 22px;margin-bottom:24px}
.ga-header h1{margin:0 0 4px;font-size:1.4rem;font-weight:700}
.ga-header .ga-meta{font-size:.85rem;opacity:.85}
.ga-card{border:1px solid #dde3ec;border-radius:10px;margin-bottom:28px;
  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.ga-card-header{padding:12px 18px;display:flex;align-items:center;gap:10px}
.ga-card-header .ga-rank{width:32px;height:32px;border-radius:50%;
  background:#fff;font-weight:700;font-size:1rem;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ga-card-header h2{margin:0;font-size:1.1rem;font-weight:600;color:#fff}
.ga-card-body{padding:16px 18px;background:#fff}
.ga-stats-row{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.ga-stat{flex:1 1 120px;background:#f5f7fb;border-radius:8px;
  padding:10px 14px;text-align:center}
.ga-stat .ga-stat-val{font-size:1.5rem;font-weight:700;color:#2c3e50}
.ga-stat .ga-stat-lbl{font-size:.75rem;color:#666;margin-top:2px}
.ga-section-title{font-size:.85rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.6px;color:#555;margin:16px 0 8px;border-bottom:2px solid #eee;
  padding-bottom:4px}
.ga-histogram{display:flex;align-items:flex-end;gap:6px;height:80px;margin-bottom:4px}
.ga-bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
.ga-bar{width:100%;border-radius:4px 4px 0 0;min-height:4px}
.ga-bar-lbl{font-size:.7rem;color:#555;white-space:nowrap}
.ga-bar-val{font-size:.7rem;font-weight:700;color:#2c3e50}
.ga-nums-grid{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.ga-ball{width:32px;height:32px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;
  font-weight:700;font-size:.8rem;color:#fff;flex-shrink:0}
.ga-ball-delay{font-size:.65rem;color:#888;text-align:center;margin-top:1px}
.ga-num-item{display:flex;flex-direction:column;align-items:center;width:40px}
.ga-analysis{background:#f9fafb;border-radius:8px;padding:12px 14px;margin-top:10px}
.ga-analysis h4{font-size:.85rem;font-weight:700;margin:0 0 10px;color:#2c3e50}
.ga-analysis-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.ga-analysis-item{background:#fff;border:1px solid #e8edf5;border-radius:6px;padding:8px 10px}
.ga-analysis-item .ga-ai-label{font-size:.7rem;color:#888;margin-bottom:2px}
.ga-analysis-item .ga-ai-val{font-size:.9rem;font-weight:700;color:#2c3e50}
</style>''')

        # ── Article header ─────────────────────────────────────────────────
        turn_label = {'all': 'General', 'tarde': 'Tarde', 'noche': 'Noche'}.get(option, option)
        parts.append(
            f'<div class="ga-wrap">'
            f'<div class="ga-header">'
            f'<h1>{title_ctx}</h1>'
            f'<div class="ga-meta">Generado el {date_str} &nbsp;&middot;&nbsp; Turno: {turn_label}</div>'
            f'</div>'
        )

        PALETTES = [
            ('#c0392b', '#e74c3c'),
            ('#1a6b3a', '#27ae60'),
            ('#154360', '#2980b9'),
            ('#6c3483', '#8e44ad'),
            ('#784212', '#d35400'),
        ]
        BALL_COLORS = ['#e74c3c', '#27ae60', '#2980b9', '#8e44ad', '#d35400',
                       '#16a085', '#2c3e50', '#c0392b', '#7d6608', '#1a5276']

        int_method = int_cfg['method']
        int_ranges = int_cfg['ranges']

        for idx, grp in enumerate(groups_data):
            grp_id   = grp.get('id')
            grp_name = grp.get('name', f'Grupo {idx + 1}')
            atraso   = grp.get('salidas_atrasadas', 0)
            atraso_t = grp.get('salidas_atrasadas_dia', 0)
            atraso_n = grp.get('salidas_atrasadas_noche', 0)

            dark, light = PALETTES[idx % len(PALETTES)]

            # Card header
            parts.append(
                f'<div class="ga-card">'
                f'<div class="ga-card-header" style="background:linear-gradient(135deg,{dark},{light})">'
                f'<div class="ga-rank" style="color:{dark}">{idx + 1}</div>'
                f'<h2>{grp_name}</h2>'
                f'</div>'
                f'<div class="ga-card-body">'
            )

            # Stats row
            parts.append('<div class="ga-stats-row">')
            for val, lbl in [
                (atraso,   'Atraso General'),
                (atraso_t, 'Atraso Tarde'),
                (atraso_n, 'Atraso Noche'),
            ]:
                parts.append(
                    f'<div class="ga-stat">'
                    f'<div class="ga-stat-val">{val}</div>'
                    f'<div class="ga-stat-lbl">{lbl}</div>'
                    f'</div>'
                )
            parts.append('</div>')

            # Delay-intervals histogram
            try:
                intervals_fn = getattr(svc, int_method)
                turn_param   = option if option != 'all' else 'general'
                iv = intervals_fn(grp_id, turn_param)
                max_val = max((iv.get(k, 0) for _, k in int_ranges), default=1) or 1
                parts.append('<div class="ga-section-title">Intervalos de atraso</div>')
                parts.append('<div class="ga-histogram">')
                for range_lbl, key in int_ranges:
                    cnt = iv.get(key, 0)
                    pct = max(int(cnt / max_val * 70), 4) if cnt else 4
                    parts.append(
                        f'<div class="ga-bar-wrap">'
                        f'<div class="ga-bar-val">{cnt}</div>'
                        f'<div class="ga-bar" style="height:{pct}px;background:{light}"></div>'
                        f'<div class="ga-bar-lbl">{range_lbl}</div>'
                        f'</div>'
                    )
                parts.append('</div>')
            except Exception:
                pass

            # Numbers grid
            try:
                grp_record = self.env['lottery.group'].browse(grp_id)
                nums = svc.get_info_groups_numbers(grp_record, 'atraso', day_es or False)
                if nums:
                    parts.append('<div class="ga-section-title">Números del grupo (por atraso)</div>')
                    parts.append('<div class="ga-nums-grid">')
                    for ni, num in enumerate(nums):
                        bc     = BALL_COLORS[ni % len(BALL_COLORS)]
                        n_name = num.get('numero', '')
                        delay  = num.get('total_atrasadas', 0)
                        parts.append(
                            f'<div class="ga-num-item">'
                            f'<div class="ga-ball" style="background:{bc}">{n_name}</div>'
                            f'<div class="ga-ball-delay">{delay}</div>'
                            f'</div>'
                        )
                    parts.append('</div>')
            except Exception:
                pass

            # Históricos Generales
            try:
                analysis = svc.get_info_group_numbers_analysis(
                    grp_id, day_es or False, week_num, month_num, limit=5
                )
                if analysis:
                    parts.append('<div class="ga-analysis"><h4>Históricos Generales</h4>')
                    parts.append('<div class="ga-analysis-grid">')

                    def _ai(lbl, val):
                        v = val.get('name', '—') if isinstance(val, dict) else (val or '—')
                        return (
                            f'<div class="ga-analysis-item">'
                            f'<div class="ga-ai-label">{lbl}</div>'
                            f'<div class="ga-ai-val">{v}</div>'
                            f'</div>'
                        )

                    parts.append(_ai('Última salida',        analysis.get('last')))
                    parts.append(_ai('Última (Tarde)',        analysis.get('last_day')))
                    parts.append(_ai('Última (Noche)',        analysis.get('last_night')))
                    parts.append(_ai('Más atrasado',          analysis.get('most_delayed')))
                    parts.append(_ai('Más atrasado Tarde',    analysis.get('most_delayed_day')))
                    parts.append(_ai('Más atrasado Noche',    analysis.get('most_delayed_night')))

                    day_d = analysis.get('day', {})
                    if day_d:
                        parts.append(_ai('Día más frecuente',   day_d.get('most')))
                        parts.append(_ai('Día menos frecuente', day_d.get('least')))

                    month_d = analysis.get('month', {})
                    if month_d:
                        parts.append(_ai('Mes más frecuente',   month_d.get('most')))
                        parts.append(_ai('Mes menos frecuente', month_d.get('least')))

                    week_d = analysis.get('week', {})
                    if week_d:
                        parts.append(_ai('Semana más frecuente',   week_d.get('most')))
                        parts.append(_ai('Semana menos frecuente', week_d.get('least')))

                    parts.append('</div></div>')
            except Exception:
                pass

            # close card-body + card
            parts.append('</div></div>')

        # close ga-wrap
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

        svc      = self.env['stats.service']
        date_str = today.strftime('%d/%m/%Y')
        slug     = f'numeros-atrasados-{today.strftime("%Y-%m-%d")}'[:100]

        general = svc.get_top_10_general()
        tarde   = svc.get_top_10_dia()
        noche   = svc.get_top_10_noche()

        html_body = self._build_numeros_atrasados_html(date_str, general, tarde, noche)

        category = self.env.ref(
            'lottery_portal.news_category_atrasos_numeros', raise_if_not_found=False
        )
        title = f'Top 10 Números más Atrasados — {date_str}'
        intro = f'Ranking de los 10 números con mayor atraso acumulado al {date_str}, en los tres turnos.'

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated numeros-atrasados article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created numeros-atrasados article: %s', slug)

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
        """Generate one article per run for today's weekday delayed numbers."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        try:
            self._generate_numeros_dia_semana_article(today)
        except Exception as e:
            _logger.error('cron_generate_numeros_dia_semana: %s', e, exc_info=True)

    def _generate_numeros_dia_semana_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['stats.service']
        date_str = today.strftime('%d/%m/%Y')
        wday     = today.weekday()                              # 0=Mon…6=Sun
        wcode    = self._WEEKDAY_CODE[wday]
        wlabel   = self._WEEKDAY_ES[wcode]
        slug     = f'numeros-atrasados-{wcode}-{today.strftime("%Y-%m-%d")}'[:100]

        rows = svc.get_top_10_por_dia_semana(wcode)

        # Enrich each row with companion data + day/night counts
        enriched = []
        for row in rows:
            num_name = row.get('name', '')
            num_rec  = self.env['lottery.number'].sudo().search(
                [('name', '=', int(num_name))], limit=1
            )
            companions = []
            dia_count = noche_count = 0
            if num_rec:
                companions  = svc.get_salidas_numeros_despues_numero(num_rec.id)[:5]
                dia_count   = num_rec.total_salidas_dia   or 0
                noche_count = num_rec.total_salidas_noche or 0
            enriched.append({
                **row,
                'companions':  companions,
                'dia_count':   dia_count,
                'noche_count': noche_count,
            })

        html_body = self._build_numeros_dia_semana_html(
            date_str, wlabel, wcode, enriched
        )

        category = self.env.ref(
            'lottery_portal.news_category_atrasos_numeros', raise_if_not_found=False
        )
        title = f'Números más atrasados los {wlabel} — {date_str}'
        intro = (f'Análisis de los 10 números con mayor atraso acumulado '
                 f'los {wlabel}, con sus acompañantes y tendencia día/noche.')

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated dia-semana article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created dia-semana article: %s', slug)

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
.nd-card-hdr .nd-rank{width:28px;height:28px;border-radius:50%;background:#fff;
  color:#1e3a5f;font-weight:700;font-size:.9rem;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
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
.nd-companions-title{font-size:.8rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;color:#555;margin-bottom:8px}
.nd-companions{display:flex;flex-wrap:wrap;gap:8px}
.nd-comp-item{display:flex;flex-direction:column;align-items:center;gap:2px}
.nd-comp-ball{width:30px;height:30px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:.78rem;color:#fff}
.nd-comp-cnt{font-size:.68rem;color:#888}
.nd-last-row{font-size:.78rem;color:#777;margin-top:10px}
</style>''')

        BALL_BG = ['#e74c3c','#e67e22','#f59e0b','#16a34a','#0891b2',
                   '#3b82f6','#8b5cf6','#ec4899','#14b8a6','#84cc16']
        COMP_BG = ['#60a5fa','#34d399','#f472b6','#fb923c','#a78bfa']

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
            companions = row.get('companions', [])

            tag_lbl = 'Tarde' if turno == 'afternoon' else ('Noche' if turno == 'evening' else '—')
            dominant = 'Más tarde' if dia_count >= noche_count else 'Más noche'
            dom_cls  = 'nd-badge-day' if dia_count >= noche_count else 'nd-badge-night'

            parts.append(
                f'<div class="nd-card">'
                f'<div class="nd-card-hdr">'
                f'<div class="nd-rank">{i + 1}</div>'
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

            # Companions (numbers that come after)
            if companions:
                parts.append('<div class="nd-companions-title">Acompañantes frecuentes (sale después)</div>')
                parts.append('<div class="nd-companions">')
                for j, comp in enumerate(companions):
                    cbc  = COMP_BG[j % len(COMP_BG)]
                    cname = str(comp.get('name', '?')).zfill(2)
                    ccnt  = comp.get('cantidad_veces', 0)
                    parts.append(
                        f'<div class="nd-comp-item">'
                        f'<div class="nd-comp-ball" style="background:{cbc}">{cname}</div>'
                        f'<div class="nd-comp-cnt">{ccnt}×</div>'
                        f'</div>'
                    )
                parts.append('</div>')

            parts.append('</div></div>')  # card-body + card

        parts.append('</div>')
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 3: Secuencias de Grupos  (mensual)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_secuencias_grupos(self, ref_date=None):
        """Generate one article per month with group-sequence analysis."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)
        try:
            self._generate_secuencias_grupos_article(today)
        except Exception as e:
            _logger.error('cron_generate_secuencias_grupos: %s', e, exc_info=True)

    def _generate_secuencias_grupos_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['stats.service']
        date_str = today.strftime('%d/%m/%Y')
        month_str = today.strftime('%Y-%m')
        slug      = f'secuencias-grupos-{month_str}'[:100]

        data = svc.get_all_group_sequences()

        html_body = self._build_secuencias_grupos_html(date_str, data)

        category = self.env.ref(
            'lottery_portal.news_category_generales', raise_if_not_found=False
        )
        title = f'Secuencias de Grupos — {today.strftime("%B %Y").capitalize()}'
        intro = (
            f'Top 5 grupos que aparecen con mayor frecuencia a continuación de '
            f'cada línea y terminal. Análisis al {date_str}.'
        )

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated secuencias-grupos article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created secuencias-grupos article: %s', slug)

    def _build_secuencias_grupos_html(self, date_str, data):
        parts = []
        parts.append('''<style>
.sg-wrap{font-family:inherit;color:#333}
.sg-header{background:linear-gradient(135deg,#0f5132,#198754);color:#fff;
  border-radius:10px;padding:18px 22px;margin-bottom:24px}
.sg-header h1{margin:0 0 4px;font-size:1.4rem;font-weight:700}
.sg-header .sg-meta{font-size:.85rem;opacity:.85}
.sg-type-title{font-size:1.1rem;font-weight:700;color:#fff;
  padding:10px 18px;border-radius:8px;margin:0 0 16px}
.sg-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:28px}
.sg-card{border:1px solid #dde3ec;border-radius:8px;overflow:hidden}
.sg-card-hdr{padding:8px 12px;font-weight:700;font-size:.9rem;color:#fff}
.sg-card-body{padding:10px 12px;background:#fff}
.sg-turn-block{margin-bottom:10px}
.sg-turn-lbl{font-size:.72rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;color:#888;margin-bottom:4px}
.sg-seq-row{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:3px}
.sg-seq-item{display:flex;align-items:center;gap:4px;background:#f5f7fb;
  border-radius:6px;padding:3px 7px;font-size:.8rem}
.sg-seq-ball{width:22px;height:22px;border-radius:50%;font-size:.68rem;
  font-weight:700;color:#fff;
  display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.sg-seq-cnt{color:#555;font-size:.75rem}
.sg-bar-bg{flex:1;background:#eee;border-radius:3px;height:5px;min-width:30px}
.sg-bar-fill{height:5px;border-radius:3px}
</style>''')

        TYPE_META = {
            'line':     ('Líneas Consecutivas',  '#0d6e3b', '#198754'),
            'terminal': ('Terminales Consecutivos', '#1e3a5f', '#2563eb'),
        }
        BALL_BG = ['#e74c3c','#f59e0b','#16a34a','#2563eb','#8b5cf6',
                   '#ec4899','#0891b2','#d97706','#15803d','#7c3aed']

        parts.append('<div class="sg-wrap">')
        parts.append(
            f'<div class="sg-header">'
            f'<h1>Secuencias de Grupos</h1>'
            f'<div class="sg-meta">Generado el {date_str} &nbsp;&middot;&nbsp; '
            f'Top 5 siguientes para cada línea y terminal</div>'
            f'</div>'
        )

        for grp_type in ('line', 'terminal'):
            type_lbl, dark, light = TYPE_META[grp_type]
            entries = data.get(grp_type, [])

            parts.append(
                f'<div class="sg-type-title" '
                f'style="background:linear-gradient(135deg,{dark},{light})">'
                f'{type_lbl}</div>'
            )
            parts.append('<div class="sg-grid">')

            for entry in entries:
                num      = entry.get('num', '?')
                sublabel = entry.get('sublabel', '')
                bc       = BALL_BG[int(num) % len(BALL_BG)]

                parts.append(
                    f'<div class="sg-card">'
                    f'<div class="sg-card-hdr" style="background:linear-gradient(135deg,{dark},{light})">'
                    f'Grupo {num} &nbsp;<span style="font-weight:400;font-size:.8rem">({sublabel})</span>'
                    f'</div>'
                    f'<div class="sg-card-body">'
                )

                for turn_key, turn_label in [
                    ('general',   'General'),
                    ('afternoon', 'Tarde'),
                    ('evening',   'Noche'),
                ]:
                    top5 = entry.get(turn_key, [])
                    if not top5:
                        continue
                    max_total = max((x.get('total', 0) for x in top5), default=1) or 1
                    parts.append(
                        f'<div class="sg-turn-block">'
                        f'<div class="sg-turn-lbl">{turn_label}</div>'
                        f'<div class="sg-seq-row">'
                    )
                    for item in top5:
                        item_bc  = BALL_BG[int(item.get('ball_num', 0)) % len(BALL_BG)]
                        itot     = item.get('total', 0)
                        ipct     = round(100 * itot / max_total)
                        parts.append(
                            f'<div class="sg-seq-item">'
                            f'<div class="sg-seq-ball" style="background:{item_bc}">'
                            f'{item.get("label","")}</div>'
                            f'<div class="sg-bar-bg"><div class="sg-bar-fill" '
                            f'style="width:{ipct}%;background:{light}"></div></div>'
                            f'<span class="sg-seq-cnt">{itot}</span>'
                            f'</div>'
                        )
                    parts.append('</div></div>')

                parts.append('</div></div>')  # card-body + card

            parts.append('</div>')  # sg-grid

        parts.append('</div>')
        return ''.join(parts)

    # ═════════════════════════════════════════════════════════════════════════
    # ARTÍCULO 4: Sábado + Domingo · Grupos más frecuentes  (1er viernes/mes)
    # ═════════════════════════════════════════════════════════════════════════
    def cron_generate_fin_de_semana_grupos(self, ref_date=None):
        """Run weekly; executes only on the 1st Friday of the month."""
        import logging
        _logger = logging.getLogger(__name__)
        today = self._parse_ref_date(ref_date)

        # Only execute on the 1st Friday of the month (day 4 = Friday; day <= 7)
        if today.weekday() != 4 or today.day > 7:
            _logger.info(
                'cron_generate_fin_de_semana_grupos skipped — today (%s) '
                'is not the first Friday of the month.', today
            )
            return

        try:
            self._generate_fin_de_semana_grupos_article(today)
        except Exception as e:
            _logger.error('cron_generate_fin_de_semana_grupos: %s', e, exc_info=True)

    def _generate_fin_de_semana_grupos_article(self, today):
        import logging
        _logger = logging.getLogger(__name__)

        svc      = self.env['stats.service']
        date_str = today.strftime('%d/%m/%Y')
        month_str = today.strftime('%Y-%m')
        slug      = f'grupos-fin-semana-{month_str}'[:100]

        data = svc.get_weekend_groups()

        html_body = self._build_fin_de_semana_grupos_html(date_str, data)

        category = self.env.ref(
            'lottery_portal.news_category_generales', raise_if_not_found=False
        )
        title = f'Sábado + Domingo · Grupos más frecuentes — {today.strftime("%B %Y").capitalize()}'
        intro = (
            f'Top 5 líneas y terminales con mayor frecuencia de salidas '
            f'los sábados y domingos. Análisis al {date_str}.'
        )

        existing = self.search([('slug', '=', slug)], limit=1)
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'is_published': True,
            'category_id':  category.id if category else False,
        }
        if existing:
            existing.write(vals)
            _logger.info('Updated fin-semana article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created fin-semana article: %s', slug)

    def _build_fin_de_semana_grupos_html(self, date_str, data):
        parts = []
        parts.append('''<style>
.fw-wrap{font-family:inherit;color:#333}
.fw-header{background:linear-gradient(135deg,#0f5132,#198754);color:#fff;
  border-radius:10px;padding:18px 22px;margin-bottom:24px}
.fw-header h1{margin:0 0 4px;font-size:1.4rem;font-weight:700}
.fw-header .fw-meta{font-size:.85rem;opacity:.85}
.fw-type-block{margin-bottom:32px}
.fw-type-title{font-size:1rem;font-weight:700;color:#fff;
  padding:10px 16px;border-radius:8px;margin-bottom:16px}
.fw-turns{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}
.fw-turn-card{border:1px solid #dde3ec;border-radius:8px;overflow:hidden}
.fw-turn-hdr{padding:7px 12px;font-size:.82rem;font-weight:700;color:#fff;text-align:center}
.fw-turn-body{padding:10px 12px;background:#fff}
.fw-bar-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.fw-bar-ball{width:28px;height:28px;border-radius:50%;font-size:.75rem;font-weight:700;
  color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fw-bar-label{font-size:.78rem;color:#555;width:48px;flex-shrink:0}
.fw-bar-bg{flex:1;background:#eef0f5;border-radius:4px;height:8px}
.fw-bar-fill{height:8px;border-radius:4px}
.fw-bar-cnt{font-size:.75rem;font-weight:700;color:#2c3e50;width:28px;text-align:right}
</style>''')

        TYPE_META = {
            'line':     ('Líneas Consecutivas',    '#7c2d12', '#ea580c'),
            'terminal': ('Terminales Consecutivos', '#1e3a5f', '#2563eb'),
        }
        TURN_META = [
            ('general',   'General',  '#374151', '#6b7280'),
            ('afternoon', 'Tarde',    '#92400e', '#d97706'),
            ('evening',   'Noche',    '#312e81', '#4f46e5'),
        ]
        BALL_BG = ['#e74c3c','#f59e0b','#16a34a','#2563eb','#8b5cf6',
                   '#ec4899','#0891b2','#d97706','#15803d','#7c3aed']

        parts.append('<div class="fw-wrap">')
        parts.append(
            f'<div class="fw-header">'
            f'<h1>Sábado + Domingo · Grupos más frecuentes</h1>'
            f'<div class="fw-meta">Generado el {date_str} &nbsp;&middot;&nbsp; '
            f'Líneas y Terminales</div>'
            f'</div>'
        )

        for grp_type in ('line', 'terminal'):
            type_lbl, dark, light = TYPE_META[grp_type]
            type_data = data.get(grp_type, {})

            parts.append(
                f'<div class="fw-type-block">'
                f'<div class="fw-type-title" '
                f'style="background:linear-gradient(135deg,{dark},{light})">'
                f'{type_lbl}</div>'
                f'<div class="fw-turns">'
            )

            for turn_key, turn_lbl, t_dark, t_light in TURN_META:
                top5 = type_data.get(turn_key, [])
                if not top5:
                    continue
                max_val = max((x.get('total', 0) for x in top5), default=1) or 1

                parts.append(
                    f'<div class="fw-turn-card">'
                    f'<div class="fw-turn-hdr" '
                    f'style="background:linear-gradient(135deg,{t_dark},{t_light})">'
                    f'{turn_lbl}</div>'
                    f'<div class="fw-turn-body">'
                )
                for item in top5:
                    num   = item.get('num', '?')
                    lbl   = item.get('label', num)
                    total = item.get('total', 0)
                    pct   = round(100 * total / max_val)
                    bc    = BALL_BG[int(num) % len(BALL_BG)]
                    parts.append(
                        f'<div class="fw-bar-row">'
                        f'<div class="fw-bar-ball" style="background:{bc}">{num}</div>'
                        f'<span class="fw-bar-label">{lbl}</span>'
                        f'<div class="fw-bar-bg">'
                        f'<div class="fw-bar-fill" style="width:{pct}%;background:{light}"></div>'
                        f'</div>'
                        f'<span class="fw-bar-cnt">{total}</span>'
                        f'</div>'
                    )
                parts.append('</div></div>')  # turn-body + turn-card

            parts.append('</div></div>')  # fw-turns + fw-type-block

        parts.append('</div>')
        return ''.join(parts)
