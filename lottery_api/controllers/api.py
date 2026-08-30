# -*- coding: utf-8 -*-
"""Endpoints REST públicos para la app móvil LotoAnálisis.

A diferencia de las rutas type='json' del portal (JSON-RPC), estas rutas son
GET planos que devuelven application/json, con CORS abierto para poder
consumirlas desde la app (y desde Chrome durante el desarrollo Flutter web).
"""

import json
from datetime import datetime

import pytz

from odoo import http
from odoo.http import request

WEEKDAYS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MONTHS_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
             'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
WEEK_LABELS = {1: '1 al 7', 2: '8 al 14', 3: '15 al 21', 4: '22 al 28', 5: '29 al 31'}
TURN_LABELS = {'afternoon': 'Tarde', 'evening': 'Noche'}


VALID_DAYS = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do')
# La Tómbola de Quiniela UY no sortea los domingos.
TOMBOLA_VALID_DAYS = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa')


def _json_response(payload, status=200):
    # Registro liviano de la consulta (IP, endpoint, sorteo, país, status).
    # Envuelto para que un fallo al loguear jamás afecte la respuesta.
    try:
        request.env['lottery.api.log'].sudo()._record(request, status)
    except Exception:
        pass
    return request.make_response(
        json.dumps(payload, ensure_ascii=False, default=str),
        headers=[('Content-Type', 'application/json; charset=utf-8')],
        status=status,
    )


def _serialize_output(record):
    """Salida (lottery.output) → dict para la app."""
    if not record:
        return None
    return {
        'date': record.date.isoformat(),
        'weekday': WEEKDAYS_ES[record.date.weekday()],
        'turn': record.turn_day,
        'turn_label': TURN_LABELS.get(record.turn_day, record.turn_day),
        'centena': str(record.hundreds_id.name) if record.hundreds_id else None,
        'numero': str(record.number_id.name).zfill(2),
        'extra': str(record.fireball_id.name) if record.fireball_id else None,
        # Números corridos (Premio 2 y 3, solo sorteos Pick3 con dato cargado)
        'premio_2': str(record.premio_2_id.name).zfill(2) if record.premio_2_id else None,
        'premio_3': str(record.premio_3_id.name).zfill(2) if record.premio_3_id else None,
    }


def _get_public_sorteo(sorteo_id):
    """Devuelve el sorteo pedido solo si está habilitado para la app; si no
    se pide ninguno, el primero habilitado (por secuencia)."""
    Sorteo = request.env['lottery.sorteo'].sudo()
    domain = [('show_in_app', '=', True)]
    if sorteo_id:
        sorteo = Sorteo.search(domain + [('id', '=', int(sorteo_id))], limit=1)
    else:
        sorteo = Sorteo.search(domain, order='sequence, id', limit=1)
    return sorteo


def _fmt_hour(value):
    """Float de Odoo (13.5) → 'HH:MM' ('13:30'), o None. Usado por
    /numeros-magicos y /curiosidades para mandar la hora de publicación
    (hora local, Uruguay) tal como la app la muestra."""
    if value is None:
        return None
    total_minutes = round(value * 60) % (24 * 60)
    h, m = divmod(total_minutes, 60)
    return '%02d:%02d' % (h, m)


def _now_local():
    """Hora actual en la zona horaria de la empresa.

    Evita el desfase UTC: en Uruguay (UTC-3) después de las 21:00 el servidor
    UTC ya está en el día siguiente, pero los cálculos de día-de-semana y
    semana-del-mes deben reflejar la hora local del usuario.
    """
    tz_name = request.env.company.partner_id.tz or 'America/Montevideo'
    return datetime.now(pytz.timezone(tz_name))


