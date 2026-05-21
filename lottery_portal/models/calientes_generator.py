# -*- coding: utf-8 -*-
"""
Cron + HTML builder + refresh action for the "Calientes" article.
Appended to news.article via _inherit.
"""
import logging
import re
from datetime import date

from odoo import models, api

_logger = logging.getLogger(__name__)


class CalientesArticleGenerator(models.Model):
    _inherit = 'news.article'

    # ─────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────

    def _calientes_today_str(self):
        """Return the next-draw date string (same logic as the controller)."""
        self.env.cr.execute(
            "SELECT (MAX(date) + INTERVAL '1 day')::date AS nd FROM lottery_output"
        )
        row = self.env.cr.dictfetchone()
        return str(row['nd']) if row and row.get('nd') else str(date.today())

    def _resolve_lottery_numbers(self, name_list):
        """Given a list of dicts with 'name' key, return lottery.number records."""
        names = [int(n['name']) for n in name_list if n.get('name') is not None]
        return self.env['lottery.number'].sudo().search([('name', 'in', names)])

    # ─────────────────────────────────────────────────────────────────────
    # Cron entry point
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def cron_generate_calientes(self, ref_date=None):
        try:
            self._generate_calientes_article()
        except Exception as e:
            _logger.error('cron_generate_calientes: %s', e, exc_info=True)

    # ─────────────────────────────────────────────────────────────────────
    # Article builder
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _generate_calientes_article(self):
        today_str = self._calientes_today_str()
        date_str  = date.fromisoformat(today_str).strftime('%d/%m/%Y')
        slug      = 'numeros-calientes'

        svc  = self.env['lottery.stats.service'].sudo()
        data = svc.get_calientes_all(today_str)

        tarde = data.get('afternoon', {})
        noche = data.get('evening', {})

        # ── Many2many resolution ──────────────────────────────────────────
        def m2m(lst):
            return [(6, 0, self._resolve_lottery_numbers(lst).ids)]

        # ── HTML ─────────────────────────────────────────────────────────
        html_body = self._build_calientes_html(date_str, data)

        # ── Category ─────────────────────────────────────────────────────
        category = self.env.ref(
            'lottery_portal.news_category_calientes', raise_if_not_found=False
        )

        title = f'Números Calientes — Pick 3 Florida · {date_str}'
        intro = (
            f'Top 30 números calientes, centenas y bola extra con mayor '
            f'probabilidad para el próximo sorteo. '
            f'Calculado con 17 criterios. Actualizado al {date_str}.'
        )

        vals = {
            'title':                title,
            'slug':                 slug,
            'summary':              intro,
            'raw_html':             html_body,
            'is_published':         False,          # siempre en borrador
            'is_calientes_article': True,
            'category_id':          category.id if category else False,
            # many2many
            'hot_number_tarde_ids': m2m(tarde.get('numbers',   [])),
            'hot_number_noche_ids': m2m(noche.get('numbers',   [])),
            'hot_centena_tarde_ids': m2m(tarde.get('centenas',  [])),
            'hot_centena_noche_ids': m2m(noche.get('centenas',  [])),
            'hot_extra_tarde_ids':  m2m(tarde.get('bola_extra', [])),
            'hot_extra_noche_ids':  m2m(noche.get('bola_extra', [])),
        }

        existing = self.search([('slug', '=', slug)], limit=1)
        if existing:
            existing.write(vals)
            _logger.info('Updated calientes article: %s', slug)
        else:
            self.create(vals)
            _logger.info('Created calientes article: %s', slug)

    # ─────────────────────────────────────────────────────────────────────
    # "Actualizar datos" button action
    # ─────────────────────────────────────────────────────────────────────

    def action_refresh_calientes(self):
        """Recalculate calientes, update many2many fields and rebuild HTML."""
        self.ensure_one()
        today_str = self._calientes_today_str()
        date_str  = date.fromisoformat(today_str).strftime('%d/%m/%Y')

        svc  = self.env['lottery.stats.service'].sudo()
        data = svc.get_calientes_all(today_str)

        tarde = data.get('afternoon', {})
        noche = data.get('evening', {})

        def m2m(lst):
            return [(6, 0, self._resolve_lottery_numbers(lst).ids)]

        # Rebuild the replaceable sections inside raw_html
        new_tarde_html = self._build_calientes_turn_block(tarde, 'Tarde',  '☀', date_str)
        new_noche_html = self._build_calientes_turn_block(noche, 'Noche', '🌙', date_str)

        html = self.raw_html or ''
        html = re.sub(
            r'<!-- HC_TARDE_START -->.*?<!-- HC_TARDE_END -->',
            f'<!-- HC_TARDE_START -->{new_tarde_html}<!-- HC_TARDE_END -->',
            html, flags=re.DOTALL,
        )
        html = re.sub(
            r'<!-- HC_NOCHE_START -->.*?<!-- HC_NOCHE_END -->',
            f'<!-- HC_NOCHE_START -->{new_noche_html}<!-- HC_NOCHE_END -->',
            html, flags=re.DOTALL,
        )

        # If markers are gone (edited manually) rebuild completely
        if '<!-- HC_TARDE_START -->' not in html:
            html = self._build_calientes_html(date_str, data)

        self.write({
            'raw_html':              html,
            'hot_number_tarde_ids':  m2m(tarde.get('numbers',   [])),
            'hot_number_noche_ids':  m2m(noche.get('numbers',   [])),
            'hot_centena_tarde_ids': m2m(tarde.get('centenas',  [])),
            'hot_centena_noche_ids': m2m(noche.get('centenas',  [])),
            'hot_extra_tarde_ids':   m2m(tarde.get('bola_extra', [])),
            'hot_extra_noche_ids':   m2m(noche.get('bola_extra', [])),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Datos calientes actualizados al {date_str}.',
                'type': 'success',
                'sticky': False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # HTML builders
    # ─────────────────────────────────────────────────────────────────────

    def _build_calientes_html(self, date_str, data):
        tarde = data.get('afternoon', {})
        noche = data.get('evening',   {})

        CSS = """
<style>
.hc-wrap{font-family:'Segoe UI',Arial,sans-serif;max-width:860px;margin:0 auto;padding:0 4px}
.hc-hero{background:linear-gradient(135deg,#7f1d1d 0%,#dc2626 50%,#f97316 100%);
  border-radius:14px;padding:28px 24px 22px;text-align:center;margin-bottom:20px;position:relative;overflow:hidden}
.hc-hero::before{content:'';position:absolute;top:-40px;left:-40px;width:180px;height:180px;
  background:rgba(255,255,255,.07);border-radius:50%}
.hc-hero::after{content:'';position:absolute;bottom:-50px;right:-30px;width:220px;height:220px;
  background:rgba(255,255,255,.05);border-radius:50%}
.hc-hero-badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);
  color:#fff;font-size:.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;
  border-radius:20px;padding:4px 14px;margin-bottom:10px}
.hc-hero-title{font-size:2rem;font-weight:900;color:#fff;margin:0 0 6px;line-height:1.15}
.hc-hero-title span{color:#fde68a}
.hc-hero-sub{color:rgba(255,255,255,.85);font-size:.9rem;margin:0}
.hc-criteria{display:inline-block;background:rgba(255,255,255,.15);border-radius:12px;
  padding:3px 12px;font-size:.78rem;color:#fef3c7;margin-top:8px}
.hc-turns{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
@media(max-width:600px){.hc-turns{grid-template-columns:1fr}}
.hc-turn{background:#fff;border-radius:12px;border:1px solid #fee2e2;overflow:hidden;
  box-shadow:0 2px 12px rgba(220,38,38,.08)}
.hc-turn-hdr{background:linear-gradient(135deg,#dc2626,#f97316);padding:12px 16px;
  display:flex;align-items:center;gap:8px}
.hc-turn-hdr.noche{background:linear-gradient(135deg,#1e3a5f,#7c3aed)}
.hc-turn-icon{font-size:1.3rem}
.hc-turn-label{font-size:1rem;font-weight:800;color:#fff;letter-spacing:.5px}
.hc-turn-date{font-size:.72rem;color:rgba(255,255,255,.8);margin-left:auto}
.hc-turn-body{padding:14px}
.hc-section-title{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
  color:#9ca3af;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.hc-section-title i{color:#f97316}
.hc-numbers-grid{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.hc-ball{width:32px;height:32px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-weight:800;font-size:.8rem;color:#fff;cursor:default;
  box-shadow:0 2px 6px rgba(0,0,0,.18);flex-shrink:0}
.hc-ball-hot{background:linear-gradient(135deg,#dc2626,#b91c1c)}
.hc-ball-warm{background:linear-gradient(135deg,#f97316,#ea580c)}
.hc-ball-cool{background:linear-gradient(135deg,#fbbf24,#d97706);color:#7c2d12}
.hc-ceb-row{display:flex;gap:12px}
.hc-ceb-col{flex:1;min-width:0}
.hc-ceb-grid{display:flex;gap:6px;flex-wrap:wrap}
.hc-badge{display:inline-flex;align-items:center;justify-content:center;
  min-width:44px;height:32px;border-radius:8px;font-weight:800;font-size:.88rem;
  padding:0 10px}
.hc-badge-hot{background:linear-gradient(135deg,#dc2626,#f97316);color:#fff}
.hc-badge-warm{background:linear-gradient(135deg,#f97316,#fbbf24);color:#fff}
.hc-badge-extra-hot{background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff}
.hc-badge-extra-warm{background:linear-gradient(135deg,#a855f7,#c084fc);color:#fff}
.hc-rank{font-size:.65rem;color:#9ca3af;display:block;text-align:center;margin-top:2px}
.hc-legend{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.hc-pip{width:11px;height:11px;border-radius:50%;display:inline-block;vertical-align:middle;margin-right:4px}
.hc-pip-hot{background:#dc2626}
.hc-pip-warm{background:#f97316}
.hc-pip-cool{background:#fbbf24}
.hc-legend-item{font-size:.72rem;color:#6b7280}
.hc-divider{border:none;border-top:1px solid #fee2e2;margin:12px 0}
</style>
"""

        tarde_block = self._build_calientes_turn_block(tarde, 'Tarde',  '☀', date_str)
        noche_block = self._build_calientes_turn_block(noche, 'Noche', '🌙', date_str)

        parts = [CSS, '<div class="hc-wrap">']

        # ── Hero ─────────────────────────────────────────────────────────
        parts.append(f'''
<div class="hc-hero">
  <div class="hc-hero-badge"><i class="fa fa-fire"></i> Análisis Predictivo</div>
  <h1 class="hc-hero-title">Números <span>Calientes</span></h1>
  <p class="hc-hero-sub">Pick 3 Florida · Actualizado al {date_str}</p>
  <span class="hc-criteria">17 criterios ponderados · Tarde y Noche</span>
</div>
''')

        # ── Turn blocks with markers ──────────────────────────────────────
        parts.append('<div class="hc-turns">')
        parts.append(f'<!-- HC_TARDE_START -->{tarde_block}<!-- HC_TARDE_END -->')
        parts.append(f'<!-- HC_NOCHE_START -->{noche_block}<!-- HC_NOCHE_END -->')
        parts.append('</div>')

        parts.append('</div>')  # hc-wrap
        return ''.join(parts)

    def _build_calientes_turn_block(self, turn_data, label, icon, date_str):
        """Build the HTML for one turn (tarde or noche). Replaceable section."""
        numbers   = turn_data.get('numbers',   [])
        centenas  = turn_data.get('centenas',  [])
        bola_extra = turn_data.get('bola_extra', [])
        next_draw = turn_data.get('next_draw', date_str)
        hdr_class = 'noche' if label == 'Noche' else ''

        parts = [f'<div class="hc-turn">']
        parts.append(
            f'<div class="hc-turn-hdr {hdr_class}">'
            f'<span class="hc-turn-icon">{icon}</span>'
            f'<span class="hc-turn-label">{label}</span>'
            f'<span class="hc-turn-date"><i class="fa fa-calendar-o"></i> {next_draw}</span>'
            f'</div>'
        )
        parts.append('<div class="hc-turn-body">')

        # Legend
        parts.append(
            '<div class="hc-legend">'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-hot"></span>#1–10</span>'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-warm"></span>#11–20</span>'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-cool"></span>#21–30</span>'
            '</div>'
        )

        # Numbers grid
        parts.append('<div class="hc-section-title"><i class="fa fa-sort-numeric-asc"></i> Números calientes</div>')
        parts.append('<div class="hc-numbers-grid">')
        for i, num in enumerate(numbers):
            if i < 10:
                cls = 'hc-ball-hot'
            elif i < 20:
                cls = 'hc-ball-warm'
            else:
                cls = 'hc-ball-cool'
            score = num.get('score', '')
            name  = str(num.get('name', '')).zfill(2)
            parts.append(
                f'<span class="hc-ball {cls}" title="#{i+1} · Score: {score}">{name}</span>'
            )
        parts.append('</div>')  # hc-numbers-grid

        parts.append('<hr class="hc-divider"/>')

        # Centenas + bola extra row
        parts.append('<div class="hc-ceb-row">')

        # Centenas
        parts.append('<div class="hc-ceb-col">')
        parts.append('<div class="hc-section-title"><i class="fa fa-th"></i> Centenas</div>')
        parts.append('<div class="hc-ceb-grid">')
        for i, cen in enumerate(centenas):
            cls = 'hc-badge-hot' if i < 2 else 'hc-badge-warm'
            parts.append(
                f'<div style="text-align:center">'
                f'<span class="hc-badge {cls}">{cen.get("name","")}</span>'
                f'<span class="hc-rank">#{i+1}</span>'
                f'</div>'
            )
        parts.append('</div></div>')  # hc-ceb-grid, hc-ceb-col

        # Bola extra
        parts.append('<div class="hc-ceb-col">')
        parts.append('<div class="hc-section-title"><i class="fa fa-star"></i> Bola Extra</div>')
        parts.append('<div class="hc-ceb-grid">')
        for i, be in enumerate(bola_extra):
            cls = 'hc-badge-extra-hot' if i < 2 else 'hc-badge-extra-warm'
            parts.append(
                f'<div style="text-align:center">'
                f'<span class="hc-badge {cls}">{be.get("name","")}</span>'
                f'<span class="hc-rank">#{i+1}</span>'
                f'</div>'
            )
        parts.append('</div></div>')  # hc-ceb-grid, hc-ceb-col

        parts.append('</div>')  # hc-ceb-row
        parts.append('</div></div>')  # hc-turn-body, hc-turn
        return ''.join(parts)
