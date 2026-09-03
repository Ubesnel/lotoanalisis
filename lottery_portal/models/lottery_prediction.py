# -*- coding: utf-8 -*-
import json
import re

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.lottery_base.models.utils import default_today_local

WEEKDAY_CODES = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do')
MESES_ES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre',
            'diciembre')

# Qué lista del ranking_snapshot del sorteo mira cada temperatura.
TEMPERATURE_KEY = {
    'hot': 'numbers',
    'cold': 'numbers_cold',
    'remaining': 'numbers_remaining',
}

# ── Pesos del botón "Completar números" ───────────────────────────────────
# Jerarquía pedida (21/08/2026): mandan los atrasos, y se miden por cantidad
# real de salidas atrasadas, no por puesto en la lista.
#   grupos > pintas > combinaciones > tabla general > tabla del turno.
# Cada señal tiene un máximo menor que la de arriba, así ninguna sola da
# vuelta a la anterior; entre varias sí pueden mover a un número.
#
# Grupos y pintas ya NO se separan en "general" y "turno": se unen los dos
# top en una sola lista y se ordena por atraso. Los dos contadores son
# comparables — ambos cuentan sorteos relevantes sin acierto y ambos tienen
# la misma esperanza (un grupo de 10 números sale 1 de cada 10 sorteos, se
# mire el general o se mire un turno). Así, si Terminal 8 lleva 45 atrasos de
# tarde y Terminal 6 lleva 30 generales, para predecir la tarde manda
# Terminal 8; y cuando el general trepe a 45-50 pasa a mandar él.
PESO_GRUPOS = 50.0
PESO_PINTAS = 28.0
PESO_COMBINACIONES = 16.0
PESO_TABLA_GENERAL = 11.0
PESO_TABLA_TURNO = 8.0

# El puntaje de grupos y pintas es proporcional al atraso: el más atrasado de
# la unión se lleva el peso entero y el resto la parte que le toca
# (atraso / atraso_del_puntero). Un grupo con la mitad de atrasos que el
# puntero vale la mitad, que es justo lo que se quiere que se note.

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

# Tabla LotoAnálisis: un acompañante no vale lo mismo pegado que lejos, pero
# es una ponderación suave, NO una regla de "gana el más lejos" — el que sale
# a veces es justo un vecino. El índice es la distancia en casillas (1 =
# adyacente) y los valores son absolutos: no se normalizan contra nada, así
# que en una tirada puede no haber ningún acompañante que llegue al tope y
# está bien. El pegadito arranca en 0.40, no en cero.
#
# Toda la señal vale 11 puntos (8 la del turno), así que entre el más cercano
# y el más lejano hay 6.6 puntos de diferencia: mueve el orden entre números
# parejos, nunca decide por sí sola.
CURVA_DISTANCIA_TABLA = (0.40, 0.55, 0.68, 0.78, 0.85, 0.90, 0.93, 0.96,
                         0.98, 0.99, 1.00)

