# -*- coding: utf-8 -*-
"""
Cron + HTML builder + refresh action for the combined "Calientes y Fríos" articles.
Two articles per day: one for Tarde, one for Noche.
Each article shows hot numbers + cold numbers for that turn only.
"""
import logging
import re
from datetime import date

from odoo import models, api

_logger = logging.getLogger(__name__)


class CalientesArticleGenerator(models.Model):
    _inherit = 'news.article'

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _calientes_today_str(self, turno='tarde'):
        """
        Tarde (23:45, después de la noche): el último sorteo registrado es el
        de esta noche → MAX(date) + 1 día = mañana → correcto para el sorteo
        de tarde del día siguiente.

        Noche (15:10, antes de la noche): usamos date.today() directamente
        para que el artículo y el algoritmo apunten al sorteo de noche de HOY,
        independientemente de si ya está cargado el turno de tarde de hoy.
        """
        if turno == 'noche':
            return str(date.today())
        # tarde: MAX global + 1 día
        self.env.cr.execute(
            "SELECT (MAX(date) + INTERVAL '1 day')::date AS nd FROM lottery_output"
        )
        row = self.env.cr.dictfetchone()
        return str(row['nd']) if row and row.get('nd') else str(date.today())

    def _resolve_lottery_numbers(self, name_list):
        names = [int(n['name']) for n in name_list if n.get('name') is not None]
        return self.env['lottery.number'].sudo().search([('name', 'in', names)])

    # ─────────────────────────────────────────────────────────────────────
    # Cron entry points
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def cron_generate_calientes_frios_tarde(self, ref_date=None):
        try:
            self._generate_calientes_frios_article('tarde')
        except Exception as e:
            _logger.error('cron_generate_calientes_frios_tarde: %s', e, exc_info=True)

    @api.model
    def cron_generate_calientes_frios_noche(self, ref_date=None):
        try:
            self._generate_calientes_frios_article('noche')
        except Exception as e:
            _logger.error('cron_generate_calientes_frios_noche: %s', e, exc_info=True)

    # ─────────────────────────────────────────────────────────────────────
    # Article builder — shared for both turnos
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _generate_calientes_frios_article(self, turno):
        """Create/update the combined calientes+fríos article for the given turno."""
        today_str  = self._calientes_today_str(turno)
        date_str   = date.fromisoformat(today_str).strftime('%d/%m/%Y')
        is_tarde   = turno == 'tarde'
        label      = 'Tarde' if is_tarde else 'Noche'
        icon       = '☀' if is_tarde else '🌙'
        # Slug con fecha: genera un artículo nuevo por día, conservando el histórico
        slug_date  = date.fromisoformat(today_str).strftime('%Y-%m-%d')
        slug       = f'calientes-frios-{turno}-{slug_date}'
        cover_file = f'sorteo {turno}.png'
        data_key   = 'afternoon' if is_tarde else 'evening'

        svc       = self.env['lottery.stats.service'].sudo()
        data      = svc.get_calientes_all(today_str)
        turn_data = data.get(data_key, {})

        def m2m(lst):
            return [(6, 0, self._resolve_lottery_numbers(lst).ids)]

        html_body = self._build_combined_article_html(date_str, turn_data, label, icon)
        cover     = self._load_cover_image(cover_file)

        category = self.env.ref(
            'lottery_portal.news_category_sorteos_diarios', raise_if_not_found=False
        )
        title = f'Calientes y Fríos {label} — Pick 3 Florida · {date_str}'
        intro = (
            f'Números calientes y fríos, centenas y bola extra para el sorteo de la {label.lower()}. '
            f'Calculado con 17 criterios. Actualizado al {date_str}.'
        )

        if is_tarde:
            m2m_vals = {
                'hot_number_tarde_ids':  m2m(turn_data.get('numbers',              [])),
                'hot_centena_tarde_ids': m2m(turn_data.get('centenas',             [])),
                'hot_extra_tarde_ids':   m2m(turn_data.get('bola_extra',           [])),
                'cold_number_tarde_ids': m2m(turn_data.get('numbers_cold',         [])),
                'cold_centena_tarde_ids':m2m(turn_data.get('centenas_cold',        [])),
                'cold_extra_tarde_ids':  m2m(turn_data.get('bola_extra_cold',      [])),
                'rem_number_tarde_ids':  m2m(turn_data.get('numbers_remaining',    [])),
                'rem_centena_tarde_ids': m2m(turn_data.get('centenas_remaining',   [])),
                'rem_extra_tarde_ids':   m2m(turn_data.get('bola_extra_remaining', [])),
            }
        else:
            m2m_vals = {
                'hot_number_noche_ids':  m2m(turn_data.get('numbers',              [])),
                'hot_centena_noche_ids': m2m(turn_data.get('centenas',             [])),
                'hot_extra_noche_ids':   m2m(turn_data.get('bola_extra',           [])),
                'cold_number_noche_ids': m2m(turn_data.get('numbers_cold',         [])),
                'cold_centena_noche_ids':m2m(turn_data.get('centenas_cold',        [])),
                'cold_extra_noche_ids':  m2m(turn_data.get('bola_extra_cold',      [])),
                'rem_number_noche_ids':  m2m(turn_data.get('numbers_remaining',    [])),
                'rem_centena_noche_ids': m2m(turn_data.get('centenas_remaining',   [])),
                'rem_extra_noche_ids':   m2m(turn_data.get('bola_extra_remaining', [])),
            }

        vals = {
            'title':                title,
            'slug':                 slug,
            'summary':              intro,
            'raw_html':             html_body,
            'is_published':         False,
            'is_calientes_article': True,
            'category_id':          category.id if category else False,
            'cover_image':          cover or False,
            **m2m_vals,
        }

        existing = self.search([('slug', '=', slug)], limit=1)
        if existing:
            existing.write(vals)
            _logger.info('Updated calientes-frios-%s article', turno)
        else:
            self.create(vals)
            _logger.info('Created calientes-frios-%s article', turno)

    # ─────────────────────────────────────────────────────────────────────
    # Helpers para reconstruir turn_data desde campos M2M almacenados
    # ─────────────────────────────────────────────────────────────────────

    def _m2m_to_num_list(self, records):
        """Convierte registros lottery.number a lista [{name, score}] para números 00-99."""
        return [{'name': str(r.name).zfill(2), 'score': ''} for r in records]

    def _m2m_to_ceb_list(self, records):
        """Convierte registros lottery.number a lista [{name}] para centenas/bola extra (0-9)."""
        return [{'name': str(r.name)} for r in records]

    def _turn_data_from_m2m(self, sfx, date_str):
        """Construye turn_data a partir de los campos M2M del artículo."""
        return {
            'numbers':      self._m2m_to_num_list(self[f'hot_number_{sfx}_ids']),
            'centenas':     self._m2m_to_ceb_list(self[f'hot_centena_{sfx}_ids']),
            'bola_extra':   self._m2m_to_ceb_list(self[f'hot_extra_{sfx}_ids']),
            'numbers_cold': self._m2m_to_num_list(self[f'cold_number_{sfx}_ids']),
            'centenas_cold':self._m2m_to_ceb_list(self[f'cold_centena_{sfx}_ids']),
            'bola_extra_cold': self._m2m_to_ceb_list(self[f'cold_extra_{sfx}_ids']),
            'next_draw':    date_str,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Intercambiar números
    # ─────────────────────────────────────────────────────────────────────

    def action_swap_numbers(self):
        self.ensure_one()
        swap = self.swap_selection
        if not swap:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Selecciona una combinación de intercambio primero.',
                    'type': 'warning', 'sticky': False,
                },
            }

        is_tarde = 'tarde' in (self.slug or '')
        sfx = 'tarde' if is_tarde else 'noche'

        _logger.info('action_swap_numbers: swap=%s slug=%s sfx=%s', swap, self.slug, sfx)

        # Prefijos de los tres grupos
        PAIRS = {
            'hot_rem':  ('hot', 'rem'),
            'hot_cold': ('hot', 'cold'),
            'rem_cold': ('rem', 'cold'),
        }
        a_pfx, b_pfx = PAIRS[swap]

        # Leer los seis campos actuales
        a_num = self[f'{a_pfx}_number_{sfx}_ids']
        b_num = self[f'{b_pfx}_number_{sfx}_ids']

        _logger.info(
            'action_swap_numbers: a_pfx=%s b_pfx=%s | a_num=%s b_num=%s',
            a_pfx, b_pfx, a_num.ids, b_num.ids,
        )

        # Guardar IDs antes del write
        a_num_ids = a_num.ids[:]
        b_num_ids = b_num.ids[:]

        # Intercambiar solo números
        self.write({
            f'{a_pfx}_number_{sfx}_ids': [(6, 0, b_num_ids)],
            f'{b_pfx}_number_{sfx}_ids': [(6, 0, a_num_ids)],
            'swap_selection': None,
        })

        label = dict(self._fields['swap_selection'].selection).get(swap, swap)
        # Recargar el formulario para que los widgets M2M reflejen el cambio
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'news.article',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_swap_notification': f'Intercambio "{label}" aplicado.',
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # Actualizar contenido desde M2M actuales
    # ─────────────────────────────────────────────────────────────────────

    def action_update_content(self):
        self.ensure_one()
        today_str = self._calientes_today_str()
        date_str  = date.fromisoformat(today_str).strftime('%d/%m/%Y')

        is_tarde = 'tarde' in (self.slug or '')
        sfx      = 'tarde' if is_tarde else 'noche'
        label    = 'Tarde' if is_tarde else 'Noche'
        icon     = '☀' if is_tarde else '🌙'

        turn_data = self._turn_data_from_m2m(sfx, date_str)
        html = self._build_combined_article_html(date_str, turn_data, label, icon)
        self.write({'raw_html': html})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'news.article',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ─────────────────────────────────────────────────────────────────────
    # HTML builder — combined article (calientes + fríos for one turno)
    # ─────────────────────────────────────────────────────────────────────

    def _build_combined_article_html(self, date_str, turn_data, label, icon):
        is_tarde  = label == 'Tarde'
        hero_grad = (
            '135deg,#7f1d1d 0%,#dc2626 50%,#f97316 100%'
            if is_tarde else
            '135deg,#0c1a2e 0%,#1e3a5f 50%,#1d4ed8 100%'
        )

        CSS = """
<style>
.cf-wrap{font-family:'Segoe UI',Arial,sans-serif;max-width:760px;margin:0 auto;padding:0 4px}
.cf-hero{border-radius:14px;padding:28px 24px 22px;text-align:center;margin-bottom:20px;position:relative;overflow:hidden}
.cf-hero::before{content:'';position:absolute;top:-40px;left:-40px;width:180px;height:180px;background:rgba(255,255,255,.07);border-radius:50%}
.cf-hero::after{content:'';position:absolute;bottom:-50px;right:-30px;width:220px;height:220px;background:rgba(255,255,255,.05);border-radius:50%}
.cf-hero-badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);color:#fff;font-size:.75rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;border-radius:20px;padding:4px 14px;margin-bottom:10px}
.cf-hero-title{font-size:2rem;font-weight:900;color:#fff;margin:0 0 6px;line-height:1.15}
.cf-hero-title span{color:#fde68a}
.cf-hero-sub{color:rgba(255,255,255,.85);font-size:.9rem;margin:0}
.cf-criteria{display:inline-block;background:rgba(255,255,255,.15);border-radius:12px;padding:3px 12px;font-size:.78rem;color:#fef3c7;margin-top:8px}
.cf-section-label{font-size:.95rem;font-weight:800;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;border-radius:8px;margin:20px 0 10px;display:flex;align-items:center;gap:8px;color:#fff}
.cf-section-label.cal{background:linear-gradient(135deg,#dc2626,#f97316)}
.cf-section-label.fri{background:linear-gradient(135deg,#1e3a5f,#1d4ed8)}
/* ── Calientes ──────────────────────────── */
.hc-turn{background:#fff;border-radius:12px;border:1px solid #fee2e2;overflow:hidden;box-shadow:0 2px 12px rgba(220,38,38,.08)}
.hc-turn-hdr{background:linear-gradient(135deg,#dc2626,#f97316);padding:12px 16px;display:flex;align-items:center;gap:8px}
.hc-turn-hdr.noche{background:linear-gradient(135deg,#1e3a5f,#7c3aed)}
.hc-turn-icon{font-size:1.3rem}
.hc-turn-label{font-size:1rem;font-weight:800;color:#fff;letter-spacing:.5px}
.hc-turn-date{font-size:.72rem;color:rgba(255,255,255,.8);margin-left:auto}
.hc-turn-body{padding:14px}
.hc-section-title{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#9ca3af;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.hc-section-title i{color:#f97316}
.hc-numbers-grid{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.hc-ball{width:32px;height:32px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:.8rem;color:#fff;cursor:default;box-shadow:0 2px 6px rgba(0,0,0,.18);flex-shrink:0}
.hc-ball-hot{background:linear-gradient(135deg,#dc2626,#b91c1c)}
.hc-ball-warm{background:linear-gradient(135deg,#f97316,#ea580c)}
.hc-ball-cool{background:linear-gradient(135deg,#fbbf24,#d97706);color:#7c2d12}
.hc-ceb-row{display:flex;gap:12px}
.hc-ceb-col{flex:1;min-width:0}
.hc-ceb-grid{display:flex;gap:6px;flex-wrap:wrap}
.hc-badge{display:inline-flex;align-items:center;justify-content:center;min-width:44px;height:32px;border-radius:8px;font-weight:800;font-size:.88rem;padding:0 10px}
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
/* ── Fríos ──────────────────────────────── */
.hf-turn{background:#fff;border-radius:12px;border:1px solid #dbeafe;overflow:hidden;box-shadow:0 2px 12px rgba(30,58,95,.08)}
.hf-turn-hdr{background:linear-gradient(135deg,#1e3a5f,#1d4ed8);padding:12px 16px;display:flex;align-items:center;gap:8px}
.hf-turn-hdr.noche{background:linear-gradient(135deg,#0c1a2e,#4338ca)}
.hf-turn-icon{font-size:1.3rem}
.hf-turn-label{font-size:1rem;font-weight:800;color:#fff;letter-spacing:.5px}
.hf-turn-date{font-size:.72rem;color:rgba(255,255,255,.75);margin-left:auto}
.hf-turn-body{padding:14px}
.hf-section-title{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#9ca3af;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.hf-section-title i{color:#3b82f6}
.hf-numbers-grid{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.hf-ball{width:32px;height:32px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:.8rem;color:#fff;cursor:default;box-shadow:0 2px 6px rgba(0,0,0,.18);flex-shrink:0}
.hf-ball-cold1{background:linear-gradient(135deg,#1e3a5f,#1d4ed8)}
.hf-ball-cold2{background:linear-gradient(135deg,#1d4ed8,#3b82f6)}
.hf-ball-cold3{background:linear-gradient(135deg,#3b82f6,#93c5fd);color:#1e3a5f}
.hf-ceb-row{display:flex;gap:12px}
.hf-ceb-col{flex:1;min-width:0}
.hf-ceb-grid{display:flex;gap:6px;flex-wrap:wrap}
.hf-badge{display:inline-flex;align-items:center;justify-content:center;min-width:44px;height:32px;border-radius:8px;font-weight:800;font-size:.88rem;padding:0 10px}
.hf-badge-cold1{background:linear-gradient(135deg,#1e3a5f,#1d4ed8);color:#fff}
.hf-badge-cold2{background:linear-gradient(135deg,#1d4ed8,#3b82f6);color:#fff}
.hf-badge-extra-cold1{background:linear-gradient(135deg,#0f766e,#0d9488);color:#fff}
.hf-badge-extra-cold2{background:linear-gradient(135deg,#0d9488,#2dd4bf);color:#fff}
.hf-rank{font-size:.65rem;color:#9ca3af;display:block;text-align:center;margin-top:2px}
.hf-legend{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.hf-pip{width:11px;height:11px;border-radius:50%;display:inline-block;vertical-align:middle;margin-right:4px}
.hf-pip-cold1{background:#1e3a5f}
.hf-pip-cold2{background:#1d4ed8}
.hf-pip-cold3{background:#93c5fd}
.hf-legend-item{font-size:.72rem;color:#6b7280}
.hf-divider{border:none;border-top:1px solid #dbeafe;margin:12px 0}
</style>
"""

        cal_block = self._build_calientes_turn_block(turn_data, label, icon, date_str)
        fri_block = self._build_frios_turn_block(turn_data, label, icon, date_str)

        parts = [CSS, '<div class="cf-wrap">']

        parts.append(f'''
<div class="cf-hero" style="background:linear-gradient({hero_grad})">
  <div class="cf-hero-badge"><i class="fa fa-fire"></i> Análisis Predictivo</div>
  <h1 class="cf-hero-title">{icon} Sorteo <span>{label}</span></h1>
  <p class="cf-hero-sub">Pick 3 Florida · Calientes y Fríos · Actualizado al {date_str}</p>
  <span class="cf-criteria">17 criterios ponderados</span>
</div>
''')

        parts.append('<div class="cf-section-label cal"><i class="fa fa-fire"></i> Números Calientes</div>')
        parts.append(f'<!-- HC_CAL_START -->{cal_block}<!-- HC_CAL_END -->')

        parts.append('<div class="cf-section-label fri" style="margin-top:24px"><i class="fa fa-snowflake-o"></i> Números Fríos</div>')
        parts.append(fri_block)

        parts.append('</div>')  # cf-wrap
        return ''.join(parts)

    # ─────────────────────────────────────────────────────────────────────
    # Calientes turn block (used by builder and refresh)
    # ─────────────────────────────────────────────────────────────────────

    def _build_calientes_turn_block(self, turn_data, label, icon, date_str):
        numbers    = turn_data.get('numbers',    [])
        centenas   = turn_data.get('centenas',   [])
        bola_extra = turn_data.get('bola_extra', [])
        next_draw  = turn_data.get('next_draw', date_str)
        hdr_class  = 'noche' if label == 'Noche' else ''

        parts = ['<div class="hc-turn">']
        parts.append(
            f'<div class="hc-turn-hdr {hdr_class}">'
            f'<span class="hc-turn-icon">{icon}</span>'
            f'<span class="hc-turn-label">{label}</span>'
            f'<span class="hc-turn-date"><i class="fa fa-calendar-o"></i> {next_draw}</span>'
            f'</div>'
        )
        parts.append('<div class="hc-turn-body">')

        parts.append(
            '<div class="hc-legend">'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-hot"></span>#1–10</span>'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-warm"></span>#11–20</span>'
            '<span class="hc-legend-item"><span class="hc-pip hc-pip-cool"></span>#21–30</span>'
            '</div>'
        )

        parts.append('<div class="hc-section-title"><i class="fa fa-sort-numeric-asc"></i> Números calientes</div>')
        parts.append('<div class="hc-numbers-grid">')
        for i, num in enumerate(numbers):
            cls   = 'hc-ball-hot' if i < 10 else 'hc-ball-warm' if i < 20 else 'hc-ball-cool'
            score = num.get('score', '')
            name  = str(num.get('name', '')).zfill(2)
            parts.append(f'<span class="hc-ball {cls}" title="#{i+1} · Score: {score}">{name}</span>')
        parts.append('</div>')

        parts.append('<hr class="hc-divider"/>')
        parts.append('<div class="hc-ceb-row">')

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
        parts.append('</div></div>')

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
        parts.append('</div></div>')

        parts.append('</div>')       # hc-ceb-row
        parts.append('</div></div>') # hc-turn-body, hc-turn
        return ''.join(parts)

    # ─────────────────────────────────────────────────────────────────────
    # Fríos turn block
    # ─────────────────────────────────────────────────────────────────────

    def _build_frios_turn_block(self, turn_data, label, icon, date_str):
        numbers    = turn_data.get('numbers_cold',    [])
        centenas   = turn_data.get('centenas_cold',   [])
        bola_extra = turn_data.get('bola_extra_cold', [])
        next_draw  = turn_data.get('next_draw', date_str)
        hdr_class  = 'noche' if label == 'Noche' else ''

        parts = ['<div class="hf-turn">']
        parts.append(
            f'<div class="hf-turn-hdr {hdr_class}">'
            f'<span class="hf-turn-icon">{icon}</span>'
            f'<span class="hf-turn-label">{label}</span>'
            f'<span class="hf-turn-date"><i class="fa fa-calendar-o"></i> {next_draw}</span>'
            f'</div>'
        )
        parts.append('<div class="hf-turn-body">')

        parts.append(
            '<div class="hf-legend">'
            '<span class="hf-legend-item"><span class="hf-pip hf-pip-cold1"></span>#1–10</span>'
            '<span class="hf-legend-item"><span class="hf-pip hf-pip-cold2"></span>#11–20</span>'
            '<span class="hf-legend-item"><span class="hf-pip hf-pip-cold3"></span>#21–30</span>'
            '</div>'
        )

        parts.append('<div class="hf-section-title"><i class="fa fa-snowflake-o"></i> Números fríos</div>')
        parts.append('<div class="hf-numbers-grid">')
        for i, num in enumerate(numbers):
            cls   = 'hf-ball-cold1' if i < 10 else 'hf-ball-cold2' if i < 20 else 'hf-ball-cold3'
            name  = str(num.get('name', '')).zfill(2)
            score = num.get('score', '')
            parts.append(f'<span class="hf-ball {cls}" title="#{i+1} · Score: {score}">{name}</span>')
        parts.append('</div>')

        parts.append('<hr class="hf-divider"/>')
        parts.append('<div class="hf-ceb-row">')

        parts.append('<div class="hf-ceb-col">')
        parts.append('<div class="hf-section-title"><i class="fa fa-th"></i> Centenas</div>')
        parts.append('<div class="hf-ceb-grid">')
        for i, cen in enumerate(centenas):
            cls = 'hf-badge-cold1' if i < 2 else 'hf-badge-cold2'
            parts.append(
                f'<div style="text-align:center">'
                f'<span class="hf-badge {cls}">{cen.get("name","")}</span>'
                f'<span class="hf-rank">#{i+1}</span>'
                f'</div>'
            )
        parts.append('</div></div>')

        parts.append('<div class="hf-ceb-col">')
        parts.append('<div class="hf-section-title"><i class="fa fa-star"></i> Bola Extra</div>')
        parts.append('<div class="hf-ceb-grid">')
        for i, be in enumerate(bola_extra):
            cls = 'hf-badge-extra-cold1' if i < 2 else 'hf-badge-extra-cold2'
            parts.append(
                f'<div style="text-align:center">'
                f'<span class="hf-badge {cls}">{be.get("name","")}</span>'
                f'<span class="hf-rank">#{i+1}</span>'
                f'</div>'
            )
        parts.append('</div></div>')

        parts.append('</div>')       # hf-ceb-row
        parts.append('</div></div>') # hf-turn-body, hf-turn
        return ''.join(parts)
