# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    ranking_snapshot = fields.Text(
        string='Ranking snapshot (JSON)', readonly=True,
        help="Ranking de calientes/fríos pre-calculado para el próximo sorteo. "
             "Se actualiza automáticamente después de cada salida registrada.")
    ranking_computed_at = fields.Datetime(
        string='Ranking calculado el', readonly=True)
    ranking_display = fields.Html(
        string='Ranking actual', compute='_compute_ranking_display',
        sanitize=False)

    def _compute_ranking_display(self):
        for rec in self:
            snapshot = rec._get_ranking_snapshot()
            if not snapshot:
                rec.ranking_display = '<p class="text-muted">Sin ranking calculado.</p>'
                continue
            rec.ranking_display = rec._render_ranking_html(snapshot)

    def _get_ranking_snapshot(self):
        self.ensure_one()
        if not self.ranking_snapshot:
            return None
        try:
            return json.loads(self.ranking_snapshot)
        except (json.JSONDecodeError, TypeError):
            return None

    def compute_ranking_snapshot(self):
        """Calcula y guarda el snapshot completo de rankings para ambos turnos.
        Almacena la salida completa de get_calientes_all (con scores, remaining,
        uses_fireball, next_draw) para que el portal lo lea directamente."""
        service = self.env['lottery.stats.service']
        for sorteo in self:
            nd, _nt = sorteo.get_next_draw()
            try:
                snapshot = service.get_calientes_all(nd, sorteo_id=sorteo.id)
            except Exception:
                _logger.exception('Error calculando ranking para sorteo %s', sorteo.name)
                continue
            sorteo.write({
                'ranking_snapshot': json.dumps(snapshot),
                'ranking_computed_at': fields.Datetime.now(),
            })

    def action_compute_ranking(self):
        """Botón manual para recalcular el ranking."""
        self.compute_ranking_snapshot()

    def get_validation_data(self, turn):
        """Lee el ranking pre-calculado para un turno. Retorna dict con los
        sets de calientes/fríos o {} si no hay snapshot."""
        self.ensure_one()
        snapshot = self._get_ranking_snapshot()
        if not snapshot:
            return {}
        return snapshot.get(turn, {})

    @staticmethod
    def _fmt_item(item):
        if isinstance(item, dict):
            return item.get('name', '?')
        return str(item)

    @classmethod
    def _render_ranking_html(cls, snapshot):
        parts = []
        for turn, label in (('afternoon', 'Tarde'), ('evening', 'Noche')):
            data = snapshot.get(turn, {})
            if not data:
                continue
            nums_hot = data.get('numbers', [])
            nums_cold = data.get('numbers_cold', [])
            cen_hot = data.get('centenas', [])
            cen_cold = data.get('centenas_cold', [])
            be_hot = data.get('bola_extra', [])
            be_cold = data.get('bola_extra_cold', [])
            fmt = cls._fmt_item

            parts.append(f'<h4 style="margin-top:12px">{label}</h4>')
            parts.append('<table class="table table-sm table-bordered" style="width:auto">')
            parts.append('<thead><tr><th></th><th>Calientes</th><th>Fríos</th></tr></thead>')
            parts.append('<tbody>')
            # Bloques por posición en el ranking (mismo criterio que la
            # validación de salidas): los primeros fijos de 10, el último
            # absorbe el resto (varía con los empates).
            def _blk_html(lst, prefix, nblocks):
                blocks = [lst[i * 10:(i + 1) * 10] for i in range(nblocks - 1)]
                blocks.append(lst[(nblocks - 1) * 10:])
                return '<br/>'.join(
                    f'<b>{prefix}{i + 1}:</b> {", ".join(fmt(n) for n in blk)}'
                    for i, blk in enumerate(blocks) if blk)

            parts.append(f'<tr><td><b>Números</b> ({len(nums_hot)}/{len(nums_cold)})</td>'
                         f'<td style="font-size:11px">{_blk_html(nums_hot, "C", 3)}</td>'
                         f'<td style="font-size:11px">{_blk_html(nums_cold, "F", 3)}</td></tr>')
            nums_rem = data.get('numbers_remaining', [])
            if nums_rem:
                parts.append(f'<tr><td><b>Restantes</b> ({len(nums_rem)})</td>'
                             f'<td colspan="2" style="font-size:11px">'
                             f'{_blk_html(nums_rem, "R", 4)}</td></tr>')
            parts.append(f'<tr><td><b>Centenas</b></td>'
                         f'<td>{", ".join(fmt(c) for c in cen_hot)}</td>'
                         f'<td>{", ".join(fmt(c) for c in cen_cold)}</td></tr>')
            if be_hot or be_cold:
                parts.append(f'<tr><td><b>Bola Extra</b></td>'
                             f'<td>{", ".join(fmt(b) for b in be_hot)}</td>'
                             f'<td>{", ".join(fmt(b) for b in be_cold)}</td></tr>')
            parts.append('</tbody></table>')
        return ''.join(parts) if parts else '<p class="text-muted">Sin datos.</p>'
