# -*- coding: utf-8 -*-
"""Tómbola de la Quiniela Uruguay: 10 combinaciones de 3 armadas con los 20
premios evaluados de una sola vez.

Es un agrupador de `lottery.prediction`. La quiniela uruguaya tiene 20
premios y cada uno es su propio `lottery.sorteo` (`quiniela_uy_1` …
`quiniela_uy_20`). Acá se corre para los 20 la MISMA lógica que el botón
"Completar números" de la predicción individual, y de cada premio se toman
sus 5 Números a predecir con su Súper Mágico: 20 grupos de 5.

El algoritmo (1 o 2) no se elige: cada premio usa el que le tocaría en las
predicciones automáticas (`_algoritmo_por_ultimas_salidas`: el 1 si sus dos
últimas salidas comparten algún dígito, el 2 si no).

Con esos 100 números (muchos repetidos entre premios) se puntúa cada
candidato distinto con cinco señales:

  - Repetición: en cuántos de los 20 grupos está. Manda.
  - A. Últimas tómbolas: en cuántas de las últimas 3 tómbolas salió, igual
    o al revés (21 cuenta si salió el 21 o el 12). Las tómbolas van en
    orden, sin importar el turno. También manda.
  - B. Dígitos: cuántos premios tuvieron una última salida que comparte
    decena o unidad con él (estilo Algoritmo 2: si el premio 3 salió 45,
    suman los candidatos con un 4 o un 5). No cuentan los premios donde el
    número es candidato.
  - C. Mes y atraso en la tómbola: los que menos salieron en lo que va del
    mes y los más atrasados. Peso bajo.
  - D. Líneas y terminales más atrasadas de la tómbola. Peso bajo.

Las 10 combinaciones no son al azar: se recorren las ternas de candidatos
de mayor a menor puntaje (la suma de los tres) y se toman con dos topes. Un
número entra como mucho en 3 combinaciones, para que si el más fuerte no
sale todavía queden otras que no dependen de él. Y dos combinaciones
comparten como mucho un número, para que no salgan casi iguales. Así los
principales quedan repartidos, cada uno con distintos compañeros.
"""

import itertools
import json

from odoo import api, fields, models
from odoo.exceptions import UserError

from .quiniela_uy_ui import (
    COLOR_TOMBOLA, DORADO, FUENTE, TEXTO, TEXTO_SUAVE, turno_color,
    turno_label, badge, bola, cabezal, tarjeta,
)

SOURCE_CODE = 'quiniela_uy'
TOTAL_PREMIOS = 20
TOP_POR_PREMIO = 5

COMBINACIONES = 10
NUMEROS_POR_COMBINACION = 3
# Combinaciones por columna en la tarjeta: 10 en dos columnas de 5.
COMBINACIONES_POR_COLUMNA = 5
# Topes del armado: en cuántas combinaciones puede estar un mismo número, y
# cuántos números pueden compartir dos combinaciones.
MAX_COMBOS_POR_NUMERO = 3
MAX_COMPARTIDOS = 1

# Cuántas salidas hacia atrás de cada premio se guardan al evaluar. Para la
# señal B se usa solo la última; las demás quedan para el algoritmo.
ULTIMAS_SALIDAS = 6
# Señal A: cuántas tómbolas hacia atrás se miran (en orden, sin turnos).
TOMBOLAS_ATRAS = 3
# Señal D: cuántas líneas y cuántos terminales atrasados cuentan.
LINEAS_ATRASADAS = 3

# Pesos. La repetición vale 1 por grupo (de 1 a 20) y la señal A 1 por
# tómbola (hasta 3): son las que mandan. B, C y D ordenan números parejos.
PESO_REPETICION = 1.0
PESO_TOMBOLA = 1.0
PESO_DIGITO = 0.25
TOPE_DIGITOS = 2.0
PESO_MES = 0.5
PESO_ATRASO = 0.5
PESO_LINEA = 0.25
PESO_TERMINAL = 0.25

