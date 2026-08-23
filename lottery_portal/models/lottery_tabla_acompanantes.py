# -*- coding: utf-8 -*-
"""Wizard "Tabla LotoAnálisis": ubica los 100 números (00-99) en una
grilla de forma que los que más salen cerca uno del otro (acompañantes,
ver stats_service.get_companion_affinity) queden en celdas adyacentes.
Vista en pantalla + descarga como PNG con el mismo diseño de marca que
las demás piezas gráficas de LotoAnálisis."""
import base64
import json

from odoo import fields, models, api
from odoo.exceptions import UserError

from .charada_data import decade_gradient
from .tabla_acompanantes_grid import build_grid
from .tabla_acompanantes_png import render_png


class LotteryTablaAcompanantes(models.TransientModel):
    _name = 'lottery.tabla.acompanantes'
    _description = 'Tabla LotoAnálisis — matriz de acompañantes'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True,
        default=lambda self: self.env.ref(
            'lottery_base.sorteo_florida', raise_if_not_found=False))
    fecha_corte = fields.Date(
        string='Fecha de corte', required=True,
        default=lambda self: self.env.company.tabla_acompanantes_fecha_referencia
        or fields.Date.context_today(self),
        help='Se calculan los acompañantes con el historial hasta esta '
             'fecha (inclusive) — la tabla puede variar según la fecha '
             'elegida, porque la información sigue cambiando. Por defecto '
             'toma la fecha de referencia de Ajustes → Loterías (o hoy, si '
             'no hay ninguna configurada).')
    turno = fields.Selection([
        ('general', 'General'), ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno', required=True, default='general',
        help='General: mezcla sorteos de tarde y noche (como siempre). '
             'Tarde/Noche: solo esa secuencia de sorteos consecutivos, '
             'salteando el otro turno.')
    grid_size = fields.Selection([
        ('11', '11 × 11'), ('12', '12 × 12'),
    ], string='Tamaño de grilla', required=True, default='12',
        help='12×12: 44 celdas decorativas (nunca dos pegadas en horizontal '
             '/vertical, pero sí pueden tocarse en diagonal — no entran sin '
             'tocarse en un tablero de ese tamaño). 11×11: 21 decorativas, '
             'ahí sí entran sin tocarse ni en diagonal. Cada tamaño da una '
             'ubicación distinta de los números, no es la misma tabla '
             'recortada.')
    result_html = fields.Html(string='Resultado', readonly=True, sanitize=False)
    # Grilla ya calculada, para no recalcularla al descargar el PNG.
    grid_json = fields.Text(readonly=True)

    numero_consulta_id = fields.Many2one(
        'lottery.number', string='Número',
        help='Elegí un número de la tabla ya generada para ver, ordenados '
             'de menor a mayor, los demás números que comparten su misma '
             'fila, columna o diagonal.')
    resultado_numero_html = fields.Html(readonly=True, sanitize=False)

    def _get_cache(self):
        self.ensure_one()
        return self.env['lottery.tabla.acompanantes.cache'].sudo().search([
            ('sorteo_id', '=', self.sorteo_id.id),
            ('fecha_corte', '=', self.fecha_corte),
            ('turno', '=', self.turno),
            ('grid_size', '=', self.grid_size),
        ], limit=1)

    def _parse_grid_json(self, grid_json):
        return {
            tuple(int(x) for x in key.split(',')): n
            for key, n in json.loads(grid_json).items()
        }

    def action_generar(self):
        self.ensure_one()
        cache = self._get_cache()
        if cache:
            # Ya calculado antes para este sorteo + fecha de corte: la
            # historia hasta esa fecha no cambia, así que el resultado es
            # el mismo — se reutiliza en vez de recalcular.
            self.grid_json = cache.grid_json
        else:
            turno = self.turno if self.turno != 'general' else False
            affinity = self.env['lottery.stats.service'].sudo().get_companion_affinity(
                self.sorteo_id.id, fecha_corte=str(self.fecha_corte), turno=turno)
            grid, _empty = build_grid(affinity, size=int(self.grid_size))
            self.grid_json = json.dumps({f'{r},{c}': n for (r, c), n in grid.items()})
            self.env['lottery.tabla.acompanantes.cache'].sudo().create({
                'sorteo_id': self.sorteo_id.id,
                'fecha_corte': self.fecha_corte,
                'turno': self.turno,
                'grid_size': self.grid_size,
                'grid_json': self.grid_json,
            })
        self.result_html = self._render_html(
            self._parse_grid_json(self.grid_json), int(self.grid_size))
        return self._reopen()

    def action_download_png(self):
        self.ensure_one()
        if not self.grid_json:
            self.action_generar()
        cache = self._get_cache()
        if cache and cache.png_attachment_id:
            attachment = cache.png_attachment_id
        else:
            grid = self._parse_grid_json(self.grid_json)
            png_bytes = render_png(grid, int(self.grid_size), self._sorteo_label())
            attachment = self.env['ir.attachment'].sudo().create({
                'name': 'tabla-lotoanalisis-%s-%s-%s-%sx%s.png' % (
                    self.sorteo_id.code or self.sorteo_id.id,
                    self.fecha_corte, self.turno,
                    self.grid_size, self.grid_size),
                'type': 'binary',
                'datas': base64.b64encode(png_bytes),
                'mimetype': 'image/png',
            })
            if cache:
                cache.png_attachment_id = attachment.id
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _sorteo_label(self):
        self.ensure_one()
        if self.turno == 'general':
            return self.sorteo_id.name
        turno_label = dict(self._fields['turno'].selection).get(self.turno)
        return f'{self.sorteo_id.name} · {turno_label}'

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _ball_html(self, n, cell):
        """Celda <td> de una bola numerada, mismo estilo (degradé + brillo)
        que usa la tabla completa — para no duplicar el diseño entre la
        grilla y la consulta por número."""
        light, dark = decade_gradient(n)
        return f'''
            <td style="width:{cell}px;height:{cell}px;padding:2px;">
                <div style="position:relative;width:100%;height:100%;
                    border-radius:50%;
                    background:linear-gradient(135deg,{light},{dark});
                    box-shadow:0 3px 5px rgba(0,0,0,.35),
                        inset 0 -3px 5px rgba(0,0,0,.2);
                    color:#fff;display:flex;align-items:center;
                    justify-content:center;font-weight:800;
                    font-size:12.5px;">
                    <div style="position:absolute;top:14%;left:22%;
                        width:32%;height:20%;border-radius:50%;
                        background:rgba(255,255,255,.55);
                        filter:blur(1px);"></div>
                    <span style="position:relative;">{n:02d}</span>
                </div>
            </td>'''

    def _face_html(self, face, cell):
        return f'''
            <td style="width:{cell}px;height:{cell}px;padding:2px;">
                <div style="width:100%;height:100%;border-radius:50%;
                    background:linear-gradient(135deg,#EDE7F6,#FFE0B2);
                    display:flex;align-items:center;justify-content:center;
                    overflow:hidden;">
                    <img src="/lottery_portal/static/src/img/{face}"
                         style="width:88%;height:88%;object-fit:cover;
                            border-radius:50%;"/>
                </div>
            </td>'''

    @api.onchange('numero_consulta_id')
    def _onchange_numero_consulta(self):
        if self.numero_consulta_id:
            self.action_ver_numero()
        else:
            self.resultado_numero_html = False

    def action_ver_numero(self):
        self.ensure_one()
        if not self.grid_json:
            raise UserError('Primero generá la tabla.')
        if not self.numero_consulta_id:
            raise UserError('Elegí un número primero.')
        n0 = self.numero_consulta_id.name

        grid = self._parse_grid_json(self.grid_json)
        pos_by_numero = {n: cell for cell, n in grid.items()}
        if n0 not in pos_by_numero:
            raise UserError('Ese número no está en la tabla generada.')
        r0, c0 = pos_by_numero[n0]

        companions = sorted(
            n for (r, c), n in grid.items()
            if n != n0 and (r == r0 or c == c0
                            or (r - c) == (r0 - c0) or (r + c) == (r0 + c0))
        )

        if not companions:
            self.resultado_numero_html = f'''
                <p class="text-muted small">
                    <b>{n0:02d}</b> no comparte fila, columna ni diagonal con
                    ningún otro número en esta tabla.
                </p>
            '''
            return self._reopen()

        self.resultado_numero_html = self._render_numero_result(n0, companions)
        return self._reopen()

    def _clasificacion_turno(self):
        """Turno cuyo caliente/restante/frío se usa para clasificar. Tabla
        Tarde → solo clasificación de tarde. Tabla Noche → solo la de
        noche. Tabla General → la del próximo sorteo (tarde o noche, el
        que corresponda — no hay una versión "general" de calientes/
        fríos, siempre es por turno)."""
        if self.turno in ('afternoon', 'evening'):
            return self.turno
        return self.sorteo_id.get_next_draw()[1]

    def _render_numero_result(self, n0, companions):
        snapshot = self.sorteo_id._get_ranking_snapshot() or {}
        turn = self._clasificacion_turno()
        turn_data = snapshot.get(turn) or {}

        if not turn_data:
            # Sin snapshot calculado todavía para este sorteo: mostramos la
            # lista simple, sin clasificar.
            cell = 42
            rows_html = []
            for i in range(0, len(companions), 8):
                row = companions[i:i + 8]
                rows_html.append('<tr>' + ''.join(
                    self._ball_html(n, cell) for n in row) + '</tr>')
            return f'''
                <div style="text-align:center;">
                    <p class="text-muted small" style="margin-bottom:8px;">
                        Números en la misma fila, columna o diagonal que
                        <b>{n0:02d}</b> ({len(companions)}). Todavía no hay
                        caliente/restante/frío calculado para este sorteo.
                    </p>
                    <table style="border-collapse:collapse;margin:0 auto;">
                        {''.join(rows_html)}
                    </table>
                </div>
            '''

        hot = {int(s['name']) for s in turn_data.get('numbers') or []}
        cold = {int(s['name']) for s in turn_data.get('numbers_cold') or []}
        remaining = {int(s['name']) for s in turn_data.get('numbers_remaining') or []}

        grupos = [
            ('Calientes', [n for n in companions if n in hot]),
            ('Restantes', [n for n in companions if n in remaining]),
            ('Fríos', [n for n in companions if n in cold]),
        ]
        turn_label = dict(self._fields['turno'].selection).get(turn, turn)

        secciones = []
        for titulo, numeros in grupos:
            if not numeros:
                continue
            rows_html = []
            for i in range(0, len(numeros), 8):
                row = numeros[i:i + 8]
                rows_html.append('<tr>' + ''.join(
                    self._ball_html(n, cell=42) for n in row) + '</tr>')
            secciones.append(f'''
                <div style="margin-bottom:14px;">
                    <p class="text-muted small" style="margin-bottom:4px;
                        font-weight:700;">{titulo} ({len(numeros)})</p>
                    <table style="border-collapse:collapse;margin:0 auto;">
                        {''.join(rows_html)}
                    </table>
                </div>
            ''')

        return f'''
            <div style="text-align:center;">
                <p class="text-muted small" style="margin-bottom:10px;">
                    Números en la misma fila, columna o diagonal que
                    <b>{n0:02d}</b> ({len(companions)}), según
                    caliente/restante/frío de {turn_label}:
                </p>
                {''.join(secciones)}
            </div>
        '''

    def _render_html(self, grid, grid_size):
        cell = 42
        face_i = 0
        rows_html = []
        for r in range(grid_size):
            cells = []
            for c in range(grid_size):
                n = grid.get((r, c))
                if n is not None:
                    cells.append(self._ball_html(n, cell))
                else:
                    face = 'mateo_cara.png' if face_i % 2 == 0 else 'valeria_cara.png'
                    face_i += 1
                    cells.append(self._face_html(face, cell))
            rows_html.append('<tr>' + ''.join(cells) + '</tr>')

        return f'''
            <div style="text-align:center;">
                <div style="background:linear-gradient(135deg,#6D28D9,#8B5CF6);
                    border-radius:18px;padding:22px 16px 18px;margin-bottom:14px;
                    position:relative;overflow:hidden;">
                    <div style="position:absolute;top:-30px;left:-20px;width:120px;
                        height:120px;border-radius:50%;
                        background:radial-gradient(circle,rgba(249,115,22,.35),transparent 70%);"></div>
                    <div style="position:absolute;bottom:-30px;right:-20px;width:110px;
                        height:110px;border-radius:50%;
                        background:radial-gradient(circle,rgba(251,191,36,.3),transparent 70%);"></div>
                    <img src="/lottery_portal/static/src/img/logo.png"
                         style="position:relative;height:60px;margin-bottom:12px;"/>
                    <div style="position:relative;display:inline-block;
                        background:rgba(255,255,255,.12);
                        border:1px solid rgba(255,255,255,.35);
                        color:#fff;font-weight:800;font-size:14px;padding:7px 20px;
                        border-radius:50px;letter-spacing:.3px;">
                        {self._sorteo_label()}
                    </div>
                </div>
                <table style="border-collapse:collapse;margin:0 auto;">
                    {''.join(rows_html)}
                </table>
            </div>
        '''