# ── Atraso del mes: criterio EXTRA, sólo para las listas de 10 y 5 ────────
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
# Cuánto puede mover el atraso del mes al elegir los 10 y los 5. Queda entre
# la tabla del turno (8) y la general (11): reordena números parejos y no
# alcanza para dar vuelta una diferencia de grupos o de pintas, que es lo que
# tiene que seguir mandando.
#
# OJO: esto NO toca la lista de 20 ni el puntaje de _score_candidatos. Los 20
# salen del mismo orden de siempre; los 10 y los 5 se sacan de esos 20
# re-ordenados sumando este puntaje.
PESO_MES_10_5 = 10.0

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

    def _score_candidatos(self):
        """Puntúa los números de `number_ids` con todas las señales y los
        devuelve ordenados de mejor a peor, con el contexto que se usó."""
        self.ensure_one()
        stats = self.env['lottery.stats.service'].sudo()
        candidatos = sorted(self.number_ids.mapped('name'))

        # 1) Grupos y pintas más atrasados: las señales que mandan el orden.
        #    Cada una une su top general con el del turno a predecir y ordena
        #    por cantidad de atrasos, no por puesto.
        day = WEEKDAY_CODES[self.date.weekday()]
        gr_pts, gr_det = self._puntos_por_atraso(
            stats.get_top_6_groups, day, PESO_GRUPOS)
        pi_pts, pi_det = self._puntos_por_atraso(
            stats.get_top_3_pintas, day, PESO_PINTAS)

        # 2) Combinaciones — desempate fino: los 10 números de un mismo grupo
        #    atrasado empatan entre sí y acá se decide cuál va primero.
        base = stats.get_combinaciones_scores(
            self.sorteo_id.id, self.date, self.combinaciones_window)
        crudos = {n: base['scores'].get('%02d' % n, 0) for n in candidatos}
        # Se estira el puntaje crudo del conjunto al rango 0-PESO_COMBINACIONES:
        # el mejor se lleva todo y el peor nada, proporcional a la distancia
        # real entre puntajes. La normalización proporcional se mantiene (con
        # rank por posición se perdía: todos los escalones medían igual); lo
        # que cambió es el recorrido, que ahora es chico y no alcanza para dar
        # vuelta un atraso.
        peor, mejor = min(crudos.values()), max(crudos.values())
        rango = mejor - peor
        comb_pts = {n: (PESO_COMBINACIONES * (v - peor) / rango if rango
                        else PESO_COMBINACIONES)
                    for n, v in crudos.items()}

        # 3) Tablas LotoAnálisis — acompañantes del último número salido,
        #    pesados por la distancia a la que están en la grilla.
        last_general = self._last_output()
        last_turno = self._last_output(turn=self.turn_day)
        acomp_general = (self._acompanantes('general', last_general.number_id.name)
                         if last_general else {})
        acomp_turno = (self._acompanantes(self.turn_day, last_turno.number_id.name)
                       if last_turno else {})

        def pts_tabla(acomp, peso, n):
            """(puntos, distancia) del número n en esa tabla."""
            dist = acomp.get(n)
            if not dist:
                return 0.0, 0
            return round(peso * _factor_distancia(dist), 2), dist

        filas = []
        for n in candidatos:
            tg, tg_dist = pts_tabla(acomp_general, PESO_TABLA_GENERAL, n)
            tt, tt_dist = pts_tabla(acomp_turno, PESO_TABLA_TURNO, n)
            fila = {
                'numero': n,
                'gr': gr_pts.get(n, 0.0),
                'pi': pi_pts.get(n, 0.0),
                'comb_score': crudos[n],
                'comb': comb_pts[n],
                'tg': tg, 'tg_dist': tg_dist,
                'tt': tt, 'tt_dist': tt_dist,
            }
            fila['total'] = round(
                fila['gr'] + fila['pi'] + fila['comb']
                + fila['tg'] + fila['tt'], 2)
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
                ('Grupos atrasados', gr_det),
                ('Pintas atrasadas', pi_det),
            ],
        }
        return filas, ctx

    def action_completar_numeros(self):
        """Completa las listas de 20, 10 y 5 en cascada a partir de los
        números a predecir: los 20 salen del conjunto entero, los 10 de esos
        20 y los 5 de esos 10 (es un único orden, así el anidamiento se
        cumple solo).

        El orden lo da la suma ponderada de: grupos más atrasados y pintas
        más atrasadas — cada una uniendo su top general con el del turno a
        predecir y ordenando por cantidad de atrasos —, después
        combinaciones y, por último, los acompañantes del último número
        salido en la tabla LotoAnálisis general y en la del turno, pesados
        por la distancia a la que están en la grilla.

        Los 10 y los 5 llevan un criterio más: dentro de esos 20 se prioriza
        a los que llevan más tiempo sin salir en el mes de la predicción (los
        "Números del mes atrasados" de la app). La lista de 20 no lo usa: sale
        del mismo orden de siempre, así que el anidamiento 5 ⊂ 10 ⊂ 20 se
        sigue cumpliendo.

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

        # Los 20 quedan como siempre. Para los 10 y los 5 se re-ordenan esos
        # mismos 20 sumándoles el atraso del mes, así el criterio nuevo elige
        # adentro de la lista de siempre y no cambia quién entra a los 20.
        atrasos = self.atrasos_del_mes(self.sorteo_id, self.date)
        for fila in filas[:20]:
            fila['mes_anios'] = atrasos.get(fila['numero'])
            fila['mes'] = self.puntos_por_atraso_mes(
                fila['mes_anios'], PESO_MES_10_5)
            fila['total_mes'] = round(fila['total'] + fila['mes'], 2)
        # Mismos desempates que el orden de siempre, para que dos corridas con
        # los mismos datos den lo mismo.
        orden_mes = [f['numero'] for f in sorted(
            filas[:20],
            key=lambda f: (-f['total_mes'], -f['comb_score'], f['numero']))]

        Number = self.env['lottery.number']

        def ids(numeros):
            return Number.search([('name', 'in', numeros)]).ids

        listas = {20: orden[:20], 10: orden_mes[:10], 5: orden_mes[:5]}
        self.write({
            'number_ids_20': [(6, 0, ids(listas[20]))],
            'number_ids_10': [(6, 0, ids(listas[10]))],
            'number_ids_5': [(6, 0, ids(listas[5]))],
            'score_html': self._render_scores_html(filas, ctx, listas),
        })
        return True

    # ── Render del desglose ────────────────────────────────────────────────

    @staticmethod
    def _fmt_pts(valor):
        return ('%.1f' % valor).rstrip('0').rstrip('.') or '0'

    def _render_scores_html(self, filas, ctx, listas):
        """`listas` es {20: [...], 10: [...], 5: [...]} con los
        números que quedaron en cada una: el fondo de cada fila sale
        de ahí y no del puesto, porque los 10 y los 5 ya no siguen el
        orden de la tabla."""
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
                '%s <span class="text-muted">(%d atrasos, %s)</span> '
                '<b>+%s</b>' % (d['name'], d['atraso'], d['origen'],
                                fmt(d['valor'])) for d in det)
            return ('<p class="small mb-1"><span class="text-muted">%s:</span> '
                    '%s</p>' % (titulo, items))

        def celda(valor):
            return ('<td class="text-center">%s</td>' % fmt(valor) if valor
                    else '<td class="text-center text-muted">·</td>')

        def celda_tabla(valor, dist):
            """Puntos de la tabla con la distancia que los justifica."""
            if not valor:
                return '<td class="text-center text-muted">·</td>'
            return ('<td class="text-center">%s <span class="text-muted" '
                    'style="font-size:10px;">(d%d)</span></td>'
                    % (fmt(valor), dist))

        def celda_mes(fila):
            """Puntos del atraso del mes con los años que los justifican."""
            if 'mes' not in fila:
                return '<td class="text-center text-muted">·</td>'
            anios = fila['mes_anios']
            if anios is None:
                return '<td class="text-center text-muted">·</td>'
            etiqueta = ('nunca' if anios >= ANIOS_MES_NUNCA
                        else '%da' % anios)
            return ('<td class="text-center">%s <span class="text-muted" '
                    'style="font-size:10px;">(%s)</span></td>'
                    % (fmt(fila['mes']), etiqueta))

        aviso = ''
        if len(filas) < 20:
            aviso = ('<div class="alert alert-warning py-2 small">Sólo hay %d '
                     'números a predecir: las listas se llenaron con los que '
                     'había.</div>' % len(filas))

        cabeza = ''.join(
            '<th class="text-center" style="font-size:11px;">%s</th>' % h
            for h in ('#', 'Nº', 'Total', 'Grupos', 'Pintas', 'Comb.',
                      'Tabla gral.', 'Tabla turno', 'Mes', 'Total 10/5'))

        en_5, en_10, en_20 = (set(listas[5]), set(listas[10]),
                              set(listas[20]))
        cuerpo = []
        for i, f in enumerate(filas):
            if f['numero'] in en_5:
                fondo, corte = '#f3e8ff', ' · 5'
            elif f['numero'] in en_10:
                fondo, corte = '#fff1e0', ' · 10'
            elif f['numero'] in en_20:
                fondo, corte = '#f1f3f5', ' · 20'
            else:
                fondo, corte = '', ''
            total_mes = (('<td class="text-center"><b>%s</b></td>'
                          % fmt(f['total_mes'])) if 'total_mes' in f
                         else '<td class="text-center text-muted">·</td>')
            cuerpo.append(
                '<tr style="background:%s;">'
                '<td class="text-center text-muted" style="font-size:11px;">'
                '%d%s</td>'
                '<td class="text-center"><b>%02d</b></td>'
                '<td class="text-center"><b>%s</b></td>'
                '%s%s'
                '<td class="text-center">%s <span class="text-muted" '
                'style="font-size:10px;">(%d)</span></td>'
                '%s%s%s%s</tr>' % (
                    fondo, i + 1, corte, f['numero'], fmt(f['total']),
                    celda(f['gr']), celda(f['pi']),
                    fmt(f['comb']), f['comb_score'],
                    celda_tabla(f['tg'], f['tg_dist']),
                    celda_tabla(f['tt'], f['tt_dist']),
                    celda_mes(f), total_mes))

        turno_txt = turn_lbl.get(self.turn_day, self.turn_day)
        mes_txt = MESES_ES[self.date.month - 1] if self.date else 'el mes'
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
                    Fondo violeta: los 5 · naranja: los 10 · gris: los 20. La
                    tabla va ordenada por Total, que es lo que define los 20.
                    Los 10 y los 5 salen de esos 20 re-ordenados por
                    <b>Total 10/5</b>, que le suma el atraso del mes (columna
                    Mes: puntos y, entre paréntesis, los años sin salir en %s
                    — "nunca" si nunca salió ese mes), así que pueden no ser
                    los primeros de la tabla. En Comb., entre paréntesis, el
                    puntaje crudo (producto de frecuencias de dígitos); en las
                    tablas, la distancia en casillas al último número salido.
                    Los atrasos de grupos y pintas son los del momento en que
                    se apretó el botón.
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
               mes_txt, cabeza, ''.join(cuerpo))


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
