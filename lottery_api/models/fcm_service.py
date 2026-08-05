# -*- coding: utf-8 -*-
"""Servicio de envío de notificaciones push via FCM HTTP v1.

Genera el JWT con la service account y lo intercambia por un access token,
luego envía el mensaje al topic del sorteo.  El token se cachea 50 min en
ir.config_parameter para no pedir uno nuevo en cada salida.
"""

import base64
import json
import logging
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from odoo import api, models

_logger = logging.getLogger(__name__)

_TOKEN_PARAM = 'lottery_api.fcm_access_token'
_TOKEN_EXP_PARAM = 'lottery_api.fcm_token_expires_at'
_SA_PARAM = 'lottery_api.fcm_service_account'
FCM_URL = 'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
OAUTH_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'


class LotteryFcmService(models.AbstractModel):
    _name = 'lottery.fcm.service'
    _description = 'Servicio FCM para notificaciones push'

    @api.model
    def _get_service_account(self):
        """Lee la service account de ir.config_parameter.
        Devuelve el dict o None si no está configurada."""
        raw = self.env['ir.config_parameter'].sudo().get_param(_SA_PARAM)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            _logger.error('lottery_api: fcm_service_account no es JSON válido')
            return None

    @api.model
    def _get_access_token(self, sa):
        """Devuelve un access token válido, usando el cacheado si no expiró."""
        Param = self.env['ir.config_parameter'].sudo()
        now = int(time.time())
        cached_token = Param.get_param(_TOKEN_PARAM)
        cached_exp = int(Param.get_param(_TOKEN_EXP_PARAM) or 0)

        if cached_token and now < cached_exp - 60:
            return cached_token

        token = self._request_new_token(sa)
        if token:
            Param.set_param(_TOKEN_PARAM, token)
            Param.set_param(_TOKEN_EXP_PARAM, str(now + 3000))  # 50 min
        return token

    @api.model
    def _request_new_token(self, sa):
        """Genera JWT con la service account y lo intercambia por access token."""
        try:
            now = int(time.time())
            header = base64.urlsafe_b64encode(
                json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode()
            ).rstrip(b'=')
            payload = base64.urlsafe_b64encode(
                json.dumps({
                    'iss': sa['client_email'],
                    'scope': SCOPE,
                    'aud': OAUTH_URL,
                    'iat': now,
                    'exp': now + 3600,
                }).encode()
            ).rstrip(b'=')

            signing_input = header + b'.' + payload
            private_key = serialization.load_pem_private_key(
                sa['private_key'].encode(), password=None
            )
            signature = private_key.sign(
                signing_input, padding.PKCS1v15(), hashes.SHA256()
            )
            sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=')
            jwt_token = (signing_input + b'.' + sig_b64).decode()

            resp = requests.post(
                OAUTH_URL,
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': jwt_token,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get('access_token')
        except Exception as e:
            _logger.error('lottery_api: error obteniendo token FCM: %s', e)
            return None

    @api.model
    def send_push(self, sorteo_id, title, body):
        """Envía una notificación push al topic del sorteo."""
        sa = self._get_service_account()
        if not sa:
            _logger.info(
                'lottery_api: FCM no configurado (sin service account), '
                'omitiendo push para sorteo %s', sorteo_id
            )
            return False

        token = self._get_access_token(sa)
        if not token:
            return False

        project_id = sa.get('project_id', '')
        topic = f'sorteo_{sorteo_id}'
        url = FCM_URL.format(project_id=project_id)

        payload = {
            'message': {
                'topic': topic,
                'notification': {
                    'title': title,
                    'body': body,
                },
                'android': {
                    # Alta prioridad: despierta el dispositivo aunque esté en
                    # Doze/segundo plano, clave para que el aviso llegue a
                    # tiempo (los mensajes 'notification' no siempre van high
                    # si no se declara explícitamente).
                    'priority': 'high',
                    'notification': {
                        'sound': 'default',
                        'channel_id': 'lottery_results',
                    },
                },
            }
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            resp.raise_for_status()
            _logger.info(
                'lottery_api: push enviado al topic %s — %s',
                topic, resp.json().get('name', '')
            )
            return True
        except Exception as e:
            _logger.error(
                'lottery_api: error enviando push al topic %s: %s', topic, e
            )
            return False
