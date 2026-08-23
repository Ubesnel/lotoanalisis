# -*- coding: utf-8 -*-
"""Tómbola de la Quiniela Uruguay: los 20 premios evaluados de una sola vez.

Es un agrupador de `lottery.prediction`. La quiniela uruguaya tiene 20
premios y cada uno es su propio `lottery.sorteo` (`quiniela_uy_1` …
`quiniela_uy_20`), así que predecirlos a mano serían 20 predicciones
individuales. Acá se corre para los 20 la MISMA lógica que el botón
"Completar números" de la predicción individual — grupos y pintas atrasados,
combinaciones y acompañantes de las tablas LotoAnálisis — y se toman los 5
mejores de cada uno: 20 grupos de 5.

Con esos 100 números (muchos repetidos entre premios) se arman 10
combinaciones de 7 para jugar a la tómbola. El sorteo es al azar pero
ponderado, con dos prioridades:

  1. Cuántas veces se repite el número entre los 20 grupos. Es la señal que
     manda: si el número quedó entre los 5 mejores de ocho premios, es
     porque ocho análisis independientes lo marcaron.
  2. Cuántas de las últimas 6 salidas de SU premio comparten decena o unidad
     con él. Es un empujón secundario: como mucho pesa lo que 1.5
     repeticiones, así que puede dar vuelta a un número con una repetición
     más, nunca a uno con tres.
  3. Si es un "interesante del mes" de su premio: los que llevan años sin
     salir en el mes que se predice, leídos con `atrasos_del_mes` de
     lottery.prediction — la misma lista que la app muestra en Números del
     mes atrasados y que el botón "Completar números" usa para elegir los
     10 y los 5. Es el criterio más flojo de los tres: aporta hasta 0.9,
     menos que una repetición.

De la misma evaluación salen otros dos informes, que no son al azar sino
listas fijas:

  - 5 Números probables a salir en los 5 Primeros Premios: de los 25 números
    que dan los premios 1 a 5, los 5 que más se repiten entre ellos; a
    igualdad de repeticiones va primero el que todavía no salió en el mes.
  - 2 Números probables a salir entre los 20 Premios: se toma la pinta más
    atrasada de cada premio (la general y la del turno que se evalúa, dos
    votos por premio), gana la que más veces aparece y de ahí salen los 2
    números que más se repiten entre los 100.
"""

import json
import math
import random

from odoo import api, fields, models
from odoo.exceptions import UserError

from .lottery_prediction import ANIOS_MES_NUNCA, WEEKDAY_CODES
from .quiniela_uy_ui import (
    COLOR_TOMBOLA, COLOR_TURNO, DORADO, FUENTE, MESES, TEXTO,
    TEXTO_SUAVE, TURN_LABEL,
    badge, bola, cabezal, tarjeta,
)

SOURCE_CODE = 'quiniela_uy'
TOTAL_PREMIOS = 20
TOP_POR_PREMIO = 5

COMBINACIONES = 10
NUMEROS_POR_COMBINACION = 7
# Combinaciones por columna en la tarjeta: 10 en dos columnas de 5.
COMBINACIONES_POR_COLUMNA = 5

# Informe "5 probables en los 5 primeros premios": los premios que entran,
# y cuántos números se sacan de los 25 que dan entre todos.
PREMIOS_PRIMEROS = 5
PROBABLES_PRIMEROS = 5

# Informe "2 probables entre los 20 premios": cuántos números salen de la
# pinta ganadora y cuántas pintas se muestran en el ranking.
PROBABLES_VEINTE = 2
PINTAS_EN_RANKING = 5

# Cuántas salidas hacia atrás de cada premio se miran para el cruce de
# dígitos. Son las 6 anteriores al sorteo que se predice, nunca la propia.
ULTIMAS_SALIDAS = 6

