# -*- coding: utf-8 -*-
"""API pública de la app Rifazo (sin login).

La app se identifica con un device_id (UUID generado en la instalación) y
cada solicitud con un access_token secreto que devuelve /reserve. Las URLs de
imágenes van relativas: la app les antepone la URL base del servidor.
"""

import base64
import functools
import io
import json

from PIL import Image

from odoo import fields, http
from odoo.http import request

from ..models.exceptions import RifazoApiError
from ..models.rifazo_request import normalize_phone

PREFIX = '/api/rifazo/v1'
PUBLIC_STATES = ('open', 'closed', 'drawn')
IMAGE_SIZES = (128, 256, 512, 1024, 1920)
PROOF_FORMATS = ('JPEG', 'PNG', 'WEBP')
MAX_TOKENS_PER_QUERY = 100


def _json(payload, status=200):
    return request.make_json_response(payload, status=status)


def _api(func):
    """Convierte RifazoApiError en respuesta JSON con su status."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RifazoApiError as error:
            return _json(error.to_dict(), status=error.status)
    return wrapper


def _body():
    try:
        data = json.loads(request.httprequest.get_data(as_text=True) or '{}')
    except ValueError:
        raise RifazoApiError('bad_json', 'El cuerpo no es un JSON válido.')
    if not isinstance(data, dict):
        raise RifazoApiError('bad_json', 'El cuerpo tiene que ser un objeto JSON.')
    return data


def _dt(value):
    """Datetime de Odoo (naive, UTC) → ISO 8601 con Z."""
    return value.isoformat() + 'Z' if value else None


def _seconds_left(until):
    if not until:
        return None
    return max(0, int((until - fields.Datetime.now()).total_seconds()))


def _unique(record):
    return int(record.write_date.timestamp()) if record.write_date else 0


def _public_state(raffle):
    """Estado que ve la app: una rifa abierta que ya pasó su hora de cierre
    figura como cerrada aunque el cron todavía no la haya cerrado."""
    if raffle.state == 'open' and raffle._is_sale_expired():
        return 'closed'
    return raffle.state


def _raffle_image_url(raffle, size=512):
    if not raffle.image_128:
        return None
    return '%s/raffles/%s/image?size=%s&unique=%s' % (PREFIX, raffle.id, size, _unique(raffle))


def _gallery_image_url(image, size=1024):
    return '%s/images/%s?size=%s&unique=%s' % (PREFIX, image.id, size, _unique(image))


def _get_raffle(raffle_id, states=PUBLIC_STATES):
    raffle = request.env['rifazo.raffle'].sudo().search(
        [('id', '=', int(raffle_id)), ('state', 'in', states)], limit=1)
    if not raffle:
        raise RifazoApiError('raffle_not_found', 'La rifa no existe o ya no está disponible.', status=404)
    return raffle


def _get_request(token):
    rifazo_request = request.env['rifazo.request'].sudo().search(
        [('access_token', '=', token or '')], limit=1) if token else None
    if not rifazo_request:
        raise RifazoApiError('request_not_found', 'No encontramos esa solicitud.', status=404)
    return rifazo_request


def _serialize_raffle(raffle, detail=False):
    total = raffle.ticket_total
    data = {
        'id': raffle.id,
        'name': raffle.name,
        'short_description': raffle.short_description or '',
        'state': _public_state(raffle),
        'price': raffle.price,
        'currency': raffle.currency_id.name,
        'currency_symbol': raffle.currency_id.symbol,
        'draw_date': _dt(raffle.draw_date),
        'sale_end_date': _dt(raffle.sale_end_date),
        # Segundos hasta el cierre según el reloj del servidor (la app no
        # depende de la hora del celular).
        'sale_seconds_left': _seconds_left(raffle.sale_end_date) if raffle.state == 'open' else None,
        'draw_method': raffle.draw_method or '',
        'number_from': raffle.number_from,
        'number_to': raffle.number_to,
        'digits': raffle.number_digits,
        'total': total,
        'available': raffle.ticket_available_count,
        # "Ocupado" para la barra de la app: todo lo que no está disponible.
        'taken_percent': round(100.0 * (total - raffle.ticket_available_count) / total, 1) if total else 0,
        'image_url': _raffle_image_url(raffle),
        'winning_number': raffle.winning_number if raffle.state == 'drawn' else None,
    }
    if detail:
        data.update({
            'description': raffle.description or '',
            'images': [_raffle_image_url(raffle, 1024)] if raffle.image_128 else [],
            'payment_instructions': raffle.payment_instructions or '',
            'whatsapp_url': raffle.whatsapp_url or '',
            'max_numbers_per_request': raffle.max_numbers_per_request,
            'reservation_minutes': raffle.reservation_minutes,
        })
        data['images'] += [_gallery_image_url(img) for img in raffle.image_ids if img.image_128]
    return data


def _serialize_request(rifazo_request, with_token=True):
    raffle = rifazo_request.raffle_id
    data = {
        'code': rifazo_request.code,
        'state': rifazo_request.state,
        'state_label': dict(rifazo_request._fields['state'].selection)[rifazo_request.state],
        'numbers': [n.strip() for n in (rifazo_request.number_list or '').split(',') if n.strip()],
        'amount': rifazo_request.amount,
        'currency_symbol': raffle.currency_id.symbol,
        'name': rifazo_request.partner_name or '',
        'phone': rifazo_request.phone or '',
        'has_proof': bool(rifazo_request.submitted_date),
        'created_at': _dt(rifazo_request.create_date),
        'expires_at': _dt(rifazo_request.reserved_until) if rifazo_request.state == 'reserved' else None,
        'seconds_left': _seconds_left(rifazo_request.reserved_until) if rifazo_request.state == 'reserved' else None,
        'rejection_reason': rifazo_request.rejection_reason or '',
        'is_winner': rifazo_request.is_winner,
        'raffle': {
            'id': raffle.id,
            'name': raffle.name,
            'state': raffle.state,
            'draw_date': _dt(raffle.draw_date),
            'image_url': _raffle_image_url(raffle),
            'winning_number': raffle.winning_number if raffle.state == 'drawn' else None,
        },
    }
    if with_token:
        data['token'] = rifazo_request.access_token
    return data


def _serialize_result(raffle):
    """Rifa sorteada para "Últimos sorteos". El ganador va abreviado: nunca
    el nombre completo ni el teléfono."""
    winner = raffle.winner_request_id
    delivered = bool(winner) and raffle.prize_delivered
    return {
        'id': raffle.id,
        'name': raffle.name,
        'image_url': _raffle_image_url(raffle),
        'currency_symbol': raffle.currency_id.symbol,
        'draw_date': _dt(raffle.draw_date),
        'draw_method': raffle.draw_method or '',
        'winning_number': raffle.winning_number,
        'has_winner': bool(winner),
        'winner_name': winner._public_winner_name() if winner else '',
        'winner_phone': winner._public_phone_masked() if winner else '',
        'prize_delivered': delivered,
        'prize_delivered_date': _dt(raffle.prize_delivered_date) if delivered else None,
        'prize_note': (raffle.prize_note or '') if delivered else '',
        'evidence_url': '%s/raffles/%s/evidence?unique=%s' % (PREFIX, raffle.id, _unique(raffle))
        if delivered and raffle.prize_evidence_image else None,
    }


def _image_response(record, size):
    size = int(size) if str(size).isdigit() and int(size) in IMAGE_SIZES else 512
    stream = request.env['ir.binary']._get_image_stream_from(record, 'image_%s' % size)
    # Con ?unique= la URL cambia cuando cambia la imagen → se puede cachear para siempre.
    return stream.get_response(immutable=bool(request.params.get('unique')))


class RifazoApi(http.Controller):

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    @http.route(PREFIX + '/raffles', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def raffles(self, **kwargs):
        # Las que pasaron su hora de cierre no se muestran aunque el cron
        # todavía no las haya cerrado.
        raffles = request.env['rifazo.raffle'].sudo().search([
            ('state', '=', 'open'),
            '|', ('sale_end_date', '=', False), ('sale_end_date', '>', fields.Datetime.now()),
        ])
        return _json({'raffles': [_serialize_raffle(r) for r in raffles]})

    @http.route(PREFIX + '/raffles/<int:raffle_id>', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def raffle_detail(self, raffle_id, **kwargs):
        return _json(_serialize_raffle(_get_raffle(raffle_id), detail=True))

    @http.route(PREFIX + '/raffles/<int:raffle_id>/numbers', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def raffle_numbers(self, raffle_id, **kwargs):
        """Solo los números NO disponibles: liviano aunque la rifa tenga
        miles. La app arma la grilla completa con from/to/digits."""
        raffle = _get_raffle(raffle_id)
        request.env.cr.execute("""
            SELECT number, state FROM rifazo_ticket
             WHERE raffle_id = %s AND state != 'available'
             ORDER BY value
        """, (raffle.id,))
        reserved, taken = [], []
        for number, state in request.env.cr.fetchall():
            (reserved if state == 'reserved' else taken).append(number)
        return _json({
            'raffle_id': raffle.id,
            'state': _public_state(raffle),
            'number_from': raffle.number_from,
            'number_to': raffle.number_to,
            'digits': raffle.number_digits,
            'reserved': reserved,
            'taken': taken,
        })

    @http.route(PREFIX + '/raffles/<int:raffle_id>/image', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def raffle_image(self, raffle_id, size=512, **kwargs):
        return _image_response(_get_raffle(raffle_id), size)

    @http.route(PREFIX + '/results', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def results(self, limit=5, **kwargs):
        """Últimos sorteos: número ganador, ganador abreviado y entrega."""
        limit = min(int(limit), 20) if str(limit).isdigit() else 5
        raffles = request.env['rifazo.raffle'].sudo().search(
            [('state', '=', 'drawn')], order='draw_date desc, id desc', limit=limit)
        return _json({'results': [_serialize_result(r) for r in raffles]})

    @http.route(PREFIX + '/raffles/<int:raffle_id>/evidence', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def prize_evidence(self, raffle_id, size=1024, **kwargs):
        raffle = request.env['rifazo.raffle'].sudo().search(
            [('id', '=', raffle_id), ('state', '=', 'drawn'), ('prize_delivered', '=', True)], limit=1)
        if not raffle or not raffle.prize_evidence_image:
            raise RifazoApiError('image_not_found', 'Imagen no encontrada.', status=404)
        size = int(size) if str(size).isdigit() and int(size) in IMAGE_SIZES else 1024
        stream = request.env['ir.binary']._get_image_stream_from(
            raffle, 'prize_evidence_image', width=size, height=size)
        return stream.get_response(immutable=bool(request.params.get('unique')))

    @http.route(PREFIX + '/images/<int:image_id>', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    @_api
    def gallery_image(self, image_id, size=1024, **kwargs):
        image = request.env['rifazo.raffle.image'].sudo().search(
            [('id', '=', image_id), ('raffle_id.state', 'in', PUBLIC_STATES)], limit=1)
        if not image:
            raise RifazoApiError('image_not_found', 'Imagen no encontrada.', status=404)
        return _image_response(image, size)

    # ------------------------------------------------------------------
    # Flujo de compra
    # ------------------------------------------------------------------

    @http.route(PREFIX + '/raffles/<int:raffle_id>/reserve', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def reserve(self, raffle_id, **kwargs):
        """{"device_id": "...", "numbers": ["007", "123"]}"""
        data = _body()
        raffle = _get_raffle(raffle_id, states=('open',))
        rifazo_request = raffle._reserve_numbers(
            data.get('numbers'), data.get('device_id'),
            ip_address=request.httprequest.remote_addr)
        return _json(_serialize_request(rifazo_request), status=201)

    @http.route(PREFIX + '/requests/<string:token>/contact', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def contact(self, token, **kwargs):
        """{"name": "...", "phone": "...", "fcm_token": "..." (opcional)}"""
        data = _body()
        rifazo_request = _get_request(token)
        rifazo_request._api_set_contact(data.get('name'), data.get('phone'), data.get('fcm_token'))
        return _json(_serialize_request(rifazo_request))

    @http.route(PREFIX + '/requests/<string:token>/proof', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def proof(self, token, image=None, **kwargs):
        """multipart/form-data con el archivo en el campo "image"."""
        rifazo_request = _get_request(token)
        if not hasattr(image, 'read'):
            raise RifazoApiError('missing_image', 'Falta la imagen del comprobante.')
        max_mb = int(request.env['ir.config_parameter'].sudo().get_param('rifazo.max_proof_mb', 8))
        content = image.read(max_mb * 1024 * 1024 + 1)
        if len(content) > max_mb * 1024 * 1024:
            raise RifazoApiError('image_too_large', 'La imagen supera los %s MB.' % max_mb, status=413)
        try:
            pil_image = Image.open(io.BytesIO(content))
            pil_image.verify()
            valid = pil_image.format in PROOF_FORMATS
        except Exception:
            valid = False
        if not valid:
            raise RifazoApiError('bad_image', 'El archivo no es una imagen JPG, PNG o WEBP.')
        rifazo_request._api_submit_proof(base64.b64encode(content))
        return _json(_serialize_request(rifazo_request))

    @http.route(PREFIX + '/requests/<string:token>/cancel', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def cancel(self, token, **kwargs):
        rifazo_request = _get_request(token)
        rifazo_request._api_cancel()
        return _json(_serialize_request(rifazo_request))

    # ------------------------------------------------------------------
    # Mis rifas
    # ------------------------------------------------------------------

    @http.route(PREFIX + '/my-requests', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def my_requests(self, **kwargs):
        """{"tokens": ["...", "..."]} → estado actual de cada solicitud.
        Los tokens que ya no existen simplemente no vuelven."""
        tokens = _body().get('tokens') or []
        if not isinstance(tokens, list):
            raise RifazoApiError('bad_tokens', 'tokens tiene que ser una lista.')
        tokens = [str(t) for t in tokens[:MAX_TOKENS_PER_QUERY] if t]
        requests_ = request.env['rifazo.request'].sudo().search(
            [('access_token', 'in', tokens)]) if tokens else []
        return _json({'requests': [_serialize_request(r) for r in requests_]})

    @http.route(PREFIX + '/recover', type='http', auth='public',
                methods=['POST'], csrf=False, cors='*')
    @_api
    def recover(self, **kwargs):
        """{"phone": "...", "code": "RZ-XXXXX"} → la solicitud con su token,
        para recuperarla en un celular nuevo. Pide los dos datos para que no
        alcance con saber el teléfono de otra persona."""
        data = _body()
        phone = normalize_phone(data.get('phone'))
        code = (data.get('code') or '').strip().upper()
        if code and not code.startswith('RZ-'):
            code = 'RZ-' + code
        rifazo_request = request.env['rifazo.request'].sudo().search(
            [('code', '=', code), ('phone', '=', phone)], limit=1) if phone and code else None
        if not rifazo_request:
            raise RifazoApiError('request_not_found',
                                 'No encontramos una solicitud con ese código y teléfono.', status=404)
        return _json(_serialize_request(rifazo_request))
