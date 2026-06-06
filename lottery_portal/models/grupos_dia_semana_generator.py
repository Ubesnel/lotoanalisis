# -*- coding: utf-8 -*-
"""
Cron + HTML builder para el artículo diario de
Líneas y Terminales más atrasadas por día de semana.

Un artículo por día (slug: lineas-terminales-{wcode}-{YYYY-MM-DD})
Secciones: Líneas (General / Tarde / Noche) + Terminales (General / Tarde / Noche)
"""
import logging

from datetime import timedelta

from odoo import models, api

_logger = logging.getLogger(__name__)

# Colores por posición dentro del top 3
_RANK_COLORS = ['#dc2626', '#d97706', '#16a34a']   # rojo, ámbar, verde
_RANK_BG     = ['#fef2f2', '#fffbeb', '#f0fdf4']
_RANK_BORDER = ['#fca5a5', '#fcd34d', '#86efac']

# Tonos para el atraso individual de cada número (0 = poco, alto = mucho)
def _delay_class(delay, max_d):
    if max_d == 0:
        return '#6b7280'
    ratio = delay / max_d
    if ratio >= 0.8:
        return '#dc2626'
    if ratio >= 0.5:
        return '#f97316'
    if ratio >= 0.2:
        return '#ca8a04'
    return '#4b5563'


