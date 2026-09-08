# -*- coding: utf-8 -*-
import json
import random
import re

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.lottery_base.models.utils import default_today_local
from .patron_atraso import _hit_cruce

WEEKDAY_CODES = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do')

# Qué lista del ranking_snapshot del sorteo mira cada temperatura.
TEMPERATURE_KEY = {
    'hot': 'numbers',
    'cold': 'numbers_cold',
    'remaining': 'numbers_remaining',
}

# ── Completar números (07/09/2026) ─────────────────────────────────────────
# La lista de 20 ya no sale de sumar puntajes: sale de "tandas" de recencia.
# Se camina el historial de salidas de este sorteo (los dos turnos
# mezclados, de la más reciente hacia atrás) y en cada paso entran los
# candidatos que todavía no habían entrado y comparten decena o unidad con
# el número de esa salida. Se sigue retrocediendo hasta juntar 20 (o agotar
# candidatos). Ver `_seleccionar_veinte`.
#
# Cuántas salidas hacia atrás se traen para esa caminata. Con una salida por
# turno y por día alcanza de sobra para juntar 20 números aunque los
# candidatos sean pocos; si el historial se agotara antes, el resto se
# completa con la cascada de abajo sobre los candidatos que quedaron afuera.
MAX_SALIDAS_HISTORIAL = 120

# Cuando una tanda trae más candidatos nuevos de los que hacen falta para
# llegar a 20 hay que elegir cuáles entran, y ese mismo criterio es el que
# arma el orden final de los 20 (del que salen los 10, los 5 y el Súper
# Mágico, siempre por recorte: 10 ⊂ 20, 5 ⊂ 10, Súper Mágico = el 1º de los
# 5). Es una cascada estricta, no una suma de puntos: cada señal sólo
# desempata a la anterior.
#   1) Tabla LotoAnálisis (unificada general+turno)
#   2) Grupos más atrasados (unión general+turno)
#   3) Pintas más atrasadas (unión general+turno)
#   4) Combinaciones (score crudo de la Consulta de números)
#   5) Cruce línea/terminal contra la última salida general
#   6) Mayoría ≥50/<50 de los últimos 10 sorteos ganadores
#   7) Al azar
# Ver `_clave_cascada`.

# Un número puede caer en varios grupos atrasados a la vez, y no son señales
# repetidas: cada familia (terminal, suma, resta, línea...) reparte los 100
# números en 10 grupos, así que un número está en uno solo de cada familia y
# que dos familias distintas lo marquen es evidencia de verdad.
#
# Aun así, estar en dos NO puede valer el doble. Se suma el mejor entero más
# una fracción de lo que aportan los demás, y esa fracción depende de EN
# CUÁNTOS grupos está, no del puesto de cada uno: con dos apenas empuja (no
# alcanza para dar vuelta a un número del grupo más atrasado), con tres o
# cuatro sí lo despega, que es cuando de verdad cambia la cosa.
#
# El coeficiente va por cantidad y no por puesto porque con un decaimiento
# por puesto las dos condiciones no entran juntas: para que dos grupos no
# ganen hace falta un 2º chico (<0.14), y con ese 2º chico el 3º tendría que
# valer MÁS que el 2º para que tres despeguen. Índice = cantidad de grupos
# menos 1; de ahí en adelante se mantiene el último.
APORTE_GRUPOS_EXTRA = (0.0, 0.12, 0.30, 0.40)

# Escala interna para el valor de grupos/pintas (ya no es una suma de puntos
# junto a otras señales, así que el número en sí no importa, sólo el orden
# que genera). Se mantiene en 100 nada más que para que el desglose se lea
# como un porcentaje del más atrasado de la unión.
ESCALA_ATRASO = 100.0

# Tabla LotoAnálisis: un acompañante no vale lo mismo pegado que lejos, pero
# es una ponderación suave, NO una regla de "gana el más lejos" — el que sale
# a veces es justo un vecino. El índice es la distancia en casillas (1 =
# adyacente) y los valores son absolutos: no se normalizan contra nada, así
# que en una tirada puede no haber ningún acompañante que llegue al tope y
# está bien. El pegadito arranca en 0.40, no en cero.
#
# La tabla general y la del turno ya no se suman por separado: un candidato
# se queda con la mejor (más alta) de las dos, igual que grupos y pintas se
# quedan con el atraso más alto entre general y turno.
CURVA_DISTANCIA_TABLA = (0.40, 0.55, 0.68, 0.78, 0.85, 0.90, 0.93, 0.96,
                         0.98, 0.99, 1.00)