# Peso de cada señal en el sorteo ponderado. La repetición vale 1 por grupo
# (va de 1 a 20) y los dígitos suman el promedio de coincidencias (0 a 6)
# multiplicado por 0.25, o sea hasta 1.5. Elegido así a propósito: un número
# que comparte dígito con las 6 últimas salidas de su premio pesa como hasta
# una repetición y media extra — mueve el orden entre números parejos y no
# alcanza para tapar a uno que aparece en dos grupos más.
PESO_REPETICION = 1.0
PESO_DIGITOS = 0.25
# Tercera señal: ser "interesante del mes" en su premio. Aporta hasta 0.9,
# menos que una repetición y menos que el cruce de dígitos, que es el lugar
# que le toca en la jerarquía.
#
# El atraso del mes en sí (qué números entran y cuánto valen los años) sale
# de lottery.prediction: es el mismo criterio que usa el botón "Completar
# números" para elegir los 10 y los 5, y tiene que haber uno solo.
PESO_MES = 0.9

# Tope de tiradas para juntar 10 combinaciones distintas. Con un puñado de
# decenas de números en el bombo las repetidas son rarísimas; el tope está
# para que un pool chico no deje el botón girando.
INTENTOS_MAX = 2000


def _coincidencias(numero, salidas):
    """Cuántas de esas salidas comparten decena o unidad con el número."""
    decena, unidad = divmod(numero, 10)
    return sum(1 for s in salidas
               if s // 10 == decena or s % 10 == unidad)


class LotteryPredictionTombolaUy(models.Model):
    _name = 'lottery.prediction.tombola.uy'
    _description = 'Tómbola Quiniela Uruguay'
    _order = 'date desc, turn_day desc, id desc'

    date = fields.Date(
        string='Fecha', required=True, index=True,
        default=lambda self: self._default_date(),
        help='Fecha del sorteo que se predice. El cálculo nunca mira ese '
             'sorteo ni ninguno posterior, así que volver a correr una '
             'tómbola vieja da lo mismo que el día que se generó.')
    turn_day = fields.Selection([
        ('afternoon', 'Vespertina'),
        ('evening', 'Nocturna'),
    ], string='Turno', required=True, index=True,
        default=lambda self: self._default_turn())
    temperature = fields.Selection([
        ('hot', 'Calientes'),
        ('remaining', 'Restantes'),
        ('cold', 'Fríos'),
        ('all', 'Todos (100)'),
    ], string='Candidatos', required=True, default='hot',
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
        help='Los 5 mejores de cada premio y las últimas salidas que se '
             'usaron. Se guarda para poder volver a tirar las combinaciones '
             'sin recalcular los 20 sorteos.')
    groups_html = fields.Html(
        string='Los 5 de cada premio', readonly=True, sanitize=False,
        copy=False)
    combos_html = fields.Html(
        string='Combinaciones Tómbola', readonly=True, sanitize=False,
        copy=False)
    probables_primeros_html = fields.Html(
        string='5 probables · primeros 5 premios', readonly=True,
        sanitize=False, copy=False)
    probables_veinte_html = fields.Html(
        string='2 probables · 20 premios', readonly=True, sanitize=False,
        copy=False)

    _sql_constraints = [
        ('unique_date_turn',
         'unique(date, turn_day)',
         'Ya existe una tómbola para esa fecha y turno.'),
    ]

    # ── Defaults: la última quiniela que haya entrado ─────────────────────

    @api.model
    def _last_quiniela_output(self):
        return self.env['lottery.output'].sudo().search(
            [('sorteo_id.source_code', '=', SOURCE_CODE)],
            order='date desc, turn_day desc, id desc', limit=1)

    @api.model
    def _default_date(self):
        last = self._last_quiniela_output()
        return last.date if last else fields.Date.context_today(self)

    @api.model
    def _default_turn(self):
        last = self._last_quiniela_output()
        return last.turn_day if last else 'evening'

    @api.depends('date', 'turn_day')
    def _compute_display_name(self):
        turnos = dict(self._fields['turn_day'].selection)
        for rec in self:
            fecha = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            rec.display_name = 'Tómbola %s / %s' % (
                fecha, turnos.get(rec.turn_day, ''))

    @api.onchange('date', 'turn_day', 'temperature', 'combinaciones_window')
    def _onchange_parametros(self):
        """Si se cambia un parámetro, lo calculado ya no corresponde: se
        limpia. Si no, quedaría en pantalla una tarjeta con la fecha vieja en
        el cabezal lista para publicar por error."""
        self.top_json = False
        self.groups_html = False
        self.combos_html = False
        self.probables_primeros_html = False
        self.probables_veinte_html = False

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
            sorteo, self.turn_day, self.temperature)

    def _prediccion(self, sorteo, candidatos):
        """Una `lottery.prediction` en memoria (`new`) para ese premio.

        No se graba nada: sólo se usa para llamar a `_score_candidatos`, que
        es la lógica del botón "Completar números". Así la tómbola y la
        predicción individual puntean exactamente igual, y no quedan 20
        predicciones basura en la base ni choca la constraint de fecha +
        turno + sorteo."""
        self.ensure_one()
        return self.env['lottery.prediction'].new({
            'sorteo_id': sorteo.id,
            'date': self.date,
            'turn_day': self.turn_day,
            'combinaciones_window': self.combinaciones_window,
            'number_ids': [(6, 0, candidatos.ids)],
        })

    # ── Acción 1: evaluar los 20 sorteos ──────────────────────────────────

    def action_evaluar(self):
        """Puntea los 20 premios y se queda con los 5 mejores de cada uno.

        Es la parte cara: cada premio corre el mismo cálculo que la
        predicción individual, y la primera vez arma además las tablas
        LotoAnálisis que le falten (quedan cacheadas, así que la segunda
        corrida es mucho más rápida)."""
        self.ensure_one()
        sorteos = self._sorteos()
        grupos, sin_datos = [], []
        for premio, sorteo in sorteos:
            candidatos = self._candidatos(sorteo)
            if len(candidatos) < TOP_POR_PREMIO:
                sin_datos.append(premio)
                continue
            pred = self._prediccion(sorteo, candidatos)
            filas, _ctx = pred._score_candidatos()
            top = [fila['numero'] for fila in filas[:TOP_POR_PREMIO]]
            # Los mismos "interesantes del mes" que la app muestra y que el
            # botón Completar números usa para los 10 y los 5, pero mirando
            # el mes de la fecha que se predice y el premio de este sorteo.
            interesantes = self.env['lottery.prediction'].atrasos_del_mes(
                sorteo, self.date)
            grupos.append({
                'premio': premio,
                'top': top,
                'salidas': pred._last_output(
                    limit=ULTIMAS_SALIDAS).mapped('number_id.name'),
                # Sólo los elegidos: es lo único que se usa después y deja
                # el JSON chico. Lista de pares y no diccionario porque en
                # JSON las claves serían texto.
                'mes': [[n, interesantes[n]] for n in top
                        if n in interesantes],
            })

        if not grupos:
            raise UserError(
                'Ningún premio quedó con al menos %d candidatos para la %s '
                '(Candidatos: %s). Generá primero los artículos del ranking '
                'o elegí Candidatos = Todos (100).' % (
                    TOP_POR_PREMIO,
                    dict(self._fields['turn_day'].selection)[self.turn_day],
                    dict(self._fields['temperature'].selection)[
                        self.temperature]))

        self.write({
            'top_json': json.dumps(grupos),
            'groups_html': self._render_grupos(grupos, sin_datos),
            'probables_primeros_html': self._render_probables_primeros(
                grupos, sorteos),
            'probables_veinte_html': self._render_probables_veinte(
                grupos, sorteos),
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

    # ── Acción 2: generar las combinaciones ───────────────────────────────

    def action_generar_combinaciones(self):
        """10 combinaciones de 7 números, al azar pero ponderado.

        Cada vez que se aprieta sale una tanda distinta: el azar es de
        verdad, lo que se fija es el peso de cada número. Las 10 no se
        repiten entre sí; los números sí se repiten de una combinación a
        otra, y dentro de una combinación los 7 son distintos."""
        self.ensure_one()
        grupos = self._grupos()
        if not grupos:
            self.action_evaluar()
            grupos = self._grupos()

        pesos, info = self._pesos(grupos)
        combos = self._combinaciones(pesos, random.Random())
        self.combos_html = self._render_combinaciones(combos, pesos, info)
        return True

    def _pesos(self, grupos):
        """({número: peso}, {número: detalle}) para el sorteo ponderado.

        El detalle es lo que explica el peso y lo que después se muestra:
        en cuántos grupos está, cuántas coincidencias de dígito juntó y cuál
        es su mayor atraso del mes (None si no es interesante en ninguno de
        sus premios).

        Dígitos y mes se promedian por grupo en vez de sumarse: si se
        sumaran, un número que aparece en muchos premios cobraría dos veces
        por lo mismo, y la repetición ya la paga la señal 1."""
        info = {}
        Prediction = self.env['lottery.prediction']
        for grupo in grupos:
            salidas = grupo.get('salidas') or []
            mes = dict(grupo.get('mes') or [])
            for numero in grupo.get('top') or []:
                datos = info.setdefault(
                    numero, {'veces': 0, 'digitos': 0, 'mes_puntos': 0.0,
                             'mes': None})
                datos['veces'] += 1
                datos['digitos'] += _coincidencias(numero, salidas)
                anios = mes.get(numero)
                if anios is not None:
                    # Con peso 1 devuelve la fracción: 2 años un cuarto,
                    # 4 la mitad, 8 o más (y "nunca") entero.
                    datos['mes_puntos'] += Prediction.puntos_por_atraso_mes(
                        anios, 1.0)
                    datos['mes'] = max(datos['mes'] or 0, anios)

        pesos = {}
        for numero, datos in info.items():
            cuantas = datos['veces']
            pesos[numero] = round(
                PESO_REPETICION * cuantas
                + PESO_DIGITOS * datos['digitos'] / cuantas
                + PESO_MES * datos['mes_puntos'] / cuantas, 3)
        return pesos, info

    @staticmethod
    def _combinaciones(pesos, rnd):
        """`COMBINACIONES` tuplas distintas de `NUMEROS_POR_COMBINACION`
        números, ordenadas de menor a mayor.

        El sorteo ponderado sin reposición se hace con la clave de
        Efraimidis-Spirakis: a cada número se le tira `random() ** (1/peso)`
        y se toman las claves más altas. Da exactamente la misma
        distribución que ir sacando bolillas de a una sin devolverlas, en
        una línea y sin sesgo."""
        bombo = list(pesos)
        posibles = (math.comb(len(bombo), NUMEROS_POR_COMBINACION)
                    if len(bombo) >= NUMEROS_POR_COMBINACION else 0)
        if posibles < COMBINACIONES:
            raise UserError(
                'Con %d números distintos entre los 20 grupos no se pueden '
                'armar %d combinaciones diferentes de %d. Probá con '
                'Candidatos = Restantes o Todos (100).' % (
                    len(bombo), COMBINACIONES, NUMEROS_POR_COMBINACION))

        vistas, intentos = set(), 0
        while len(vistas) < COMBINACIONES and intentos < INTENTOS_MAX:
            intentos += 1
            elegidos = sorted(
                bombo, key=lambda n: rnd.random() ** (1.0 / pesos[n]),
                reverse=True)[:NUMEROS_POR_COMBINACION]
            vistas.add(tuple(sorted(elegidos)))
        if len(vistas) < COMBINACIONES:
            raise UserError(
                'No se pudieron armar %d combinaciones distintas en %d '
                'tiradas: hay muy pocos números en juego.' % (
                    COMBINACIONES, INTENTOS_MAX))
        return sorted(vistas)

    # ── Informe: 5 probables en los 5 primeros premios ────────────────────

    def _salidos_en_el_mes(self, sorteo_ids):
        """Números que ya salieron en el mes de la predicción en esos
        premios, mirando sólo salidas ANTERIORES a la fecha que se evalúa."""
        self.ensure_one()
        outputs = self.env['lottery.output'].sudo().search([
            ('sorteo_id', 'in', list(sorteo_ids)),
            ('month', '=', str(self.date.month)),
            ('year', '=', self.date.year),
            ('date', '<', self.date),
        ])
        return set(outputs.mapped('number_id.name'))

    def _probables_primeros(self, grupos, sorteos):
        """Los `PROBABLES_PRIMEROS` números más probables de los primeros
        premios, con el detalle que los justifica.

        De los premios 1 a `PREMIOS_PRIMEROS` salen 25 números (5 por
        premio) con repetidos. Manda cuántas veces se repite entre esos
        premios; a igualdad de repeticiones va primero el que TODAVÍA no
        salió en el mes, y después el que quedó mejor rankeado en su premio.
        No hay azar acá: la misma evaluación da siempre la misma lista."""
        self.ensure_one()
        primeros = [(premio, sorteo) for premio, sorteo in sorteos
                    if premio <= PREMIOS_PRIMEROS]
        elegidos = {premio for premio, _sorteo in primeros}
        salidos = self._salidos_en_el_mes(
            [sorteo.id for _premio, sorteo in primeros])

        detalle = {}
        for grupo in grupos:
            if grupo['premio'] not in elegidos:
                continue
            for puesto, numero in enumerate(grupo['top'], 1):
                datos = detalle.setdefault(
                    numero, {'numero': numero, 'veces': 0, 'puesto': 99,
                             'premios': []})
                datos['veces'] += 1
                datos['puesto'] = min(datos['puesto'], puesto)
                datos['premios'].append(grupo['premio'])
        for datos in detalle.values():
            datos['salio_mes'] = datos['numero'] in salidos

        orden = sorted(detalle.values(),
                       key=lambda d: (-d['veces'], d['salio_mes'],
                                      d['puesto'], d['numero']))
        return orden[:PROBABLES_PRIMEROS]

    # ── Informe: 2 probables entre los 20 premios ─────────────────────────

    def _ranking_pintas(self, sorteos):
        """[{id, name, votos, general, turno}, …] de más votada a menos.

        Cada premio vota dos veces: por su pinta más atrasada en general y
        por la más atrasada en el turno que se evalúa. Con 20 premios son 40
        votos, y la pinta que más se repite es la que más "coincide".

        Los dos tops salen de `get_top_3_pintas`, la misma función que ya usa
        el puntaje de cada premio, así que vienen de la caché y no cuestan
        consultas nuevas."""
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        day = WEEKDAY_CODES[self.date.weekday()]
        votos = {}
        for _premio, sorteo in sorteos:
            for option, clave in (('general', 'general'),
                                  (self.turn_day, 'turno')):
                filas = stats.get_top_3_pintas(option, day,
                                               sorteo_id=sorteo.id)
                if not filas:
                    continue
                pinta = filas[0]
                entrada = votos.setdefault(
                    pinta['id'], {'id': pinta['id'], 'name': pinta['name'],
                                  'votos': 0, 'general': 0, 'turno': 0})
                entrada['votos'] += 1
                entrada[clave] += 1
        return sorted(votos.values(),
                      key=lambda p: (-p['votos'], p['name']))

    def _probables_veinte(self, grupos, sorteos):
        """(pinta ganadora, [números], ranking, repeticiones).

        Gana la pinta más votada que tenga al menos `PROBABLES_VEINTE`
        números entre los 100 de la evaluación — si la primera no los tiene,
        se baja a la siguiente del ranking, porque el informe pide números
        que además hayan quedado bien puntuados, no cualquiera de la pinta.
        Entre los de la pinta ganadora eligen los que más se repiten."""
        self.ensure_one()
        veces = {}
        for grupo in grupos:
            for numero in grupo['top']:
                veces[numero] = veces.get(numero, 0) + 1

        ranking = self._ranking_pintas(sorteos)
        Group = self.env['lottery.group'].sudo()
        mejor = None
        for pinta in ranking:
            numeros = set(Group.browse(pinta['id']).number_ids.mapped('name'))
            candidatos = sorted((n for n in veces if n in numeros),
                                key=lambda n: (-veces[n], n))
            if mejor is None or len(candidatos) > len(mejor[1]):
                mejor = (pinta, candidatos)
            if len(candidatos) >= PROBABLES_VEINTE:
                mejor = (pinta, candidatos)
                break
        if not mejor:
            return None, [], ranking, veces
        pinta, candidatos = mejor
        return pinta, candidatos[:PROBABLES_VEINTE], ranking, veces

    # ── Render ────────────────────────────────────────────────────────────

    @staticmethod
    def _texto_anios(anios):
        """'nunca' o '5 años': cómo se lee un atraso del mes."""
        if anios is None:
            return ''
        return 'nunca' if anios >= ANIOS_MES_NUNCA else '%d años' % anios

    def _pie(self, texto):
        return (
            '<div style="margin:2px 14px 0;padding:8px 10px;'
            'border-radius:9px;background:#FFFFFF;border:1px solid #C6E4CF;'
            'font:600 11px/1.45 %s;color:%s;text-align:center;">%s</div>'
            % (FUENTE, TEXTO_SUAVE, texto)
        )

    def _panel_mes(self, destacados):
        """Franja dorada con los interesantes del mes.

        `destacados` es [(número, años), …] ya ordenado. Es la parte vistosa
        del criterio 3: qué números de los que salieron llevan años sin
        aparecer en el mes, y cuántos."""
        self.ensure_one()
        if not destacados:
            return ''
        mes = MESES[self.date.month - 1]
        chips = ''.join(
            '<span style="display:inline-block;margin:4px 3px 0;'
            'padding:5px 11px;border-radius:50px;'
            'background:linear-gradient(135deg,#FFFDF3,#FFF1C9);'
            'border:1px solid %s;font:800 11.5px/1 %s;color:#7A5A10;'
            'box-shadow:0 1px 3px rgba(196,150,20,.25);">'
            '%02d <span style="font-weight:600;opacity:.75;">%s</span>'
            '</span>' % (DORADO, FUENTE, numero, self._texto_anios(anios))
            for numero, anios in destacados)
        return (
            '<div style="margin:10px 14px 0;padding:10px 10px 12px;'
            'border-radius:12px;'
            'background:linear-gradient(135deg,rgba(255,201,60,.16),'
            'rgba(255,201,60,.06));border:1px solid %s;text-align:center;">'
            '<div style="font:900 11.5px/1.3 %s;color:#7A5A10;'
            'letter-spacing:1.1px;text-transform:uppercase;">'
            'Interesantes de %s</div>'
            '<div style="margin-top:3px;font:600 10.5px/1.4 %s;'
            'color:#8A6416;">De los que entraron, los que llevan años sin '
            'salir en %s</div>'
            '<div>%s</div></div>'
            % (DORADO, FUENTE, mes, FUENTE, mes, chips)
        )

    def _render_grupos(self, grupos, sin_datos):
        """Tarjeta con los 5 mejores de cada premio, en dos columnas de 10."""
        self.ensure_one()
        color = COLOR_TURNO[self.turn_day]
        por_premio = {g['premio']: g for g in grupos}

        filas = []
        for i in range(1, TOTAL_PREMIOS // 2 + 1):
            celdas = []
            for premio in (i, i + TOTAL_PREMIOS // 2):
                grupo = por_premio.get(premio)
                if grupo:
                    bolas = ''.join(bola('%02d' % n, color, diam=34)
                                    for n in grupo['top'])
                else:
                    bolas = ('<span style="font:600 11px/1 %s;color:%s;">'
                             'sin datos</span>' % (FUENTE, TEXTO_SUAVE))
                celdas.append(
                    '<td style="padding:6px 5px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s<div style="display:flex;gap:7px;">%s</div></div>'
                    '</td>' % (badge(premio, lado=24), bolas))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        pie = self._pie(
            'Los 5 mejores de cada premio · Candidatos: %s · ventana de '
            'combinaciones: %d' % (
                dict(self._fields['temperature'].selection)[self.temperature],
                self.combinaciones_window))
        if sin_datos:
            pie += (
                '<div style="margin:8px 14px 0;padding:8px 10px;'
                'border-radius:9px;background:#FFF7E3;'
                'border:1px solid #F5E3B3;font:600 11px/1.45 %s;'
                'color:#8A6416;text-align:center;">'
                'Sin candidatos suficientes en los premios %s: quedaron '
                'afuera del sorteo.</div>'
                % (FUENTE, ', '.join(str(p) for p in sin_datos)))

        cuerpo = (
            '<div style="padding:12px 8px 12px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>' % (''.join(filas), pie))
        return tarjeta(
            cabezal(self.turn_day, self.date,
                    titulo='Tómbola · los 5 de cada premio'),
            cuerpo, ancho=524)

    def _render_combinaciones(self, combos, pesos, info):
        """Tarjeta publicable: 10 combinaciones en dos columnas de 5, cada
        una con sus 7 bolas rojas ordenadas de menor a mayor."""
        self.ensure_one()
        filas = []
        for i in range(COMBINACIONES_POR_COLUMNA):
            celdas = []
            for j in (i, i + COMBINACIONES_POR_COLUMNA):
                bolas = ''.join(bola('%02d' % n, COLOR_TOMBOLA, diam=40)
                                for n in combos[j])
                celdas.append(
                    '<td style="padding:6px 6px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s<div style="display:flex;gap:8px;">%s</div></div>'
                    '</td>' % (badge(j + 1, lado=24), bolas))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        # Los interesantes del mes que de verdad entraron en alguna
        # combinación, del más atrasado al menos.
        jugados = {n for combo in combos for n in combo}
        destacados = sorted(
            ((n, info[n]['mes']) for n in jugados
             if info[n]['mes'] is not None),
            key=lambda par: (-par[1], par[0]))

        # Los que más mandaron en el sorteo, para poder contar de dónde
        # salieron las combinaciones cuando se publican.
        mejores = sorted(pesos, key=lambda n: (-pesos[n], n))[:6]
        detalle = ' · '.join(
            '%02d (%d grupos%s)' % (
                n, info[n]['veces'],
                ', %d dígitos' % info[n]['digitos'] if info[n]['digitos']
                else '')
            for n in mejores)

        cuerpo = (
            '<div style="padding:12px 8px 12px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s%s</div>'
            % (''.join(filas), self._panel_mes(destacados),
               self._pie('Más pesados: %s' % detalle)))
        return tarjeta(
            cabezal(self.turn_day, self.date,
                    titulo='Combinaciones Tómbola'),
            cuerpo, ancho=780)

    def _chips(self, textos, color_borde='#C6E4CF', color_texto=None):
        """Fila de cápsulas con el detalle de cada número."""
        return ''.join(
            '<span style="display:inline-block;margin:4px 3px 0;'
            'padding:5px 11px;border-radius:50px;background:#FFFFFF;'
            'border:1px solid %s;font:700 11px/1 %s;color:%s;">%s</span>'
            % (color_borde, FUENTE, color_texto or TEXTO_SUAVE, texto)
            for texto in textos)

    def _render_probables_primeros(self, grupos, sorteos):
        """Tarjeta de los 5 probables de los primeros 5 premios."""
        self.ensure_one()
        probables = self._probables_primeros(grupos, sorteos)
        mes = MESES[self.date.month - 1]
        if not probables:
            cuerpo = (
                '<div style="padding:22px 18px;text-align:center;'
                'font:700 13px/1.5 %s;color:%s;">Todavía no hay números '
                'evaluados en los primeros %d premios.</div>'
                % (FUENTE, TEXTO_SUAVE, PREMIOS_PRIMEROS))
            return tarjeta(
                cabezal(self.turn_day, self.date,
                        titulo='Probables · primeros %d premios'
                               % PREMIOS_PRIMEROS),
                cuerpo, ancho=452)

        color = COLOR_TURNO[self.turn_day]
        bolas = ''.join(bola('%02d' % d['numero'], color, diam=56)
                        for d in probables)
        detalle = self._chips(
            '%02d · %s · %s' % (
                d['numero'],
                ('%d premios' % d['veces'] if d['veces'] > 1
                 else 'premio %d' % d['premios'][0]),
                'salió en %s' % mes if d['salio_mes']
                else 'sin salir en %s' % mes)
            for d in probables)

        cuerpo = (
            '<div style="padding:16px 12px 14px;">'
            '<div style="font:900 13px/1.2 %s;color:%s;text-align:center;'
            'letter-spacing:.4px;margin-bottom:12px;">'
            '%d números probables en los %d primeros premios</div>'
            '<div style="display:flex;justify-content:center;gap:10px;">'
            '%s</div>'
            '<div style="text-align:center;margin-top:6px;">%s</div>'
            '%s</div>'
            % (FUENTE, TEXTO, PROBABLES_PRIMEROS, PREMIOS_PRIMEROS, bolas,
               detalle,
               self._pie('De los %d números que dan los premios 1 a %d. '
                         'Manda cuántas veces se repite entre ellos; '
                         'a igualdad, primero el que no salió en %s.'
                         % (PREMIOS_PRIMEROS * TOP_POR_PREMIO,
                            PREMIOS_PRIMEROS, mes))))
        return tarjeta(
            cabezal(self.turn_day, self.date,
                    titulo='Probables · primeros %d premios'
                           % PREMIOS_PRIMEROS),
            cuerpo, ancho=452)

    def _render_probables_veinte(self, grupos, sorteos):
        """Tarjeta de los 2 probables entre los 20 premios, con el ranking
        de pintas que los eligió."""
        self.ensure_one()
        pinta, numeros, ranking, veces = self._probables_veinte(
            grupos, sorteos)
        titulo = 'Probables · %d premios' % TOTAL_PREMIOS
        if not pinta or not numeros:
            cuerpo = (
                '<div style="padding:22px 18px;text-align:center;'
                'font:700 13px/1.5 %s;color:%s;">No hay pintas atrasadas '
                'cargadas para estos premios.</div>' % (FUENTE, TEXTO_SUAVE))
            return tarjeta(cabezal(self.turn_day, self.date, titulo=titulo),
                           cuerpo, ancho=452)

        color = COLOR_TURNO[self.turn_day]
        bolas = ''.join(bola('%02d' % n, color, diam=64) for n in numeros)
        detalle = self._chips(
            '%02d · %d de %d premios' % (n, veces[n], TOTAL_PREMIOS)
            for n in numeros)

        total_votos = sum(p['votos'] for p in ranking) or 1
        tope = ranking[0]['votos'] or 1
        barras = []
        for p in ranking[:PINTAS_EN_RANKING]:
            gana = p['id'] == pinta['id']
            barras.append(
                '<tr>'
                '<td style="padding:3px 6px 3px 0;font:%s 11.5px/1 %s;'
                'color:%s;white-space:nowrap;">%s</td>'
                '<td style="padding:3px 0;width:100%%;">'
                '<div style="height:9px;border-radius:5px;background:#E4F1E8;'
                'overflow:hidden;">'
                '<div style="height:9px;width:%d%%;border-radius:5px;'
                'background:%s;"></div></div></td>'
                '<td style="padding:3px 0 3px 8px;font:800 11px/1 %s;'
                'color:%s;white-space:nowrap;">%d</td></tr>'
                % ('900' if gana else '600', FUENTE,
                   TEXTO if gana else TEXTO_SUAVE, p['name'].title(),
                   round(100.0 * p['votos'] / tope),
                   DORADO if gana else '#9CCBA9', FUENTE,
                   TEXTO if gana else TEXTO_SUAVE, p['votos']))

        cuerpo = (
            '<div style="padding:16px 14px 14px;">'
            '<div style="font:900 13px/1.2 %s;color:%s;text-align:center;'
            'letter-spacing:.4px;">%d números probables entre los %d '
            'premios</div>'
            '<div style="text-align:center;margin-top:8px;">'
            '<span style="display:inline-block;padding:6px 14px;'
            'border-radius:50px;background:linear-gradient(135deg,'
            '#FFFDF3,#FFF1C9);border:1px solid %s;font:900 11.5px/1 %s;'
            'color:#7A5A10;letter-spacing:.8px;text-transform:uppercase;">'
            '%s · la más atrasada en %d de %d</span></div>'
            '<div style="display:flex;justify-content:center;gap:14px;'
            'margin-top:12px;">%s</div>'
            '<div style="text-align:center;margin-top:6px;">%s</div>'
            '<div style="margin:12px 4px 0;">'
            '<div style="font:800 10.5px/1 %s;color:%s;letter-spacing:1px;'
            'text-transform:uppercase;margin-bottom:5px;">'
            'Ranking de pintas · %d votos</div>'
            '<table style="width:100%%;border-collapse:collapse;">'
            '<tbody>%s</tbody></table></div>'
            '%s</div>'
            % (FUENTE, TEXTO, PROBABLES_VEINTE, TOTAL_PREMIOS,
               DORADO, FUENTE, pinta['name'].title(), pinta['votos'],
               total_votos, bolas, detalle, FUENTE, TEXTO_SUAVE, total_votos,
               ''.join(barras),
               self._pie('Cada premio vota dos veces: su pinta más atrasada '
                         'en general y la más atrasada de la %s. De la pinta '
                         'ganadora salen los números que más se repiten '
                         'entre los %d de la evaluación.'
                         % (TURN_LABEL[self.turn_day].lower(),
                            TOTAL_PREMIOS * TOP_POR_PREMIO))))
        return tarjeta(cabezal(self.turn_day, self.date, titulo=titulo),
                       cuerpo, ancho=452)
