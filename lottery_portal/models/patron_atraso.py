# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

TURN_LABEL = {'afternoon': 'Tarde', 'evening': 'Noche'}
WEEKDAY_LABEL = {
    'lu': 'Lunes', 'ma': 'Martes', 'mi': 'Miércoles', 'ju': 'Jueves',
    'vi': 'Viernes', 'sa': 'Sábado', 'do': 'Domingo',
}
# date.weekday(): 0=lunes … 6=domingo
WEEKDAY_BY_PYTHON_INDEX = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']


def _hit_cruce(prev_num, next_num):
    """La línea del anterior pasa a terminal del siguiente, o el terminal
    del anterior pasa a línea del siguiente (ej: 45 -> entre 50-59, ó
    terminando en 4)."""
    linea_prev, terminal_prev = divmod(prev_num, 10)
    linea_next, terminal_next = divmod(next_num, 10)
    return terminal_next == linea_prev or linea_next == terminal_prev


def _hit_repeticion(prev_num, next_num):
    """Se repite la misma línea, o se repite el mismo terminal, en el
    siguiente sorteo (ej: 45 -> entre 40-49, ó terminando en 5)."""
    linea_prev, terminal_prev = divmod(prev_num, 10)
    linea_next, terminal_next = divmod(next_num, 10)
    return linea_next == linea_prev or terminal_next == terminal_prev


PATRONES = {
    'cruce': (
        'Cruce línea/terminal',
        'la línea (decena) del sorteo anterior pasa a ser terminal '
        '(unidad) del siguiente, o el terminal anterior pasa a ser línea '
        'del siguiente (ej: 45 → entre 50 y 59, ó terminando en 4).',
        _hit_cruce,
    ),
    'repeticion': (
        'Repetición de línea o terminal',
        'se repite la misma línea (decena) del sorteo anterior, o se '
        'repite el mismo terminal (unidad), en el siguiente (ej: 45 → '
        'entre 40 y 49, ó terminando en 5).',
        _hit_repeticion,
    ),
}