class GruposDiaSemanagenerator(models.Model):
    _inherit = 'news.article'

    # ─────────────────────────────────────────────────────────────────────
    # Cron
    # ─────────────────────────────────────────────────────────────────────

    _WEEKDAY_CODE = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
    _WEEKDAY_ES   = {
        'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles',
        'ju': 'Jueves', 'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo',
    }

    @api.model
    def cron_generate_grupos_dia_semana(self, ref_date=None):
        """Genera diariamente dos artículos: líneas atrasadas y terminales atrasadas."""
        today     = self._parse_ref_date(ref_date)   # fecha real de generación (timezone-aware)
        yesterday = today - timedelta(days=1)         # día de semana a analizar
        try:
            self._generate_lineas_dia_semana_article(yesterday, today)
        except Exception as e:
            _logger.error('cron_generate_lineas_dia_semana: %s', e, exc_info=True)
        try:
            self._generate_terminales_dia_semana_article(yesterday, today)
        except Exception as e:
            _logger.error('cron_generate_terminales_dia_semana: %s', e, exc_info=True)

    # ─────────────────────────────────────────────────────────────────────
    # Artículo de LÍNEAS
    # ─────────────────────────────────────────────────────────────────────

    _COVER_LINEAS = {
        'lu': 'linea atrasada lunes.png',
        'ma': 'linea atrasada martes.png',
        'mi': 'linea atrasada miercoles.png',
        'ju': 'linea atrasada jueves.png',
        'vi': 'linea atrasada viernes.png',
        'sa': 'linea atrasada sabado.png',
        'do': 'linea atrasada domingo.png',
    }

    _COVER_TERMINALES = {
        'lu': 'terminales atrasado lunes.png',
        'ma': 'terminales atrasado martes.png',
        'mi': 'terminales atrasado miercoles.png',
        'ju': 'terminales atrasado jueves.png',
        'vi': 'terminales atrasado viernes.png',
        'sa': 'terminales atrasado sabado.png',
        'do': 'terminales atrasado domingo.png',
    }

    @api.model
    def _generate_lineas_dia_semana_article(self, today, generated_date=None):
        # today = día analizado (ayer); generated_date = fecha real de generación
        wcode, wlabel = self._wday_info(today)
        generated_str = (generated_date or today).strftime('%d/%m/%Y')
        slug  = f'lineas-atrasadas-{wcode}'
        akey  = f'lineas_dia_{wcode}'

        svc  = self.env['lottery.stats.service'].sudo()
        data = svc.get_lineas_terminales_dia_semana(wcode, top_n=3)

        html_body = self._build_grupos_dia_semana_html(
            generated_str, wlabel, 'lineas', data, only='lineas'
        )
        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        title = f'Atraso de Líneas los {wlabel} — {generated_str}'
        intro = (
            f'Top 3 líneas con mayor atraso acumulado los {wlabel}, '
            f'desglosado por turno General, Tarde y Noche. '
            f'Números de la línea, atrasos individuales, último en salir y mayor atraso.'
        )
        cover = self._load_cover_image(self._COVER_LINEAS.get(wcode, 'linea atrasada lunes.png'))

        existing = self._upsert_article(slug, akey, title, intro, html_body, category, cover)
        _logger.info('Upserted lineas-atrasadas article: %s', slug)

        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old lineas-atrasadas articles for %s', len(old), wcode)

    # ─────────────────────────────────────────────────────────────────────
    # Artículo de TERMINALES
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _generate_terminales_dia_semana_article(self, today, generated_date=None):
        wcode, wlabel = self._wday_info(today)
        generated_str = (generated_date or today).strftime('%d/%m/%Y')
        slug  = f'terminales-atrasados-{wcode}'
        akey  = f'terminales_dia_{wcode}'

        svc  = self.env['lottery.stats.service'].sudo()
        data = svc.get_lineas_terminales_dia_semana(wcode, top_n=3)

        html_body = self._build_grupos_dia_semana_html(
            generated_str, wlabel, 'terminales', data, only='terminales'
        )
        category = self.env.ref(
            'lottery_portal.news_category_analisis_diarios', raise_if_not_found=False
        )
        title = f'Atrasos de los Terminales los {wlabel} — {generated_str}'
        intro = (
            f'Top 3 terminales con mayor atraso acumulado los {wlabel}, '
            f'desglosado por turno General, Tarde y Noche. '
            f'Números del terminal, atrasos individuales, último en salir y mayor atraso.'
        )
        cover = self._load_cover_image(self._COVER_TERMINALES.get(wcode, 'terminales atrasado lunes.png'))

        existing = self._upsert_article(slug, akey, title, intro, html_body, category, cover)
        _logger.info('Upserted terminales-atrasados article: %s', slug)

        old = self.search([('article_key', '=', akey), ('id', '!=', existing.id)])
        if old:
            old.unlink()
            _logger.info('Deleted %d old terminales-atrasados articles for %s', len(old), wcode)

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _wday_info(self, today):
        """Devuelve (wcode, wlabel) para el día analizado. La fecha de display se calcula aparte."""
        wcode  = self._WEEKDAY_CODE[today.weekday()]
        wlabel = self._WEEKDAY_ES[wcode]
        return wcode, wlabel

    def _upsert_article(self, slug, article_key, title, intro, html_body, category, cover):
        from odoo import fields as odoo_fields
        vals = {
            'title':        title,
            'slug':         slug,
            'summary':      intro,
            'raw_html':     html_body,
            'publish_date': odoo_fields.Datetime.now(),
            'is_published': True,
            'article_key':  article_key,
            'category_id':  category.id if category else False,
            'cover_image':  cover or False,
        }
        existing = self.search([('article_key', '=', article_key)], limit=1)
        if existing:
            existing.write(vals)
        else:
            existing = self.create(vals)
        return existing

    # ─────────────────────────────────────────────────────────────────────
    # HTML
    # ─────────────────────────────────────────────────────────────────────

    def _build_grupos_dia_semana_html(self, date_str, wlabel, wcode, data, only=None):
        TURN_META = {
            'general':   ('General',  '📊', '#4f46e5', '#e0e7ff'),
            'afternoon': ('Tarde',    '☀',  '#d97706', '#fffbeb'),
            'evening':   ('Noche',    '🌙', '#1e3a5f', '#eff6ff'),
        }

        CSS = """
<style>
.gds-wrap{font-family:'Segoe UI',Arial,sans-serif;max-width:900px;margin:0 auto;padding:0 4px}
.gds-hero{border-radius:14px;padding:24px 20px 18px;text-align:center;margin-bottom:22px;
  background:linear-gradient(135deg,#312e81 0%,#4f46e5 50%,#7c3aed 100%);position:relative;overflow:hidden}
.gds-hero::before{content:'';position:absolute;top:-40px;left:-40px;width:160px;height:160px;
  background:rgba(255,255,255,.07);border-radius:50%}
.gds-hero-badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);
  color:#fff;font-size:.72rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;
  border-radius:20px;padding:3px 12px;margin-bottom:8px}
.gds-hero-title{font-size:1.8rem;font-weight:900;color:#fff;margin:0 0 4px}
.gds-hero-title span{color:#c4b5fd}
.gds-hero-sub{color:rgba(255,255,255,.8);font-size:.88rem;margin:0}
/* Secciones (Líneas / Terminales) */
.gds-section{margin-bottom:30px}
.gds-section-hd{font-size:1rem;font-weight:800;color:#fff;padding:10px 16px;border-radius:8px;
  margin-bottom:14px;display:flex;align-items:center;gap:8px;letter-spacing:.4px}
.gds-section-hd.lineas{background:linear-gradient(135deg,#0f766e,#0d9488)}
.gds-section-hd.terminales{background:linear-gradient(135deg,#7c2d8e,#a855f7)}
/* Tabs de turno */
.gds-turns{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:640px){.gds-turns{grid-template-columns:1fr}}
.gds-turn{border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.gds-turn-hd{padding:8px 12px;display:flex;align-items:center;gap:6px;font-weight:700;color:#fff;font-size:.85rem}
.gds-turn-body{padding:10px;background:#fff}
/* Cards de cada grupo (top 1,2,3) */
.gds-grp-card{border-radius:8px;padding:10px 12px;margin-bottom:8px;border:1px solid}
.gds-grp-rank{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.6px;
  margin-bottom:4px;opacity:.75}
.gds-grp-name{font-size:1.05rem;font-weight:900;margin-bottom:2px}
.gds-grp-delay{font-size:.78rem;color:#6b7280;margin-bottom:8px}
.gds-grp-delay strong{color:#111;font-weight:700}
/* Números del grupo */
.gds-nums{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.gds-num{display:inline-flex;flex-direction:column;align-items:center;gap:1px}
.gds-ball{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.68rem;color:#fff;box-shadow:0 1px 4px rgba(0,0,0,.2)}
.gds-num-d{font-size:.55rem;color:#9ca3af;text-align:center;line-height:1}
/* Badges de info */
.gds-info-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.gds-badge{display:inline-flex;align-items:center;gap:4px;font-size:.7rem;
  border-radius:6px;padding:3px 8px;font-weight:600}
.gds-badge-last{background:#f0fdf4;color:#15803d;border:1px solid #86efac}
.gds-badge-max{background:#fef2f2;color:#dc2626;border:1px solid #fca5a5}
</style>
"""

        def _grp_card(rank, grp, turn_bg, turn_border, turn_color):
            color  = _RANK_COLORS[rank]
            bg     = _RANK_BG[rank]
            border = _RANK_BORDER[rank]
            rank_lbl = ['🥇 1.°', '🥈 2.°', '🥉 3.°'][rank]

            nums   = grp.get('numbers', [])
            max_d  = max((n['delay'] for n in nums), default=1) or 1

            balls_html = ''
            for n in nums:
                ball_color = _delay_class(n['delay'], max_d)
                balls_html += (
                    f'<div class="gds-num">'
                    f'<div class="gds-ball" style="background:{ball_color}">{n["name"]}</div>'
                    f'<span class="gds-num-d">{n["delay"]}</span>'
                    f'</div>'
                )

            last_num  = grp.get('last_num', '-')
            last_date = grp.get('last_date', '-')
            max_num   = grp.get('max_delay_num', '-')
            max_val   = grp.get('max_delay_val', 0)

            return (
                f'<div class="gds-grp-card" style="background:{bg};border-color:{border}">'
                f'  <div class="gds-grp-rank" style="color:{color}">{rank_lbl}</div>'
                f'  <div class="gds-grp-name" style="color:{color}">{grp["name"]}</div>'
                f'  <div class="gds-grp-delay">Atraso acumulado: <strong>{grp["delay"]}</strong> sorteos</div>'
                f'  <div class="gds-nums">{balls_html}</div>'
                f'  <div class="gds-info-row">'
                f'    <span class="gds-badge gds-badge-max">'
                f'      <i class="fa fa-hourglass-half"></i> Mayor atraso: <strong>{max_num}</strong> ({max_val})'
                f'    </span>'
                f'    <span class="gds-badge gds-badge-last">'
                f'      <i class="fa fa-check-circle"></i> Último: <strong>{last_num}</strong> · {last_date}'
                f'    </span>'
                f'  </div>'
                f'</div>'
            )

        def _turn_col(turn_key, groups):
            label, icon, hd_color, bg_color = TURN_META[turn_key]
            cards_html = ''
            for i, grp in enumerate(groups):
                cards_html += _grp_card(i, grp, None, None, hd_color)
            if not groups:
                cards_html = '<p style="color:#9ca3af;font-size:.8rem">Sin datos</p>'
            return (
                f'<div class="gds-turn">'
                f'  <div class="gds-turn-hd" style="background:{hd_color}">'
                f'    <span>{icon}</span><span>{label}</span>'
                f'  </div>'
                f'  <div class="gds-turn-body">{cards_html}</div>'
                f'</div>'
            )

        def _section(section_key, section_label, icon, css_cls):
            grp_data = data.get(section_key, {})
            turns_html = (
                _turn_col('general',   grp_data.get('general',   [])) +
                _turn_col('afternoon', grp_data.get('afternoon', [])) +
                _turn_col('evening',   grp_data.get('evening',   []))
            )
            return (
                f'<div class="gds-section">'
                f'  <div class="gds-section-hd {css_cls}">'
                f'    <i class="fa {icon}"></i> {section_label}'
                f'  </div>'
                f'  <div class="gds-turns">{turns_html}</div>'
                f'</div>'
            )

        parts = [CSS, '<div class="gds-wrap">']

        _titles = {
            'lineas':     (f'Atraso de Líneas <span>los {wlabel}</span>', '#0f766e', '#e0f7f6'),
            'terminales': (f'Atrasos de los Terminales <span>los {wlabel}</span>', '#7c2d8e', '#faf0fe'),
            None:         (f'Líneas y Terminales <span>los {wlabel}</span>', '#4f46e5', '#e0e7ff'),
        }
        hero_title, _, _ = _titles.get(only, _titles[None])
        parts.append(f'''
<div class="gds-hero">
  <div class="gds-hero-badge"><i class="fa fa-calendar"></i> Análisis del día</div>
  <h1 class="gds-hero-title">{hero_title}</h1>
  <p class="gds-hero-sub">Pick 3 Florida · Top 3 más atrasadas · {date_str}</p>
</div>
''')

        if only in (None, 'lineas'):
            parts.append(_section('lineas',     'Atraso de Líneas',         'fa-bars',    'lineas'))
        if only in (None, 'terminales'):
            parts.append(_section('terminales', 'Atrasos de los Terminales', 'fa-hashtag', 'terminales'))

        parts.append('</div>')  # gds-wrap
        return ''.join(parts)