# Últimos N sorteos ganadores (ambos turnos) sobre los que se cuenta la
# mayoría ≥50/<50 del anteúltimo escalón de la cascada.
VENTANA_MAYORIA = 10

# ── Atraso del mes ─────────────────────────────────────────────────────────
# Ya NO se usa para elegir los 10 y los 5 de "Completar números" (eso ahora
# lo decide la cascada de arriba); sigue viva porque la Tómbola de la
# Quiniela Uruguay la usa como una de sus señales propias.
#
# Son los mismos números que la app muestra en "Números del mes atrasados"
# (endpoint /api/lottery/v1/stats/numeros-mes-atrasados): los que llevan años
# sin salir en el mes en curso. Umbrales de la app: 2 años entre los que más
# salen y los medios, 4 entre los que menos salen.
ANIOS_MES_TOP = 2
ANIOS_MES_MID = 2
ANIOS_MES_BOTTOM = 4
# "Nunca salió en ese mes" se guarda como un atraso enorme, así ordena arriba
# de todo sin necesitar un caso aparte.
ANIOS_MES_NUNCA = 99
# De acá para arriba el atraso ya vale el máximo. Es un valor absoluto y no
# relativo a la tirada: si se normalizara contra el más atrasado del conjunto,
# un solo número que nunca salió aplastaría a todos los demás (2 años pasaría
# a valer 0.02) y dos corridas no se podrían comparar.
TOPE_ANIOS_MES = 8

# Campo de lottery_group_stat que mide el atraso de cada lista.
CAMPO_ATRASO = {
    'general': 'salidas_atrasadas',
    'afternoon': 'salidas_atrasadas_dia',
    'evening': 'salidas_atrasadas_noche',
}


def _factor_distancia(dist):
    """Parte del peso de la tabla que se lleva un acompañante a `dist`
    casillas. Valor absoluto: dos tiradas distintas se miden con la misma
    vara y nadie se lleva el tope sólo por ser el más lejano de su cruz."""
    tope = len(CURVA_DISTANCIA_TABLA)
    return CURVA_DISTANCIA_TABLA[min(max(int(dist), 1), tope) - 1]


def _digitos(numero):
    """(línea, terminal) = (decena, unidad) de un número 00-99."""
    return divmod(numero, 10)


def _comparte_digito(candidato, salida):
    """True si `candidato` tiene, en línea o en terminal, algún dígito que
    también aparece en `salida` (en cualquiera de sus dos posiciones).

    Ej: salida 25 → dígitos {2, 5}. Comparten 02, 12, 20-29, 52-59, 32, 42,
    72... cualquier número con un 2 o un 5 en la línea o en el terminal."""
    return bool(set(_digitos(candidato)) & set(_digitos(salida)))


def _default_sorteo(self):
    return self.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)


