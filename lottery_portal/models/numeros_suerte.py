# -*- coding: utf-8 -*-
"""Números de la Suerte: 20 → 15 → 10 → 5 → Súper Mágico armados sobre la
UNIÓN de los dos turnos de una misma temperatura.

Se diferencia de `lottery.prediction` en cuatro cosas, y son justamente las
cuatro razones por las que es un modelo aparte y no un botón más de aquél:

  1. NO tiene turno. Los candidatos salen de juntar la tabla de tarde y la de
     noche del `ranking_snapshot` del sorteo (la misma que se ve en el
     formulario del sorteo, pestaña "Ranking calientes / fríos") en una sola
     bolsa sin repetidos. Un número que está en las DOS tablas arrastra esa
     marca: es el primer criterio de orden (ver `_clave`).

  2. La caminata de recencia que arma los 20 avanza por DÍA ENTERO — las dos
     salidas del día se miran juntas —, no salida por salida como
     `_seleccionar_veinte` de la predicción.

  3. Las tablas LotoAnálisis se miran en TRES referencias en vez de dos:
       general → contra la última salida (que normalmente es la de la noche)
       noche   → contra ese mismo número
       tarde   → contra el número que salió en la tarde

  4. Los grupos y las pintas atrasados también se miran en tres niveles
     (general, tarde y noche) en lugar de general + turno.

Los recortes van con las tablas primero y los grupos después:
     20 → 15  tabla general
     15 → 10  en cuántas de las dos tablas de turno aparece (0, 1 ó 2)
     10 →  5  grupos atrasados generales
      5 → SM  en cuántos niveles de grupos de turno aparece (0, 1 ó 2)
y la cascada de `lottery.prediction` desempata dentro de cada nivel.

Es un modelo INTERNO: no se publica en la app ni dispara notificaciones.
"""
import json
import random

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.lottery_base.models.utils import default_today_local

from .lottery_prediction import (
    APORTE_GRUPOS_EXTRA,
    ESCALA_ATRASO,
    TEMPERATURE_KEY,
    VENTANA_MAYORIA,
    WEEKDAY_CODES,
    _comparte_digito,
    _default_sorteo,
    _factor_distancia,
)
from .patron_atraso import _hit_cruce

# Los tres niveles en que se miran tablas, grupos y pintas. El orden importa
# sólo para el desglose HTML; para el puntaje se unen los tres.
NIVELES = (
    ('general', 'general'),
    ('evening', 'noche'),
    ('afternoon', 'tarde'),
)

# Campo de lottery_group_stat que mide el atraso de cada nivel.
CAMPO_ATRASO = {
    'general': 'salidas_atrasadas',
    'afternoon': 'salidas_atrasadas_dia',
    'evening': 'salidas_atrasadas_noche',
}

# Cuántos días hacia atrás se camina buscando coincidencias de dígito. Con dos
# salidas por día y 60 días hay de sobra para juntar 20 aunque los candidatos
# sean pocos; si se agota antes, el resto entra por la cascada.
MAX_DIAS_HISTORIAL = 60


