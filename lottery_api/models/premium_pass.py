# -*- coding: utf-8 -*-
"""LotoAnálisis Premium: pase emitido por Odoo a partir de una compra de
Google Play.

La app manda el purchaseToken de la suscripción, Odoo lo valida contra la
Google Play Developer API con la cuenta de servicio `play-premium`, lo
confirma (acknowledge; sin eso Google reembolsa a los 3 días) y devuelve un
pase firmado con vencimiento. Los endpoints premium exigen ese pase en la
cabecera X-Premium-Pass.

`origin` deja lugar al código de regalo, que va a emitir el mismo pase.
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PLAY_SA_PARAM = 'lottery_api.play_service_account'
PLAY_PACKAGE_PARAM = 'lottery_api.play_package_name'
DEFAULT_PACKAGE = 'com.seusit.lotoanalisis'
SECRET_PARAM = 'lottery_api.premium_secret'
_TOKEN_PARAM = 'lottery_api.play_access_token'
_TOKEN_EXP_PARAM = 'lottery_api.play_token_expires_at'
PLAY_SCOPE = 'https://www.googleapis.com/auth/androidpublisher'
PLAY_API = 'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{pkg}'

PREMIUM_PRODUCTS = ('premium',)
TOKEN_RE = re.compile(r'^[A-Za-z0-9._-]{10,500}$')

# subscriptionState de subscriptionsv2 → estado del pase.
GOOGLE_STATES = {
    'SUBSCRIPTION_STATE_PENDING': 'pending',
    'SUBSCRIPTION_STATE_ACTIVE': 'active',
    'SUBSCRIPTION_STATE_PAUSED': 'paused',
    'SUBSCRIPTION_STATE_IN_GRACE_PERIOD': 'grace',
    'SUBSCRIPTION_STATE_ON_HOLD': 'on_hold',
    'SUBSCRIPTION_STATE_CANCELED': 'canceled',
    'SUBSCRIPTION_STATE_EXPIRED': 'expired',
    'SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED': 'expired',
}
# Cancelada sigue con acceso hasta el vencimiento del período pagado.
ACCESS_STATES = ('active', 'grace', 'canceled')
FINAL_STATES = ('expired', 'replaced', 'revoked')
# Retención declarada en /politica-privacidad: vigencia + 2 años.
RETENTION_DAYS = 730


class PremiumError(Exception):
    """Error de validación con un código que el controlador devuelve tal cual."""

    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _parse_google_time(value):
    """'2026-11-30T15:00:00.123Z' → datetime UTC naive, o False."""
    if not value:
        return False
    try:
        return datetime.strptime(value.rstrip('Z').split('.')[0], '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return False


class LotteryPremiumPass(models.Model):
    _name = 'lottery.premium.pass'
    _description = 'Pase LotoAnálisis Premium'
    _order = 'create_date desc'

    origin = fields.Selection([
        ('subscription', 'Suscripción Google Play'),
        ('gift', 'Código de regalo'),
    ], string='Origen', required=True, default='subscription', index=True)
    state = fields.Selection([
        ('pending', 'Pago pendiente'),
        ('active', 'Activa'),
        ('grace', 'Período de gracia'),
        ('on_hold', 'Suspendida (pago fallido)'),
        ('paused', 'Pausada'),
        ('canceled', 'Cancelada (con acceso hasta vencer)'),
        ('expired', 'Vencida'),
        ('replaced', 'Reemplazada (cambio de plan)'),
        ('revoked', 'Revocada'),
    ], string='Estado', required=True, default='pending', index=True)
    is_premium = fields.Boolean(string='Da Premium', compute='_compute_is_premium')
    expiry_date = fields.Datetime(string='Vence', index=True)
    purchase_token = fields.Char(string='Purchase token', index=True, copy=False)
    linked_purchase_token = fields.Char(string='Token anterior (cambio de plan)', copy=False)
    product_id = fields.Char(string='Producto')
    base_plan_id = fields.Char(string='Plan')
    order_id = fields.Char(string='Pedido de Google', index=True, copy=False)
    auto_renewing = fields.Boolean(string='Renovación automática')
    acknowledged = fields.Boolean(string='Confirmada en Google', copy=False)
    is_test = fields.Boolean(string='Compra de prueba')
    last_check = fields.Datetime(string='Última consulta a Google')
    google_response = fields.Text(string='Última respuesta de Google')

    _sql_constraints = [
        ('purchase_token_uniq', 'unique(purchase_token)',
         'Ya existe un pase para ese purchase token.'),
    ]

    @api.depends('state', 'expiry_date')
    def _compute_is_premium(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_premium = bool(
                rec.state in ACCESS_STATES and rec.expiry_date and rec.expiry_date > now)

    @api.depends('base_plan_id', 'order_id', 'origin')
    def _compute_display_name(self):
        labels = dict(self._fields['origin'].selection)
        for rec in self:
            rec.display_name = ' · '.join(filter(None, [
                rec.base_plan_id or labels.get(rec.origin), rec.order_id or str(rec.id)]))

    # ── Pase firmado ──────────────────────────────────────────────────

    @api.model
    def _secret(self):
        Param = self.env['ir.config_parameter'].sudo()
        secret = Param.get_param(SECRET_PARAM)
        if not secret:
            secret = secrets.token_urlsafe(32)
            Param.set_param(SECRET_PARAM, secret)
        return secret.encode()

    def _issue_token(self):
        """Pase 'v1.<payload>.<firma>' con el id y el vencimiento."""
        self.ensure_one()
        payload = _b64(json.dumps({
            'p': self.id,
            'e': int(self.expiry_date.replace(tzinfo=timezone.utc).timestamp()) if self.expiry_date else 0,
        }, separators=(',', ':')).encode())
        sig = _b64(hmac.new(self._secret(), payload.encode(), hashlib.sha256).digest())
        return 'v1.%s.%s' % (payload, sig)

    @api.model
    def _from_token(self, token):
        """Pase vigente que corresponde al token, o un recordset vacío. Además de
        la firma mira el registro, así un reembolso corta el acceso enseguida."""
        empty = self.browse()
        try:
            version, payload, sig = (token or '').split('.')
        except ValueError:
            return empty
        if version != 'v1':
            return empty
        expected = _b64(hmac.new(self._secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig):
            return empty
        try:
            data = json.loads(_unb64(payload))
        except Exception:
            return empty
        if int(data.get('e') or 0) < time.time():
            return empty
        rec = self.sudo().browse(int(data.get('p') or 0)).exists()
        return rec if rec and rec.is_premium else empty

    def _api_payload(self, with_token=True):
        """Lo que la app recibe de /premium/verify y /premium/status."""
        self.ensure_one()
        res = {
            'premium': self.is_premium,
            'state': self.state,
            'plan': self.base_plan_id or self.origin,
            'expires_at': self.expiry_date.isoformat() + 'Z' if self.expiry_date else None,
            'auto_renewing': self.auto_renewing,
        }
        if with_token:
            res['pass'] = self._issue_token() if self.is_premium else None
        return res

    # ── Google Play Developer API ─────────────────────────────────────

    @api.model
    def _play_config(self):
        Param = self.env['ir.config_parameter'].sudo()
        raw = Param.get_param(PLAY_SA_PARAM)
        if not raw:
            raise PremiumError('not_configured', 503)
        try:
            sa = json.loads(raw)
        except Exception:
            _logger.error('lottery_api: play_service_account no es JSON válido')
            raise PremiumError('not_configured', 503)
        return sa, Param.get_param(PLAY_PACKAGE_PARAM) or DEFAULT_PACKAGE

    @api.model
    def _play_access_token(self, sa):
        Param = self.env['ir.config_parameter'].sudo()
        now = int(time.time())
        cached = Param.get_param(_TOKEN_PARAM)
        if cached and now < int(Param.get_param(_TOKEN_EXP_PARAM) or 0) - 60:
            return cached
        token = self.env['lottery.fcm.service']._request_new_token(sa, scope=PLAY_SCOPE)
        if not token:
            raise PremiumError('google_auth', 502)
        Param.set_param(_TOKEN_PARAM, token)
        Param.set_param(_TOKEN_EXP_PARAM, str(now + 3000))
        return token

    @api.model
    def _play_request(self, method, path, **kwargs):
        sa, pkg = self._play_config()
        url = PLAY_API.format(pkg=pkg) + path
        try:
            resp = requests.request(
                method, url, timeout=15,
                headers={'Authorization': 'Bearer %s' % self._play_access_token(sa)},
                **kwargs)
        except requests.RequestException as e:
            _logger.error('lottery_api: Google Play inaccesible: %s', e)
            raise PremiumError('google_unavailable', 502)
        if resp.status_code in (400, 404, 410):
            raise PremiumError('invalid_purchase', 400)
        if resp.status_code in (401, 403):
            # Recién invitada en Play Console, la cuenta tarda hasta 24 h en tener permiso.
            _logger.error('lottery_api: Google Play rechazó la cuenta de servicio: %s', resp.text[:500])
            raise PremiumError('google_auth', 502)
        if resp.status_code >= 300:
            _logger.error('lottery_api: Google Play %s: %s', resp.status_code, resp.text[:500])
            raise PremiumError('google_error', 502)
        return resp.json() if resp.content else {}

    @api.model
    def verify_subscription(self, purchase_token):
        """Valida el token en Google, crea o actualiza el pase y lo confirma."""
        if not purchase_token:
            raise PremiumError('missing_purchase_token')
        if not TOKEN_RE.match(purchase_token):
            raise PremiumError('invalid_purchase')
        data = self._play_request(
            'GET', '/purchases/subscriptionsv2/tokens/%s' % purchase_token)
        line = (data.get('lineItems') or [{}])[0]
        if line.get('productId') not in PREMIUM_PRODUCTS:
            raise PremiumError('invalid_product')

        rec = self.sudo().search([('purchase_token', '=', purchase_token)], limit=1)
        vals = self._vals_from_google(data, line)
        if rec:
            rec.write(vals)
        else:
            rec = self.sudo().create(dict(vals, purchase_token=purchase_token))
        if vals.get('linked_purchase_token'):
            self.sudo().search([
                ('purchase_token', '=', vals['linked_purchase_token']),
            ]).write({'state': 'replaced'})
        rec._acknowledge_if_needed(data)
        return rec

    @api.model
    def _vals_from_google(self, data, line):
        return {
            'origin': 'subscription',
            'state': GOOGLE_STATES.get(data.get('subscriptionState'), 'pending'),
            'expiry_date': _parse_google_time(line.get('expiryTime')),
            'product_id': line.get('productId'),
            'base_plan_id': (line.get('offerDetails') or {}).get('basePlanId'),
            'order_id': line.get('latestSuccessfulOrderId') or data.get('latestOrderId'),
            'auto_renewing': bool((line.get('autoRenewingPlan') or {}).get('autoRenewEnabled')),
            'acknowledged': data.get('acknowledgementState') == 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
            'linked_purchase_token': data.get('linkedPurchaseToken') or False,
            'is_test': 'testPurchase' in data,
            'last_check': fields.Datetime.now(),
            'google_response': json.dumps(data, indent=2),
        }

    def _acknowledge_if_needed(self, data):
        """Sin acknowledge en 3 días Google reembolsa. Un fallo acá no corta la
        compra: el cron lo reintenta."""
        self.ensure_one()
        if self.acknowledged or self.state not in ACCESS_STATES:
            return
        try:
            self._play_request(
                'POST', '/purchases/subscriptions/%s/tokens/%s:acknowledge'
                % (self.product_id, self.purchase_token), json={})
            self.acknowledged = True
        except PremiumError as e:
            _logger.warning('lottery_api: acknowledge pendiente del pase %s: %s', self.id, e.code)

    @api.model
    def _cron_refresh_subscriptions(self):
        """Consulta a Google los pases que vencen pronto, los que esperan un pago
        y los que no se pudieron confirmar. Reemplaza a las notificaciones de
        Pub/Sub: una cancelación se ve al día siguiente."""
        soon = fields.Datetime.now() + timedelta(days=1)
        passes = self.sudo().search([
            ('origin', '=', 'subscription'),
            ('state', 'not in', FINAL_STATES),
            '|', '|',
            ('expiry_date', '<=', soon),
            ('state', 'in', ('pending', 'grace', 'on_hold', 'paused')),
            ('acknowledged', '=', False),
        ])
        for rec in passes:
            try:
                self.verify_subscription(rec.purchase_token)
            except PremiumError as e:
                if e.code == 'invalid_purchase':
                    rec.state = 'expired'
                elif e.code in ('not_configured', 'google_auth'):
                    _logger.error('lottery_api: cron Premium detenido: %s', e.code)
                    return
                else:
                    _logger.warning('lottery_api: no se pudo refrescar el pase %s: %s', rec.id, e.code)
            self.env.cr.commit()

    @api.model
    def _cron_purge_old_passes(self):
        """Borra los pases vencidos hace más de 2 años, como dice la política de privacidad."""
        cutoff = fields.Datetime.now() - timedelta(days=RETENTION_DAYS)
        old = self.sudo().search([
            '|',
            ('expiry_date', '<', cutoff),
            '&', ('expiry_date', '=', False), ('create_date', '<', cutoff),
        ])
        if old:
            _logger.info('lottery_api: se borran %s pases Premium vencidos hace más de 2 años', len(old))
            old.unlink()