class LotteryPatronAtraso(models.TransientModel):
    """Atraso de patrones de dígitos sobre la línea/terminal (decena/unidad
    del número de 2 cifras) de un sorteo, elegible entre varios patrones
    (ver PATRONES).

    Muestra, para varias formas de "consecutivo" (general, solo tarde,
    solo noche, cruzado tarde/noche, y el día de semana de la fecha
    elegida): el atraso actual, con qué números se cumplió por última vez,
    el promedio histórico de atraso y el pico máximo registrado.
    """
    _name = 'lottery.patron.atraso'
    _description = 'Atraso de patrones línea/terminal'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True,
        default=lambda self: self.env['lottery.sorteo'].search([], limit=1))
    date = fields.Date(
        string='Fecha', required=True, default=fields.Date.context_today,
        help='Se analiza el historial hasta esta fecha (inclusive). '
             'El día de la semana evaluado es el de esta fecha.')
    patron = fields.Selection(
        [(k, v[0]) for k, v in PATRONES.items()],
        string='Patrón', required=True, default='cruce')
    result_html = fields.Html(string='Resultado', readonly=True, sanitize=False)

    def _fetch_rows(self, sorteo_id, target_date):
        self.env.cr.execute("""
            SELECT o.date, o.turn_day, o.week_day, n.name
            FROM lottery_output o
            JOIN lottery_number n ON n.id = o.number_id
            WHERE o.sorteo_id = %s AND o.date <= %s
            ORDER BY o.date,
                     CASE o.turn_day WHEN 'afternoon' THEN 0 ELSE 1 END
        """, (sorteo_id, target_date))
        return self.env.cr.fetchall()

    @staticmethod
    def _par(a, b):
        """(date_prev, turn_prev, numero_prev, date_next, turn_next, numero_next)."""
        return (a[0], a[1], a[3], b[0], b[1], b[3])

    @staticmethod
    def _analizar(pares, hit_fn):
        """Devuelve atraso actual, último acierto, promedio y máximo
        histórico de la lista de pares consecutivos (ya ordenada
        cronológicamente), según la función de acierto `hit_fn`. El
        promedio/máximo solo considera rachas CERRADAS (que terminaron en
        un acierto) — la racha final, si sigue abierta, es justamente el
        atraso actual y no cuenta como "resuelta".
        """
        total = len(pares)
        if not total:
            return None
        hits = [hit_fn(p[2], p[5]) for p in pares]

        last_hit_idx = next(
            (i for i in range(total - 1, -1, -1) if hits[i]), None)
        atraso_actual = (
            total if last_hit_idx is None else total - last_hit_idx - 1)
        ultimo_acierto = pares[last_hit_idx] if last_hit_idx is not None else None

        rachas_cerradas = []
        inicio = None
        for i, h in enumerate(hits):
            if not h:
                if inicio is None:
                    inicio = i
            elif inicio is not None:
                rachas_cerradas.append((inicio, i - 1))
                inicio = None
        # la racha final (si sigue abierta, inicio is not None) no se agrega:
        # todavía no terminó, es el atraso_actual de arriba.

        largos = [fin - ini + 1 for ini, fin in rachas_cerradas]
        promedio = round(sum(largos) / len(largos), 1) if largos else None
        maximo = None
        if largos:
            i_max = max(range(len(rachas_cerradas)), key=lambda i: largos[i])
            ini, fin = rachas_cerradas[i_max]
            maximo = {
                'largo': largos[i_max],
                'desde': pares[ini][0],
                'hasta': pares[fin][3],
            }
        return {
            'total': total,
            'atraso_actual': atraso_actual,
            'ultimo_acierto': ultimo_acierto,
            'promedio': promedio,
            'maximo': maximo,
        }

    def _categorias(self, rows, target_date):
        """rows: (date, turn_day, week_day, numero) ordenadas cronológicamente."""
        weekday_target = WEEKDAY_BY_PYTHON_INDEX[target_date.weekday()]

        general = [self._par(rows[i], rows[i + 1]) for i in range(len(rows) - 1)]

        tardes = [r for r in rows if r[1] == 'afternoon']
        noches = [r for r in rows if r[1] == 'evening']
        solo_tarde = [self._par(tardes[i], tardes[i + 1])
                      for i in range(len(tardes) - 1)]
        solo_noche = [self._par(noches[i], noches[i + 1])
                      for i in range(len(noches) - 1)]

        por_fecha_noche = {r[0]: r for r in noches}
        por_fecha_tarde = {r[0]: r for r in tardes}
        cruzado_tn = [
            self._par(t, por_fecha_noche[t[0] + timedelta(days=1)])
            for t in tardes if (t[0] + timedelta(days=1)) in por_fecha_noche
        ]
        cruzado_nt = [
            self._par(n, por_fecha_tarde[n[0] + timedelta(days=1)])
            for n in noches if (n[0] + timedelta(days=1)) in por_fecha_tarde
        ]

        dia_tarde = [r for r in tardes if r[2] == weekday_target]
        dia_noche = [r for r in noches if r[2] == weekday_target]
        patron_dia_tarde = [self._par(dia_tarde[i], dia_tarde[i + 1])
                            for i in range(len(dia_tarde) - 1)]
        patron_dia_noche = [self._par(dia_noche[i], dia_noche[i + 1])
                            for i in range(len(dia_noche) - 1)]

        dia_nombre = WEEKDAY_LABEL[weekday_target]
        # (key estable, nombre ES para el wizard, día de semana ES o None, pares)
        return [
            ('general', 'General (cualquier turno, consecutivos)', None, general),
            ('solo_tarde', 'Solo tarde, consecutivos', None, solo_tarde),
            ('solo_noche', 'Solo noche, consecutivos', None, solo_noche),
            ('cruzado_tn', 'Cruzado: tarde → noche (día siguiente)', None,
             cruzado_tn),
            ('cruzado_nt', 'Cruzado: noche → tarde (día siguiente)', None,
             cruzado_nt),
            ('dia_tarde', f'{dia_nombre}, turno tarde', dia_nombre,
             patron_dia_tarde),
            ('dia_noche', f'{dia_nombre}, turno noche', dia_nombre,
             patron_dia_noche),
        ]

    def _row_html(self, nombre, pares, hit_fn):
        info = self._analizar(pares, hit_fn)
        if info is None:
            return (
                f'<tr><td>{nombre}</td>'
                '<td colspan="4" class="text-muted text-center">'
                'Sin datos suficientes</td></tr>')

        if info['ultimo_acierto']:
            dp, tp, np_, dn, tn, nn = info['ultimo_acierto']
            ultimo_txt = (
                f'{np_:02d} ({dp.strftime("%d/%m/%y")} '
                f'{TURN_LABEL.get(tp, tp)}) → {nn:02d} '
                f'({dn.strftime("%d/%m/%y")} {TURN_LABEL.get(tn, tn)})')
        else:
            ultimo_txt = '—'

        maximo_txt = '—'
        if info['maximo']:
            m = info['maximo']
            maximo_txt = (
                f'{m["largo"]} ({m["desde"].strftime("%d/%m/%y")} → '
                f'{m["hasta"].strftime("%d/%m/%y")})')

        promedio_txt = info['promedio'] if info['promedio'] is not None else '—'

        atraso_txt = str(info['atraso_actual'])
        if (info['atraso_actual'] > 0 and info['maximo']
                and info['atraso_actual'] >= info['maximo']['largo']):
            atraso_txt += ' <span class="badge bg-danger">RÉCORD</span>'

        return f"""
            <tr>
                <td>{nombre}</td>
                <td class="text-center"><b>{atraso_txt}</b></td>
                <td>{ultimo_txt}</td>
                <td class="text-center">{promedio_txt}</td>
                <td class="text-center">{maximo_txt}</td>
            </tr>
        """

    @api.model
    def compute_patron_atraso(self, sorteo_id, target_date, patron='cruce'):
        """Datos estructurados del atraso de patrones (para el endpoint REST
        de la app). Misma lógica que action_consultar pero sin HTML."""
        if patron not in PATRONES:
            patron = 'cruce'
        label, desc, hit_fn = PATRONES[patron]
        rows = self._fetch_rows(sorteo_id, target_date)
        categorias = []
        if len(rows) >= 2:
            for key, nombre, weekday, pares in self._categorias(
                    rows, target_date):
                categorias.append(self._serialize_categoria(
                    key, nombre, weekday, self._analizar(pares, hit_fn)))
        return {
            'patron': patron,
            'patron_label': label,
            'patron_desc': desc,
            'categorias': categorias,
        }

    @api.model
    def _serialize_categoria(self, key, nombre, weekday, info):
        if info is None:
            return {'key': key, 'nombre': nombre, 'weekday': weekday,
                    'sin_datos': True}
        ua = info['ultimo_acierto']
        ultimo = None
        if ua:
            dp, tp, np_, dn, tn, nn = ua
            ultimo = {
                'prev': {'number': np_, 'date': dp.strftime('%d/%m/%y'),
                         'turn_label': TURN_LABEL.get(tp, tp)},
                'next': {'number': nn, 'date': dn.strftime('%d/%m/%y'),
                         'turn_label': TURN_LABEL.get(tn, tn)},
            }
        maximo = info['maximo']
        record = bool(info['atraso_actual'] > 0 and maximo
                      and info['atraso_actual'] >= maximo['largo'])
        return {
            'key': key,
            'nombre': nombre,
            'weekday': weekday,
            'sin_datos': False,
            'atraso_actual': info['atraso_actual'],
            'promedio': info['promedio'],
            'maximo': maximo['largo'] if maximo else None,
            'maximo_desde': maximo['desde'].strftime('%d/%m/%y') if maximo else None,
            'maximo_hasta': maximo['hasta'].strftime('%d/%m/%y') if maximo else None,
            'record': record,
            'ultimo_acierto': ultimo,
        }

    def action_consultar(self):
        self.ensure_one()
        rows = self._fetch_rows(self.sorteo_id.id, self.date)
        if len(rows) < 2:
            self.result_html = (
                '<div class="alert alert-warning">No hay suficientes '
                'salidas registradas para este sorteo hasta la fecha '
                'indicada.</div>')
            return self._reopen()

        nombre_patron, descripcion_patron, hit_fn = PATRONES[self.patron]
        rows_html = ''.join(
            self._row_html(nombre, pares, hit_fn)
            for _key, nombre, _wd, pares in self._categorias(rows, self.date)
        )

        self.result_html = f"""
            <div>
                <h5>Atraso del patrón "{nombre_patron}" — {self.sorteo_id.name}
                    al {self.date.strftime('%d/%m/%Y')}</h5>
                <p class="text-muted small">
                    Patrón: {descripcion_patron} Atraso = pares consecutivos
                    seguidos sin que se cumpla. El promedio/máximo solo
                    cuenta rachas ya resueltas por un acierto (no la racha
                    en curso).
                </p>
                <table class="table table-sm table-bordered align-middle">
                    <thead>
                        <tr>
                            <th>Categoría</th>
                            <th class="text-center">Atraso actual</th>
                            <th>Último acierto (números)</th>
                            <th class="text-center">Promedio histórico</th>
                            <th class="text-center">Máximo histórico</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        """
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