def _default_hour(self):
    """Hora local actual como float, que es lo que espera el widget
    float_time: 13.5 se muestra como 13:30.

    Se pasa por context_timestamp porque fields.Datetime.now() devuelve UTC;
    sin eso, a las 21:00 en Uruguay se propondría 00:00. Mismo helper que
    lottery.curiosity: acá se duplica (no hay un módulo de utils compartido
    en lottery_portal.models) en vez de importarlo desde ese archivo."""
    ahora = fields.Datetime.context_timestamp(self, fields.Datetime.now())
    return ahora.hour + ahora.minute / 60.0


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
        default=default_today_local,
        help='Fecha del sorteo para el que se predicen los números.')
    turn_day = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno del día', required=True, index=True)
    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='Solo las predicciones publicadas se envían a la app móvil '
             '(Números Mágicos). Permite prepararlas con anticipación y '
             'publicarlas cuando estén listas.')
    hour = fields.Float(
        string='Hora publicación', default=_default_hour,
        help='Hora en que se publica la predicción, en hora local (Uruguay). '
             'Se edita con el widget de horas (13.5 = 13:30). La app la '
             'muestra en Números Mágicos rotulada "Hora de Uruguay".')
    published_date = fields.Datetime(
        string='Publicada el', readonly=True, copy=False,
        help='Fecha y hora reales en que se marcó "Publicado" (se completa '
             'sola). No confundir con "Fecha de predicción", que es la del '
             'sorteo: si se carga de noche una predicción para el turno '
             'siguiente, esta fecha puede ser un día anterior a esa.')

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

    # ── Ternas y Tómbola ─────────────────────────────────────────────────
    # Se cuelgan de la misma predicción (normalmente la del premio 1) porque
    # comparten fecha y turno: la Tómbola sale del mismo sorteo físico que
    # los 20 premios, y las ternas se leen igual sin importar en qué premio
    # de ese sorteo salieron. No tiene sentido cargarlas de nuevo en la
    # predicción de cada premio.
    terna_ids = fields.One2many(
        'lottery.prediction.terna', 'prediction_id',
        string='Ternas a predecir',
        help='Números de 3 cifras (000-999) que se predicen para este '
             'sorteo (fecha y turno), sin importar el premio.')
    tombola_linea_ids = fields.One2many(
        'lottery.prediction.tombola.linea', 'prediction_id',
        string='Líneas de Tómbola a predecir',
        help='Cada línea son los 7 números (00-99) de una combinación '
             'completa a jugar en la Tómbola de este mismo sorteo (fecha y '
             'turno): un juego aparte de la Quiniela, ver '
             'lottery.tombola.output.')

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

    super_magico_id = fields.Many2one(
        'lottery.number', string='Súper Mágico',
        help='La apuesta más fuerte de la predicción: uno de los 5 Números '
             'a predecir, destacado aparte. Se carga a mano.')

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
    cumplida_super_magico = fields.Boolean(
        '¿Se acertó el Súper Mágico?', default=False, index=True,
        help='El número salido fue el Súper Mágico de esta predicción.')
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('published'):
                vals.setdefault('published_date', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        recien_publicadas = self.browse()
        if vals.get('published'):
            recien_publicadas = self.filtered(lambda r: not r.published)
        res = super().write(vals)
        if recien_publicadas:
            recien_publicadas.write({'published_date': fields.Datetime.now()})
        return res

    @api.constrains('super_magico_id', 'number_ids_5')
    def _check_super_magico_en_5(self):
        for rec in self:
            if (rec.super_magico_id
                    and rec.super_magico_id not in rec.number_ids_5):
                raise ValidationError(
                    'El Súper Mágico tiene que ser uno de los 5 Números a '
                    'predecir.')

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

    @api.model
    def numbers_by_temperature(self, sorteo, turn_day, temperature):
        """Números calientes / restantes / fríos de ese sorteo y turno, tal
        como los dejó el último artículo generado (`ranking_snapshot`).

        Está afuera del onchange porque la Tómbola de la Quiniela Uruguay
        (`lottery.prediction.tombola.uy`) necesita los mismos candidatos para
        los 20 sorteos de una, y el criterio tiene que ser uno solo: si acá
        cambia, cambia igual en la predicción individual.

        Devuelve un recordset vacío si el sorteo todavía no tiene snapshot."""
        Number = self.env['lottery.number']
        if not (sorteo and turn_day and temperature):
            return Number
        try:
            snapshot = json.loads(sorteo.ranking_snapshot or '{}')
        except (ValueError, TypeError):
            return Number
        items = snapshot.get(turn_day, {}).get(
            TEMPERATURE_KEY.get(temperature), []) or []
        names = []
        for item in items:
            raw = item.get('name') if isinstance(item, dict) else str(item)
            try:
                names.append(int(raw))
            except (ValueError, TypeError):
                pass
        return Number.search([('name', 'in', names)]) if names else Number

    @api.onchange('temperature', 'turn_day', 'sorteo_id')
    def _onchange_temperature(self):
        if not self.temperature or not self.turn_day or not self.sorteo_id:
            return
        self.number_ids = self.numbers_by_temperature(
            self.sorteo_id, self.turn_day, self.temperature)

    # ── Atraso del mes ────────────────────────────────────────────────────

    @api.model
    def atrasos_del_mes(self, sorteo, date):
        """{número: años sin salir en el mes de `date`} para ese sorteo.

        Sale de `get_month_overdue_sections`, el mismo cálculo que hay detrás
        del endpoint /api/lottery/v1/stats/numeros-mes-atrasados que consume
        la app, y con los mismos umbrales. Los números que no llegan al
        umbral no están en el diccionario.

        Está afuera del botón porque también lo usa la Tómbola de la Quiniela
        Uruguay: el criterio del mes tiene que ser uno solo.

        `ANIOS_MES_NUNCA` marca a los que nunca salieron en ese mes."""
        secciones = self.env['lottery.stats.service'].sudo() \
            .get_month_overdue_sections(
                date.month, date.year, sorteo_id=sorteo.id,
                years_top=ANIOS_MES_TOP, years_mid=ANIOS_MES_MID,
                years_bottom=ANIOS_MES_BOTTOM)
        atrasos = {}
        for categoria in secciones.values():
            for item in categoria.get('all') or []:
                try:
                    numero = int(item['name'])
                except (KeyError, TypeError, ValueError):
                    continue
                anios = (ANIOS_MES_NUNCA if item.get('nunca_salio_mes')
                         else item.get('years_sin_salir_mes') or 0)
                # Cada número cae en una sola categoría, pero si algo cambiara
                # allá arriba manda el atraso más grande.
                atrasos[numero] = max(atrasos.get(numero, 0), anios)
        return atrasos

    @api.model
    def puntos_por_atraso_mes(self, anios, peso):
        """Parte de `peso` que se lleva ese atraso del mes.

        2 años valen un cuarto, 4 la mitad, 8 o más (y "nunca salió") el peso
        entero. `anios=None` (no llegó al umbral) vale cero."""
        if anios is None:
            return 0.0
        return round(peso * min(anios, TOPE_ANIOS_MES) / TOPE_ANIOS_MES, 2)

    # ── Completar números: 20 / 10 / 5 en cascada ──────────────────────────

    def _last_output(self, turn=None, limit=1):
        """Última salida ANTERIOR al sorteo que se está prediciendo.

        turn=None → la última sin importar el turno (si se predice la noche
        de hoy y la tarde ya salió, es la de la tarde). turn='afternoon' /
        'evening' → la última de ese turno. Nunca mira el propio sorteo a
        predecir ni ninguno posterior, así que volver a correr una predicción
        vieja da lo mismo que el día que se generó.

        `limit` sube de 1 para pedir las últimas N (la Tómbola pide 6 para
        comparar dígitos), y devuelve el recordset ordenado de más reciente a
        más vieja."""
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
            domain, order='date desc, turn_day desc, id desc', limit=limit)

    def _acompanantes(self, turno, numero):
        """{número: distancia en casillas} de los que comparten fila, columna
        o diagonal con `numero` en la Tabla LotoAnálisis — la misma grilla que
        muestra el wizard: fecha de corte de Ajustes → Loterías y 12×12,
        reusando la caché.

        La distancia sirve para pesar: los pegados al número valen algo menos
        y el peso sube con la distancia. Como cada acompañante cae en una sola
        de las cuatro rectas (fila, columna y las dos diagonales se cruzan
        únicamente en el propio número), la distancia es única y el máximo de
        las dos coordenadas la mide bien en los cuatro casos."""
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

    def _puntos_por_atraso(self, top_fn, day, peso):
        """{número: puntos} de los grupos (o pintas) más atrasados, uniendo el
        top general con el top del turno a predecir en UNA sola lista.

        El orden lo da la cantidad de salidas atrasadas, no el puesto: si un
        grupo lleva 45 atrasos en el turno y otro 30 en el general, para ese
        turno manda el de 45. Un grupo que aparece en las dos listas se queda
        con su atraso más alto. El puntero de la unión se lleva `peso` entero
        y el resto la parte proporcional a su atraso, así la distancia real
        entre 45 y 30 se ve en el puntaje.

        Un número que cae en varios grupos suma: se lleva el mejor entero
        más una fracción de los demás, y la fracción sale de
        `APORTE_GRUPOS_EXTRA` según en cuántos grupos está. Estar en dos no
        vale el doble ni alcanza para dar vuelta a un número del grupo más
        atrasado — no se busca que gane por acumular en vez de por atraso —,
        pero estar en tres o cuatro sí lo despega."""
        self.ensure_one()
        turno_lbl = dict(self._fields['turn_day'].selection).get(
            self.turn_day, self.turn_day).lower()

        entradas = {}
        for option, etiqueta in (('general', 'general'),
                                 (self.turn_day, turno_lbl)):
            campo = CAMPO_ATRASO[option]
            for row in top_fn(option, day, sorteo_id=self.sorteo_id.id):
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

    def _valor_tabla(self, candidatos, last_general, last_turno):
        """{número: (factor, distancia, origen)} de la Tabla LotoAnálisis,
        uniendo la general y la del turno: cada candidato se queda con la
        que le da mejor (más alto) factor, igual que grupos y pintas se
        quedan con el atraso más alto entre las dos uniones."""
        self.ensure_one()
        acomp_general = (self._acompanantes('general', last_general.number_id.name)
                         if last_general else {})
        acomp_turno = (self._acompanantes(self.turn_day, last_turno.number_id.name)
                       if last_turno else {})
        turno_lbl = dict(self._fields['turn_day'].selection).get(
            self.turn_day, self.turn_day).lower()

        valores = {}
        for n in candidatos:
            opciones = []
            if acomp_general.get(n):
                d = acomp_general[n]
                opciones.append((_factor_distancia(d), d, 'general'))
            if acomp_turno.get(n):
                d = acomp_turno[n]
                opciones.append((_factor_distancia(d), d, turno_lbl))
            valores[n] = max(opciones, default=(0.0, 0, None))
        return valores

    def _rango_preferido_mayoria(self, ultimos):
        """None si los últimos `VENTANA_MAYORIA` sorteos ganadores no tienen
        mayoría clara; 'bajo' si conviene <50 (porque salieron más ≥50), o
        'alto' si conviene ≥50 (porque salieron más <50)."""
        if not ultimos:
            return None
        altos = sum(1 for o in ultimos if o.number_id.name >= 50)
        bajos = len(ultimos) - altos
        if altos > bajos:
            return 'bajo'
        if bajos > altos:
            return 'alto'
        return None

    def _valores_cascada(self, candidatos):
        """{número: {señal: valor}} con las 6 señales de la cascada (más el
        desempate al azar) para cada candidato, y el contexto para el
        desglose. El orden de las claves del dict es el orden de prioridad;
        `_clave_cascada` lo usa tal cual para ordenar."""
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        day = WEEKDAY_CODES[self.date.weekday()]

        last_general = self._last_output()
        last_turno = self._last_output(turn=self.turn_day)
        tabla = self._valor_tabla(candidatos, last_general, last_turno)

        gr_pts, gr_det = self._puntos_por_atraso(
            stats.get_top_6_groups, day, ESCALA_ATRASO)
        pi_pts, pi_det = self._puntos_por_atraso(
            stats.get_top_3_pintas, day, ESCALA_ATRASO)

        base = stats.get_combinaciones_scores(
            self.sorteo_id.id, self.date, self.combinaciones_window)
        comb = {n: base['scores'].get('%02d' % n, 0) for n in candidatos}

        # Cruce línea/terminal: contra la última salida general (ver
        # `_hit_cruce` en patron_atraso.py — mismo patrón que ya se usa en
        # la Consulta de atraso de patrones).
        ref_cruce = last_general.number_id.name if last_general else None

        ultimos = self._last_output(limit=VENTANA_MAYORIA)
        rango_mayoria = self._rango_preferido_mayoria(ultimos)

        valores = {}
        for n in candidatos:
            tf, td, torigen = tabla[n]
            if rango_mayoria == 'bajo':
                mayoria = n < 50
            elif rango_mayoria == 'alto':
                mayoria = n >= 50
            else:
                mayoria = False
            valores[n] = {
                'tabla': tf, 'tabla_dist': td, 'tabla_origen': torigen,
                'grupos': gr_pts.get(n, 0.0),
                'pintas': pi_pts.get(n, 0.0),
                'comb': comb[n],
                'cruce': bool(ref_cruce is not None
                             and _hit_cruce(ref_cruce, n)),
                'mayoria': mayoria,
                'azar': random.random(),
            }

        ctx = {
            'window_used': len(base['outputs']),
            'window_asked': self.combinaciones_window,
            'last_general': last_general,
            'last_turno': last_turno,
            'ref_cruce': ref_cruce,
            'rango_mayoria': rango_mayoria,
            'ultimos_mayoria': ultimos,
            'detalles': [
                ('Grupos atrasados', gr_det),
                ('Pintas atrasadas', pi_det),
            ],
        }
        return valores, ctx

    @staticmethod
    def _clave_cascada(valores, n):
        """Tupla de comparación para ordenar por la cascada: cada posición
        sólo desempata si todas las anteriores dieron igual. Se usa tanto
        para cortar una tanda de recencia como para el orden final de los
        20 (del que salen 10, 5 y Súper Mágico por recorte)."""
        v = valores[n]
        return (v['tabla'], v['grupos'], v['pintas'], v['comb'],
                v['cruce'], v['mayoria'], v['azar'])

    def _seleccionar_veinte(self, candidatos, valores):
        """Arma el conjunto de hasta 20 candidatos caminando el historial de
        salidas de este sorteo (los dos turnos mezclados) de la más reciente
        hacia atrás: en cada paso entran los candidatos que comparten línea
        o terminal con esa salida y todavía no habían entrado por una salida
        más reciente. Cuando una salida trae más candidatos nuevos de los
        que faltan para 20, se cortan con `_clave_cascada`.

        Si el historial se agota antes de llegar a 20 (sorteo con poco
        historial, o muchos candidatos), lo que falta se completa con los
        candidatos que quedaron afuera, ordenados también por la cascada.

        Devuelve (orden_final, origen): `orden_final` son los números en el
        orden que van a tener los 20 (y de ahí salen 10 y 5), y `origen` es
        {número: salida que lo trajo (o None si entró por la cascada al
        agotarse el historial)}, para mostrarlo en el desglose."""
        self.ensure_one()
        objetivo = min(20, len(candidatos))
        outputs = self._last_output(limit=MAX_SALIDAS_HISTORIAL)

        def clave(n):
            return self._clave_cascada(valores, n)

        seleccionados, vistos, origen = [], set(), {}
        for output in outputs:
            if len(seleccionados) >= objetivo:
                break
            ref = output.number_id.name
            nuevos = sorted(
                (n for n in candidatos
                 if n not in vistos and _comparte_digito(n, ref)),
                key=clave, reverse=True)
            if not nuevos:
                continue
            lugar = objetivo - len(seleccionados)
            elegidos = nuevos[:lugar]
            for n in elegidos:
                origen[n] = output
            seleccionados.extend(elegidos)
            vistos.update(elegidos)

        if len(seleccionados) < objetivo:
            restantes = sorted(
                (n for n in candidatos if n not in vistos),
                key=clave, reverse=True)
            faltan = objetivo - len(seleccionados)
            seleccionados.extend(restantes[:faltan])

        orden_final = sorted(seleccionados, key=clave, reverse=True)
        return orden_final, origen

    def _orden_completar_numeros(self):
        """Los números de `number_ids` en el mismo orden que arma el botón
        "Completar números": primero los 20 (o menos, ver
        `_seleccionar_veinte`) y detrás el resto de los candidatos, ambos
        tramos ordenados por la cascada de desempate.

        Es el método que reusa la Tómbola de la Quiniela Uruguay para
        puntear sus 20 premios exactamente igual que una predicción
        individual, sin tener que grabar 20 `lottery.prediction` de más."""
        self.ensure_one()
        candidatos = sorted(self.number_ids.mapped('name'))
        valores, _ctx = self._valores_cascada(candidatos)
        veinte, _origen = self._seleccionar_veinte(candidatos, valores)
        if len(veinte) >= len(candidatos):
            return veinte
        vistos = set(veinte)
        resto = sorted(
            (n for n in candidatos if n not in vistos),
            key=lambda n: self._clave_cascada(valores, n), reverse=True)
        return veinte + resto

    def action_completar_numeros(self):
        """Completa las listas de 20, 10, 5 y el Súper Mágico a partir de
        los números a predecir.

        Los 20 se arman caminando el historial de salidas de este sorteo
        (los dos turnos mezclados, de la más reciente hacia atrás): en cada
        paso entran los candidatos que comparten línea o terminal con esa
        salida y todavía no habían entrado por una más reciente, hasta
        juntar 20 (ver `_seleccionar_veinte`).

        Los 10 y los 5 salen de recortar esos 20, y el Súper Mágico es el
        primero de los 5 — todo un único orden, dado por la cascada de
        desempate (tabla LotoAnálisis → grupos atrasados → pintas atrasadas
        → combinaciones → cruce línea/terminal → mayoría ≥50/<50 → al azar),
        que también es la que corta una tanda de recencia cuando trae más
        candidatos de los que hacen falta para llegar a 20.

        Los atrasos de grupos y pintas son los de HOY, no los de la fecha de
        la predicción: está pensado para correrlo antes de cada salida. Las
        cuatro listas quedan editables, el botón sólo las precarga."""
        self.ensure_one()
        if len(self.number_ids) < 5:
            raise UserError(
                'Cargá primero los números a predecir (con el campo '
                'Temperatura o a mano): hacen falta al menos 5 para armar '
                'las listas de 20, 10 y 5.')

        candidatos = sorted(self.number_ids.mapped('name'))
        valores, ctx = self._valores_cascada(candidatos)
        veinte, origen = self._seleccionar_veinte(candidatos, valores)

        orden_10 = veinte[:10]
        orden_5 = orden_10[:5]
        super_magico = orden_5[0] if orden_5 else False

        Number = self.env['lottery.number']

        def ids(numeros):
            return Number.search([('name', 'in', numeros)]).ids

        listas = {20: veinte, 10: orden_10, 5: orden_5}
        vals = {
            'number_ids_20': [(6, 0, ids(listas[20]))],
            'number_ids_10': [(6, 0, ids(listas[10]))],
            'number_ids_5': [(6, 0, ids(listas[5]))],
            'score_html': self._render_scores_html(
                candidatos, valores, ctx, listas, origen),
        }
        if super_magico:
            vals['super_magico_id'] = ids([super_magico])[0]
        self.write(vals)
        return True

    # ── Render del desglose ────────────────────────────────────────────────

    @staticmethod
    def _fmt_pts(valor):
        return ('%.1f' % valor).rstrip('0').rstrip('.') or '0'

    def _render_scores_html(self, candidatos, valores, ctx, listas, origen):
        """`listas` es {20: [...], 10: [...], 5: [...]} en el orden final de
        la cascada. `origen` es {número: salida que lo trajo a los 20} —
        los que faltan ahí entraron por la cascada al agotarse el
        historial."""
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
            items = ' · '.join(
                '%s <span class="text-muted">(%d atrasos, %s)</span>'
                % (d['name'], d['atraso'], d['origen']) for d in det)
            return ('<p class="small mb-1"><span class="text-muted">%s:</span> '
                    '%s</p>' % (titulo, items))

        def celda_tabla(v):
            if not v['tabla']:
                return '<td class="text-center text-muted">·</td>'
            return ('<td class="text-center">%s <span class="text-muted" '
                    'style="font-size:10px;">(d%d, %s)</span></td>'
                    % (fmt(v['tabla']), v['tabla_dist'], v['tabla_origen']))

        def celda_bool(valor):
            return ('<td class="text-center">%s</td>'
                    % ('✓' if valor else '<span class="text-muted">·</span>'))

        def celda_origen(n):
            o = origen.get(n)
            if o is None:
                return ('<td class="text-center text-muted" '
                        'style="font-size:11px;">cascada</td>')
            return ('<td class="text-center" style="font-size:11px;">'
                    '%02d <span class="text-muted">(%s %s)</span></td>'
                    % (o.number_id.name, o.date.strftime('%d/%m'),
                       turn_lbl.get(o.turn_day, o.turn_day)[:1]))

        aviso = ''
        if len(candidatos) < 20:
            aviso = ('<div class="alert alert-warning py-2 small">Sólo hay %d '
                     'números a predecir: las listas se llenaron con los que '
                     'había.</div>' % len(candidatos))

        en_5, en_10, en_20 = (set(listas[5]), set(listas[10]),
                              set(listas[20]))
        fuera = sorted(
            (n for n in candidatos if n not in en_20),
            key=lambda n: self._clave_cascada(valores, n), reverse=True)

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', 'Entró por', 'Tabla', 'Grupos', 'Pintas',
                      'Comb.', 'Cruce', 'Mayoría'))

        def fila_html(i, n, mostrar_origen):
            v = valores[n]
            if n in en_5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif n in en_10:
                fondo, corte = '#fff1e0', ' · 10'
            elif n in en_20:
                fondo, corte = '#f1f3f5', ' · 20'
            else:
                fondo, corte = '', ''
            origen_html = (celda_origen(n) if mostrar_origen else
                          '<td class="text-center text-muted">—</td>')
            return (
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td>'
                '<td class="text-center"><b>%02d</b></td>'
                '%s%s'
                '<td class="text-center">%s</td>'
                '<td class="text-center">%s</td>'
                '<td class="text-center">%d</td>'
                '%s%s</tr>' % (
                    fondo, i, corte, n, origen_html, celda_tabla(v),
                    fmt(v['grupos']), fmt(v['pintas']), v['comb'],
                    celda_bool(v['cruce']), celda_bool(v['mayoria'])))

        cuerpo = [fila_html(i + 1, n, True) for i, n in enumerate(listas[20])]
        if fuera:
            cuerpo.append(
                '<tr><td colspan="9" class="text-center text-muted small">'
                '— fuera de los 20: no compartieron dígito con el historial '
                'reciente — </td></tr>')
            cuerpo += [fila_html(i + 1, n, False)
                      for i, n in enumerate(fuera, len(listas[20]))]

        turno_txt = turn_lbl.get(self.turn_day, self.turn_day)
        rango_txt = {'bajo': 'sí, a favor de los <50',
                    'alto': 'sí, a favor de los ≥50'}.get(
            ctx['rango_mayoria'], 'no (empate o sin datos)')
        return """
            <div>
                %s
                <p class="small mb-1">
                    <span class="text-muted">Ventana de combinaciones:</span>
                    %d salidas usadas (pedidas %d) ·
                    <span class="text-muted">Último número (general, usado
                    también para el cruce línea/terminal):</span> %s ·
                    <span class="text-muted">Último de %s:</span> %s ·
                    <span class="text-muted">Mayoría últimos %d:</span> %s
                </p>
                %s
                <p class="text-muted small mb-2">
                    Fondo violeta: los 5 · naranja: los 10 · gris: los 20.
                    Los 20 salen de caminar el historial de salidas (columna
                    <b>Entró por</b>: la salida que trajo a ese número
                    compartiendo línea o terminal con ella; "cascada" si
                    entró porque el historial se agotó antes de llegar a 20).
                    Dentro de eso, y para ordenar los 20 (de donde salen 10,
                    5 y Súper Mágico por recorte), manda la cascada Tabla →
                    Grupos → Pintas → Comb. → Cruce → Mayoría → azar: cada
                    columna sólo desempata a la anterior. Tabla muestra la
                    distancia en casillas a la tabla que le dio mejor factor
                    (general o el turno); Cruce y Mayoría son sí/no. Los
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
               salida(ctx['last_turno']), len(ctx['ultimos_mayoria']),
               rango_txt,
               ''.join(detalle(t, d) for t, d in ctx['detalles']),
               cabeza, ''.join(cuerpo))


class LotteryPredictionTerna(models.Model):
    """Terna (número de 3 cifras) a predecir, colgada de lottery.prediction.
    Ver el comentario junto a terna_ids: se cargan sin importar el premio."""
    _name = 'lottery.prediction.terna'
    _description = 'Terna a predecir'
    _order = 'terna'

    prediction_id = fields.Many2one(
        'lottery.prediction', string='Predicción',
        required=True, ondelete='cascade', index=True)
    # Char, no Integer: un Integer se come el 0 a la izquierda (098 → 98) y
    # la terna deja de mostrarse como se cargó.
    terna = fields.Char(
        string='Terna', required=True, size=3,
        help='Número de 3 cifras (000-999) que se predice, con el 0 a la '
             'izquierda si hace falta (ej. 098).')

    _sql_constraints = [
        ('terna_unique_por_prediccion', 'unique(prediction_id, terna)',
         'Esa terna ya está cargada en esta predicción.'),
    ]

    @api.constrains('terna')
    def _check_terna_formato(self):
        for rec in self:
            if not rec.terna or not re.fullmatch(r'\d{3}', rec.terna):
                raise ValidationError(
                    'La terna tiene que ser un número de 3 cifras, entre '
                    '000 y 999 (con el 0 a la izquierda si hace falta).')

    @api.depends('terna')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.terna or ''


class LotteryPredictionTombolaLinea(models.Model):
    """Línea de 7 números de Tómbola a predecir, colgada de
    lottery.prediction. Ver el comentario junto a tombola_linea_ids: cada
    línea es una combinación completa a jugar, no una lista suelta de
    números sueltos como sería con un many2many."""
    _name = 'lottery.prediction.tombola.linea'
    _description = 'Línea de Tómbola a predecir'

    prediction_id = fields.Many2one(
        'lottery.prediction', string='Predicción',
        required=True, ondelete='cascade', index=True)
    numero_1 = fields.Many2one('lottery.number', string='Número 1', required=True)
    numero_2 = fields.Many2one('lottery.number', string='Número 2', required=True)
    numero_3 = fields.Many2one('lottery.number', string='Número 3', required=True)
    numero_4 = fields.Many2one('lottery.number', string='Número 4', required=True)
    numero_5 = fields.Many2one('lottery.number', string='Número 5', required=True)
    numero_6 = fields.Many2one('lottery.number', string='Número 6', required=True)
    numero_7 = fields.Many2one('lottery.number', string='Número 7', required=True)

    @api.depends('numero_1.name', 'numero_2.name', 'numero_3.name',
                'numero_4.name', 'numero_5.name', 'numero_6.name', 'numero_7.name')
    def _compute_display_name(self):
        for rec in self:
            numeros = (rec.numero_1, rec.numero_2, rec.numero_3, rec.numero_4,
                      rec.numero_5, rec.numero_6, rec.numero_7)
            rec.display_name = ' - '.join('%02d' % n.name for n in numeros if n)
