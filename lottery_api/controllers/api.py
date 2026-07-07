# -*- coding: utf-8 -*-
"""Endpoints REST públicos para la app móvil LotoAnálisis.

A diferencia de las rutas type='json' del portal (JSON-RPC), estas rutas son
GET planos que devuelven application/json, con CORS abierto para poder
consumirlas desde la app (y desde Chrome durante el desarrollo Flutter web).
"""

import json
from datetime import datetime

from odoo import http
from odoo.http import request

WEEKDAYS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
TURN_LABELS = {'afternoon': 'Tarde', 'evening': 'Noche'}


VALID_DAYS = ('lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do')


def _json_response(payload, status=200):
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
        'centena': str(record.hundreds_id.name),
        'numero': str(record.number_id.name).zfill(2),
        'extra': str(record.fireball_id.name) if record.fireball_id else None,
    }


def _get_public_sorteo(sorteo_id):
    """Devuelve el sorteo pedido solo si es visible públicamente; si no se
    pide ninguno, el primero público."""
    Sorteo = request.env['lottery.sorteo'].sudo()
    domain = [('show_in_public', '=', True)]
    if sorteo_id:
        sorteo = Sorteo.search(domain + [('id', '=', int(sorteo_id))], limit=1)
    else:
        sorteo = Sorteo.search(domain, order='sequence, id', limit=1)
    return sorteo


class LotteryAppApi(http.Controller):

    @http.route('/api/lottery/v1/sorteos', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def sorteos(self, **kwargs):
        sorteos = request.env['lottery.sorteo'].sudo().search(
            [('show_in_public', '=', True)], order='sequence, id')
        return _json_response({
            'sorteos': [{
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'uses_fireball': s.uses_fireball,
            } for s in sorteos],
            'default_id': sorteos[0].id if sorteos else None,
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
                       'uses_fireball': sorteo.uses_fireball},
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
        return VALID_DAYS[datetime.now().weekday()]

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

    @http.route('/api/lottery/v1/stats/salidas-dia', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def salidas_dia(self, sorteo_id=None, day=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        day = self._resolve_day(day)
        return _json_response({
            'day': day,
            'items': self._stats().get_ultimas_salidas_por_dia(day, sorteo_id=sorteo.id),
        })

    @http.route('/api/lottery/v1/stats/ultimas-salidas', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def ultimas_salidas(self, sorteo_id=None, **kwargs):
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)
        return _json_response({
            'items': self._stats().get_ultimas_salidas_col1(sorteo_id=sorteo.id),
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
        return _json_response({
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

    @http.route('/api/lottery/v1/stats/proximo-sorteo', type='http',
                auth='public', methods=['GET'], csrf=False, cors='*')
    def proximo_sorteo(self, sorteo_id=None, **kwargs):
        """Mejores números por líneas para el próximo sorteo.

        La tabla de origen (calientes / restantes / fríos) se define en
        Ajustes → Loterías → App móvil; la app muestra lo que se devuelva
        aquí, sin lógica propia.
        """
        sorteo = _get_public_sorteo(sorteo_id)
        if not sorteo:
            return _json_response({'error': 'sorteo_not_found'}, status=404)

        key_map = {
            'calientes': 'numbers',
            'restantes': 'numbers_remaining',
            'frios': 'numbers_cold',
        }
        labels = {'calientes': 'Calientes', 'restantes': 'Restantes',
                  'frios': 'Fríos'}
        tabla = request.env['ir.config_parameter'].sudo().get_param(
            'lottery_api.proximo_sorteo_tabla', 'restantes')
        if tabla not in key_map:
            tabla = 'restantes'

        date_str, turn = sorteo.get_next_draw()
        snapshot = sorteo._get_ranking_snapshot() or {}
        turn_data = snapshot.get(turn) or {}
        raw_numbers = turn_data.get(key_map[tabla]) or []

        lines = {}
        for item in raw_numbers:
            try:
                n = int(item.get('name'))
            except (TypeError, ValueError):
                continue
            lines.setdefault(n // 10, []).append(str(n).zfill(2))

        return _json_response({
            'tabla': tabla,
            'tabla_label': labels[tabla],
            'turn': turn,
            'turn_label': TURN_LABELS.get(turn),
            'next_draw': turn_data.get('next_draw') or date_str,
            'lines': [{
                'line': line,
                'label': f'Línea {line}',
                'range': f'{line * 10:02d}-{line * 10 + 9:02d}',
                'numbers': sorted(nums),
            } for line, nums in sorted(lines.items())],
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