class LotteryAppApi(http.Controller):

    @http.route('/api/lottery/v1/sorteos', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def sorteos(self, **kwargs):
        sorteos = request.env['lottery.sorteo'].sudo().search(
            [('show_in_app', '=', True)], order='sequence, id')
        min_build = request.env['ir.config_parameter'].sudo().get_param(
            'lottery_api.min_build_number')
        return _json_response({
            'sorteos': [{
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'uses_fireball': s.uses_fireball,
                'uses_hundreds': s.uses_hundreds,
                # Solo el ISO: el nombre del país y la bandera los resuelve la
                # app, que ya es bilingüe y arma el emoji desde el código.
                'country_code': s.country_id.code or None,
            } for s in sorteos],
            'default_id': sorteos[0].id if sorteos else None,
            # Build mínimo requerido (versionCode de Android); 0 = sin
            # exigencia. La app lo compara contra su propio PackageInfo y
            # bloquea con una pantalla de actualización obligatoria si está
            # por debajo. Ajustable en Ajustes → Loterías → Actualización
            # obligatoria.
            'min_build_number': int(min_build or 0),
        })

    @http.route('/api/lottery/v1/results/latest', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def latest_results(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        Output = request.env['lottery.output'].sudo()
        latest = {
            turn: _serialize_output(Output.search(
                [('turn_day', '=', turn), ('sorteo_id', '=', sorteo.id)],
                order='date desc', limit=1))
            for turn in ('afternoon', 'evening')
        }

        next_date, next_turn = sorteo.get_next_draw()
        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name, 'code': sorteo.code,
                       'uses_fireball': sorteo.uses_fireball,
                       'uses_hundreds': sorteo.uses_hundreds},
            'afternoon': latest['afternoon'],
            'evening': latest['evening'],
            'next_draw': {'date': next_date, 'turn': next_turn,
                          'turn_label': TURN_LABELS.get(next_turn)},
        })

    @http.route('/api/lottery/v1/results/search', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def search_results(self, date=None, sorteo_id=None, **kwargs):
        if not date:
            return _json_response({'error': 'missing_date'}, status=400)
        try:
            date_dt = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return _json_response({'error': 'invalid_date'}, status=400)

        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        salidas = request.env['lottery.output'].sudo().search([
            ('date', '=', date), ('sorteo_id', '=', sorteo.id)])

        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name, 'code': sorteo.code},
            'date': date,
            'weekday': WEEKDAYS_ES[date_dt.weekday()],
            'afternoon': _serialize_output(salidas.filtered(lambda s: s.turn_day == 'afternoon')[:1]),
            'evening': _serialize_output(salidas.filtered(lambda s: s.turn_day == 'evening')[:1]),
        })

    # ── Estadísticas (mismos servicios que la homepage /inicio) ──────────

    def _stats(self):
        return request.env['lottery.stats.service'].sudo()

    def _resolve_day(self, day):
        """Código de día ('lu'..'do'); por defecto, el día de hoy."""
        if day in VALID_DAYS:
            return day
        return VALID_DAYS[_now_local().weekday()]

    def _resolve_tombola_day(self):
        """Día de hoy en código 'lu'..'sa' para Tómbola. Los domingos no hay
        sorteo, así que ese día se informa como el lunes (próximo sorteo)."""
        code = VALID_DAYS[_now_local().weekday()]
        return code if code in TOMBOLA_VALID_DAYS else 'lu'

    @http.route('/api/lottery/v1/stats/atrasos-numeros', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_numeros(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        stats = self._stats()
        return _json_response({
            'general': stats.get_top_10_general(sorteo_id=sorteo.id),
            'afternoon': stats.get_top_10_dia(sorteo_id=sorteo.id),
            'evening': stats.get_top_10_noche(sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/atrasos-numeros-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_numeros_dia(self, sorteo_id=None, day=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        day = self._resolve_day(day)
        return _json_response({
            'day': day,
            'items': self._stats().get_top_10_por_dia_semana(day, sorteo_id=sorteo.id),
        })

    def _attach_corridos(self, items, sorteo_id):
        """Agrega premio2/premio3 (números corridos) por turno a las filas de
        salidas (que vienen de la MV, sin esos campos). Claves nuevas:
        premio2_dia, premio3_dia, premio2_noche, premio3_noche."""
        dates = [i['date'] for i in items if i.get('date')]
        if not dates:
            return items
        request.env.cr.execute("""
            SELECT o.date, o.turn_day, n2.name AS p2, n3.name AS p3
            FROM lottery_output o
            LEFT JOIN lottery_number n2 ON n2.id = o.premio_2_id
            LEFT JOIN lottery_number n3 ON n3.id = o.premio_3_id
            WHERE o.sorteo_id = %s AND o.date = ANY(%s)
              AND (o.premio_2_id IS NOT NULL OR o.premio_3_id IS NOT NULL)
        """, (sorteo_id, dates))
        corridos = {(r['date'], r['turn_day']): r
                    for r in request.env.cr.dictfetchall()}
        for item in items:
            for turn, suffix in (('afternoon', 'dia'), ('evening', 'noche')):
                row = corridos.get((item.get('date'), turn))
                item['premio2_' + suffix] = (
                    str(row['p2']).zfill(2) if row and row['p2'] is not None else None)
                item['premio3_' + suffix] = (
                    str(row['p3']).zfill(2) if row and row['p3'] is not None else None)
        return items

    @http.route('/api/lottery/v1/stats/salidas-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def salidas_dia(self, sorteo_id=None, day=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        day = self._resolve_day(day)
        items = self._stats().get_ultimas_salidas_por_dia(day, sorteo_id=sorteo.id)
        return _json_response({
            'day': day,
            'items': self._attach_corridos(items, sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/ultimas-salidas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def ultimas_salidas(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        items = self._stats().get_ultimas_salidas_col1(sorteo_id=sorteo.id)
        return _json_response({
            'items': self._attach_corridos(items, sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/atrasos-lineas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_lineas(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(
            self._stats().get_all_atrasos_lineas(sorteo_id=sorteo.id))

    @http.route('/api/lottery/v1/stats/atrasos-terminales', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_terminales(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(
            self._stats().get_all_atrasos_terminales(sorteo_id=sorteo.id))

    @http.route('/api/lottery/v1/stats/atrasos-parejas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_parejas(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(
            self._stats().get_all_atrasos_parejas(sorteo_id=sorteo.id))

    @http.route('/api/lottery/v1/stats/atrasos-centenas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_centenas(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        stats = self._stats()
        if not sorteo.uses_hundreds:
            return _json_response({
                'uses_hundreds': False,
                'general': [], 'afternoon': [], 'evening': [],
            })
        return _json_response({
            'uses_hundreds': True,
            'general': stats.get_top5_centenas_general(sorteo_id=sorteo.id)[:4],
            'afternoon': stats.get_top5_centenas_afternoon(sorteo_id=sorteo.id)[:4],
            'evening': stats.get_top5_centenas_evening(sorteo_id=sorteo.id)[:4],
        })

    @http.route('/api/lottery/v1/stats/atrasos-bola-extra', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def atrasos_bola_extra(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        stats = self._stats()
        return _json_response({
            'general': stats.get_top5_bola_extra_general(sorteo_id=sorteo.id)[:4],
            'afternoon': stats.get_top5_bola_extra_afternoon(sorteo_id=sorteo.id)[:4],
            'evening': stats.get_top5_bola_extra_evening(sorteo_id=sorteo.id)[:4],
        })

    @http.route('/api/lottery/v1/stats/secuencias-grupos', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def secuencias_grupos(self, sorteo_id=None, **kwargs):
        """Para cada línea/terminal, top 5 grupos que más salen a continuación."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(
            self._stats().get_all_group_sequences(sorteo_id=sorteo.id))

    @http.route('/api/lottery/v1/stats/numeros-magicos', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def numeros_magicos(self, sorteo_id=None, **kwargs):
        """Predicción de números (lottery.prediction) para el próximo sorteo.

        Si no hay predicción cargada para esa fecha/turno, found = false y la
        app muestra el aviso de "todavía no se han definido".
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        date_str, turn = sorteo.get_next_draw()
        base = {
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'date': date_str,
            'weekday': WEEKDAYS_ES[datetime.strptime(date_str, '%Y-%m-%d').weekday()],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn, turn),
        }

        prediction = request.env['lottery.prediction'].sudo().search([
            ('sorteo_id', '=', sorteo.id),
            ('date', '=', date_str),
            ('turn_day', '=', turn),
            ('published', '=', True),
        ], limit=1)

        def _nums(field):
            return [str(n).zfill(2) for n in sorted(field.mapped('name'))]

        if not prediction or not (
            prediction.number_ids or prediction.number_ids_20
            or prediction.number_ids_10 or prediction.number_ids_5
        ):
            return _json_response(dict(
                base, found=False,
                numbers=[], numbers_20=[], numbers_10=[], numbers_5=[],
                super_magico=None, hour=None,
            ))

        return _json_response(dict(
            base, found=True,
            numbers=_nums(prediction.number_ids),
            numbers_20=_nums(prediction.number_ids_20),
            numbers_10=_nums(prediction.number_ids_10),
            numbers_5=_nums(prediction.number_ids_5),
            super_magico=(
                str(prediction.super_magico_id.name).zfill(2)
                if prediction.super_magico_id else None),
            # Hora de publicación (hora local, Uruguay): la app la rotula
            # "Hora de Uruguay" en el header de Números Mágicos.
            hour=_fmt_hour(prediction.hour),
        ))

    @http.route('/api/lottery/v1/stats/grupos-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def grupos_dia(self, sorteo_id=None, day=None, **kwargs):
        """Top 2 grupos, líneas y terminales más atrasados de un día de semana."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        day = self._resolve_day(day)
        data = self._stats().get_grupos_por_dia(day, sorteo_id=sorteo.id)
        data['day'] = day
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/recomendados', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def recomendados(self, sorteo_id=None, **kwargs):
        """Líneas y terminales recomendados por LotoAnálisis para el próximo
        sorteo, con los números de cruce (combinación) debajo."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        date_str, turn = sorteo.get_next_draw()
        if turn not in ('afternoon', 'evening'):
            turn = 'afternoon'
        data = self._stats().get_lineas_terminales_probables(
            turn, date_str, sorteo_id=sorteo.id)
        # El desglose de puntajes es interno; la app no lo necesita.
        for side in ('lineas', 'terminales'):
            for item in data.get(side) or []:
                item.pop('breakdown', None)
        return _json_response(data)

    def _grupos_atrasados_payload(self, sorteo, top_fn, analysis_limit):
        """Payload común de grupos/pintas atrasados: por turno, cada grupo con
        sus 4 contadores de atraso, los números que lo forman (ordenados por
        el atraso del turno) y el análisis de números que muestra la web."""
        stats = self._stats()
        now = _now_local()
        day = VALID_DAYS[now.weekday()]
        week = (now.day + 6) // 7  # semana del mes, como la web (ceil(día/7))
        month = now.month
        field_map = {'general': 'salidas_atrasadas',
                     'afternoon': 'salidas_atrasadas_dia',
                     'evening': 'salidas_atrasadas_noche'}
        orden_map = {'general': 'total_atrasadas',
                     'afternoon': 'total_atrasadas_dia',
                     'evening': 'total_atrasadas_noche'}
        Group = request.env['lottery.group'].sudo()

        payload = {
            'day': day,
            'day_label': WEEKDAYS_ES[now.weekday()],
            'week_label': WEEK_LABELS.get(week, ''),
            'month_label': MONTHS_ES[month - 1],
        }
        analysis_cache = {}
        for option, field in field_map.items():
            items = []
            for r in top_fn(option, day, sorteo_id=sorteo.id):
                gid = r['id']
                if gid not in analysis_cache:
                    analysis_cache[gid] = stats.get_info_group_numbers_analysis(
                        gid, day, week, month, analysis_limit,
                        sorteo_id=sorteo.id)
                numbers = stats.get_info_groups_numbers(
                    Group.browse(gid), orden_map[option], day,
                    sorteo_id=sorteo.id)
                items.append({
                    'id': gid,
                    'name': r['name'],
                    'atraso': r[field] or 0,
                    'salidas_atrasadas': r['salidas_atrasadas'] or 0,
                    'salidas_atrasadas_dia': r['salidas_atrasadas_dia'] or 0,
                    'salidas_atrasadas_noche': r['salidas_atrasadas_noche'] or 0,
                    'salidas_atrasadas_por_dia': r['salidas_atrasadas_por_dia'] or 0,
                    'numbers': [n['numero'] for n in numbers],
                    'analysis': analysis_cache[gid],
                })
            payload[option] = items
        return payload

    @http.route('/api/lottery/v1/stats/grupos-atrasados', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def grupos_atrasados(self, sorteo_id=None, **kwargs):
        """Top 5 grupos más atrasados por turno, con números y análisis."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(self._grupos_atrasados_payload(
            sorteo, self._stats().get_top_6_groups, analysis_limit=3))

    @http.route('/api/lottery/v1/stats/pintas-atrasadas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def pintas_atrasadas(self, sorteo_id=None, **kwargs):
        """Top 3 pintas más atrasadas por turno, con números y análisis."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response(self._grupos_atrasados_payload(
            sorteo, self._stats().get_top_3_pintas, analysis_limit=8))

    PINTA_CODES = ['pinta_%d' % i for i in range(10)]

    @http.route('/api/lottery/v1/stats/grupos-lista', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def grupos_lista(self, tipo='grupos', **kwargs):
        """Grupos disponibles para el gráfico de históricos."""
        domain = ([('code', 'in', self.PINTA_CODES)] if tipo == 'pintas'
                  else [('code', 'not in', self.PINTA_CODES)])
        grupos = request.env['lottery.group'].sudo().search(domain, order='name')
        return _json_response({
            'items': [{'id': g.id, 'name': g.name, 'code': g.code}
                      for g in grupos],
        })

    @http.route('/api/lottery/v1/stats/grupo-historico', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def grupo_historico(self, group_id=None, tipo='grupos', sorteo_id=None,
                        **kwargs):
        """Histograma de intervalos de atraso de un grupo, por turno."""
        if not group_id or not str(group_id).isdigit():
            return _json_response({'error': 'invalid_group'}, status=400)
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        group = request.env['lottery.group'].sudo().browse(int(group_id))
        if not group.exists():
            return _json_response({'error': 'group_not_found'}, status=404)

        stats = self._stats()
        method = (stats.get_group_delay_intervals_pintas if tipo == 'pintas'
                  else stats.get_group_delay_intervals)
        return _json_response({
            'group': {'id': group.id, 'name': group.name},
            'general': method(group.id, sorteo_id=sorteo.id),
            'afternoon': method(group.id, 'afternoon', sorteo_id=sorteo.id),
            'evening': method(group.id, 'evening', sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/numeros-mes', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def numeros_mes(self, sorteo_id=None, **kwargs):
        """Números que más / menos salen en el mes actual + intermedios,
        con las salidas que van registrando en el mes (mismas 3 tablas de
        /estadisticas-numeros)."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        stats = self._stats()
        now = _now_local()
        return _json_response({
            'month': now.month,
            'month_label': MONTHS_ES[now.month - 1],
            'year': now.year,
            'top': stats.get_top_numbers_month(
                now.month, now.year, sorteo_id=sorteo.id),
            'intermedios': stats.get_remaining_numbers_month(
                now.month, now.year, sorteo_id=sorteo.id),
            'bottom': stats.get_bottom_numbers_month(
                now.month, now.year, sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/consulta-combinaciones', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def consulta_combinaciones(self, sorteo_id=None, date=None, window=15,
                               top=25, **kwargs):
        """N números candidatos por combinación de dígitos (versión app del
        wizard lottery.consulta.combinaciones). Params: sorteo_id, date
        (YYYY-MM-DD, default hoy), window (default 15), top (default 25,
        tope 50)."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        try:
            day = (datetime.strptime(date, '%Y-%m-%d').date()
                   if date else _now_local().date())
        except (TypeError, ValueError):
            day = _now_local().date()
        try:
            win = max(1, min(int(window), 200))
        except (TypeError, ValueError):
            win = 15
        try:
            top_n = max(1, min(int(top), 50))
        except (TypeError, ValueError):
            top_n = 25
        data = self._stats().get_combinaciones(sorteo.id, day, win, top_n)
        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'date': day.strftime('%d/%m/%Y'),
            'day_month': day.strftime('%d/%m'),
            'window_requested': win,
            'top_requested': top_n,
            **data,
        })

    @http.route('/api/lottery/v1/tabla-acompanantes', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tabla_acompanantes(self, sorteo_id=None, turno='general', **kwargs):
        """Tabla LotoAnálisis 12×12 (versión app del wizard
        lottery.tabla.acompanantes). La fecha de corte NO es un parámetro: se
        toma de Ajustes → Loterías (company.tabla_acompanantes_fecha_referencia,
        o hoy si no hay). Params: sorteo_id, turno (general|afternoon|evening).
        Los acompañantes (misma fila/columna/diagonal) los resuelve la app
        sobre la grilla — acá solo se devuelve la matriz de celdas."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        if turno not in ('general', 'afternoon', 'evening'):
            turno = 'general'
        company = request.env.company.sudo()
        fecha_corte = (company.tabla_acompanantes_fecha_referencia
                       or _now_local().date())
        size = 12
        grid = request.env['lottery.tabla.acompanantes.cache'].sudo().get_grid(
            sorteo.id, fecha_corte, turno, str(size))
        # Matriz de celdas: número (con su línea = decena) o cara decorativa
        # (mateo/valeria alternadas en orden de lectura, igual que la web).
        face_i = 0
        cells = []
        for r in range(size):
            row = []
            for c in range(size):
                n = grid.get((r, c))
                if n is not None:
                    row.append({'number': n, 'line': n // 10})
                else:
                    row.append(
                        {'face': 'mateo' if face_i % 2 == 0 else 'valeria'})
                    face_i += 1
            cells.append(row)
        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'turno': turno,
            'size': size,
            'cells': cells,
        })

    @http.route('/api/lottery/v1/patron-atraso', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def patron_atraso(self, sorteo_id=None, date=None, patron='cruce',
                      **kwargs):
        """Atraso de patrones línea/terminal (versión app del wizard
        lottery.patron.atraso). Params: sorteo_id, date (YYYY-MM-DD, default
        hoy — es el corte del historial y define el día de la semana de las
        categorías por día), patron (cruce|repeticion)."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        try:
            day = (datetime.strptime(date, '%Y-%m-%d').date()
                   if date else _now_local().date())
        except (TypeError, ValueError):
            day = _now_local().date()
        data = request.env['lottery.patron.atraso'].sudo() \
            .compute_patron_atraso(sorteo.id, day, patron)
        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'date': day.strftime('%d/%m/%Y'),
            **data,
        })

    @http.route('/api/lottery/v1/curiosidades', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def curiosidades(self, sorteo_id=None, limit=50, **kwargs):
        """Curiosidades publicadas del sorteo, para la sección
        "LotoAnálisis informa" de la app (estilo noticias, más reciente
        primero). Solo se devuelven las marcadas como publicadas."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        try:
            limit = min(max(int(limit), 1), 200)
        except (TypeError, ValueError):
            limit = 50

        curiosities = request.env['lottery.curiosity'].sudo().search([
            ('sorteo_id', '=', sorteo.id),
            ('published', '=', True),
        ], order='date desc, id desc', limit=limit)

        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'items': [{
                'id': c.id,
                'date': c.date.strftime('%d/%m/%Y'),
                'weekday': WEEKDAYS_ES[c.date.weekday()],
                # Hora de publicación (hora local, Uruguay): la app la
                # rotula "Hora de Uruguay" junto a la fecha de la noticia.
                'hour': _fmt_hour(c.hour),
                'text': c.text,
                # Traducción opcional; si está vacía la app cae al español.
                'text_en': c.text_en or None,
            } for c in curiosities],
        })

    @http.route('/api/lottery/v1/stats/numeros-mes-atrasados', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def numeros_mes_atrasados(self, sorteo_id=None, years_top=2,
                              years_intermedios=2, years_bottom=4, **kwargs):
        """Números del mes con atraso en años, en 3 secciones por categoría.

        Por cada categoría de /numeros-mes (top / intermedios / bottom)
        devuelve los números que llevan N o más años completos sin salir en
        el mes actual — sin contar el año en curso, que es el que se evalúa.
        Umbrales por defecto: top e intermedios ≥ 2 años, bottom ≥ 4 (se
        pueden ajustar por query param: years_top, years_intermedios,
        years_bottom).

        Estructura por categoría:
          all            → Sección 1: todos los que cumplen el umbral
          salieron_anio  → Sección 2: de la 1, ya salieron en el año actual
          sin_salir_anio → Sección 3: de la 1, aún no salen este año
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        try:
            years_top = max(int(years_top), 0)
            years_intermedios = max(int(years_intermedios), 0)
            years_bottom = max(int(years_bottom), 0)
        except (TypeError, ValueError):
            return _json_response({'error': 'invalid_years_param'}, status=400)

        now = _now_local()
        data = self._stats().get_month_overdue_sections(
            now.month, now.year, sorteo_id=sorteo.id,
            years_top=years_top, years_mid=years_intermedios,
            years_bottom=years_bottom)
        return _json_response(dict(
            data,
            month=now.month,
            month_label=MONTHS_ES[now.month - 1],
            year=now.year,
        ))

    @http.route('/api/lottery/v1/stats/numeros-salidas-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def numeros_salidas_dia(self, sorteo_id=None, **kwargs):
        """Top / bottom 15 números por día de la semana (todos los días en
        una sola respuesta; la app cambia de día sin volver a consultar)."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        data = self._stats().get_numbers_all_weekdays(sorteo_id=sorteo.id)
        data['day'] = VALID_DAYS[_now_local().weekday()]
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/numeros-salidas-semana', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def numeros_salidas_semana(self, sorteo_id=None, **kwargs):
        """Top / bottom 15 números por semana del mes (sem_1..sem_5)."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        data = self._stats().get_numbers_all_weeks(sorteo_id=sorteo.id)
        data['week'] = 'sem_%d' % min((_now_local().day + 6) // 7, 5)
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/centenas-bolas-salidas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def centenas_bolas_salidas(self, sorteo_id=None, **kwargs):
        """Centenas y bolas extra que más / menos salen: histórico global,
        por día de la semana y por semana del mes."""
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        stats = self._stats()
        Output = request.env['lottery.output'].sudo()

        def historico(field):
            groups = Output.read_group(
                [('sorteo_id', '=', sorteo.id), (field, '!=', False)],
                ['id'], [field])
            items = sorted(
                ({'centena': g[field][1], 'total_salidas': g[f'{field}_count']}
                 for g in groups if g.get(field)),
                key=lambda x: x['total_salidas'], reverse=True)
            return {'top': items[:4], 'bottom': list(reversed(items[-4:]))}

        # Sin centena las consultas ya devuelven vacío solas (no hay filas con
        # hundreds_id), y estos dicts traen también la bola extra: se llaman
        # igual para no alterar la forma del JSON ni perder la bola.
        _now = _now_local()
        return _json_response({
            'day': VALID_DAYS[_now.weekday()],
            'week': 'sem_%d' % min((_now.day + 6) // 7, 5),
            'uses_hundreds': bool(sorteo.uses_hundreds),
            'historico': {
                'centena': historico('hundreds_id'),
                'bola': historico('fireball_id'),
            },
            'por_dia': stats.get_centenas_all_weekdays(sorteo_id=sorteo.id),
            'por_semana': stats.get_centenas_all_weeks(sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/faq', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def faq(self, **kwargs):
        """Preguntas frecuentes del sitio, agrupadas por categoría (mismos
        datos que la página /faq de la web)."""
        categories = request.env['website.faq.category'].sudo().search(
            [], order='sequence, id')
        faqs = request.env['website.faq'].sudo().search(
            [('active', '=', True)], order='sequence, id')
        by_cat = {}
        for f in faqs:
            by_cat.setdefault(f.category_id.id, []).append({
                'question': f.question,
                'answer': f.answer,
            })
        return _json_response({
            'categories': [{
                'id': c.id,
                'name': c.name,
                'icon': c.icon,
                'faqs': by_cat.get(c.id, []),
            } for c in categories if by_cat.get(c.id)],
        })

    @http.route('/api/lottery/v1/stats/acompanantes', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def acompanantes(self, numero=None, sorteo_id=None, **kwargs):
        if numero is None or not str(numero).strip().isdigit():
            return _json_response({'error': 'invalid_number'}, status=400)
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        number = request.env['lottery.number'].sudo().search(
            [('name', '=', int(numero))], limit=1)
        if not number:
            return _json_response({'error': 'number_not_found'}, status=404)

        stats = self._stats()
        return _json_response({
            'numero': str(numero).zfill(2),
            'despues': stats.get_salidas_numeros_despues_numero(
                number.id, sorteo_id=sorteo.id),
            'antes': stats.get_salidas_numeros_antes_numero(
                number.id, sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/historial-fechas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def historial_fechas(self, sorteo_id=None, **kwargs):
        """Fechas disponibles en el historial de predicciones.

        Devuelve la lista de fechas (más reciente primero) en las que hay una
        predicción publicada para el sorteo, indicando qué turnos están
        disponibles por fecha. Respeta la fecha mínima configurada en
        lottery_api.historial_desde.
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        since = request.env['ir.config_parameter'].sudo().get_param(
            'lottery_api.historial_desde')

        domain = [
            ('sorteo_id', '=', sorteo.id),
            ('published', '=', True),
        ]
        if since:
            domain.append(('date', '>=', since))

        preds = request.env['lottery.prediction'].sudo().search(
            domain, order='date desc, id desc')

        by_date = {}
        for p in preds:
            key = p.date.isoformat()
            if key not in by_date:
                by_date[key] = []
            if p.turn_day not in by_date[key]:
                by_date[key].append(p.turn_day)

        return _json_response({
            'since': since or None,
            'dates': [{'date': d, 'turns': turns}
                      for d, turns in by_date.items()],
        })

    @http.route('/api/lottery/v1/stats/historial-resumen', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def historial_resumen(self, sorteo_id=None, year=None, month=None,
                          solo_aciertos='1', **kwargs):
        """Dashboard del historial de predicciones.

        Devuelve en una sola llamada: los totales de aciertos por sublista
        (todos / 20 / 10 / 5), el desglose por año y mes, y la lista de fechas
        con sus turnos. Los totales y el desglose son SIEMPRE del histórico
        completo; year/month y solo_aciertos filtran solo la lista de fechas.

        Una predicción cuenta en los totales únicamente si ya se jugó el
        sorteo, y cada sublista tiene su propio denominador (si no se cargaron
        los 10 o los 5 de esa fecha, no cuentan como fallo).
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        try:
            year = int(year) if year else None
            month = int(month) if month else None
        except (TypeError, ValueError):
            return _json_response({'error': 'invalid_period'}, status=400)

        only_hits = str(solo_aciertos).lower() not in ('0', 'false', 'no')

        since = request.env['ir.config_parameter'].sudo().get_param(
            'lottery_api.historial_desde')

        domain = [
            ('sorteo_id', '=', sorteo.id),
            ('published', '=', True),
        ]
        if since:
            domain.append(('date', '>=', since))

        preds = request.env['lottery.prediction'].sudo().search(
            domain, order='date desc, turn_day desc')

        # Salidas del rango: dan el número ganador y permiten considerar
        # "evaluada" una predicción cargada después de registrada la salida
        # (en ese caso verification_date queda vacío).
        results = {}
        if preds:
            dates = preds.mapped('date')
            outputs = request.env['lottery.output'].sudo().search([
                ('sorteo_id', '=', sorteo.id),
                ('date', '>=', min(dates)),
                ('date', '<=', max(dates)),
            ])
            for out in outputs:
                results[(out.date, out.turn_day)] = (
                    str(out.number_id.name).zfill(2) if out.number_id else None)

        levels = (
            ('total', 'number_ids',    'cumplida'),
            ('n20',   'number_ids_20', 'cumplida_20'),
            ('n10',   'number_ids_10', 'cumplida_10'),
            ('n5',    'number_ids_5',  'cumplida_5'),
        )
        bucket_keys = {'total': 'aciertos', 'n20': 'aciertos_20',
                       'n10': 'aciertos_10', 'n5': 'aciertos_5'}

        totales = {name: {'jugadas': 0, 'aciertos': 0} for name, _, _ in levels}
        evaluadas = 0
        periodos = {}
        by_date = {}

        for pred in preds:
            key = (pred.date, pred.turn_day)
            evaluada = bool(pred.verification_date) or key in results
            counts = {name: len(pred[field]) for name, field, _ in levels}

            if evaluada:
                evaluadas += 1
                bucket = periodos.setdefault(
                    (pred.date.year, pred.date.month),
                    {'predicciones': 0, 'aciertos': 0, 'aciertos_20': 0,
                     'aciertos_10': 0, 'aciertos_5': 0})
                bucket['predicciones'] += 1
                for name, _field, flag in levels:
                    if not counts[name]:
                        continue
                    totales[name]['jugadas'] += 1
                    if pred[flag]:
                        totales[name]['aciertos'] += 1
                        bucket[bucket_keys[name]] += 1

            if year and pred.date.year != year:
                continue
            if month and pred.date.month != month:
                continue
            hit = any(pred[flag] for _n, _f, flag in levels)
            if only_hits and not hit:
                continue

            by_date.setdefault(pred.date, []).append({
                'turn': pred.turn_day,
                'turn_label': TURN_LABELS.get(pred.turn_day, pred.turn_day),
                'result_number': results.get(key),
                'evaluada': evaluada,
                'cumplida':    pred.cumplida,
                'cumplida_20': pred.cumplida_20,
                'cumplida_10': pred.cumplida_10,
                'cumplida_5':  pred.cumplida_5,
                'counts': counts,
            })

        def _pct(data):
            return round(100.0 * data['aciertos'] / data['jugadas'], 1) \
                if data['jugadas'] else 0.0

        turn_order = {'afternoon': 0, 'evening': 1}
        by_year = {}
        for (y, m), data in periodos.items():
            entry = by_year.setdefault(y, {'year': y, 'predicciones': 0,
                                           'aciertos': 0, 'meses': []})
            entry['predicciones'] += data['predicciones']
            entry['aciertos'] += data['aciertos']
            entry['meses'].append(
                dict(data, month=m, month_label=MONTHS_ES[m - 1]))

        for entry in by_year.values():
            entry['meses'].sort(key=lambda x: x['month'], reverse=True)

        return _json_response({
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'since': since or None,
            'evaluadas': evaluadas,
            'totales': {name: dict(data, pct=_pct(data))
                        for name, data in totales.items()},
            'periodos': [by_year[y] for y in sorted(by_year, reverse=True)],
            'filtro': {'year': year, 'month': month, 'solo_aciertos': only_hits},
            'fechas': [{
                'date': d.isoformat(),
                'weekday': WEEKDAYS_ES[d.weekday()],
                'turnos': sorted(turnos,
                                 key=lambda t: turn_order.get(t['turn'], 9)),
            } for d, turnos in sorted(by_date.items(), reverse=True)],
        })

    QUINIELA_UY_TOTAL_PREMIOS = 20
    TOMBOLA_UY_TOTAL_NUMEROS = 20

    @http.route('/api/lottery/v1/stats/quiniela-uy-historico', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def quiniela_uy_historico(self, date=None, turn=None, **kwargs):
        """Los 20 premios de la Quiniela Uruguay de una fecha y turno
        puntuales (buscador histórico de la app; ver
        lottery.quiniela.uy.resultados.get_premios, mismo dato que usa el
        wizard de Odoo)."""
        if not date or turn not in ('afternoon', 'evening'):
            return _json_response({'error': 'date_and_turn_required'}, status=400)
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return _json_response({'error': 'invalid_date'}, status=400)

        premios = request.env['lottery.quiniela.uy.resultados'].sudo() \
            .get_premios(date, turn)
        return _json_response({
            'date': date,
            'weekday': WEEKDAYS_ES[date_obj.weekday()],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn, turn),
            'premios': [{'premio': p, 'numero': n} for p, n in premios],
            'total_esperado': self.QUINIELA_UY_TOTAL_PREMIOS,
            'completo': len(premios) == self.QUINIELA_UY_TOTAL_PREMIOS,
        })

    def _quiniela_uy_sorteo_ids(self, premio):
        """(sorteo_ids, premio_int, error) para el ámbito Quiniela UY: los 20
        premios juntos (General) sin `premio`, o uno puntual (1-20) con
        `premio`. `error` es el dict de _json_response si `premio` vino
        inválido o no existe; en ese caso los otros dos son None."""
        Sorteo = request.env['lottery.sorteo'].sudo()
        if not premio:
            return tuple(Sorteo.search([('source_code', '=', 'quiniela_uy')]).ids), None, None
        try:
            premio = int(premio)
        except (TypeError, ValueError):
            return None, None, {'error': 'invalid_premio'}
        sorteo = Sorteo.search([
            ('source_code', '=', 'quiniela_uy'),
            ('code', '=', 'quiniela_uy_%d' % premio),
        ], limit=1)
        if not sorteo:
            return None, None, {'error': 'premio_not_found'}
        return (sorteo.id,), premio, None

    @http.route('/api/lottery/v1/stats/quiniela-uy-ternas-atrasadas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def quiniela_uy_ternas_atrasadas(self, premio=None, **kwargs):
        """Top 20 ternas (números de 3 cifras, 000-999) más atrasadas de la
        Quiniela Uruguay. Sin `premio`: ámbito General, los 20 premios
        juntos (una terna "sale" si salió en cualquiera). Con `premio`
        (1-20): solo ese premio. Reusa el cálculo del wizard de Odoo
        lottery.quiniela.uy.ternas (get_ternas_atrasadas), ya cacheado e
        invalidado junto con las demás stats de lottery.output."""
        sorteo_ids, premio, error = self._quiniela_uy_sorteo_ids(premio)
        if error:
            return _json_response(error, status=404 if error['error'] == 'premio_not_found' else 400)

        Ternas = request.env['lottery.quiniela.uy.ternas'].sudo()
        fecha_corte = str(_now_local().date())
        ternas = Ternas.get_ternas_atrasadas(sorteo_ids, 'general', fecha_corte)[:20]
        return _json_response({
            'premio': premio,
            'ternas': [dict(t, rank=i + 1) for i, t in enumerate(ternas)],
        })

    @http.route('/api/lottery/v1/stats/quiniela-uy-centenas-numero', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def quiniela_uy_centenas_numero(self, premio=None, **kwargs):
        """Top 3 / bottom 3 centenas que más y menos acompañan a cada número
        00-99 de la Quiniela Uruguay. Sin `premio`: ámbito General (los 20
        premios juntos). Con `premio` (1-20): solo ese premio."""
        sorteo_ids, premio, error = self._quiniela_uy_sorteo_ids(premio)
        if error:
            return _json_response(error, status=404 if error['error'] == 'premio_not_found' else 400)

        data = self._stats().get_quiniela_uy_centenas_top_bottom(sorteo_ids)
        return _json_response({'premio': premio, 'numeros': data})

    @http.route('/api/lottery/v1/stats/quiniela-uy-ternas-tombola', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def quiniela_uy_ternas_tombola(self, **kwargs):
        """Predicción de ternas y de las líneas de Tómbola (7 números cada
        una) para el próximo sorteo de la Quiniela Uruguay
        (lottery.prediction, campos terna_ids / tombola_linea_ids). Se
        cargan siempre en la predicción del premio 1: el dato es del sorteo
        completo (fecha y turno), no de un premio en particular, así que no
        hace falta pedirle `premio` al cliente."""
        sorteo = request.env['lottery.sorteo'].sudo().search([
            ('source_code', '=', 'quiniela_uy'),
            ('code', '=', 'quiniela_uy_1'),
        ], limit=1)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        date_str, turn = sorteo.get_next_draw()
        base = {
            'date': date_str,
            'weekday': WEEKDAYS_ES[datetime.strptime(date_str, '%Y-%m-%d').weekday()],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn, turn),
        }

        prediction = request.env['lottery.prediction'].sudo().search([
            ('sorteo_id', '=', sorteo.id),
            ('date', '=', date_str),
            ('turn_day', '=', turn),
            ('published', '=', True),
        ], limit=1)

        if not prediction or not (prediction.terna_ids or prediction.tombola_linea_ids):
            return _json_response(dict(base, found=False, ternas=[], tombola_lineas=[]))

        def _linea_numeros(linea):
            campos = (linea.numero_1, linea.numero_2, linea.numero_3, linea.numero_4,
                      linea.numero_5, linea.numero_6, linea.numero_7)
            return sorted(str(n.name).zfill(2) for n in campos if n)

        return _json_response(dict(
            base, found=True,
            ternas=sorted(prediction.terna_ids.mapped('terna')),
            tombola_lineas=[_linea_numeros(l) for l in prediction.tombola_linea_ids],
        ))

    @http.route('/api/lottery/v1/stats/tombola-uy-historico', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_uy_historico(self, date=None, turn=None, **kwargs):
        """Los números de la Tómbola de la Quiniela Uruguay de una fecha y
        turno puntuales, ordenados de menor a mayor (buscador histórico de
        la app; juego aparte de la Quiniela, ver lottery.tombola.output)."""
        if not date or turn not in ('afternoon', 'evening'):
            return _json_response({'error': 'date_and_turn_required'}, status=400)
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return _json_response({'error': 'invalid_date'}, status=400)

        outputs = request.env['lottery.tombola.output'].sudo().search([
            ('date', '=', date), ('turn_day', '=', turn),
        ])
        numeros = sorted(str(o.number_id.name).zfill(2) for o in outputs)
        return _json_response({
            'date': date,
            'weekday': WEEKDAYS_ES[date_obj.weekday()],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn, turn),
            'numeros': numeros,
            'total_esperado': self.TOMBOLA_UY_TOTAL_NUMEROS,
            'completo': len(numeros) == self.TOMBOLA_UY_TOTAL_NUMEROS,
        })

    @http.route('/api/lottery/v1/stats/tombola-atrasos-numeros', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_atrasos_numeros(self, **kwargs):
        """Top 10 números más atrasados de la Tómbola: general, tarde y
        noche. Juego aparte de la Quiniela (sin sorteo_id), ver
        lottery.tombola.number.stat."""
        stats = self._stats()
        return _json_response({
            'general': stats.get_tombola_top_10_general(),
            'afternoon': stats.get_tombola_top_10_dia(),
            'evening': stats.get_tombola_top_10_noche(),
        })

    @http.route('/api/lottery/v1/stats/tombola-numeros-salidas-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_numeros_salidas_dia(self, **kwargs):
        """Top/bottom 15 números que más/menos salen en la Tómbola por día
        de la semana (lu..sa; sin domingo, no hay sorteo ese día)."""
        data = self._stats().get_tombola_numbers_all_weekdays()
        data['day'] = self._resolve_tombola_day()
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/tombola-numeros-salidas-semana', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_numeros_salidas_semana(self, **kwargs):
        """Top/bottom 15 números que más/menos salen en la Tómbola por
        semana del mes (sem_1..sem_5)."""
        data = self._stats().get_tombola_numbers_all_weeks()
        data['week'] = 'sem_%d' % min((_now_local().day + 6) // 7, 5)
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/tombola-grupos-salidas-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_grupos_salidas_dia(self, **kwargs):
        """Líneas y terminales de Tómbola que más salen, por día de semana
        (lu..sa; sin domingo, no hay sorteo ese día)."""
        data = self._stats().get_tombola_groups_all_weekdays()
        data['day'] = self._resolve_tombola_day()
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/tombola-grupos-salidas-semana', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_grupos_salidas_semana(self, **kwargs):
        """Líneas y terminales de Tómbola que más salen, por semana del mes
        (sem_1..sem_5)."""
        data = self._stats().get_tombola_groups_all_weeks()
        data['week'] = 'sem_%d' % min((_now_local().day + 6) // 7, 5)
        return _json_response(data)

    @http.route('/api/lottery/v1/stats/tombola-numeros-mes', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def tombola_numeros_mes(self, **kwargs):
        """Números de Tómbola del mes actual: más salen / intermedios / menos
        salen. Mismo patrón que /numeros-mes de las loterías con sorteo."""
        stats = self._stats()
        now = _now_local()
        return _json_response({
            'month': now.month,
            'month_label': MONTHS_ES[now.month - 1],
            'year': now.year,
            'top': stats.get_tombola_top_numbers_month(now.month, now.year),
            'intermedios': stats.get_tombola_remaining_numbers_month(now.month, now.year),
            'bottom': stats.get_tombola_bottom_numbers_month(now.month, now.year),
        })

    @http.route('/api/lottery/v1/stats/historial-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def historial_dia(self, sorteo_id=None, date=None, turn=None, **kwargs):
        """Detalle de la predicción de un día y turno concreto.

        Devuelve los 4 sublistas predichas (total, 20, 10, 5), el número
        ganador real (si ya se jugó) y los 4 booleanos de cumplimiento.
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        if not date or not turn:
            return _json_response({'error': 'date_and_turn_required'}, status=400)

        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return _json_response({'error': 'invalid_date'}, status=400)

        pred = request.env['lottery.prediction'].sudo().search([
            ('sorteo_id', '=', sorteo.id),
            ('date', '=', date),
            ('turn_day', '=', turn),
            ('published', '=', True),
        ], limit=1)

        if not pred:
            return _json_response({'error': 'not_found'}, status=404)

        output = request.env['lottery.output'].sudo().search([
            ('sorteo_id', '=', sorteo.id),
            ('date', '=', date),
            ('turn_day', '=', turn),
        ], limit=1)

        def _nums(field):
            return [str(n).zfill(2) for n in sorted(field.mapped('name'))]

        return _json_response({
            'date': date,
            'weekday': WEEKDAYS_ES[date_obj.weekday()],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn, turn),
            'sorteo': {'id': sorteo.id, 'name': sorteo.name},
            'result_number': (
                str(output.number_id.name).zfill(2)
                if output and output.number_id else None
            ),
            'cumplida':    pred.cumplida,
            'cumplida_20': pred.cumplida_20,
            'cumplida_10': pred.cumplida_10,
            'cumplida_5':  pred.cumplida_5,
            'numbers':    _nums(pred.number_ids),
            'numbers_20': _nums(pred.number_ids_20),
            'numbers_10': _nums(pred.number_ids_10),
            'numbers_5':  _nums(pred.number_ids_5),
            # Para resaltar en el tab "5" cuál de esos 5 números era la
            # apuesta fuerte (aro de estrellitas en la app); no agrega un
            # nivel nuevo al historial, sólo decora la lista de 5 que ya
            # existe.
            'super_magico': (
                str(pred.super_magico_id.name).zfill(2)
                if pred.super_magico_id else None),
        })
