# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

WEEKDAY_CODES = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do')

# ── Pesos del botón "Completar números" ───────────────────────────────────
# Jerarquía pedida: combinaciones manda, y ninguna señal de abajo puede, por
# sí sola, dar vuelta ese orden (su máximo es siempre menor que los 50 puntos
# de recorrido de combinaciones). Cada escalón pesa menos que el anterior:
# tabla general > tabla del turno > grupos generales > grupos del turno >
# pintas generales > pintas del turno. Entre varias señales sí pueden mover
# a un número — de eso se trata el reparto.
PESO_COMBINACIONES = 50.0
PESO_TABLA_GENERAL = 18.0
PESO_TABLA_TURNO = 14.0
# Puntos por puesto en el ranking de atraso (1º, 2º, 3º...). El corte es el
# mismo que muestran la web y la app: 5 grupos y 3 pintas.
ESCALA_GRUPOS_GENERAL = (9.0, 7.0, 5.0, 3.0, 1.0)
ESCALA_GRUPOS_TURNO = (7.0, 5.0, 4.0, 2.0, 1.0)
ESCALA_PINTAS_GENERAL = (5.0, 3.0, 1.0)
ESCALA_PINTAS_TURNO = (4.0, 2.0, 1.0)


def _default_sorteo(self):
    return self.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)