class LotteryNumerosSuerte(models.Model):
    _name = 'lottery.numeros.suerte'
    _description = 'Números de la Suerte'
    _order = 'date desc, id desc'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=_default_sorteo,
        help='Sorteo/juego del que se leen las dos tablas de temperatura.')
    date = fields.Date(
        string='Fecha', required=True, index=True,
        default=default_today_local,
        help='Fecha del sorteo al que apunta la selección. El historial que '
             'se camina para armar los 20 arranca en el día ANTERIOR a esta '
             'fecha, con las dos salidas de ese día juntas.')
    temperature = fields.Selection([
        ('hot',       'Calientes'),
        ('remaining', 'Restantes'),
        ('cold',      'Fríos'),
    ], string='Temperatura', required=True, index=True,
        help='Al seleccionar, carga los números de esa temperatura uniendo '
             'la tabla de tarde y la de noche del ranking del sorteo.')

    combinaciones_window = fields.Integer(
        string='Ventana de combinaciones', default=50, required=True,
        help='Cuántas salidas hacia atrás mira el puntaje de combinaciones '
             '(el mismo de la Consulta de números), que es el 4º escalón de '
             'la cascada de desempate. Tope 200.')

    # ── Listas ──────────────────────────────────────────────────────────
    number_ids = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_rel',
        'suerte_id', 'number_id',
        string='Candidatos',
        help='Unión de las dos tablas (tarde y noche) de la temperatura '
             'elegida. Se puede editar a mano antes de calcular.')
    number_ids_20 = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_20_rel',
        'suerte_id', 'number_id', string='20 Números')
    number_ids_15 = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_15_rel',
        'suerte_id', 'number_id', string='15 Números')
    number_ids_10 = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_10_rel',
        'suerte_id', 'number_id', string='10 Números')
    number_ids_5 = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_5_rel',
        'suerte_id', 'number_id', string='5 Números')
    doble_turno_ids = fields.Many2many(
        'lottery.number', 'lottery_suerte_number_doble_rel',
        'suerte_id', 'number_id', string='En los dos turnos', readonly=True,
        help='Los que estaban en la tabla de esa temperatura TANTO en tarde '
             'como en noche. Es el primer criterio de orden de los 20.')
    super_magico_id = fields.Many2one(
        'lottery.number', string='Súper Mágico',
        help='El 1º de los 5, por en cuántos niveles de grupos atrasados de '
             'turno (tarde y noche) aparece.')

    numbers_count = fields.Integer(
        string='Candidatos', compute='_compute_counts', store=True)
    numbers_count_doble = fields.Integer(
        string='En los dos turnos', compute='_compute_counts', store=True)

    score_html = fields.Html(
        string='Puntajes', readonly=True, sanitize=False, copy=False,
        help='Desglose de la última corrida: por qué quedó cada número donde '
             'quedó.')

    _sql_constraints = [
        (
            'unique_date_temp_sorteo',
            'unique(date, temperature, sorteo_id)',
            'Ya hay unos Números de la Suerte para esa fecha, temperatura y '
            'sorteo.'
        )
    ]

    @api.depends('number_ids', 'doble_turno_ids')
    def _compute_counts(self):
        for rec in self:
            rec.numbers_count = len(rec.number_ids)
            rec.numbers_count_doble = len(rec.doble_turno_ids)

    @api.depends('date', 'temperature', 'sorteo_id.name')
    def _compute_display_name(self):
        etiquetas = dict(self._fields['temperature'].selection)
        for rec in self:
            rec.display_name = '%s / %s%s' % (
                rec.date.strftime('%d-%m-%Y') if rec.date else '',
                etiquetas.get(rec.temperature, ''),
                ' / %s' % rec.sorteo_id.name if rec.sorteo_id else '')

    # ── Candidatos ──────────────────────────────────────────────────────

    def _tablas_snapshot(self):
        """{número: {turnos en que aparece}} para la temperatura elegida.

        Lee el `ranking_snapshot` del sorteo, que es lo mismo que muestra la
        pestaña "Ranking calientes / fríos" del formulario del sorteo. Dict
        vacío si el sorteo todavía no tiene snapshot calculado."""
        self.ensure_one()
        if not (self.sorteo_id and self.temperature):
            return {}
        try:
            snapshot = json.loads(self.sorteo_id.ranking_snapshot or '{}')
        except (ValueError, TypeError):
            return {}
        clave = TEMPERATURE_KEY.get(self.temperature)
        turnos = {}
        for turno in ('afternoon', 'evening'):
            for item in snapshot.get(turno, {}).get(clave, []) or []:
                raw = item.get('name') if isinstance(item, dict) else item
                try:
                    numero = int(raw)
                except (ValueError, TypeError):
                    continue
                turnos.setdefault(numero, set()).add(turno)
        return turnos

    @api.onchange('temperature', 'sorteo_id')
    def _onchange_temperature(self):
        if not (self.temperature and self.sorteo_id):
            return
        turnos = self._tablas_snapshot()
        Number = self.env['lottery.number']
        todos = Number.search([('name', 'in', list(turnos))]) if turnos else Number
        self.number_ids = todos
        self.doble_turno_ids = todos.filtered(
            lambda n: len(turnos.get(n.name, ())) > 1)

    def action_cargar_candidatos(self):
        """Recarga los candidatos desde el ranking del sorteo, pisando lo que
        hubiera. Es el mismo onchange, pero disponible con el registro ya
        guardado."""
        for rec in self:
            turnos = rec._tablas_snapshot()
            if not turnos:
                raise UserError(
                    'El sorteo %s no tiene ranking calculado todavía. Abrí el '
                    'sorteo y tocá "Recalcular ranking".' % rec.sorteo_id.name)
            Number = rec.env['lottery.number']
            todos = Number.search([('name', 'in', list(turnos))])
            rec.write({
                'number_ids': [(6, 0, todos.ids)],
                'doble_turno_ids': [(6, 0, todos.filtered(
                    lambda n: len(turnos.get(n.name, ())) > 1).ids)],
            })
        return True

    # ── Historial ───────────────────────────────────────────────────────

    def _last_output(self, turn=None, limit=1):
        """Últimas salidas ANTERIORES a la fecha de esta selección.

        A diferencia de la predicción no hay turno al que apuntar, así que el
        corte es siempre `date < self.date`: el día de la fecha no se mira
        nunca, ni siquiera su turno de tarde. Devuelve el recordset de la más
        reciente a la más vieja ('evening' antes que 'afternoon' del mismo
        día, que es lo que da `turn_day desc`)."""
        self.ensure_one()
        domain = [('sorteo_id', '=', self.sorteo_id.id),
                  ('date', '<', self.date)]
        if turn:
            domain += [('turn_day', '=', turn)]
        return self.env['lottery.output'].sudo().search(
            domain, order='date desc, turn_day desc, id desc', limit=limit)

    def _salidas_por_dia(self, max_dias=MAX_DIAS_HISTORIAL):
        """[(fecha, [salidas de ese día])] de la más reciente hacia atrás.

        Las dos salidas de un mismo día viajan juntas: la caminata que arma
        los 20 avanza de día en día, no de salida en salida."""
        self.ensure_one()
        outputs = self._last_output(limit=max_dias * 4)
        dias = []
        for output in outputs:
            if not dias or dias[-1][0] != output.date:
                if len(dias) >= max_dias:
                    break
                dias.append((output.date, []))
            dias[-1][1].append(output)
        return dias

    # ── Señales ─────────────────────────────────────────────────────────

    def _acompanantes(self, turno, numero):
        """{número: distancia en casillas} de los que comparten fila, columna
        o diagonal con `numero` en la Tabla LotoAnálisis de ese nivel.

        Misma grilla 12×12 y misma fecha de corte que el wizard y que la
        predicción, reusando la caché."""
        self.ensure_one()
        fecha_corte = (self.env.company.tabla_acompanantes_fecha_referencia
                       or fields.Date.context_today(self))
        grid = self.env['lottery.tabla.acompanantes.cache'].sudo().get_grid(
            self.sorteo_id.id, fecha_corte, turno=turno, grid_size='12')
        pos = {n: rc for rc, n in grid.items()}
        if numero not in pos:
            return {}
        r0, c0 = pos[numero]
        return {n: max(abs(r - r0), abs(c - c0))
                for (r, c), n in grid.items()
                if n != numero and (r == r0 or c == c0
                                    or (r - c) == (r0 - c0)
                                    or (r + c) == (r0 + c0))}

    def _valores_tabla(self, candidatos, refs):
        """{nivel: {número: (factor, distancia)}} de las tres tablas.

        Cada nivel se mira contra SU número de referencia: la general contra
        la última salida, la de noche contra el número de la noche y la de
        tarde contra el de la tarde. Un candidato puede puntuar en las tres,
        en una o en ninguna."""
        self.ensure_one()
        salida = {}
        for nivel, _lbl in NIVELES:
            ref = refs.get(nivel)
            acomp = self._acompanantes(nivel, ref.number_id.name) if ref else {}
            salida[nivel] = {n: (_factor_distancia(acomp[n]), acomp[n])
                             for n in candidatos if acomp.get(n)}
        return salida

    def _numeros_por_nivel(self, top_fn, day, nivel):
        """set de números que caen en alguno de los grupos (o pintas) más
        atrasados de ese nivel. Se usa para las señales de recorte, que
        cuentan presencia y no atraso."""
        self.ensure_one()
        numeros = set()
        for row in top_fn(nivel, day, sorteo_id=self.sorteo_id.id):
            numeros.update(
                self.env['lottery.group'].browse(row['id']).number_ids
                .mapped('name'))
        return numeros

    def _puntos_por_atraso(self, top_fn, day, niveles, peso):
        """{número: puntos} de los grupos (o pintas) más atrasados, uniendo
        los niveles pedidos en UNA sola lista.

        Es el mismo criterio que `lottery.prediction._puntos_por_atraso`, con
        la única diferencia de que acá los niveles son tres (general, tarde y
        noche) y no dos: el orden lo da la cantidad de salidas atrasadas y no
        el puesto, un grupo que aparece en varios niveles se queda con su
        atraso más alto, y un número que cae en varios grupos suma el mejor
        entero más la fracción de `APORTE_GRUPOS_EXTRA` según en cuántos
        está."""
        self.ensure_one()
        entradas = {}
        for nivel, etiqueta in NIVELES:
            if nivel not in niveles:
                continue
            campo = CAMPO_ATRASO[nivel]
            for row in top_fn(nivel, day, sorteo_id=self.sorteo_id.id):
                atraso = row.get(campo) or 0
                previa = entradas.get(row['id'])
                if previa is None:
                    entradas[row['id']] = {
                        'id': row['id'], 'name': row['name'],
                        'atraso': atraso, 'origenes': [etiqueta],
                    }
                else:
                    previa['origenes'].append(etiqueta)
                    previa['atraso'] = max(previa['atraso'], atraso)

        puntero = max((e['atraso'] for e in entradas.values()), default=0)
        aportes, detalle = {}, []
        for e in sorted(entradas.values(),
                        key=lambda e: (-e['atraso'], e['name'])):
            valor = round(peso * e['atraso'] / puntero, 2) if puntero else peso
            numeros = self.env['lottery.group'].browse(
                e['id']).number_ids.mapped('name')
            detalle.append({
                'name': e['name'], 'atraso': e['atraso'],
                'origen': ' + '.join(e['origenes']), 'valor': valor,
                'numeros': numeros,
            })
            for n in numeros:
                aportes.setdefault(n, []).append(valor)

        puntos = {}
        for n, valores in aportes.items():
            valores.sort(reverse=True)
            coef = APORTE_GRUPOS_EXTRA[
                min(len(valores), len(APORTE_GRUPOS_EXTRA)) - 1]
            puntos[n] = round(valores[0] + coef * sum(valores[1:]), 2)
        return puntos, detalle

    def _valores_cascada(self, candidatos):
        """{número: {señal: valor}} con todo lo que necesitan el orden de los
        20 y los cuatro recortes, más el contexto para el desglose.

        Las claves que lee `lottery.prediction._clave_cascada` (tabla, grupos,
        pintas, comb, cruce, mayoria, azar) se arman con el mismo significado
        que allá para que la cascada sea literalmente la misma; el resto son
        las señales propias de este modelo."""
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        Pred = self.env['lottery.prediction']
        day = WEEKDAY_CODES[self.date.weekday()]
        todos_niveles = tuple(nivel for nivel, _lbl in NIVELES)

        refs = {
            'general':   self._last_output(),
            'evening':   self._last_output(turn='evening'),
            'afternoon': self._last_output(turn='afternoon'),
        }
        tablas = self._valores_tabla(candidatos, refs)

        gr_pts, gr_det = self._puntos_por_atraso(
            stats.get_top_6_groups, day, todos_niveles, ESCALA_ATRASO)
        pi_pts, pi_det = self._puntos_por_atraso(
            stats.get_top_3_pintas, day, todos_niveles, ESCALA_ATRASO)
        # Sólo la general: es la señal del recorte 10 → 5.
        gr_gen_pts, gr_gen_det = self._puntos_por_atraso(
            stats.get_top_6_groups, day, ('general',), ESCALA_ATRASO)
        # Presencia por turno: es la señal del recorte 5 → Súper Mágico.
        gr_turno = {
            nivel: self._numeros_por_nivel(stats.get_top_6_groups, day, nivel)
            for nivel in ('afternoon', 'evening')
        }

        base = stats.get_combinaciones_scores(
            self.sorteo_id.id, self.date, self.combinaciones_window)
        comb = {n: base['scores'].get('%02d' % n, 0) for n in candidatos}

        ref_cruce = (refs['general'].number_id.name
                     if refs['general'] else None)
        ultimos = self._last_output(limit=VENTANA_MAYORIA)
        rango_mayoria = Pred._rango_preferido_mayoria(ultimos)

        turnos_snapshot = self._tablas_snapshot()
        dobles = {n for n, turnos in turnos_snapshot.items() if len(turnos) > 1}
        # Si los candidatos se editaron a mano el snapshot puede no cubrirlos;
        # el campo guardado manda sobre el snapshot para que lo que se ve en
        # el formulario sea lo que puntúa.
        if self.doble_turno_ids:
            dobles = set(self.doble_turno_ids.mapped('name'))

        valores = {}
        for n in candidatos:
            factores = {nivel: tablas[nivel].get(n, (0.0, 0))
                        for nivel, _lbl in NIVELES}
            if rango_mayoria == 'bajo':
                mayoria = n < 50
            elif rango_mayoria == 'alto':
                mayoria = n >= 50
            else:
                mayoria = False
            # Para la cascada: la mejor de las tres tablas, igual que la
            # predicción se queda con la mejor entre general y turno.
            mejor_f, mejor_d, mejor_lbl = 0.0, 0, None
            for nivel, lbl in NIVELES:
                factor, dist = factores[nivel]
                if factor > mejor_f:
                    mejor_f, mejor_d, mejor_lbl = factor, dist, lbl
            valores[n] = {
                'doble': n in dobles,
                'tabla': mejor_f,
                'tabla_dist': mejor_d,
                'tabla_origen': mejor_lbl,
                'factores': factores,
                'grupos': gr_pts.get(n, 0.0),
                'pintas': pi_pts.get(n, 0.0),
                'comb': comb[n],
                'cruce': bool(ref_cruce is not None
                              and _hit_cruce(ref_cruce, n)),
                'mayoria': mayoria,
                'azar': random.random(),
            }

        ctx = {
            'refs': refs,
            'ref_cruce': ref_cruce,
            'rango_mayoria': rango_mayoria,
            'window_used': len(base['outputs']),
            'window_asked': self.combinaciones_window,
            'dia': day,
            'detalles': [
                ('Grupos atrasados (general + tarde + noche)', gr_det),
                ('Pintas atrasadas (general + tarde + noche)', pi_det),
                ('Grupos atrasados generales (recorte 10 → 5)', gr_gen_det),
            ],
        }
        senales = {
            # 20 → 15: la tabla general, contra la última salida.
            'tabla_general': {n: valores[n]['factores']['general'][0]
                              for n in candidatos},
            # 15 → 10: en cuántas de las dos tablas de turno aparece.
            'tablas_turnos': {
                n: sum(1 for nivel in ('evening', 'afternoon')
                       if valores[n]['factores'][nivel][0])
                for n in candidatos},
            # 10 → 5: los grupos atrasados generales.
            'grupos_general': {n: gr_gen_pts.get(n, 0.0) for n in candidatos},
            # 5 → Súper Mágico: en cuántos niveles de turno cae.
            'grupos_turnos': {
                n: sum(1 for nivel in ('afternoon', 'evening')
                       if n in gr_turno[nivel])
                for n in candidatos},
        }
        return valores, senales, ctx

    # ── Orden y selección ───────────────────────────────────────────────

    def _clave(self, valores, n):
        """Orden de los 20: primero estar en las dos tablas de temperatura y
        después la cascada de la predicción, tal cual (tabla → grupos →
        pintas → combinaciones → cruce → mayoría → azar)."""
        Pred = self.env['lottery.prediction']
        return (valores[n]['doble'],) + Pred._clave_cascada(valores, n)

    def _seleccionar_veinte(self, candidatos, valores):
        """Los hasta 20, caminando el historial DÍA POR DÍA de la fecha hacia
        atrás: en cada paso entran los candidatos que comparten decena o
        unidad con alguna de las dos salidas de ese día y todavía no habían
        entrado por un día más reciente.

        Cuando un día trae más candidatos de los que faltan, se cortan con
        `_clave`. Si el historial se agota antes de llegar a 20, el resto se
        completa con los que quedaron afuera, también por `_clave`.

        Devuelve (orden_final, origen), con `origen` = {número: fecha del día
        que lo trajo} o None si entró por la cascada."""
        self.ensure_one()
        objetivo = min(20, len(candidatos))

        def clave(n):
            return self._clave(valores, n)

        seleccionados, vistos, origen = [], set(), {}
        for fecha, salidas in self._salidas_por_dia():
            if len(seleccionados) >= objetivo:
                break
            refs = [o.number_id.name for o in salidas]
            nuevos = sorted(
                (n for n in candidatos
                 if n not in vistos
                 and any(_comparte_digito(n, r) for r in refs)),
                key=clave, reverse=True)
            if not nuevos:
                continue
            elegidos = nuevos[:objetivo - len(seleccionados)]
            for n in elegidos:
                origen[n] = (fecha, refs)
            seleccionados.extend(elegidos)
            vistos.update(elegidos)

        if len(seleccionados) < objetivo:
            resto = sorted((n for n in candidatos if n not in vistos),
                           key=clave, reverse=True)
            seleccionados.extend(resto[:objetivo - len(seleccionados)])

        return sorted(seleccionados, key=clave, reverse=True), origen

    def action_calcular(self):
        """Arma las cuatro listas y el Súper Mágico.

        Los 20 salen de la caminata por días; los 15, 10 y 5 son recortes
        sucesivos (15 ⊂ 20, 10 ⊂ 15, 5 ⊂ 10, Súper Mágico = el 1º de los 5) y
        cada recorte tiene su propia señal, que manda antes que la cascada:

          20 → 15  tabla LotoAnálisis general
          15 → 10  en cuántas tablas de turno (tarde/noche) aparece
          10 →  5  grupos atrasados generales
           5 → SM  en cuántos niveles de grupos de turno aparece

        Los atrasos de grupos y pintas son los de HOY, no los de la fecha del
        registro: está pensado para correrlo antes del sorteo. Las cuatro
        listas quedan editables; el botón sólo las precarga."""
        self.ensure_one()
        if len(self.number_ids) < 5:
            raise UserError(
                'Cargá primero los candidatos (elegí la temperatura o tocá '
                '"Cargar candidatos"): hacen falta al menos 5 para armar las '
                'listas.')

        candidatos = sorted(self.number_ids.mapped('name'))
        valores, senales, ctx = self._valores_cascada(candidatos)
        veinte, origen = self._seleccionar_veinte(candidatos, valores)

        def por_senal(senal):
            """Primero la señal del recorte; la cascada desempata dentro de
            cada nivel de esa señal."""
            return lambda n: ((senal.get(n, 0),) + self._clave(valores, n))

        orden_15 = sorted(
            veinte, key=por_senal(senales['tabla_general']), reverse=True)[:15]
        orden_10 = sorted(
            orden_15, key=por_senal(senales['tablas_turnos']),
            reverse=True)[:10]
        orden_5 = sorted(
            orden_10, key=por_senal(senales['grupos_general']),
            reverse=True)[:5]
        orden_5 = sorted(
            orden_5, key=por_senal(senales['grupos_turnos']), reverse=True)
        super_magico = orden_5[0] if orden_5 else False

        Number = self.env['lottery.number']

        def ids(numeros):
            return Number.search([('name', 'in', numeros)]).ids

        listas = {20: veinte, 15: orden_15, 10: orden_10, 5: orden_5}
        vals = {
            'number_ids_20': [(6, 0, ids(listas[20]))],
            'number_ids_15': [(6, 0, ids(listas[15]))],
            'number_ids_10': [(6, 0, ids(listas[10]))],
            'number_ids_5': [(6, 0, ids(listas[5]))],
            'super_magico_id': ids([super_magico])[0] if super_magico else False,
            'score_html': self._render_scores_html(
                candidatos, valores, senales, ctx, listas, origen,
                super_magico),
        }
        self.write(vals)
        return True

    # ── Desglose ────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_pts(valor):
        return ('%.1f' % valor).rstrip('0').rstrip('.') or '0'

    def _render_scores_html(self, candidatos, valores, senales, ctx, listas,
                            origen, super_magico=False):
        """Tabla de auditoría: qué señal sacó cada candidato y en qué lista
        quedó. `origen` es {número: (fecha, [números de ese día])} para los
        que entraron por la caminata, y `super_magico` es el de ESTA corrida
        (el campo todavía no está escrito cuando se arma el desglose)."""
        self.ensure_one()
        fmt = self._fmt_pts
        turn_lbl = {'afternoon': 'Tarde', 'evening': 'Noche'}

        def salida(rec):
            if not rec:
                return '<span class="text-muted">sin salidas previas</span>'
            return '<b>%02d</b> (%s %s)' % (
                rec.number_id.name, rec.date.strftime('%d/%m/%Y'),
                turn_lbl.get(rec.turn_day, rec.turn_day))

        def celda_num(valor):
            if not valor:
                return '<td class="text-center text-muted">·</td>'
            return '<td class="text-center">%s</td>' % fmt(valor)

        def celda_factor(par):
            factor, dist = par
            if not factor:
                return '<td class="text-center text-muted">·</td>'
            return ('<td class="text-center">%s <span class="text-muted" '
                    'style="font-size:10px;">(d%d)</span></td>'
                    % (fmt(factor), dist))

        def celda_bool(valor):
            return ('<td class="text-center">%s</td>'
                    % ('✓' if valor else '<span class="text-muted">·</span>'))

        def celda_origen(n):
            o = origen.get(n)
            if o is None:
                return ('<td class="text-center text-muted" '
                        'style="font-size:11px;">cascada</td>')
            fecha, refs = o
            return ('<td class="text-center" style="font-size:11px;">%s '
                    '<span class="text-muted">(%s)</span></td>'
                    % (fecha.strftime('%d/%m'),
                       ' · '.join('%02d' % r for r in refs)))

        en_5, en_10 = set(listas[5]), set(listas[10])
        en_15, en_20 = set(listas[15]), set(listas[20])
        fuera = sorted((n for n in candidatos if n not in en_20),
                       key=lambda n: self._clave(valores, n), reverse=True)

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', '2 turnos', 'Entró por', 'Tabla gral.',
                      'Tabla noche', 'Tabla tarde', 'Grupos gral.',
                      'Grupos turno', 'Grupos', 'Pintas', 'Comb.', 'Cruce',
                      'Mayoría'))

        def fila_html(i, n, mostrar_origen):
            v = valores[n]
            if n in en_5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif n in en_10:
                fondo, corte = '#fff1e0', ' · 10'
            elif n in en_15:
                fondo, corte = '#e8f5e9', ' · 15'
            elif n in en_20:
                fondo, corte = '#f1f3f5', ' · 20'
            else:
                fondo, corte = '', ''
            marca_sm = ' ★' if super_magico == n else ''
            origen_html = (celda_origen(n) if mostrar_origen else
                           '<td class="text-center text-muted">—</td>')
            return (
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td>'
                '<td class="text-center"><b>%02d</b>%s</td>'
                '%s%s%s%s%s%s'
                '<td class="text-center">%s</td>'
                '%s%s'
                '<td class="text-center">%d</td>'
                '%s%s</tr>' % (
                    fondo, i, corte, n, marca_sm,
                    celda_bool(v['doble']), origen_html,
                    celda_factor(v['factores']['general']),
                    celda_factor(v['factores']['evening']),
                    celda_factor(v['factores']['afternoon']),
                    celda_num(senales['grupos_general'].get(n, 0)),
                    ('<b>%d</b>' % senales['grupos_turnos'][n]
                     if senales['grupos_turnos'].get(n)
                     else '<span class="text-muted">·</span>'),
                    celda_num(v['grupos']), celda_num(v['pintas']),
                    v['comb'],
                    celda_bool(v['cruce']), celda_bool(v['mayoria'])))

        cuerpo = [fila_html(i + 1, n, True) for i, n in enumerate(listas[20])]
        if fuera:
            cuerpo.append(
                '<tr><td colspan="14" class="text-center text-muted small">'
                '— fuera de los 20: no compartieron dígito con el historial '
                'reciente —</td></tr>')
            cuerpo += [fila_html(i + 1, n, False)
                       for i, n in enumerate(fuera, len(listas[20]))]

        def detalle(titulo, det):
            if not det:
                return ('<p class="small text-muted mb-1">%s: sin datos</p>'
                        % titulo)
            items = ' · '.join(
                '%s <span class="text-muted">(%d atrasos, %s)</span>'
                % (d['name'], d['atraso'], d['origen']) for d in det)
            return ('<p class="small mb-1"><span class="text-muted">%s:</span> '
                    '%s</p>' % (titulo, items))

        aviso = ''
        if len(candidatos) < 20:
            aviso = ('<div class="alert alert-warning py-2 small">Sólo hay %d '
                     'candidatos: las listas se llenaron con los que '
                     'había.</div>' % len(candidatos))

        mayoria_txt = {
            'bajo': 'conviene &lt;50 (salieron más ≥50)',
            'alto': 'conviene ≥50 (salieron más &lt;50)',
        }.get(ctx['rango_mayoria'], 'sin mayoría clara')

        return (
            '%s'
            '<div class="small mb-2">'
            '<p class="mb-1"><span class="text-muted">Referencias de las '
            'tablas:</span> general → %s · noche → %s · tarde → %s</p>'
            '<p class="mb-1"><span class="text-muted">Cruce línea/terminal '
            'contra:</span> %s · <span class="text-muted">Mayoría últimos %d:'
            '</span> %s</p>'
            '<p class="mb-1"><span class="text-muted">Combinaciones:</span> '
            'ventana de %d salidas (pedidas %d) · '
            '<span class="text-muted">En las dos tablas de temperatura:</span> '
            '%d de %d candidatos</p>'
            '%s%s%s'
            '<p class="mb-1 text-muted">Recortes: 20 → 15 por tabla general · '
            '15 → 10 por tablas de turno · 10 → 5 por grupos generales · '
            '5 → Súper Mágico (★) por grupos de turno.</p>'
            '</div>'
            '<table class="table table-sm table-bordered" '
            'style="font-size:12px;"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table>' % (
                aviso,
                salida(ctx['refs']['general']),
                salida(ctx['refs']['evening']),
                salida(ctx['refs']['afternoon']),
                ('<b>%02d</b>' % ctx['ref_cruce']
                 if ctx['ref_cruce'] is not None else '—'),
                VENTANA_MAYORIA, mayoria_txt,
                ctx['window_used'], ctx['window_asked'],
                sum(1 for n in candidatos if valores[n]['doble']),
                len(candidatos),
                detalle(*ctx['detalles'][0]),
                detalle(*ctx['detalles'][1]),
                detalle(*ctx['detalles'][2]),
                cabeza, ''.join(cuerpo)))