# Bola del Súper Mágico en la tarjeta de los 5 de cada premio: dorada y con
# aro, para encontrarla de un vistazo entre las otras cuatro (que van con el
# color del turno).
COLOR_SUPER_MAGICO = (0xF5, 0xB0, 0x0B)

TOMBOLA_STATS_START_PARAM = 'lottery_portal.tombola_stats_start_date'


def _reves(numero):
    """21 → 12, 7 → 70. Un capicúa queda igual."""
    decena, unidad = divmod(numero, 10)
    return unidad * 10 + decena


def _comparte_digito(numero, salida):
    """True si `numero` tiene algún dígito de `salida`, en cualquier
    posición (45 → los que tienen un 4 o un 5)."""
    return bool(set(divmod(numero, 10)) & set(divmod(salida, 10)))


class LotteryPredictionTombolaUy(models.Model):
    _name = 'lottery.prediction.tombola.uy'
    _description = 'Tómbola Quiniela Uruguay'
    _order = 'date desc, turno_sequence desc, id desc'

    date = fields.Date(
        string='Fecha', required=True, index=True,
        default=lambda self: self._default_date(),
        help='Fecha del sorteo que se predice. El cálculo nunca mira ese '
             'sorteo ni ninguno posterior, así que volver a correr una '
             'tómbola vieja da lo mismo que el día que se generó.')
    turno_id = fields.Many2one(
        'lottery.turno', string='Turno', required=True, index=True,
        domain="[('sorteo_ids.source_code', '=', '%s')]" % SOURCE_CODE,
        default=lambda self: self._default_turn())
    turno_code = fields.Char(related='turno_id.code', string='Código del turno')
    turno_sequence = fields.Integer(related='turno_id.sequence', store=True, index=True,
                                    string='Secuencia del turno')
    temperature = fields.Selection([
        ('hot', 'Calientes'),
        ('remaining', 'Restantes'),
        ('cold', 'Fríos'),
        ('all', 'Todos (100)'),
    ], string='Candidatos', required=True, default='remaining',
        help='De dónde salen los números que se puntean en cada premio, '
             'igual que el campo Temperatura de la predicción individual. '
             '"Todos" saltea el ranking y evalúa los 100 números.')
    combinaciones_window = fields.Integer(
        string='Ventana de combinaciones', default=50, required=True,
        help='Cuántas salidas hacia atrás mira el puntaje de combinaciones '
             'de cada premio. Tope 200.')
    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='Marca manual: estas combinaciones ya salieron publicadas. '
             'Todavía no las consume la app.')

    top_json = fields.Text(
        string='Top por premio (JSON)', readonly=True, copy=False,
        help='Los 5 mejores de cada premio, su algoritmo y las últimas '
             'salidas que se usaron. Se guarda para poder volver a armar '
             'las combinaciones sin recalcular los 20 sorteos.')
    groups_html = fields.Html(
        string='Los 5 de cada premio', readonly=True, sanitize=False,
        copy=False)
    combos_html = fields.Html(
        string='Combinaciones Tómbola', readonly=True, sanitize=False,
        copy=False)

    _sql_constraints = [
        ('unique_date_turn',
         'unique(date, turno_id)',
         'Ya existe una tómbola para esa fecha y turno.'),
    ]

    # ── Defaults: la última quiniela que haya entrado ─────────────────────

    @api.model
    def _last_quiniela_output(self):
        return self.env['lottery.output'].sudo().search(
            [('sorteo_id.source_code', '=', SOURCE_CODE)],
            order='date desc, turno_sequence desc, id desc', limit=1)

    @api.model
    def _default_date(self):
        last = self._last_quiniela_output()
        return last.date if last else fields.Date.context_today(self)

    @api.model
    def _default_turn(self):
        last = self._last_quiniela_output()
        return last.turno_id.id if last else False

    @api.depends('date', 'turno_id')
    def _compute_display_name(self):
        for rec in self:
            fecha = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            rec.display_name = 'Tómbola %s / %s' % (
                fecha, turno_label(rec.turno_code))

    @api.onchange('date', 'turno_id', 'temperature', 'combinaciones_window')
    def _onchange_parametros(self):
        """Si se cambia un parámetro, lo calculado ya no corresponde: se
        limpia. Si no, quedaría en pantalla una tarjeta con la fecha vieja en
        el cabezal lista para publicar por error."""
        self.top_json = False
        self.groups_html = False
        self.combos_html = False

    # ── Los 20 premios ────────────────────────────────────────────────────

    def _sorteos(self):
        """[(premio, sorteo), …] ordenado por número de premio.

        El número sale del sufijo del código (`quiniela_uy_7` → 7), igual que
        en el informe de resultados: es más robusto que el `sequence`, que es
        un dato de presentación y se puede reordenar desde la interfaz."""
        pares = []
        for sorteo in self.env['lottery.sorteo'].sudo().search(
                [('source_code', '=', SOURCE_CODE)]):
            try:
                pares.append((int(sorteo.code.rsplit('_', 1)[-1]), sorteo))
            except (ValueError, AttributeError):
                continue
        return sorted(pares, key=lambda par: par[0])

    def _candidatos(self, sorteo):
        """Números a puntear en ese premio, según el campo Candidatos."""
        self.ensure_one()
        if self.temperature == 'all':
            return self.env['lottery.number'].search([])
        return self.env['lottery.prediction'].numbers_by_temperature(
            sorteo, self.turno_code, self.temperature)

    def _prediccion(self, sorteo, candidatos):
        """Una `lottery.prediction` en memoria (`new`) para ese premio, con
        el algoritmo que le toca según sus últimas salidas.

        No se graba nada: sólo se usa para llamar a `_calcular_listas`, que
        es la lógica del botón "Completar números". Así la tómbola y la
        predicción individual puntean exactamente igual, y no quedan 20
        predicciones basura en la base ni choca la constraint de fecha +
        turno + sorteo."""
        self.ensure_one()
        pred = self.env['lottery.prediction'].new({
            'sorteo_id': sorteo.id,
            'date': self.date,
            'turno_id': self.turno_id.id,
            'combinaciones_window': self.combinaciones_window,
            'number_ids': [(6, 0, candidatos.ids)],
        })
        pred.algoritmo = pred._algoritmo_por_ultimas_salidas()
        return pred

    # ── Acción 1: evaluar los 20 sorteos ──────────────────────────────────

    def action_evaluar(self):
        """Corre "Completar números" en los 20 premios, cada uno con su
        algoritmo, y se queda con los 5 Números a predecir y el Súper
        Mágico de cada uno.

        Es la parte cara: cada premio corre el mismo cálculo que la
        predicción individual, y la primera vez arma además las tablas
        LotoAnálisis que le falten (quedan cacheadas, así que la segunda
        corrida es mucho más rápida)."""
        self.ensure_one()
        grupos, sin_datos = [], []
        for premio, sorteo in self._sorteos():
            candidatos = self._candidatos(sorteo)
            if len(candidatos) < TOP_POR_PREMIO:
                sin_datos.append(premio)
                continue
            pred = self._prediccion(sorteo, candidatos)
            res = pred._calcular_listas()
            grupos.append({
                'premio': premio,
                'algoritmo': pred.algoritmo,
                # Los 5 vienen con el Súper Mágico primero.
                'top': res['listas'][5][:TOP_POR_PREMIO],
                'super_magico': res['super_magico'],
                'salidas': pred._last_output(
                    limit=ULTIMAS_SALIDAS).mapped('number_id.name'),
            })

        if not grupos:
            raise UserError(
                'Ningún premio quedó con al menos %d candidatos para la %s '
                '(Candidatos: %s). Generá primero los artículos del ranking '
                'o elegí Candidatos = Todos (100).' % (
                    TOP_POR_PREMIO,
                    turno_label(self.turno_code),
                    dict(self._fields['temperature'].selection)[
                        self.temperature]))

        self.write({
            'top_json': json.dumps(grupos),
            'groups_html': self._render_grupos(grupos, sin_datos),
            'combos_html': False,
        })
        return True

    def _grupos(self):
        """Los grupos guardados por la última evaluación."""
        self.ensure_one()
        try:
            return json.loads(self.top_json or '[]')
        except (ValueError, TypeError):
            return []

    # ── Acción 2: armar las combinaciones ─────────────────────────────────

    def action_generar_combinaciones(self):
        """10 combinaciones de 3, fijas: la misma evaluación da siempre las
        mismas. Ver el docstring del módulo."""
        self.ensure_one()
        grupos = self._grupos()
        if not grupos:
            self.action_evaluar()
            grupos = self._grupos()

        info = self._puntajes(grupos)
        combos = self._combinaciones(
            {n: datos['puntaje'] for n, datos in info.items()})
        self.combos_html = self._render_combinaciones(combos, info)
        return True

    # ── La tómbola hasta el sorteo que se predice ─────────────────────────

    def _tombola_previa(self):
        """(sorteos, salidas): la tómbola ANTERIOR al sorteo que se predice,
        desde la fecha de inicio de estadísticas de Ajustes.

        `sorteos` es [(fecha, secuencia del turno), …] de más viejo a más
        nuevo y `salidas` es {(fecha, secuencia): {números}}. Se lee una vez y
        de acá salen las señales A, C y D."""
        self.ensure_one()
        inicio = self.env['ir.config_parameter'].sudo().get_param(
            TOMBOLA_STATS_START_PARAM) or '1900-01-01'
        self.env.cr.execute("""
            SELECT o.date, o.turno_sequence, ln.name::int AS numero
            FROM lottery_tombola_output o
            JOIN lottery_number ln ON ln.id = o.number_id
            WHERE o.date >= %(inicio)s
              AND (o.date < %(fecha)s
                   OR (o.date = %(fecha)s AND o.turno_sequence < %(seq)s))
        """, {'inicio': inicio, 'fecha': self.date,
              'seq': self.turno_id.sequence})
        salidas = {}
        for fecha, seq, numero in self.env.cr.fetchall():
            salidas.setdefault((fecha, seq), set()).add(numero)
        return sorted(salidas), salidas

    @staticmethod
    def _atrasos(sorteos, salidas, clave):
        """{valor: sorteos de tómbola sin salir} para cada valor de
        `clave(número)` (el número mismo, su línea o su terminal). El que
        nunca salió cuenta todos los sorteos."""
        ultimo = {}
        for i, sorteo in enumerate(sorteos):
            for numero in salidas[sorteo]:
                ultimo[clave(numero)] = i
        total = len(sorteos)
        return lambda valor: total - 1 - ultimo[valor] if valor in ultimo else total

    # ── Puntaje de cada candidato ─────────────────────────────────────────

    def _puntajes(self, grupos):
        """{número: detalle} de cada candidato distinto de los 20 grupos,
        con el puntaje total y lo que suma cada señal."""
        self.ensure_one()
        sorteos, salidas = self._tombola_previa()

        info = {}
        for grupo in grupos:
            for numero in grupo.get('top') or []:
                datos = info.setdefault(numero, {'premios': set()})
                datos['premios'].add(grupo['premio'])

        # A. Últimas tómbolas, igual o al revés.
        recientes = [salidas[s] for s in sorteos[-TOMBOLAS_ATRAS:]]
        # B. Última salida de cada premio.
        ultimas = {g['premio']: g['salidas'][0]
                   for g in grupos if g.get('salidas')}
        # C. Salidas del mes en la tómbola y atraso de cada número.
        mes = {}
        for fecha, seq in sorteos:
            if (fecha.year, fecha.month) == (self.date.year, self.date.month):
                for numero in salidas[(fecha, seq)]:
                    mes[numero] = mes.get(numero, 0) + 1
        atraso = self._atrasos(sorteos, salidas, lambda n: n)
        # D. Líneas y terminales más atrasadas de la tómbola.
        atraso_linea = self._atrasos(sorteos, salidas, lambda n: n // 10)
        atraso_term = self._atrasos(sorteos, salidas, lambda n: n % 10)
        lineas = set(sorted(range(10), key=lambda d: -atraso_linea(d))[:LINEAS_ATRASADAS])
        terminales = set(sorted(range(10), key=lambda d: -atraso_term(d))[:LINEAS_ATRASADAS])

        for numero, datos in info.items():
            datos['veces'] = len(datos['premios'])
            datos['tombolas'] = sum(
                1 for s in recientes if numero in s or _reves(numero) in s)
            datos['digitos'] = sum(
                1 for premio, salida in ultimas.items()
                if premio not in datos['premios']
                and _comparte_digito(numero, salida))
            datos['mes'] = mes.get(numero, 0)
            datos['atraso'] = atraso(numero)
            datos['linea'] = numero // 10 in lineas
            datos['terminal'] = numero % 10 in terminales

        # C se mide entre los candidatos: el que menos salió en el mes y el
        # más atrasado se llevan el peso entero, el otro extremo nada.
        def _escala(valor, valores, al_reves=False):
            bajo, alto = min(valores), max(valores)
            if alto == bajo:
                return 0.0
            t = (valor - bajo) / (alto - bajo)
            return 1 - t if al_reves else t

        meses = [d['mes'] for d in info.values()]
        atrasos = [d['atraso'] for d in info.values()]
        for numero, datos in info.items():
            partes = {
                'repeticion': PESO_REPETICION * datos['veces'],
                'tombola': PESO_TOMBOLA * datos['tombolas'],
                'digitos': min(PESO_DIGITO * datos['digitos'], TOPE_DIGITOS),
                'mes': PESO_MES * _escala(datos['mes'], meses, al_reves=True),
                'atraso': PESO_ATRASO * _escala(datos['atraso'], atrasos),
                'linea_terminal': (PESO_LINEA * datos['linea']
                                   + PESO_TERMINAL * datos['terminal']),
            }
            datos['partes'] = {k: round(v, 2) for k, v in partes.items()}
            datos['puntaje'] = round(sum(partes.values()), 2)
            datos['premios'] = sorted(datos['premios'])
        return info

    # ── Armado de las combinaciones ───────────────────────────────────────

    @staticmethod
    def _combinaciones(puntajes):
        """`COMBINACIONES` ternas de mayor a menor puntaje, con los topes
        `MAX_COMBOS_POR_NUMERO` y `MAX_COMPARTIDOS`. Cada terna va ordenada
        de menor a mayor; las ternas, en el orden en que se eligieron (la
        primera es la más fuerte)."""
        if len(puntajes) < NUMEROS_POR_COMBINACION:
            raise UserError(
                'Hay %d números distintos entre los 20 grupos: no alcanzan '
                'para armar combinaciones de %d.' % (
                    len(puntajes), NUMEROS_POR_COMBINACION))
        # A igual puntaje, el número más chico primero: así la misma
        # evaluación da siempre las mismas combinaciones.
        orden = sorted(puntajes, key=lambda n: (-puntajes[n], n))
        puesto = {n: i for i, n in enumerate(orden)}
        ternas = sorted(
            itertools.combinations(orden, NUMEROS_POR_COMBINACION),
            key=lambda t: (-sum(puntajes[n] for n in t),
                           [puesto[n] for n in t]))

        elegidas, usos = [], {}
        for terna in ternas:
            if any(usos.get(n, 0) >= MAX_COMBOS_POR_NUMERO for n in terna):
                continue
            if any(len(set(terna) & set(otra)) > MAX_COMPARTIDOS
                   for otra in elegidas):
                continue
            elegidas.append(terna)
            for n in terna:
                usos[n] = usos.get(n, 0) + 1
            if len(elegidas) == COMBINACIONES:
                break
        if len(elegidas) < COMBINACIONES:
            raise UserError(
                'Con %d números distintos sólo se pudieron armar %d '
                'combinaciones respetando los topes. Probá con Candidatos = '
                'Todos (100).' % (len(puntajes), len(elegidas)))
        return [tuple(sorted(t)) for t in elegidas]

    # ── Render ────────────────────────────────────────────────────────────

    def _pie(self, texto):
        return (
            '<div style="margin:2px 14px 0;padding:8px 10px;'
            'border-radius:9px;background:#FFFFFF;border:1px solid #C6E4CF;'
            'font:600 11px/1.45 %s;color:%s;text-align:center;">%s</div>'
            % (FUENTE, TEXTO_SUAVE, texto)
        )

    @staticmethod
    def _bola_grupo(numero, grupo, color):
        """Bola de un número en la tarjeta de los 5 de cada premio: la del
        Súper Mágico va dorada y con un aro; las otras, del color del
        turno. Grupos evaluados antes de que existiera el Súper Mágico no
        lo traen y se dibujan todas iguales."""
        if numero != grupo.get('super_magico'):
            return bola('%02d' % numero, color, diam=34)
        return ('<div style="border-radius:50%%;'
                'box-shadow:0 0 0 2px #FFFFFF,0 0 0 4px %s;">%s</div>'
                % (DORADO, bola('%02d' % numero, COLOR_SUPER_MAGICO, diam=34)))

    @staticmethod
    def _etiqueta_algoritmo(grupo):
        """Cápsula 'A1' / 'A2' con el algoritmo que usó el premio. Las
        tómbolas evaluadas antes de que cada premio eligiera el suyo no lo
        traen."""
        algoritmo = grupo.get('algoritmo')
        if not algoritmo:
            return ''
        return ('<span style="padding:3px 7px;border-radius:50px;'
                'background:#FFFFFF;border:1px solid #C6E4CF;'
                'font:800 10px/1 %s;color:%s;">A%s</span>'
                % (FUENTE, TEXTO_SUAVE, algoritmo))

    def _render_grupos(self, grupos, sin_datos):
        """Tarjeta con los 5 mejores de cada premio y su algoritmo, en dos
        columnas de 10."""
        self.ensure_one()
        color = turno_color(self.turno_code)
        por_premio = {g['premio']: g for g in grupos}

        filas = []
        for i in range(1, TOTAL_PREMIOS // 2 + 1):
            celdas = []
            for premio in (i, i + TOTAL_PREMIOS // 2):
                grupo = por_premio.get(premio)
                if grupo:
                    # Se muestran de menor a mayor (el Súper Mágico ya se
                    # distingue por el color).
                    bolas = ''.join(self._bola_grupo(n, grupo, color)
                                    for n in sorted(grupo['top']))
                    algoritmo = self._etiqueta_algoritmo(grupo)
                else:
                    bolas = ('<span style="font:600 11px/1 %s;color:%s;">'
                             'sin datos</span>' % (FUENTE, TEXTO_SUAVE))
                    algoritmo = ''
                celdas.append(
                    '<td style="padding:6px 5px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s<div style="display:flex;gap:7px;">%s</div>%s</div>'
                    '</td>' % (badge(premio, lado=24), bolas, algoritmo))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        pie = self._pie(
            'Los 5 de cada premio · <b>dorada: Súper Mágico</b> · '
            'A1 / A2: algoritmo de cada premio · Candidatos: %s · '
            'ventana de combinaciones: %d' % (
                dict(self._fields['temperature'].selection)[self.temperature],
                self.combinaciones_window))
        if sin_datos:
            pie += (
                '<div style="margin:8px 14px 0;padding:8px 10px;'
                'border-radius:9px;background:#FFF7E3;'
                'border:1px solid #F5E3B3;font:600 11px/1.45 %s;'
                'color:#8A6416;text-align:center;">'
                'Sin candidatos suficientes en los premios %s: quedaron '
                'afuera.</div>'
                % (FUENTE, ', '.join(str(p) for p in sin_datos)))

        cuerpo = (
            '<div style="padding:12px 8px 12px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>' % (''.join(filas), pie))
        return tarjeta(
            cabezal(self.turno_code, self.date,
                    titulo='Tómbola · los 5 de cada premio'),
            cuerpo, ancho=580)

    def _render_combinaciones(self, combos, info):
        """Tarjeta publicable con las 10 combinaciones de 3, y debajo el
        detalle de por qué entró cada número."""
        self.ensure_one()
        filas = []
        for i in range(COMBINACIONES_POR_COLUMNA):
            celdas = []
            for j in (i, i + COMBINACIONES_POR_COLUMNA):
                bolas = ''.join(bola('%02d' % n, COLOR_TOMBOLA, diam=44)
                                for n in combos[j])
                celdas.append(
                    '<td style="padding:6px 10px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s<div style="display:flex;gap:8px;">%s</div></div>'
                    '</td>' % (badge(j + 1, lado=24), bolas))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        jugados = sorted({n for combo in combos for n in combo},
                         key=lambda n: (-info[n]['puntaje'], n))
        usos = {n: sum(1 for c in combos if n in c) for n in jugados}
        detalle = ''.join(self._fila_detalle(n, info[n], usos[n])
                          for n in jugados)

        cuerpo = (
            '<div style="padding:12px 8px 12px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>'
            '<div style="margin:12px 14px 0;">'
            '<table style="width:100%%;border-collapse:collapse;'
            'font:600 11px/1.3 %s;color:%s;">'
            '<thead><tr style="font-weight:800;color:%s;">'
            '<td style="padding:4px;">Nº</td>'
            '<td style="padding:4px;">Puntaje</td>'
            '<td style="padding:4px;">Premios</td>'
            '<td style="padding:4px;">Tómbolas</td>'
            '<td style="padding:4px;">Dígitos</td>'
            '<td style="padding:4px;">Mes · atraso</td>'
            '<td style="padding:4px;">Línea / terminal</td>'
            '<td style="padding:4px;">Combinaciones</td>'
            '</tr></thead><tbody>%s</tbody></table></div>%s</div>'
            % (''.join(filas), FUENTE, TEXTO_SUAVE, TEXTO, detalle,
               self._pie(
                   'Premios: en cuántos de los 20 grupos está · Tómbolas: '
                   'en cuántas de las últimas %d salió, igual o al revés · '
                   'Dígitos: cuántos premios tuvieron una última salida con '
                   'un dígito suyo · Mes y atraso: en la tómbola · Línea / '
                   'terminal: entre las %d más atrasadas de la tómbola. Un '
                   'número entra como mucho en %d combinaciones.'
                   % (TOMBOLAS_ATRAS, LINEAS_ATRASADAS,
                      MAX_COMBOS_POR_NUMERO))))
        return tarjeta(
            cabezal(self.turno_code, self.date,
                    titulo='Combinaciones Tómbola'),
            cuerpo, ancho=780)

    @staticmethod
    def _fila_detalle(numero, datos, usos):
        """Una fila del detalle: el valor de cada señal y lo que sumó."""
        partes = datos['partes']
        lt = '/'.join(filter(None, (
            'L%d' % (numero // 10) if datos['linea'] else '',
            'T%d' % (numero % 10) if datos['terminal'] else '')))
        celda = '<td style="padding:4px;border-top:1px solid #E4F1E8;">%s</td>'
        return '<tr>%s</tr>' % ''.join(celda % texto for texto in (
            '<b style="color:%s;">%02d</b>' % (TEXTO, numero),
            '<b style="color:%s;">%.2f</b>' % (TEXTO, datos['puntaje']),
            '%d (%s)' % (datos['veces'],
                         ', '.join(str(p) for p in datos['premios'])),
            '%d · +%.2f' % (datos['tombolas'], partes['tombola']),
            '%d · +%.2f' % (datos['digitos'], partes['digitos']),
            '%d en el mes · %d atrás · +%.2f' % (
                datos['mes'], datos['atraso'],
                partes['mes'] + partes['atraso']),
            '%s · +%.2f' % (lt or '—', partes['linea_terminal']),
            str(usos),
        ))
