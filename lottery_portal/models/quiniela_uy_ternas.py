# -*- coding: utf-8 -*-
"""Informe de ternas de la Quiniela Uruguay: los números de 3 cifras.

Todo el resto del módulo analiza las dos últimas cifras (00-99). Acá se mira
la terna completa (000-999), que es lo que de verdad sale en cada premio.

El atraso se cuenta en SORTEOS, y qué es un sorteo depende del ámbito:

  · Un premio    → cada fecha+turno de ESE premio. La terna "sale" si salió
                   en ese premio.
  · General      → cada fecha+turno de la quiniela. La terna "sale" si salió
                   en CUALQUIERA de los 20 premios.

Filtrando por turno, sólo cuentan los sorteos de ese turno.

Las consultas van acá y no en `lottery.stats.service` porque son propias de
la quiniela y no las usa nadie más — mismo criterio que
`lottery.consulta.combinaciones`, que también carga su SQL. Si algún día
esto va a la app, el lugar natural pasa a ser el servicio de stats y el SQL
se muda tal cual.

Los tres cálculos van con `ormcache` y devuelven la lista ENTERA de ternas:
el recorte al límite pedido se hace en Python, así cambiar de 20 a 5 no
vuelve a pegarle a la base.
"""

from odoo import api, fields, models, tools

from .quiniela_uy_ui import (
    COLOR_TURNO, FUENTE, MESES, TEXTO, TEXTO_SUAVE, TURN_LABEL,
    badge, bola, tarjeta, cabezal,
)

SOURCE_CODE = 'quiniela_uy'
LIMITE_MAX = 100
# Con pocas ternas, una sola columna se lee mejor que dos con huecos.
COLUMNA_UNICA_HASTA = 6
CENTENAS_POR_NUMERO = 3

TURNO_CORTO = {'afternoon': 'Vesp.', 'evening': 'Noct.'}


def _filtro_turno(turn_day):
    """Fragmento de WHERE para el turno. 'general' no filtra nada."""
    return '' if turn_day == 'general' else 'AND o.turn_day = %(turno)s'


def _texto_premios(premios):
    """'premio 7' o 'premios 3 y 12'.

    Son varios cuando la terna salió en más de un premio del mismo sorteo:
    pasa poco, pero pasa, y decir sólo uno sería mentir."""
    premios = [p for p in (premios or []) if p]
    if not premios:
        return ''
    if len(premios) == 1:
        return 'premio %d' % premios[0]
    return 'premios %s y %d' % (', '.join(str(p) for p in premios[:-1]),
                                premios[-1])


