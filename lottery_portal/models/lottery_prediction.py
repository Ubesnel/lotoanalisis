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

# La columna de centenas del MISMO bloque, en paralelo a TEMPERATURE_KEY: el
# snapshot guarda calientes/restantes/fríos por separado para números y para
# centenas, y una predicción usa siempre las dos mitades del mismo bloque (si
# los números son los restantes, las centenas son las de restantes).
CENTENA_TEMPERATURE_KEY = {
    'hot': 'centenas',
    'cold': 'centenas_cold',
    'remaining': 'centenas_remaining',
}

# Cómo se reparten las 7 ternas entre los 5 números, por orden de
# importancia: los dos primeros se llevan dos ternas cada uno (con las dos
# centenas más importantes) y los otros tres una sola (con la más
# importante). 2+2+1+1+1 = 7.
TERNAS_POR_PUESTO = (2, 2, 1, 1, 1)

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

# ── Tabla de 30 (26/09/2026) ───────────────────────────────────────────────
# Los 30 son los 20 de siempre MÁS diez que se eligen aparte, al revés que
# aquéllos: en vez de los que comparten dígito con las salidas recientes, los
# que NO comparten ninguno. Nada del cálculo de 20/10/5/Súper Mágico cambia —
# esto se calcula después y por su cuenta (ver `_seleccionar_diez_extra`).
#
# Cuántos dígitos distintos cuentan como "las salidas recientes": se caminan
# las salidas de la más nueva hacia atrás tomando decena y unidad de cada una
# hasta juntar estos cuatro, así el filtro no depende de cuántas salidas haga
# falta recorrer ni de cuántos candidatos haya.
DIGITOS_RECIENTES = 4

# Cuántos números se suman a los 20 para llegar a la tabla de 30.
EXTRA_PARA_30 = 10

# ── Algoritmo de "Completar números" (01/10/2026) ──────────────────────────
# La predicción elige con qué algoritmo se llenan las listas. El 1 es el de
# siempre (tandas de recencia + cascada + señales de recorte + tabla de 30);
# el 2 es uno nuevo. El texto de cada uno es lo que muestra el formulario en
# "Criterio del algoritmo" — si cambia la lógica, hay que actualizarlo acá.
DESCRIPCION_ALGORITMO = {
    '1': (
        "20 números: se recorren las salidas de este sorteo de la más "
        "reciente hacia atrás (los dos turnos mezclados) y en cada una entran "
        "los candidatos que comparten línea o terminal con ese número y no "
        "habían entrado antes, hasta juntar 20. Si una salida trae más de los "
        "que faltan, se cortan con la cascada de desempate.\n\n"
        "Cascada de desempate (cada señal sólo desempata a la anterior): "
        "1) Tabla LotoAnálisis (general y turno, la mejor de las dos), "
        "2) grupos más atrasados, 3) pintas más atrasadas, 4) combinaciones, "
        "5) cruce línea/terminal con la última salida, 6) mayoría ≥50/<50 de "
        "los últimos 10 sorteos, 7) al azar.\n\n"
        "10 números: de los 20, primero los que están en las 3 líneas o los 3 "
        "terminales recomendados (el cruce vale doble); la cascada desempata.\n\n"
        "5 números: de los 10, primero los que coinciden con los 2 grupos, 2 "
        "líneas y 2 terminales más atrasados del día de la semana; la cascada "
        "desempata.\n\n"
        "Súper Mágico: de los 5, el que es acompañante en más de las tres "
        "tablas LotoAnálisis (general, tarde y noche).\n\n"
        "30 números: los 20 más diez de los que quedaron afuera, con el "
        "criterio inverso: primero los que NO comparten dígito con las "
        "salidas recientes y están en líneas o terminales recomendados."
    ),
    '2': (
        "30 números: la misma caminata que arma los 20 en el Algoritmo 1, "
        "pero hasta juntar 30: se recorren las salidas de la más reciente "
        "hacia atrás y entran los que comparten línea o terminal con cada "
        "una; si una salida trae de más, se cortan con la cascada de "
        "siempre.\n\n"
        "20 números: de los 30, los que tienen en línea o terminal alguno de "
        "los 5 dígitos distintos más recientes. Si sobran o faltan, ordena: "
        "1) coincide con alguno de los 3 dígitos más recientes, 2) grupos "
        "más atrasados, 3) tabla LotoAnálisis, pintas, combinaciones, cruce, "
        "mayoría y azar.\n\n"
        "10 números: de los 20, los que tienen alguno de los 2 dígitos "
        "distintos más recientes. Si sobran o faltan: tabla → pintas → "
        "grupos → azar.\n\n"
        "Dígitos recientes (5, 3 y 2): si una salida aporta más dígitos de "
        "los que faltan, gana el que está en más líneas/terminales "
        "recomendados, después el que tiene más acompañantes en la tabla "
        "general y después en la del turno.\n\n"
        "5 números: de los 10, los cruzados con la última salida (con 34: "
        "línea 40-49 o terminal 3). Si sobran o faltan: tabla → pintas → "
        "grupos → azar.\n\n"
        "Súper Mágico: de los 5, el que tiene la línea en las 3 recomendadas; "
        "si empatan, el terminal en los 3 recomendados; si sigue el empate, "
        "el que pertenece a la mejor línea o mejor terminal recomendado."
    ),
}

