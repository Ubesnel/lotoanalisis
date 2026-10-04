# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

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
            SELECT o.date, t.name, o.week_day, n.name, t.code, t.sequence
            FROM lottery_output o
            JOIN lottery_number n ON n.id = o.number_id
            JOIN lottery_turno t ON t.id = o.turno_id
            WHERE o.sorteo_id = %s AND o.date <= %s
            ORDER BY o.date, o.turno_sequence, o.id
        """, (sorteo_id, target_date))
        return self.env.cr.fetchall()

    @staticmethod
    def _par(a, b):
        """(date_prev, turno_prev, numero_prev, date_next, turno_next, numero_next),
        con el turno como su nombre (es lo que se muestra)."""
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
        """rows: (date, nombre turno, week_day, numero, código turno, secuencia
        turno) ordenadas cronológicamente.

        Categorías: la general (cualquier turno), cada turno solo, cada par
        de turnos cruzado (turno A de un día → turno B del día siguiente) y
        cada turno en el día de la semana de `target_date`."""
        weekday_target = WEEKDAY_BY_PYTHON_INDEX[target_date.weekday()]
        dia_nombre = WEEKDAY_LABEL[weekday_target]

        def consecutivos(lista):
            return [self._par(lista[i], lista[i + 1]) for i in range(len(lista) - 1)]

        # Turnos con salidas, en orden del día.
        turnos = sorted({(r[5], r[4], r[1]) for r in rows})
        por_turno = {code: [r for r in rows if r[4] == code] for _seq, code, _n in turnos}

        # (key estable, nombre ES para el wizard, día de semana ES o None, pares)
        categorias = [('general', 'General (cualquier turno, consecutivos)', None,
                       consecutivos(rows))]
        for _seq, code, nombre in turnos:
            categorias.append(('solo_%s' % code, 'Solo %s, consecutivos' % nombre.lower(),
                               None, consecutivos(por_turno[code])))
        for _sa, code_a, nombre_a in turnos:
            for _sb, code_b, nombre_b in turnos:
                if code_a == code_b:
                    continue
                por_fecha_b = {r[0]: r for r in por_turno[code_b]}
                pares = [self._par(r, por_fecha_b[r[0] + timedelta(days=1)])
                         for r in por_turno[code_a]
                         if (r[0] + timedelta(days=1)) in por_fecha_b]
                categorias.append((
                    'cruzado_%s_%s' % (code_a, code_b),
                    'Cruzado: %s → %s (día siguiente)' % (nombre_a.lower(), nombre_b.lower()),
                    None, pares))
        for _seq, code, nombre in turnos:
            del_dia = [r for r in por_turno[code] if r[2] == weekday_target]
            categorias.append(('dia_%s' % code, '%s, turno %s' % (dia_nombre, nombre.lower()),
                               dia_nombre, consecutivos(del_dia)))
        return categorias

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
                f'{tp}) → {nn:02d} '
                f'({dn.strftime("%d/%m/%y")} {tn})')
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
                         'turn_label': tp},
                'next': {'number': nn, 'date': dn.strftime('%d/%m/%y'),
                         'turn_label': tn},
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