class LotteryQuinielaUyTernas(models.TransientModel):
    """Wizard: ternas más atrasadas, atrasadas del mes y centenas por número."""
    _name = 'lottery.quiniela.uy.ternas'
    _description = 'Informe de ternas Quiniela Uruguay'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Premio',
        domain=[('source_code', '=', SOURCE_CODE)],
        help='Dejalo vacío para el análisis General: ahí un sorteo es una '
             'fecha y turno de la quiniela, y la terna cuenta como salida si '
             'salió en cualquiera de los 20 premios.')
    turn_day = fields.Selection([
        ('general', 'General'),
        ('afternoon', 'Vespertina'),
        ('evening', 'Nocturna'),
    ], string='Turno', required=True, default='general')
    fecha_corte = fields.Date(
        string='Fecha de corte', required=True,
        default=lambda self: fields.Date.context_today(self),
        help='El atraso se mide hasta esta fecha inclusive. Sirve para '
             'reproducir un informe de otro día.')
    mes = fields.Selection(
        [(str(i), MESES[i - 1].capitalize()) for i in range(1, 13)],
        string='Mes a analizar', required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
        help='Mes del informe "Atrasadas del mes": qué ternas llevan más '
             'años sin salir en ese mes.')
    limite = fields.Integer(
        string='Cuántas ternas', required=True, default=20,
        help='Cuántas ternas se muestran en los dos primeros informes. '
             'Tope 100.')

    atrasadas_html = fields.Html(
        string='Más atrasadas', readonly=True, sanitize=False)
    atrasadas_mes_html = fields.Html(
        string='Atrasadas del mes', readonly=True, sanitize=False)
    centenas_html = fields.Html(
        string='Centenas por número', readonly=True, sanitize=False)

    # ── Ámbito ────────────────────────────────────────────────────────────

    def _sorteo_ids(self):
        """Los premios que entran en el análisis, como tupla (hashable, va a
        la clave del ormcache)."""
        self.ensure_one()
        if self.sorteo_id:
            return (self.sorteo_id.id,)
        return tuple(self.env['lottery.sorteo'].sudo().search(
            [('source_code', '=', SOURCE_CODE)]).ids)

    def _etiqueta_ambito(self):
        self.ensure_one()
        return self.sorteo_id.name if self.sorteo_id else 'los 20 premios'

    # ── Consultas ─────────────────────────────────────────────────────────

    @api.model
    @tools.ormcache('sorteo_ids', 'turn_day', 'fecha_corte')
    def get_ternas_atrasadas(self, sorteo_ids, turn_day, fecha_corte):
        """Las 1000 ternas ordenadas de más atrasada a menos.

        Se numeran los sorteos del ámbito (fecha+turno, sin repetir aunque
        sean 20 premios) y el atraso es cuántos pasaron desde el último en
        que salió la terna. Las que nunca salieron llevan el total de
        sorteos, que es el atraso máximo posible."""
        if not sorteo_ids:
            return []
        self.env.cr.execute("""
            WITH ordenados AS (
                SELECT date, turn_day,
                       ROW_NUMBER() OVER (
                           ORDER BY date,
                           CASE turn_day WHEN 'afternoon' THEN 0 ELSE 1 END
                       ) AS orden
                FROM (
                    SELECT DISTINCT o.date, o.turn_day
                    FROM lottery_output o
                    WHERE o.sorteo_id IN %(sorteo_ids)s
                      AND o.date <= %(corte)s
                      {turno}
                ) d
            ),
            tope AS (SELECT COALESCE(MAX(orden), 0) AS maximo FROM ordenados),
            salidas AS (
                SELECT o.complete_number, ord.orden, o.date, o.turn_day,
                       SUBSTRING(so.code FROM '(\\d+)$')::int AS premio
                FROM lottery_output o
                JOIN lottery_sorteo so ON so.id = o.sorteo_id
                JOIN ordenados ord
                  ON ord.date = o.date AND ord.turn_day = o.turn_day
                WHERE o.sorteo_id IN %(sorteo_ids)s
                  AND o.date <= %(corte)s
                  AND o.complete_number IS NOT NULL
                  {turno}
            ),
            -- El último sorteo en que salió cada terna, y TODOS los premios
            -- en que salió ese día: la misma terna puede caer en dos premios
            -- del mismo sorteo.
            tope_terna AS (
                SELECT complete_number, MAX(orden) AS orden
                FROM salidas GROUP BY complete_number
            ),
            ultima AS (
                SELECT sa.complete_number, sa.orden, sa.date, sa.turn_day,
                       ARRAY_AGG(sa.premio ORDER BY sa.premio) AS premios
                FROM salidas sa
                JOIN tope_terna tt
                  ON tt.complete_number = sa.complete_number
                 AND tt.orden = sa.orden
                GROUP BY sa.complete_number, sa.orden, sa.date, sa.turn_day
            ),
            totales AS (
                SELECT complete_number, COUNT(*) AS total
                FROM salidas GROUP BY complete_number
            ),
            universo AS (
                SELECT LPAD(g::text, 3, '0') AS terna
                FROM generate_series(0, 999) g
            )
            SELECT u.terna,
                   (SELECT maximo FROM tope)
                       - COALESCE(ul.orden, 0) AS atraso,
                   COALESCE(t.total, 0) AS total,
                   TO_CHAR(ul.date, 'DD/MM/YYYY') AS ultima_fecha,
                   ul.turn_day AS ultimo_turno,
                   ul.premios
            FROM universo u
            LEFT JOIN ultima ul ON ul.complete_number = u.terna
            LEFT JOIN totales t ON t.complete_number = u.terna
            ORDER BY atraso DESC, u.terna
        """.format(turno=_filtro_turno(turn_day)), {
            'sorteo_ids': tuple(sorteo_ids),
            'corte': fecha_corte,
            'turno': turn_day,
        })
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_ids', 'turn_day', 'mes', 'fecha_corte')
    def get_ternas_atrasadas_mes(self, sorteo_ids, turn_day, mes, fecha_corte):
        """Las 1000 ternas ordenadas por años sin salir en ese mes.

        El año del corte SÍ cuenta: si la terna ya salió en ese mes de este
        año, su atraso es 0 y se va al fondo de la lista.

        Esto es distinto de `get_month_overdue_sections`, que es lo que
        consume la app: ahí el año en curso se excluye a propósito, porque es
        el que se está prediciendo y lo que interesa es que el número venía
        atrasado al entrar al mes. Acá no se predice nada, se le muestra un
        ranking al usuario, y una terna que ya salió este agosto arriba de
        "las más atrasadas de agosto" se lee como un error.

        Las que nunca salieron en ese mes encabezan."""
        if not sorteo_ids:
            return []
        anio = fields.Date.to_date(fecha_corte).year
        self.env.cr.execute("""
            WITH salidas AS (
                SELECT o.complete_number, o.year, o.date,
                       SUBSTRING(so.code FROM '(\\d+)$')::int AS premio
                FROM lottery_output o
                JOIN lottery_sorteo so ON so.id = o.sorteo_id
                WHERE o.sorteo_id IN %(sorteo_ids)s
                  AND o.month = %(mes)s
                  AND o.date <= %(corte)s
                  AND o.complete_number IS NOT NULL
                  {turno}
            ),
            resumen AS (
                SELECT complete_number, MAX(year) AS ultimo_anio,
                       MAX(date) AS ultima_fecha, COUNT(*) AS total_mes
                FROM salidas GROUP BY complete_number
            ),
            -- Los premios de esa última salida en el mes, igual que arriba.
            ultimas AS (
                SELECT r.complete_number, r.ultimo_anio, r.ultima_fecha,
                       r.total_mes,
                       ARRAY_AGG(sa.premio ORDER BY sa.premio) AS premios
                FROM resumen r
                JOIN salidas sa
                  ON sa.complete_number = r.complete_number
                 AND sa.date = r.ultima_fecha
                GROUP BY r.complete_number, r.ultimo_anio, r.ultima_fecha,
                         r.total_mes
            ),
            universo AS (
                SELECT LPAD(g::text, 3, '0') AS terna
                FROM generate_series(0, 999) g
            )
            SELECT u.terna,
                   ul.ultimo_anio,
                   %(anio)s - ul.ultimo_anio AS anios,
                   COALESCE(ul.total_mes, 0) AS total_mes,
                   TO_CHAR(ul.ultima_fecha, 'DD/MM/YYYY') AS ultima_fecha,
                   ul.premios
            FROM universo u
            LEFT JOIN ultimas ul ON ul.complete_number = u.terna
            ORDER BY (ul.ultimo_anio IS NULL) DESC, anios DESC, u.terna
        """.format(turno=_filtro_turno(turn_day)), {
            'sorteo_ids': tuple(sorteo_ids),
            'mes': mes,
            'corte': fecha_corte,
            'anio': anio,
            'turno': turn_day,
        })
        return self.env.cr.dictfetchall()

    @api.model
    @tools.ormcache('sorteo_ids', 'turn_day', 'fecha_corte')
    def get_centenas_por_numero(self, sorteo_ids, turn_day, fecha_corte):
        """[{numero, centena, veces, puesto}] con las `CENTENAS_POR_NUMERO`
        centenas más salidas de cada número 00-99.

        Se parte `complete_number` en vez de unir contra lottery_number dos
        veces: el dato ya está armado en la columna y sale más barato."""
        if not sorteo_ids:
            return []
        self.env.cr.execute("""
            WITH conteo AS (
                SELECT RIGHT(o.complete_number, 2) AS numero,
                       LEFT(o.complete_number, 1) AS centena,
                       COUNT(*) AS veces,
                       ROW_NUMBER() OVER (
                           PARTITION BY RIGHT(o.complete_number, 2)
                           ORDER BY COUNT(*) DESC,
                                    LEFT(o.complete_number, 1)
                       ) AS puesto
                FROM lottery_output o
                WHERE o.sorteo_id IN %(sorteo_ids)s
                  AND o.date <= %(corte)s
                  AND o.complete_number IS NOT NULL
                  {turno}
                GROUP BY 1, 2
            )
            SELECT numero, centena, veces, puesto
            FROM conteo WHERE puesto <= %(cuantas)s
            ORDER BY numero, puesto
        """.format(turno=_filtro_turno(turn_day)), {
            'sorteo_ids': tuple(sorteo_ids),
            'corte': fecha_corte,
            'cuantas': CENTENAS_POR_NUMERO,
            'turno': turn_day,
        })
        return self.env.cr.dictfetchall()

    # ── Acción ────────────────────────────────────────────────────────────

    def action_consultar(self):
        self.ensure_one()
        ids = self._sorteo_ids()
        corte = str(self.fecha_corte)
        limite = max(1, min(self.limite or 20, LIMITE_MAX))

        atrasadas = self.get_ternas_atrasadas(ids, self.turn_day, corte)
        del_mes = self.get_ternas_atrasadas_mes(
            ids, self.turn_day, self.mes, corte)
        centenas = self.get_centenas_por_numero(ids, self.turn_day, corte)

        self.write({
            'limite': limite,
            'atrasadas_html': self._render_atrasadas(atrasadas[:limite]),
            # El informe del mes muestra también cuándo salió por última
            # vez en CUALQUIER mes, que es lo primero que uno se pregunta al
            # ver una terna con años de atraso. El dato ya viene calculado
            # en el informe de atrasadas, así que no cuesta una consulta más.
            'atrasadas_mes_html': self._render_atrasadas_mes(
                del_mes[:limite], {f['terna']: f for f in atrasadas}),
            'centenas_html': self._render_centenas(centenas),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    # ── Render ────────────────────────────────────────────────────────────

    def _premio_de(self, item):
        """' · premio 7' para el ámbito General; vacío si ya se está mirando
        un premio solo, donde el dato sería siempre el mismo."""
        self.ensure_one()
        if self.sorteo_id:
            return ''
        texto = _texto_premios(item.get('premios'))
        return ' · %s' % texto if texto else ''

    def _titulo(self):
        self.ensure_one()
        return 'Ternas · %s' % self._etiqueta_ambito()

    def _pie(self, texto):
        return (
            '<div style="margin:10px 14px 0;padding:8px 10px;'
            'border-radius:9px;background:#FFFFFF;border:1px solid #C6E4CF;'
            'font:600 11px/1.45 %s;color:%s;text-align:center;">%s</div>'
            % (FUENTE, TEXTO_SUAVE, texto)
        )

    def _vacio(self, texto):
        return (
            '<div style="padding:22px 18px;text-align:center;'
            'font:700 13px/1.5 %s;color:%s;">%s</div>'
            % (FUENTE, TEXTO_SUAVE, texto)
        )

    def _filas_ternas(self, items, detalle, ancho_texto=190):
        """Tabla de ternas en una o dos columnas: puesto, bola y detalle.

        `detalle` es la función que arma el texto de cada fila."""
        self.ensure_one()
        color = COLOR_TURNO[self.turn_day]
        columnas = 1 if len(items) <= COLUMNA_UNICA_HASTA else 2
        por_columna = -(-len(items) // columnas)   # techo de la división

        filas = []
        for i in range(por_columna):
            celdas = []
            for col in range(columnas):
                pos = i + col * por_columna
                if pos >= len(items):
                    celdas.append('<td></td>')
                    continue
                item = items[pos]
                celdas.append(
                    '<td style="padding:5px 7px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s%s<div style="width:%dpx;font:600 10.5px/1.35 %s;'
                    'color:%s;">%s</div></div></td>'
                    % (badge(pos + 1, lado=22),
                       bola(item['terna'], color, diam=44),
                       ancho_texto, FUENTE, TEXTO_SUAVE, detalle(item)))
            filas.append('<tr>%s</tr>' % ''.join(celdas))
        ancho = 60 + columnas * (22 + 8 + 44 + 8 + ancho_texto + 14)
        return ''.join(filas), ancho

    def _render_atrasadas(self, items):
        self.ensure_one()
        if not items:
            cuerpo = self._vacio('No hay salidas cargadas para este ámbito.')
            return tarjeta(cabezal(self.turn_day, self.fecha_corte,
                                   titulo=self._titulo()), cuerpo)

        def detalle(item):
            if not item['total']:
                return ('<b style="color:%s;">nunca salió</b><br/>%d sorteos '
                        'de historia' % (TEXTO, item['atraso']))
            turno = TURNO_CORTO.get(item['ultimo_turno'], '')
            return ('<b style="color:%s;">%d sorteos</b> sin salir<br/>'
                    'última: %s %s%s<br/>%d salidas'
                    % (TEXTO, item['atraso'], item['ultima_fecha'], turno,
                       self._premio_de(item), item['total']))

        filas, ancho = self._filas_ternas(items, detalle, ancho_texto=205)
        cuerpo = (
            '<div style="padding:12px 8px 14px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>'
            % (filas,
               self._pie('Las %d ternas con más sorteos sin salir en %s. '
                         'Un sorteo es una fecha y turno; con el turno '
                         'filtrado, sólo los de ese turno.'
                         % (len(items), self._etiqueta_ambito()))))
        return tarjeta(cabezal(self.turn_day, self.fecha_corte,
                               titulo=self._titulo()), cuerpo, ancho=ancho)

    def _render_atrasadas_mes(self, items, ultimas):
        """`ultimas` es {terna: fila del informe de atrasadas}, para poder
        decir cuándo salió por última vez en cualquier mes."""
        self.ensure_one()
        mes = MESES[int(self.mes) - 1]
        if not items:
            cuerpo = self._vacio('No hay salidas cargadas para este ámbito.')
            return tarjeta(cabezal(self.turn_day, self.fecha_corte,
                                   titulo=self._titulo()), cuerpo)

        def ultima_global(item):
            fila = ultimas.get(item['terna'])
            if not fila or not fila.get('total'):
                return ''
            return ('<br/>última salida: %s%s <span style="opacity:.75;">'
                    '(%d sorteos)</span>'
                    % (fila['ultima_fecha'], self._premio_de(fila),
                       fila['atraso']))

        def detalle(item):
            if item['ultimo_anio'] is None:
                cabeza = ('<b style="color:%s;">nunca salió</b> en %s'
                          % (TEXTO, mes))
            else:
                cabeza = ('<b style="color:%s;">%d %s</b> sin salir en %s<br/>'
                          'último %s: %s%s · %d salidas'
                          % (TEXTO, item['anios'],
                             'año' if item['anios'] == 1 else 'años',
                             mes, mes, item['ultima_fecha'],
                             self._premio_de(item), item['total_mes']))
            return cabeza + ultima_global(item)

        filas, ancho = self._filas_ternas(items, detalle, ancho_texto=225)
        cuerpo = (
            '<div style="padding:12px 8px 14px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>'
            % (filas,
               self._pie('Las %d ternas que llevan más años sin salir en %s '
                         'en %s. Si ya salió en %s de este año el atraso es '
                         'cero, así que ninguna de estas salió este %s.'
                         % (len(items), mes, self._etiqueta_ambito(), mes,
                            mes))))
        return tarjeta(cabezal(self.turn_day, self.fecha_corte,
                               titulo='Ternas de %s · %s'
                                      % (mes, self._etiqueta_ambito())),
                       cuerpo, ancho=ancho)

    def _render_centenas(self, items):
        """Matriz 10×10: fila = decena, columna = unidad. En cada celda el
        número y sus 3 centenas más salidas, la primera destacada."""
        self.ensure_one()
        if not items:
            cuerpo = self._vacio('No hay salidas cargadas para este ámbito.')
            return tarjeta(cabezal(self.turn_day, self.fecha_corte,
                                   titulo=self._titulo()), cuerpo)

        por_numero = {}
        for item in items:
            por_numero.setdefault(item['numero'], []).append(item)

        filas = []
        for decena in range(10):
            celdas = []
            for unidad in range(10):
                numero = '%d%d' % (decena, unidad)
                top = por_numero.get(numero, [])
                chips = ''.join(
                    '<div style="text-align:center;">'
                    '<div style="width:19px;height:19px;border-radius:50%%;'
                    'background:%s;color:#fff;font:800 11px/19px %s;">%s</div>'
                    '<div style="font:600 8.5px/1.2 %s;color:%s;margin-top:1px;">'
                    '%d</div></div>'
                    % ('#2FA850' if c['puesto'] == 1 else '#9CCBA9',
                       FUENTE, c['centena'], FUENTE, TEXTO_SUAVE, c['veces'])
                    for c in top)
                celdas.append(
                    '<td style="padding:3px;">'
                    '<div style="width:76px;border-radius:9px;'
                    'background:#FFFFFF;border:1px solid #C6E4CF;'
                    'padding:5px 4px 4px;text-align:center;">'
                    '<div style="font:900 13px/1 %s;color:%s;'
                    'letter-spacing:.5px;">%s</div>'
                    '<div style="display:flex;justify-content:center;gap:5px;'
                    'margin-top:4px;">%s</div></div></td>'
                    % (FUENTE, TEXTO, numero,
                       chips or '<span style="font:600 9px/19px %s;color:%s;">'
                                'sin datos</span>' % (FUENTE, TEXTO_SUAVE)))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        cuerpo = (
            '<div style="padding:12px 6px 14px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>'
            % (''.join(filas),
               self._pie('Las %d centenas que más salieron con cada número '
                         'en %s. La verde oscura es la primera; abajo de '
                         'cada una, cuántas veces salió.'
                         % (CENTENAS_POR_NUMERO, self._etiqueta_ambito()))))
        return tarjeta(
            cabezal(self.turn_day, self.fecha_corte,
                    titulo='Centenas por número · %s'
                           % self._etiqueta_ambito()),
            cuerpo, ancho=880)