# Algoritmo 2: los 30 salen de la caminata de recencia (la misma que arma
# los 20 en el Algoritmo 1, con objetivo 30). De esos 30, los 20 son los que
# tienen alguno de los DIGITOS_20_ALG2 dígitos distintos más recientes; si
# sobran o faltan, se corta / completa con: coincidir con los
# DIGITOS_CERCANOS_ALG2 más recientes (que son los primeros de aquellos
# cinco) → grupos más atrasados → resto de la cascada.
DIGITOS_20_ALG2 = 5
DIGITOS_CERCANOS_ALG2 = 3
# Los 10 salen de los 20: los que tienen alguno de los DIGITOS_10_ALG2
# dígitos distintos más recientes. Esos dígitos se juntan con
# `_digitos_recientes_alg2`, que cuando una salida aporta más dígitos de los
# que faltan (22 → {2}, después 34 → 3 y 4 pero falta uno) elige con
# recomendadas → tabla general → tabla del turno.
DIGITOS_10_ALG2 = 2

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

    sorteo_source_code = fields.Char(
        related='sorteo_id.source_code', string='Código de origen del sorteo',
        help='Sólo para condicionar la vista: las ternas existen únicamente '
             'en los sorteos de Quiniela Uruguay.')

    algoritmo = fields.Selection([
        ('1', 'Algoritmo 1'),
        ('2', 'Algoritmo 2'),
    ], string='Algoritmo', default='1', required=True,
        help='Con qué criterio llena el botón "Completar números" las listas '
             'de 30, 20, 10, 5 y el Súper Mágico.')
    algoritmo_descripcion = fields.Text(
        string='Criterio del algoritmo',
        compute='_compute_algoritmo_descripcion',
        help='Cómo completa los números el algoritmo elegido.')

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
    number_ids_30 = fields.Many2many(
        'lottery.number', 'lottery_prediction_number_30_rel',
        'prediction_id', 'number_id',
        string='30 Números a predecir',
        help='Los 20 más diez elegidos entre los candidatos que quedaron '
             'afuera, con el criterio inverso: los que NO comparten dígito '
             'con las salidas recientes.')
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
    numbers_count_30 = fields.Integer(
        string='Cantidad 30', compute='_compute_numbers_count_30', store=True)
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
    cumplida_30 = fields.Boolean(
        'Cumplida en 30?', default=False, index=True,
        help='El número salido estaba entre los 30 Números a predecir.')
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

    @api.depends('algoritmo')
    def _compute_algoritmo_descripcion(self):
        for rec in self:
            rec.algoritmo_descripcion = DESCRIPCION_ALGORITMO.get(
                rec.algoritmo, '')

    @api.depends('number_ids')
    def _compute_numbers_count(self):
        for rec in self:
            rec.numbers_count = len(rec.number_ids)

    @api.depends('number_ids_30')
    def _compute_numbers_count_30(self):
        for rec in self:
            rec.numbers_count_30 = len(rec.number_ids_30)

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

    @api.model
    def centenas_by_temperature(self, sorteo, turn_day, temperature):
        """Centenas calientes / restantes / frías de ese sorteo y turno, tal
        como las dejó el último artículo generado (`ranking_snapshot`).

        Es el equivalente de `numbers_by_temperature` para la otra mitad del
        mismo bloque. Devuelve una LISTA de strings de un dígito y no un
        recordset justamente porque acá el orden es el dato: la primera es la
        centena más importante.

        Lista vacía si el sorteo no usa centena o todavía no tiene snapshot."""
        if not (sorteo and turn_day and temperature):
            return []
        try:
            snapshot = json.loads(sorteo.ranking_snapshot or '{}')
        except (ValueError, TypeError):
            return []
        items = snapshot.get(turn_day, {}).get(
            CENTENA_TEMPERATURE_KEY.get(temperature), []) or []
        centenas = []
        for item in items:
            raw = item.get('name') if isinstance(item, dict) else item
            try:
                centenas.append(str(int(raw)))
            except (ValueError, TypeError):
                continue
        return centenas

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

    def _seleccionar_veinte(self, candidatos, valores, cantidad=20):
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
        agotarse el historial)}, para mostrarlo en el desglose.

        `cantidad` es cuántos junta la caminata: 20 en el Algoritmo 1, 30 en
        el Algoritmo 2 (que arma así su tabla de 30)."""
        self.ensure_one()
        objetivo = min(cantidad, len(candidatos))
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

    def _senales_recorte(self, candidatos):
        """Señales de los tres recortes: 20 → 10, 10 → 5 y Súper Mágico.

        Cada una es {número: cuántas coincidencias} y manda ANTES que la
        cascada: la cascada pasa a desempatar dentro de cada nivel.

        - `rec_lt`  (20 → 10): 3 líneas y 3 terminales recomendados para
          esta fecha y turno. Vale 2 si el número está en una línea Y en un
          terminal recomendados (los del cruce), 1 si está en uno solo.
        - `atr_dia` (10 → 5): 2 grupos + 2 líneas + 2 terminales más
          atrasados del DÍA DE LA SEMANA de la predicción. De 0 a 3.
        - `tablas`  (5 → Súper Mágico): en cuántas de las tres tablas
          LotoAnálisis (general, tarde y noche) el número es acompañante de
          la última salida de esa serie. De 0 a 3.
        """
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        day = WEEKDAY_CODES[self.date.weekday()]

        reco = stats.get_lineas_terminales_probables(
            self.turn_day, str(self.date), sorteo_id=self.sorteo_id.id) or {}
        lineas_reco = {l['idx'] for l in reco.get('lineas') or []}
        term_reco = {t['idx'] for t in reco.get('terminales') or []}
        rec_lt = {}
        for n in candidatos:
            linea, terminal = _digitos(n)
            rec_lt[n] = int(linea in lineas_reco) + int(terminal in term_reco)

        atrasados = stats.get_atrasados_dia_semana(self.sorteo_id.id, day, 2)
        conjuntos = [(item['name'], set(item['numeros']))
                     for familia in ('grupos', 'lineas', 'terminales')
                     for item in atrasados.get(familia) or []]
        atr_dia, atr_det = {}, {}
        for n in candidatos:
            pega = [nombre for nombre, nums in conjuntos if n in nums]
            atr_dia[n] = len(pega)
            atr_det[n] = pega

        tablas, tablas_det = {n: 0 for n in candidatos}, {}
        refs = []
        for turno in ('general', 'afternoon', 'evening'):
            ref = (self._last_output() if turno == 'general'
                   else self._last_output(turn=turno))
            refs.append((turno, ref))
            if not ref:
                continue
            acomp = self._acompanantes(turno, ref.number_id.name)
            for n in candidatos:
                if acomp.get(n):
                    tablas[n] += 1
                    tablas_det.setdefault(n, []).append(turno)

        ctx = {
            'lineas_reco': sorted(lineas_reco),
            'term_reco': sorted(term_reco),
            'atrasados': conjuntos,
            'atr_det': atr_det,
            'tablas_det': tablas_det,
            'refs_tablas': refs,
            'dia': day,
        }
        return {'rec_lt': rec_lt, 'atr_dia': atr_dia, 'tablas': tablas}, ctx

    # ── Tabla de 30 ─────────────────────────────────────────────

    def _digitos_recientes(self, cantidad=DIGITOS_RECIENTES):
        """Los `cantidad` dígitos distintos más recientes de este sorteo.

        Se caminan las salidas de la más nueva hacia atrás tomando decena y
        unidad de cada una (en ese orden, que es como se lee el número) y se
        corta al juntar `cantidad` dígitos diferentes. Una salida capicúa
        como 77 aporta uno solo, así que a veces hacen falta tres salidas
        para llegar a cuatro dígitos.

        Ojo, no es lo que hace la selección de los 20: aquélla camina salida
        por salida y se detiene cuando llenó la lista, así que consume una
        cantidad variable de salidas. Ésta es una ventana fija, a propósito,
        para que el filtro de los diez no dependa de cuántos candidatos
        hubiera ese día."""
        self.ensure_one()
        digitos = []
        for output in self._last_output(limit=MAX_SALIDAS_HISTORIAL):
            for d in _digitos(output.number_id.name):
                if d not in digitos:
                    digitos.append(d)
            if len(digitos) >= cantidad:
                break
        return set(digitos[:cantidad])

    def _seleccionar_diez_extra(self, candidatos, veinte, valores, senales,
                                cantidad=EXTRA_PARA_30):
        """Los diez que se suman a los 20 para armar la tabla de 30.

        Salen de los candidatos que NO entraron en los 20 (y como
        5 ⊂ 10 ⊂ 20, eso es exactamente `candidatos - veinte`), con el
        criterio inverso al de aquéllos:

        1º  los que no comparten ninguno de los `DIGITOS_RECIENTES` dígitos
            recientes Y están en una línea o terminal recomendados;
        2º  los que no comparten dígito aunque no estén en las recomendadas;
        3º  el resto de los sobrantes, para completar los diez.

        Dentro de cada escalón ordena: primero cuántas recomendadas toca
        (el cruce línea+terminal vale 2), después los que NO aparecen en
        ninguna tabla LotoAnálisis —el desempate pedido— y al final la
        cascada de siempre.

        No toca nada de lo que ya calcularon `_seleccionar_veinte` ni
        `_senales_recorte`: recibe sus resultados y elige entre las sobras."""
        self.ensure_one()
        ya_estan = set(veinte)
        sobrantes = [n for n in candidatos if n not in ya_estan]
        if not sobrantes:
            return []

        digitos = self._digitos_recientes()
        rec_lt = senales.get('rec_lt') or {}
        tablas = senales.get('tablas') or {}

        def limpio(n):
            """No comparte decena ni unidad con los dígitos recientes."""
            return not (set(_digitos(n)) & digitos)

        def clave(n):
            return (rec_lt.get(n, 0),
                    tablas.get(n, 0) == 0) + self._clave_cascada(valores, n)

        escalones = [
            [n for n in sobrantes if limpio(n) and rec_lt.get(n, 0)],
            [n for n in sobrantes if limpio(n) and not rec_lt.get(n, 0)],
            sobrantes,
        ]
        elegidos, vistos = [], set()
        for escalon in escalones:
            if len(elegidos) >= cantidad:
                break
            nuevos = sorted((n for n in escalon if n not in vistos),
                            key=clave, reverse=True)
            elegidos.extend(nuevos[:cantidad - len(elegidos)])
            vistos = set(elegidos)
        return elegidos

    def action_completar_numeros(self):
        """Completa las listas de 30, 20, 10, 5 y el Súper Mágico con el
        algoritmo elegido en la predicción (campo `algoritmo`)."""
        self.ensure_one()
        if len(self.number_ids) < 5:
            raise UserError(
                'Cargá primero los números a predecir (con el campo '
                'Temperatura o a mano): hacen falta al menos 5 para armar '
                'las listas de 20, 10 y 5.')
        return self._grabar_listas(self._calcular_listas())

    # ── Algoritmo 2 ─────────────────────────────────────────────

    @staticmethod
    def _recortar_alg2(base, entra, clave, cantidad):
        """Recorte común a los 20, 10 y 5 del Algoritmo 2.

        De `base` entran primero los que cumplen `entra(n)`, ordenados por
        `clave`; si son más de `cantidad` se cortan, y si son menos se
        completa con el resto de `base`, también por `clave`. Devuelve la
        lista en ese orden: los que cumplen primero y los de relleno
        después."""
        cumplen = sorted((n for n in base if entra(n)), key=clave,
                         reverse=True)[:cantidad]
        if len(cumplen) < cantidad:
            ya_estan = set(cumplen)
            relleno = sorted((n for n in base if n not in ya_estan),
                             key=clave, reverse=True)
            cumplen += relleno[:cantidad - len(cumplen)]
        return cumplen

    def _recomendadas_alg2(self):
        """(líneas, terminales) recomendados para esta fecha y turno, cada
        uno como lista en el orden del pronóstico (la 1ª es la mejor). Es
        el mismo `get_lineas_terminales_probables` que usa el Algoritmo 1
        para el recorte 20 → 10."""
        self.ensure_one()
        reco = self.env['lottery.stats.service'].sudo() \
            .get_lineas_terminales_probables(
                self.turn_day, str(self.date),
                sorteo_id=self.sorteo_id.id) or {}
        return ([l['idx'] for l in reco.get('lineas') or []],
                [t['idx'] for t in reco.get('terminales') or []])

    def _digitos_recientes_alg2(self, cantidad, lineas_reco, term_reco):
        """Los `cantidad` dígitos distintos más recientes, como
        `_digitos_recientes`, pero desempatando cuando una salida aporta
        más dígitos nuevos de los que faltan.

        Ej: la anterior fue 22 (aporta el 2) y antes 34 (aporta 3 y 4) y
        hacen falta 2: entra el 2 y entre el 3 y el 4 se elige por, en
        este orden:
          1) en cuántas recomendadas está (línea y terminal recomendados
             de esta fecha y turno: 0, 1 o 2),
          2) cuántos acompañantes de la última salida en la tabla
             LotoAnálisis general tienen ese dígito (en línea o terminal),
          3) ídem en la tabla del turno a predecir con la última salida de
             ese turno.
        Si todo empata queda el orden de lectura (decena antes que unidad).

        Devuelve una lista en el orden en que entraron."""
        self.ensure_one()
        last_general = self._last_output()
        last_turno = self._last_output(turn=self.turn_day)
        acomp_general = (self._acompanantes('general', last_general.number_id.name)
                         if last_general else {})
        acomp_turno = (self._acompanantes(self.turn_day, last_turno.number_id.name)
                       if last_turno else {})

        def con_digito(acomp, d):
            return sum(1 for n in acomp if d in _digitos(n))

        def clave(d):
            return (int(d in lineas_reco) + int(d in term_reco),
                    con_digito(acomp_general, d),
                    con_digito(acomp_turno, d))

        digitos = []
        for output in self._last_output(limit=MAX_SALIDAS_HISTORIAL):
            nuevos = []
            for d in _digitos(output.number_id.name):
                if d not in digitos and d not in nuevos:
                    nuevos.append(d)
            faltan = cantidad - len(digitos)
            if len(nuevos) > faltan:
                # sorted es estable: a igualdad queda decena antes que unidad.
                nuevos = sorted(nuevos, key=clave, reverse=True)[:faltan]
            digitos.extend(nuevos)
            if len(digitos) >= cantidad:
                break
        return digitos

    @staticmethod
    def _clave_super_magico_alg2(n, lineas_reco, term_reco):
        """Orden del Súper Mágico del Algoritmo 2: 1) su línea está en las
        3 recomendadas, 2) su terminal está en los 3 recomendados, 3) la
        mejor posición que ocupa su línea o su terminal en esas listas (la
        1ª recomendada gana)."""
        linea, terminal = _digitos(n)
        puestos = []
        if linea in lineas_reco:
            puestos.append(lineas_reco.index(linea))
        if terminal in term_reco:
            puestos.append(term_reco.index(terminal))
        mejor = -min(puestos) if puestos else -len(lineas_reco) - len(term_reco)
        return (linea in lineas_reco, terminal in term_reco, mejor)

    def _calcular_algoritmo_2(self):
        """Algoritmo 2: calcula las listas de 30, 20, 10, 5 y el Súper
        Mágico a partir de los números a predecir (sin grabar nada; el
        Súper Mágico queda 1º de los 5). Cada lista se recorta de
        la anterior (5 ⊂ 10 ⊂ 20 ⊂ 30):

        - 30: la caminata de recencia del Algoritmo 1 (`_seleccionar_veinte`)
          con objetivo 30, cortando cada tanda con la cascada de siempre.
        - 20: los que tienen alguno de los `DIGITOS_20_ALG2` dígitos más
          recientes. Corta/completa: coincide con alguno de los
          `DIGITOS_CERCANOS_ALG2` más recientes → grupos → tabla → pintas →
          combinaciones → cruce → mayoría → azar.
        - 10: los que tienen alguno de los `DIGITOS_10_ALG2` dígitos más
          recientes (con desempate de dígitos, ver
          `_digitos_recientes_alg2`). Corta/completa: tabla → pintas →
          grupos → azar.
        - 5: los cruzados con la última salida general (la línea de la
          anterior pasa a terminal, o el terminal a línea: con 34, la línea
          40-49 o el terminal 3). Corta/completa: tabla → pintas → grupos →
          azar.
        - Súper Mágico: de los 5, ver `_clave_super_magico_alg2`; si sigue
          el empate, el orden de los 5.

        Las listas quedan editables, el botón sólo las precarga."""
        self.ensure_one()
        candidatos = sorted(self.number_ids.mapped('name'))
        valores, ctx = self._valores_cascada(candidatos)
        lineas_reco, term_reco = self._recomendadas_alg2()

        # Los tres juegos de dígitos usan el mismo desempate cuando una
        # salida aporta de más, así que el de 2 ⊂ el de 3 ⊂ el de 5.
        dig_20 = set(self._digitos_recientes_alg2(
            DIGITOS_20_ALG2, lineas_reco, term_reco))
        dig_cercanos = set(self._digitos_recientes_alg2(
            DIGITOS_CERCANOS_ALG2, lineas_reco, term_reco))
        dig_10 = self._digitos_recientes_alg2(
            DIGITOS_10_ALG2, lineas_reco, term_reco)

        def comparte(digitos):
            return lambda n: bool(set(_digitos(n)) & set(digitos))

        def clave_20(n):
            v = valores[n]
            return (comparte(dig_cercanos)(n), v['grupos'], v['tabla'],
                    v['pintas'], v['comb'], v['cruce'], v['mayoria'],
                    v['azar'])

        def clave_10_5(n):
            v = valores[n]
            return (v['tabla'], v['pintas'], v['grupos'], v['azar'])

        treinta, origen = self._seleccionar_veinte(
            candidatos, valores, cantidad=20 + EXTRA_PARA_30)
        veinte = self._recortar_alg2(treinta, comparte(dig_20), clave_20, 20)
        diez = self._recortar_alg2(veinte, comparte(dig_10), clave_10_5, 10)
        # `cruce` de la cascada ya es contra la última salida general.
        cinco = self._recortar_alg2(
            diez, lambda n: valores[n]['cruce'], clave_10_5, 5)
        # sorted es estable: a igualdad de recomendadas queda el orden de
        # los 5 (tabla → pintas → grupos → azar).
        cinco = sorted(
            cinco, key=lambda n: self._clave_super_magico_alg2(
                n, lineas_reco, term_reco), reverse=True)
        super_magico = cinco[0] if cinco else False

        ctx.update({
            'dig_20': sorted(dig_20),
            'dig_cercanos': sorted(dig_cercanos),
            'dig_10': dig_10,
            'lineas_reco': lineas_reco,
            'term_reco': term_reco,
        })

        return {
            'listas': {30: treinta, 20: veinte, 10: diez, 5: cinco},
            'super_magico': super_magico,
            'candidatos': candidatos, 'valores': valores, 'ctx': ctx,
            'origen': origen,
        }

    def _calcular_algoritmo_1(self):
        """Algoritmo 1: calcula las listas de 30, 20, 10, 5 y el Súper
        Mágico a partir de los números a predecir (sin grabar nada).

        La de 30 se calcula APARTE y al final: son los 20 de abajo más diez
        elegidos entre los candidatos que quedaron afuera, con el criterio
        inverso (ver `_seleccionar_diez_extra`). Nada de lo que sigue cambia
        por eso — 20, 10, 5 y Súper Mágico salen igual que siempre.

        Los 20 se arman caminando el historial de salidas de este sorteo
        (los dos turnos mezclados, de la más reciente hacia atrás): en cada
        paso entran los candidatos que comparten línea o terminal con esa
        salida y todavía no habían entrado por una más reciente, hasta
        juntar 20 (ver `_seleccionar_veinte`).

        Los 10, los 5 y el Súper Mágico se recortan de esos 20, pero cada
        recorte tiene su propia señal, que manda antes que la cascada (ver
        `_senales_recorte`):

        - 20 → 10: estar en las 3 líneas o los 3 terminales recomendados
          para esta fecha y turno (los del cruce, que están en los dos,
          pesan doble).
        - 10 → 5: coincidir con los 2 grupos, 2 líneas y 2 terminales más
          atrasados del día de la semana de la predicción.
        - 5 → Súper Mágico: aparecer en más de las tres tablas LotoAnálisis
          (general, tarde y noche).

        La cascada de desempate (tabla LotoAnálisis → grupos atrasados →
        pintas atrasadas → combinaciones → cruce línea/terminal → mayoría
        ≥50/<50 → al azar) desempata dentro de cada nivel de esas señales,
        ordena los 20 y corta una tanda de recencia cuando trae más
        candidatos de los que hacen falta para llegar a 20.

        Los atrasos de grupos y pintas son los de HOY, no los de la fecha de
        la predicción: está pensado para correrlo antes de cada salida. Las
        cuatro listas quedan editables, el botón sólo las precarga."""
        self.ensure_one()
        candidatos = sorted(self.number_ids.mapped('name'))
        valores, ctx = self._valores_cascada(candidatos)
        veinte, origen = self._seleccionar_veinte(candidatos, valores)
        senales, ctx_sen = self._senales_recorte(candidatos)
        ctx.update(ctx_sen)
        ctx['senales'] = senales

        def por_senal(senal):
            """Orden: primero la señal del recorte, y la cascada desempata
            dentro de cada nivel."""
            return lambda n: ((senal.get(n, 0),)
                              + self._clave_cascada(valores, n))

        orden_10 = sorted(
            veinte, key=por_senal(senales['rec_lt']), reverse=True)[:10]
        orden_5 = sorted(
            orden_10, key=por_senal(senales['atr_dia']), reverse=True)[:5]
        # El Súper Mágico es el primero de los 5, ordenados por en cuántas
        # tablas aparece.
        orden_5 = sorted(
            orden_5, key=por_senal(senales['tablas']), reverse=True)
        super_magico = orden_5[0] if orden_5 else False

        # La tabla de 30 se arma recién acá, con los 20 ya cerrados: son
        # esos mismos más los diez del criterio inverso. Si en "Números a
        # predecir" hay exactamente 30, los sobrantes son justo diez y
        # entran todos por el último escalón, así que la tabla de 30 termina
        # siendo igual a los 30 cargados — sin necesidad de un caso aparte.
        treinta = veinte + self._seleccionar_diez_extra(
            candidatos, veinte, valores, senales)

        return {
            'listas': {30: treinta, 20: veinte, 10: orden_10, 5: orden_5},
            'super_magico': super_magico,
            'candidatos': candidatos, 'valores': valores, 'ctx': ctx,
            'origen': origen,
        }

    def _calcular_listas(self):
        """Corre el algoritmo elegido (`algoritmo`) SIN grabar nada y
        devuelve {'listas': {30, 20, 10, 5}, 'super_magico', ...}. Los 5
        vienen con el Súper Mágico primero.

        Es lo que hace el botón "Completar números" antes de escribir, y lo
        que reusa la Tómbola de la Quiniela Uruguay sobre predicciones en
        memoria (`new`) para cada premio, sin crear 20 predicciones."""
        self.ensure_one()
        if self.algoritmo == '2':
            return self._calcular_algoritmo_2()
        return self._calcular_algoritmo_1()

    def _grabar_listas(self, res):
        """Escribe en la predicción el resultado de `_calcular_listas`, con
        el desglose de puntajes del algoritmo que lo calculó."""
        self.ensure_one()
        Number = self.env['lottery.number']

        def ids(numeros):
            return Number.search([('name', 'in', numeros)]).ids

        listas = res['listas']
        render = (self._render_scores_html_alg2 if self.algoritmo == '2'
                  else self._render_scores_html)
        vals = {
            'number_ids_30': [(6, 0, ids(listas[30]))],
            'number_ids_20': [(6, 0, ids(listas[20]))],
            'number_ids_10': [(6, 0, ids(listas[10]))],
            'number_ids_5': [(6, 0, ids(listas[5]))],
            'score_html': render(res['candidatos'], res['valores'],
                                 res['ctx'], listas, res['origen']),
        }
        if res['super_magico'] is not False:
            vals['super_magico_id'] = ids([res['super_magico']])[0]
        self.write(vals)
        return True

    # ── Completar ternas ────────────────────────────────────────

    def _orden_de_los_cinco(self):
        """Los 5 Números a predecir ordenados por importancia decreciente.

        El 1º es SIEMPRE el Súper Mágico guardado, no el que daría un cálculo
        de hoy: es un dato ya escrito en la predicción y el puesto que más
        pesa en el reparto de ternas, así que no puede moverse porque se
        corra el botón otro día. Del 2º al 5º se reconstruye el orden con la
        cascada (`_clave_cascada`), que no se guarda en ningún lado porque
        `number_ids_5` es un Many2many y pierde el orden. La señal de tablas
        de `_senales_recorte` no entra acá: esa sólo define quién es el
        Súper Mágico, que ya viene resuelto.

        Ojo: los atrasos de esa cascada son los de HOY, así que si esto se
        corre días después de completar los números, los puestos 2 a 5 pueden
        salir permutados respecto de la corrida original. Las ternas quedan
        editables, igual que las listas de números."""
        self.ensure_one()
        cinco = self.number_ids_5.mapped('name')
        # La cascada se evalúa sobre TODOS los candidatos, como en la corrida
        # original: algunos valores dependen del conjunto, y puntuar sólo
        # sobre los 5 podría dar otro orden.
        candidatos = sorted(set(self.number_ids.mapped('name')) | set(cinco))
        valores, _ctx = self._valores_cascada(candidatos)
        super_magico = self.super_magico_id.name
        resto = sorted(
            (n for n in cinco if n != super_magico),
            key=lambda n: self._clave_cascada(valores, n), reverse=True)
        return [super_magico] + resto

    def action_completar_ternas(self):
        """Completa las 7 ternas a predecir cruzando los 5 Números con las
        centenas del mismo bloque de temperatura.

        Reparto (ver TERNAS_POR_PUESTO): el Súper Mágico y el 2º llevan dos
        ternas cada uno, con las dos centenas más importantes; el 3º, 4º y
        5º una sola, con la más importante. Siempre dan 7 ternas distintas:
        los cinco números son distintos entre sí y las dos ternas de un
        mismo número usan centenas distintas.

        Las centenas salen del bloque que marca la Temperatura de la
        predicción — restantes con restantes, calientes con calientes,
        fríos con fríos — y ese snapshot ya viene por sorteo y por turno.

        Como el de números, el botón sólo precarga: las ternas quedan
        editables."""
        self.ensure_one()
        # Import local para no adelantar la carga de quiniela_uy_ternas, que
        # en models/__init__.py va después de este archivo.
        from .quiniela_uy_ternas import SOURCE_CODE as QUINIELA_UY

        if self.sorteo_id.source_code != QUINIELA_UY:
            raise UserError(
                'Las ternas son sólo para los sorteos de Quiniela Uruguay.')
        if not self.temperature:
            raise UserError(
                'Elegí primero la Temperatura: las centenas de la terna salen '
                'del mismo bloque (calientes, restantes o fríos) del que '
                'salieron los números.')
        if len(self.number_ids_5) < 5 or not self.super_magico_id:
            raise UserError(
                'Completá primero los 5 Números a predecir y el Súper Mágico '
                'con el botón "Completar números".')

        centenas = self.centenas_by_temperature(
            self.sorteo_id, self.turn_day, self.temperature)
        if len(centenas) < 2:
            raise UserError(
                'El sorteo no tiene al menos dos centenas en el bloque '
                '"%s" de ese turno. Regenerá el artículo de calientes/'
                'restantes/fríos y volvé a intentar.'
                % dict(self._fields['temperature'].selection)[self.temperature])

        ternas = []
        for puesto, numero in enumerate(self._orden_de_los_cinco()):
            for centena in centenas[:TERNAS_POR_PUESTO[puesto]]:
                ternas.append('%s%02d' % (centena, numero))

        self.terna_ids = [(5, 0, 0)] + [(0, 0, {'terna': t}) for t in ternas]
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

        senales = ctx.get('senales') or {
            'rec_lt': {}, 'atr_dia': {}, 'tablas': {}}

        def celda_senal(cantidad, titulo):
            """Cuántas coincidencias aportó la señal de ese recorte."""
            if not cantidad:
                return '<td class="text-center text-muted">·</td>'
            return ('<td class="text-center" title="%s"><b>%d</b></td>'
                    % (titulo, cantidad))

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
        # Los diez extra de la tabla de 30 viven en el tramo de abajo (no
        # entraron a los 20), así que se tiñen distinto para poder verlos.
        en_30 = set(listas.get(30) or [])
        fuera = sorted(
            (n for n in candidatos if n not in en_20),
            key=lambda n: self._clave_cascada(valores, n), reverse=True)

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', 'Entró por', 'L/T rec.', 'Atras. día',
                      'Tablas', 'Tabla', 'Grupos', 'Pintas', 'Comb.',
                      'Cruce', 'Mayoría'))

        def fila_html(i, n, mostrar_origen):
            v = valores[n]
            if n in en_5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif n in en_10:
                fondo, corte = '#fff1e0', ' · 10'
            elif n in en_20:
                fondo, corte = '#f1f3f5', ' · 20'
            elif n in en_30:
                fondo, corte = '#e3f2fd', ' · 30'
            else:
                fondo, corte = '', ''
            origen_html = (celda_origen(n) if mostrar_origen else
                          '<td class="text-center text-muted">—</td>')
            return (
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td>'
                '<td class="text-center"><b>%02d</b></td>'
                '%s%s%s%s%s'
                '<td class="text-center">%s</td>'
                '<td class="text-center">%s</td>'
                '<td class="text-center">%d</td>'
                '%s%s</tr>' % (
                    fondo, i, corte, n, origen_html,
                    celda_senal(senales['rec_lt'].get(n, 0),
                                'línea/terminal recomendados'),
                    celda_senal(senales['atr_dia'].get(n, 0),
                                ' · '.join(ctx['atr_det'].get(n) or [])),
                    celda_senal(senales['tablas'].get(n, 0),
                                ' · '.join(ctx['tablas_det'].get(n) or [])),
                    celda_tabla(v),
                    fmt(v['grupos']), fmt(v['pintas']), v['comb'],
                    celda_bool(v['cruce']), celda_bool(v['mayoria'])))

        cuerpo = [fila_html(i + 1, n, True) for i, n in enumerate(listas[20])]
        if fuera:
            cuerpo.append(
                '<tr><td colspan="12" class="text-center text-muted small">'
                '— fuera de los 20: no compartieron dígito con el historial '
                'reciente — </td></tr>')
            cuerpo += [fila_html(i + 1, n, False)
                      for i, n in enumerate(fuera, len(listas[20]))]

        def lista_txt(valores_txt):
            return (' · '.join(valores_txt) if valores_txt
                    else '<span class="text-muted">sin datos</span>')

        dia_lbl = {'lu': 'lunes', 'ma': 'martes', 'mi': 'miércoles',
                   'ju': 'jueves', 'vi': 'viernes', 'sa': 'sábado',
                   'do': 'domingo'}.get(ctx.get('dia'), ctx.get('dia') or '')
        recortes_txt = (
            '<p class="small mb-1">'
            '<span class="text-muted">20 → 10, recomendados:</span> '
            'líneas %s · terminales %s<br/>'
            '<span class="text-muted">10 → 5, más atrasados del %s:</span> %s'
            '</p>' % (
                lista_txt(['%d' % i for i in ctx.get('lineas_reco') or []]),
                lista_txt(['%d' % i for i in ctx.get('term_reco') or []]),
                dia_lbl,
                lista_txt([nombre for nombre, _nums
                           in ctx.get('atrasados') or []])))

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
                %s
                <p class="text-muted small mb-2">
                    Fondo violeta: los 5 · naranja: los 10 · gris: los 20.
                    Los 20 salen de caminar el historial de salidas (columna
                    <b>Entró por</b>: la salida que trajo a ese número
                    compartiendo línea o terminal con ella; "cascada" si
                    entró porque el historial se agotó antes de llegar a 20).
                    De ahí, cada recorte tiene su señal propia, que manda
                    antes que la cascada: <b>L/T rec.</b> para los 10 (2 si
                    está en línea y terminal recomendados), <b>Atras. día</b>
                    para los 5 (cuántos de los 2 grupos + 2 líneas + 2
                    terminales más atrasados del día lo contienen) y
                    <b>Tablas</b> para el Súper Mágico (en cuántas de las
                    tres tablas es acompañante). Pasá el mouse por esos
                    números para ver el detalle. Dentro de cada nivel, y para
                    ordenar los 20, desempata la cascada Tabla → Grupos →
                    Pintas → Comb. → Cruce → Mayoría → azar: cada columna
                    sólo desempata a la anterior. Tabla muestra la distancia
                    en casillas a la que le dio mejor factor (general o el
                    turno); Cruce y Mayoría son sí/no. Los atrasos de grupos
                    y pintas son los del momento en que se apretó el botón.
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
               recortes_txt, cabeza, ''.join(cuerpo))

    def _render_scores_html_alg2(self, candidatos, valores, ctx, listas,
                                 origen):
        """Desglose del Algoritmo 2. `listas` es {30, 20, 10, 5} en el
        orden de cada recorte (el 1º de los 5 es el Súper Mágico) y
        `origen` es {número: salida de la caminata que lo trajo a los 30}."""
        self.ensure_one()
        turn_lbl = dict(self._fields['turn_day'].selection)
        fmt = self._fmt_pts
        lineas_reco, term_reco = ctx['lineas_reco'], ctx['term_reco']

        def salida(rec):
            if not rec:
                return '<span class="text-muted">sin salidas previas</span>'
            return '<b>%02d</b> (%s %s)' % (
                rec.number_id.name, rec.date.strftime('%d/%m/%Y'),
                turn_lbl.get(rec.turn_day, rec.turn_day))

        def lista_txt(items):
            return (' · '.join('%d' % i for i in items) if items
                    else '<span class="text-muted">sin datos</span>')

        def marca(valor):
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

        def celda_tabla(v):
            if not v['tabla']:
                return '<td class="text-center text-muted">·</td>'
            return ('<td class="text-center">%s <span class="text-muted" '
                    'style="font-size:10px;">(d%d, %s)</span></td>'
                    % (fmt(v['tabla']), v['tabla_dist'], v['tabla_origen']))

        def tiene(n, digitos):
            return bool(set(_digitos(n)) & set(digitos))

        def reco_txt(n):
            linea, terminal = _digitos(n)
            partes = []
            if linea in lineas_reco:
                partes.append('L%d' % linea)
            if terminal in term_reco:
                partes.append('T%d' % terminal)
            return ('<td class="text-center">%s</td>' % ' '.join(partes)
                    if partes else '<td class="text-center text-muted">·</td>')

        sm = listas[5][0] if listas[5] else None
        en_5, en_10, en_20 = set(listas[5]), set(listas[10]), set(listas[20])

        def fila(i, n):
            v = valores[n]
            if n == sm:
                fondo, corte = '#e9d5ff', ' · SM'
            elif n in en_5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif n in en_10:
                fondo, corte = '#fff1e0', ' · 10'
            elif n in en_20:
                fondo, corte = '#f1f3f5', ' · 20'
            else:
                fondo, corte = '#e3f2fd', ' · 30'
            return (
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td><td class="text-center"><b>%02d</b></td>'
                '%s%s%s%s%s%s%s'
                '<td class="text-center">%s</td><td class="text-center">%s</td>'
                '<td class="text-center">%d</td></tr>' % (
                    fondo, i, corte, n, celda_origen(n),
                    marca(tiene(n, ctx['dig_20'])),
                    marca(tiene(n, ctx['dig_cercanos'])),
                    marca(tiene(n, ctx['dig_10'])),
                    marca(v['cruce']), reco_txt(n), celda_tabla(v),
                    fmt(v['grupos']), fmt(v['pintas']), v['comb']))

        # Orden de la tabla: los 5 (SM primero), después el resto de los 10,
        # de los 20 y de los 30, cada tramo en el orden de su recorte.
        orden, vistos = [], set()
        for clave in (5, 10, 20, 30):
            for n in listas[clave]:
                if n not in vistos:
                    orden.append(n)
                    vistos.add(n)

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', 'Entró por',
                      'Díg. %s' % ''.join(map(str, ctx['dig_20'])),
                      'Díg. %s' % ''.join(map(str, ctx['dig_cercanos'])),
                      'Díg. %s' % ''.join(map(str, ctx['dig_10'])),
                      'Cruce', 'L/T rec.', 'Tabla', 'Grupos', 'Pintas',
                      'Comb.'))
        afuera = len(candidatos) - len(listas[30])

        return """
            <div>
                <p class="small mb-1"><b>Algoritmo 2</b> ·
                    <span class="text-muted">Último número (general, usado
                    para el cruce):</span> %s ·
                    <span class="text-muted">Recomendadas:</span>
                    líneas %s · terminales %s ·
                    <span class="text-muted">Candidatos fuera de los 30:</span>
                    %d
                </p>
                <p class="text-muted small mb-2">
                    30: caminata de recencia (columna <b>Entró por</b>).
                    20: los que tienen algún dígito de <b>Díg. %s</b>;
                    desempata <b>Díg. %s</b> → grupos → tabla → pintas →
                    comb. → cruce → mayoría → azar.
                    10: los que tienen algún dígito de <b>Díg. %s</b>;
                    desempata tabla → pintas → grupos → azar.
                    5: los de <b>Cruce</b> con el último número; mismo
                    desempate que los 10. Súper Mágico (SM): línea
                    recomendada → terminal recomendado → mejor puesto en las
                    recomendadas. Los atrasos de grupos y pintas son los del
                    momento en que se apretó el botón.
                </p>
                <table class="table table-sm table-bordered"
                       style="font-size:12px;">
                    <thead><tr>%s</tr></thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """ % (salida(ctx['last_general']), lista_txt(lineas_reco),
               lista_txt(term_reco), afuera,
               ''.join(map(str, ctx['dig_20'])),
               ''.join(map(str, ctx['dig_cercanos'])),
               ''.join(map(str, ctx['dig_10'])),
               cabeza,
               ''.join(fila(i + 1, n) for i, n in enumerate(orden)))


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