class LotteryPrediction(models.Model):
    _name = 'lottery.prediction'
    _description = 'Predicción de números'
    _order = 'date desc, turn_day desc, id desc'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=_default_sorteo,
        help='Sorteo/juego para el que se hace la predicción.')
    date = fields.Date(
        string='Fecha de predicción', required=True, index=True,
        default=lambda self: fields.Date.today(),
        help='Fecha del sorteo para el que se predicen los números.')
    turn_day = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno del día', required=True, index=True)
    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='Solo las predicciones publicadas se envían a la app móvil '
             '(Números Mágicos). Permite prepararlas con anticipación y '
             'publicarlas cuando estén listas.')

    temperature = fields.Selection([
        ('hot',       'Calientes'),
        ('remaining', 'Restantes'),
        ('cold',      'Fríos'),
    ], string='Temperatura', index=True,
        help='Al seleccionar, carga automáticamente los números calientes, '
             'restantes o fríos del último artículo generado para este turno.')

    combinaciones_window = fields.Integer(
        string='Ventana de combinaciones', default=50, required=True,
        help='Cuántas salidas hacia atrás mira el puntaje de combinaciones '
             '(el mismo de la Consulta de números) al completar las listas '
             'de 20, 10 y 5. Tope 200.')
    score_html = fields.Html(
        string='Puntajes', readonly=True, sanitize=False, copy=False,
        help='Desglose de la última corrida de "Completar números": qué '
             'puntaje sacó cada candidato y por qué.')

    # ── Números a predecir (listas independientes) ─────────────────────────
    number_ids = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_rel',
        'prediction_id', 'number_id',
        string='Números a predecir')
    number_ids_20 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_20_rel',
        'prediction_id', 'number_id',
        string='20 Números a predecir')
    number_ids_10 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_10_rel',
        'prediction_id', 'number_id',
        string='10 Números a predecir')
    number_ids_5 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_5_rel',
        'prediction_id', 'number_id',
        string='5 Números a predecir')

    numbers_count = fields.Integer(
        string='Cantidad', compute='_compute_numbers_count', store=True)
    numbers_count_20 = fields.Integer(
        string='Cantidad 20', compute='_compute_numbers_count_20', store=True)
    numbers_count_10 = fields.Integer(
        string='Cantidad 10', compute='_compute_numbers_count_10', store=True)
    numbers_count_5 = fields.Integer(
        string='Cantidad 5', compute='_compute_numbers_count_5', store=True)

    # ── Verificación ───────────────────────────────────────────────────────
    cumplida = fields.Boolean(
        'Se cumplió?', default=False, index=True,
        help='El número que salió en el sorteo estaba entre los números '
             'de esta predicción. Se marca automáticamente al registrar '
             'la salida.')
    cumplida_20 = fields.Boolean(
        'Cumplida en 20?', default=False, index=True,
        help='El número salido estaba entre los 20 Números a predecir.')
    cumplida_10 = fields.Boolean(
        'Cumplida en 10?', default=False, index=True,
        help='El número salido estaba entre los 10 Números a predecir.')
    cumplida_5 = fields.Boolean(
        'Cumplida en 5?', default=False, index=True,
        help='El número salido estaba entre los 5 Números a predecir.')
    verification_date = fields.Datetime(
        'Verificada el', readonly=True,
        help='Momento en que se registró la salida y se verificó la '
             'predicción. Vacío = el sorteo aún no se jugó.')

    _sql_constraints = [
        (
            'unique_date_turn_sorteo',
            'unique(date, turn_day, sorteo_id)',
            'Ya existe una predicción registrada para esa fecha, turno y sorteo.'
        )
    ]

    @api.depends('number_ids')
    def _compute_numbers_count(self):
        for rec in self:
            rec.numbers_count = len(rec.number_ids)

    @api.depends('number_ids_20')
    def _compute_numbers_count_20(self):
        for rec in self:
            rec.numbers_count_20 = len(rec.number_ids_20)

    @api.depends('number_ids_10')
    def _compute_numbers_count_10(self):
        for rec in self:
            rec.numbers_count_10 = len(rec.number_ids_10)

    @api.depends('number_ids_5')
    def _compute_numbers_count_5(self):
        for rec in self:
            rec.numbers_count_5 = len(rec.number_ids_5)

    @api.depends('date', 'turn_day', 'sorteo_id.name')
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            turn_label = dict(self._fields['turn_day'].selection).get(rec.turn_day, '')
            sorteo_label = f" / {rec.sorteo_id.name}" if rec.sorteo_id else ''
            rec.display_name = f"{date_str} / {turn_label}{sorteo_label}"

    @api.onchange('temperature', 'turn_day', 'sorteo_id')
    def _onchange_temperature(self):
        if not self.temperature or not self.turn_day or not self.sorteo_id:
            return
        import json as _json
        snapshot_raw = self.sorteo_id.ranking_snapshot
        if not snapshot_raw:
            return
        try:
            snapshot = _json.loads(snapshot_raw)
        except (ValueError, TypeError):
            return
        turn_data = snapshot.get(self.turn_day, {})
        key_map = {
            'hot':       'numbers',
            'cold':      'numbers_cold',
            'remaining': 'numbers_remaining',
        }
        items = turn_data.get(key_map[self.temperature], [])
        names = []
        for item in items:
            raw = item.get('name') if isinstance(item, dict) else str(item)
            try:
                names.append(int(raw))
            except (ValueError, TypeError):
                pass
        if names:
            self.number_ids = self.env['lottery.number'].search([('name', 'in', names)])
        else:
            self.number_ids = self.env['lottery.number']

    # ── Completar números: 20 / 10 / 5 en cascada ──────────────────────────

    def _last_output(self, turn=None):
        """Última salida ANTERIOR al sorteo que se está prediciendo.

        turn=None → la última sin importar el turno (si se predice la noche
        de hoy y la tarde ya salió, es la de la tarde). turn='afternoon' /
        'evening' → la última de ese turno. Nunca mira el propio sorteo a
        predecir ni ninguno posterior, así que volver a correr una predicción
        vieja da lo mismo que el día que se generó."""
        self.ensure_one()
        domain = [('sorteo_id', '=', self.sorteo_id.id)]
        if self.turn_day == 'evening':
            domain += ['|', ('date', '<', self.date),
                       '&', ('date', '=', self.date),
                       ('turn_day', '=', 'afternoon')]
        else:
            domain += [('date', '<', self.date)]
        if turn:
            domain += [('turn_day', '=', turn)]
        # turn_day desc deja 'evening' antes que 'afternoon' del mismo día.
        return self.env['lottery.output'].sudo().search(
            domain, order='date desc, turn_day desc, id desc', limit=1)

    def _acompanantes(self, turno, numero):
        """Números que comparten fila, columna o diagonal con `numero` en la
        Tabla LotoAnálisis — la misma grilla que muestra el wizard: fecha de
        corte de Ajustes → Loterías y 12×12, reusando la caché."""
        self.ensure_one()
        fecha_corte = (self.env.company.tabla_acompanantes_fecha_referencia
                       or fields.Date.context_today(self))
        grid = self.env['lottery.tabla.acompanantes.cache'].sudo().get_grid(
            self.sorteo_id.id, fecha_corte, turno=turno, grid_size='12')
        pos = {n: rc for rc, n in grid.items()}
        if numero not in pos:
            return set()
        r0, c0 = pos[numero]
        return {n for (r, c), n in grid.items()
                if n != numero and (r == r0 or c == c0
                                    or (r - c) == (r0 - c0)
                                    or (r + c) == (r0 + c0))}

    def _puntos_por_grupos(self, top_fn, option, day, escala):
        """{número: puntos} según los grupos (o pintas) más atrasados: el 1º
        de la lista reparte el primer valor de la escala entre todos sus
        números, el 2º el segundo, y así.

        Un número que cae en varios grupos se queda con el mejor puesto, NO
        suma: si sumara, un número repetido en tres grupos podría superar por
        sí solo a las tablas, que pesan más en la jerarquía."""
        self.ensure_one()
        puntos, detalle = {}, []
        for i, row in enumerate(top_fn(option, day, sorteo_id=self.sorteo_id.id)):
            if i >= len(escala):
                break
            valor = escala[i]
            numeros = self.env['lottery.group'].browse(
                row['id']).number_ids.mapped('name')
            detalle.append((row['name'], valor, numeros))
            for n in numeros:
                if valor > puntos.get(n, 0.0):
                    puntos[n] = valor
        return puntos, detalle

    def _score_candidatos(self):
        """Puntúa los números de `number_ids` con todas las señales y los
        devuelve ordenados de mejor a peor, con el contexto que se usó."""
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        candidatos = sorted(self.number_ids.mapped('name'))

        # 1) Combinaciones — la señal que manda el orden.
        base = stats.get_combinaciones_scores(
            self.sorteo_id.id, self.date, self.combinaciones_window)
        crudos = {n: base['scores'].get('%02d' % n, 0) for n in candidatos}
        # Se estira el puntaje crudo del conjunto al rango 0-PESO_COMBINACIONES:
        # el mejor se lleva todo y el peor nada, proporcional a la distancia
        # real entre puntajes. Así dos candidatos casi empatados quedan casi
        # empatados (y ahí deciden las tablas y los atrasos), mientras que una
        # diferencia grande de combinaciones no la da vuelta nadie. Con rank
        # por posición eso se perdía: todos los escalones medían igual.
        peor, mejor = min(crudos.values()), max(crudos.values())
        rango = mejor - peor
        comb_pts = {n: (PESO_COMBINACIONES * (v - peor) / rango if rango
                        else PESO_COMBINACIONES)
                    for n, v in crudos.items()}

        # 2) Tablas LotoAnálisis — acompañantes del último número salido.
        last_general = self._last_output()
        last_turno = self._last_output(turn=self.turn_day)
        acomp_general = (self._acompanantes('general', last_general.number_id.name)
                         if last_general else set())
        acomp_turno = (self._acompanantes(self.turn_day, last_turno.number_id.name)
                       if last_turno else set())

        # 3) Grupos y pintas más atrasados, general y del turno a predecir.
        day = WEEKDAY_CODES[self.date.weekday()]
        gg_pts, gg_det = self._puntos_por_grupos(
            stats.get_top_6_groups, 'general', day, ESCALA_GRUPOS_GENERAL)
        gt_pts, gt_det = self._puntos_por_grupos(
            stats.get_top_6_groups, self.turn_day, day, ESCALA_GRUPOS_TURNO)
        pg_pts, pg_det = self._puntos_por_grupos(
            stats.get_top_3_pintas, 'general', day, ESCALA_PINTAS_GENERAL)
        pt_pts, pt_det = self._puntos_por_grupos(
            stats.get_top_3_pintas, self.turn_day, day, ESCALA_PINTAS_TURNO)

        filas = []
        for n in candidatos:
            fila = {
                'numero': n,
                'comb_score': crudos[n],
                'comb': comb_pts[n],
                'tg': PESO_TABLA_GENERAL if n in acomp_general else 0.0,
                'tt': PESO_TABLA_TURNO if n in acomp_turno else 0.0,
                'gg': gg_pts.get(n, 0.0),
                'gt': gt_pts.get(n, 0.0),
                'pg': pg_pts.get(n, 0.0),
                'pt': pt_pts.get(n, 0.0),
            }
            fila['total'] = round(
                fila['comb'] + fila['tg'] + fila['tt'] + fila['gg']
                + fila['gt'] + fila['pg'] + fila['pt'], 2)
            filas.append(fila)

        # Desempates: puntaje crudo de combinaciones y después número más
        # chico, para que dos corridas con los mismos datos den lo mismo.
        filas.sort(key=lambda f: (-f['total'], -f['comb_score'], f['numero']))

        ctx = {
            'window_used': len(base['outputs']),
            'window_asked': self.combinaciones_window,
            'last_general': last_general,
            'last_turno': last_turno,
            'detalles': [
                ('Grupos atrasados (general)', gg_det),
                ('Grupos atrasados (turno)', gt_det),
                ('Pintas atrasadas (general)', pg_det),
                ('Pintas atrasadas (turno)', pt_det),
            ],
        }
        return filas, ctx

    def action_completar_numeros(self):
        """Completa las listas de 20, 10 y 5 en cascada a partir de los
        números a predecir: los 20 salen del conjunto entero, los 10 de esos
        20 y los 5 de esos 10 (es un único orden, así el anidamiento se
        cumple solo).

        El orden lo da la suma ponderada de: combinaciones (la señal que
        manda), acompañantes del último número en la tabla general, ídem en
        la tabla del turno a predecir, y grupos y pintas más atrasados,
        general y del turno.

        Los atrasos de grupos y pintas son los de HOY, no los de la fecha de
        la predicción: está pensado para correrlo antes de cada salida. Las
        tres listas quedan editables, el botón sólo las precarga."""
        self.ensure_one()
        if len(self.number_ids) < 5:
            raise UserError(
                'Cargá primero los números a predecir (con el campo '
                'Temperatura o a mano): hacen falta al menos 5 para armar '
                'las listas de 20, 10 y 5.')

        filas, ctx = self._score_candidatos()
        orden = [f['numero'] for f in filas]
        Number = self.env['lottery.number']

        def ids(numeros):
            return Number.search([('name', 'in', numeros)]).ids

        self.write({
            'number_ids_20': [(6, 0, ids(orden[:20]))],
            'number_ids_10': [(6, 0, ids(orden[:10]))],
            'number_ids_5': [(6, 0, ids(orden[:5]))],
            'score_html': self._render_scores_html(filas, ctx),
        })
        return True

    # ── Render del desglose ────────────────────────────────────────────────

    @staticmethod
    def _fmt_pts(valor):
        return ('%.1f' % valor).rstrip('0').rstrip('.') or '0'

    def _render_scores_html(self, filas, ctx):
        self.ensure_one()
        turn_lbl = dict(self._fields['turn_day'].selection)
        fmt = self._fmt_pts

        def salida(rec):
            if not rec:
                return '<span class="text-muted">sin salidas previas</span>'
            return '<b>%02d</b> (%s %s)' % (
                rec.number_id.name, rec.date.strftime('%d/%m/%Y'),
                turn_lbl.get(rec.turn_day, rec.turn_day))

        def detalle(titulo, det):
            if not det:
                return ('<p class="small text-muted mb-1">%s: sin datos</p>'
                        % titulo)
            items = ' · '.join('%s <b>+%s</b>' % (nombre, fmt(valor))
                               for nombre, valor, _numeros in det)
            return ('<p class="small mb-1"><span class="text-muted">%s:</span> '
                    '%s</p>' % (titulo, items))

        def celda(valor):
            return ('<td class="text-center">%s</td>' % fmt(valor) if valor
                    else '<td class="text-center text-muted">·</td>')

        aviso = ''
        if len(filas) < 20:
            aviso = ('<div class="alert alert-warning py-2 small">Sólo hay %d '
                     'números a predecir: las listas se llenaron con los que '
                     'había.</div>' % len(filas))

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', 'Total', 'Comb.', 'Tabla gral.',
                      'Tabla turno', 'Grupos gral.', 'Grupos turno',
                      'Pintas gral.', 'Pintas turno'))

        cuerpo = []
        for i, f in enumerate(filas):
            if i < 5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif i < 10:
                fondo, corte = '#fff1e0', ' · 10'
            elif i < 20:
                fondo, corte = '#f1f3f5', ' · 20'
            else:
                fondo, corte = '', ''
            cuerpo.append(
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td>'
                '<td class="text-center"><b>%02d</b></td>'
                '<td class="text-center"><b>%s</b></td>'
                '<td class="text-center">%s <span class="text-muted" '
                'style="font-size:10px;">(%d)</span></td>'
                '%s%s%s%s%s%s</tr>' % (
                    fondo, i + 1, corte, f['numero'], fmt(f['total']),
                    fmt(f['comb']), f['comb_score'], celda(f['tg']),
                    celda(f['tt']), celda(f['gg']), celda(f['gt']),
                    celda(f['pg']), celda(f['pt'])))

        turno_txt = turn_lbl.get(self.turn_day, self.turn_day)
        return """
            <div>
                %s
                <p class="small mb-1">
                    <span class="text-muted">Ventana de combinaciones:</span>
                    %d salidas usadas (pedidas %d) ·
                    <span class="text-muted">Último número (general):</span> %s ·
                    <span class="text-muted">Último de %s:</span> %s
                </p>
                %s
                <p class="text-muted small mb-2">
                    Fondo violeta: los 5 · naranja: hasta los 10 · gris: hasta
                    los 20. Entre paréntesis, el puntaje crudo de
                    combinaciones (producto de frecuencias de dígitos). Los
                    atrasos de grupos y pintas son los del momento en que se
                    apretó el botón.
                </p>
                <table class="table table-sm table-bordered"
                       style="font-size:12px;">
                    <thead><tr>%s</tr></thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """ % (aviso, ctx['window_used'], ctx['window_asked'],
               salida(ctx['last_general']), turno_txt,
               salida(ctx['last_turno']),
               ''.join(detalle(t, d) for t, d in ctx['detalles']),
               cabeza, ''.join(cuerpo))
