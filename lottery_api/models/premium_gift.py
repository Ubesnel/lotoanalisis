# -*- coding: utf-8 -*-
"""Regalar Premium: alguien compra en la app un código de 1 o 12 meses
(producto de compra única de Google Play) y otra persona lo canjea.

El canje lo resuelve Odoo, no Google: anda en teléfonos sin Play Billing. Un código comprado no
vence; los de cortesía, sí.
El pase que emite queda atado al ID de instalación del teléfono que lo
canjeó; cargarlo en otro teléfono lo muda (con tope por mes), así que
repartir el código no le sirve a nadie.

La prueba gratis la pide la app con un botón: Odoo arma un código de días y
lo canjea en el acto. Va una por teléfono, por el ANDROID_ID, que no cambia al
reinstalar.
"""

import ipaddress
import json
import logging
import re
import secrets
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .premium_pass import PremiumError, TOKEN_RE

_logger = logging.getLogger(__name__)

# Productos de compra única en Play Console → meses que regalan.
GIFT_PRODUCTS = {'regalo_1_mes': 1, 'regalo_12_meses': 12}
# Sin 0/O ni 1/I para que se pueda dictar por teléfono.
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
UNREDEEMED_DAYS = 365
MAX_MOVES = 2
MOVES_WINDOW = timedelta(days=30)
DEVICE_RE = re.compile(r'^[A-Za-z0-9-]{16,64}$')
RETENTION_DAYS = 730
HARDWARE_RE = re.compile(r'^[A-Za-z0-9-]{8,64}$')
TRIAL_PARAM = 'lottery_api.premium_trial'
TRIAL_DAYS_PARAM = 'lottery_api.premium_trial_days'
# Rangos propios de Google (no Google Cloud): de ahí llegan los robots de Play.
GOOGLE_NETS = [ipaddress.ip_network(n) for n in (
    '66.249.64.0/19', '66.102.0.0/20', '64.233.160.0/19', '72.14.192.0/18',
    '74.125.0.0/16', '108.177.0.0/17', '173.194.0.0/16', '209.85.128.0/17',
    '216.239.32.0/19', '216.58.192.0/19', '172.217.0.0/16', '142.250.0.0/15',
)]


def is_google_ip(ip):
    try:
        addr = ipaddress.ip_address(ip or '')
    except ValueError:
        return False
    return any(addr in net for net in GOOGLE_NETS)


def normalize_code(text):
    """'loto 7f3k-92qa' → 'LOTO-7F3K-92QA', o None si no tiene forma de código."""
    raw = re.sub(r'[^A-Za-z0-9]', '', text or '').upper()
    if len(raw) == 12 and raw.startswith('LOTO'):
        raw = raw[4:]
    if len(raw) != 8 or any(c not in CODE_ALPHABET for c in raw):
        return None
    return 'LOTO-%s-%s' % (raw[:4], raw[4:])


class LotteryPremiumGift(models.Model):
    _name = 'lottery.premium.gift'
    _description = 'Código de regalo LotoAnálisis Premium'
    _order = 'create_date desc'

    name = fields.Char(string='Código', required=True, readonly=True, copy=False,
                       index=True, default=lambda self: self._new_code())
    origin = fields.Selection([
        ('purchase', 'Comprado en Google Play'),
        ('courtesy', 'Cortesía'),
        ('trial', 'Prueba gratis'),
    ], string='Origen', required=True, default='courtesy', readonly=True)
    months = fields.Integer(string='Meses', required=True, default=1)
    days = fields.Integer(string='Días', help='Si tiene días, valen los días y no los meses.')
    hardware_id = fields.Char(string='ID del teléfono', readonly=True, index=True, copy=False,
                              help='ANDROID_ID del teléfono que pidió la prueba gratis.')
    request_ip = fields.Char(string='IP', readonly=True, copy=False)
    google_robot = fields.Boolean(
        string='Robot de Google', readonly=True, index=True, copy=False,
        help='Pedida desde un teléfono de prueba de Google Play (informe previo al '
             'lanzamiento) o desde una IP de Google.')
    state = fields.Selection([
        ('available', 'Sin canjear'),
        ('redeemed', 'Canjeado'),
        ('expired', 'Vencido sin canjear'),
        ('revoked', 'Anulado'),
    ], string='Estado', required=True, default='available', readonly=True, index=True)
    valid_until = fields.Datetime(
        string='Canjear antes de',
        default=lambda self: fields.Datetime.now() + timedelta(days=UNREDEEMED_DAYS),
        help='Vacío: no vence. Los códigos comprados no vencen.')
    note = fields.Char(string='Nota', help='Para las cortesías: a quién o por qué se dio.')

    pass_id = fields.Many2one('lottery.premium.pass', string='Pase', readonly=True,
                              ondelete='set null')
    pass_expiry = fields.Datetime(related='pass_id.expiry_date', string='Premium hasta')
    redeemed_date = fields.Datetime(string='Canjeado el', readonly=True)
    activation_ids = fields.One2many('lottery.premium.gift.activation', 'gift_id',
                                     string='Teléfonos', readonly=True)

    purchase_token = fields.Char(string='Purchase token', readonly=True, copy=False)
    product_id = fields.Char(string='Producto', readonly=True)
    order_id = fields.Char(string='Pedido de Google', readonly=True, index=True, copy=False)
    is_test = fields.Boolean(string='Compra de prueba', readonly=True)
    acknowledged = fields.Boolean(string='Confirmada en Google', readonly=True, copy=False)
    consumed = fields.Boolean(string='Consumida en Google', readonly=True, copy=False)
    google_response = fields.Text(string='Respuesta de Google', readonly=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ya existe ese código.'),
        ('purchase_token_uniq', 'unique(purchase_token)', 'Ya existe un código para esa compra.'),
        ('months_positive', 'CHECK(months > 0 OR days > 0)',
         'Los meses o los días tienen que ser más de cero.'),
    ]

    @api.model
    def _new_code(self):
        while True:
            raw = ''.join(secrets.choice(CODE_ALPHABET) for _i in range(8))
            code = 'LOTO-%s-%s' % (raw[:4], raw[4:])
            if not self.sudo().search_count([('name', '=', code)]):
                return code

    def _api_payload(self):
        self.ensure_one()
        return {
            'code': self.name,
            'months': self.months,
            'days': self.days or 0,
            'product_id': self.product_id,
            'valid_until': self.valid_until.isoformat() + 'Z' if self.valid_until else None,
        }

    def _delta(self):
        self.ensure_one()
        return relativedelta(days=self.days) if self.days else relativedelta(months=self.months)

    def action_revoke(self):
        """Anula el código y corta el Premium que dio (reembolsos, abusos)."""
        for rec in self:
            rec.pass_id.write({'state': 'revoked'})
            rec.state = 'revoked'

    # ── Compra ────────────────────────────────────────────────────────

    @api.model
    def verify_purchase(self, purchase_token, product_id):
        """Valida la compra en Google y devuelve su código, siempre el mismo
        para la misma compra."""
        if not purchase_token or not TOKEN_RE.match(purchase_token):
            raise PremiumError('invalid_purchase')
        if product_id not in GIFT_PRODUCTS:
            raise PremiumError('invalid_product')
        Pass = self.env['lottery.premium.pass']
        rec = self.sudo().search([('purchase_token', '=', purchase_token)], limit=1)
        if rec:
            rec._confirm_in_google()
            return rec

        data = Pass._play_request(
            'GET', '/purchases/products/%s/tokens/%s' % (product_id, purchase_token))
        # purchaseState: 0 comprado, 1 cancelado, 2 pendiente.
        if data.get('purchaseState') == 2:
            raise PremiumError('purchase_pending', 409)
        if data.get('purchaseState') != 0:
            raise PremiumError('invalid_purchase')
        rec = self.sudo().create({
            'origin': 'purchase',
            'months': GIFT_PRODUCTS[product_id],
            'valid_until': False,
            'purchase_token': purchase_token,
            'product_id': product_id,
            'order_id': data.get('orderId'),
            'is_test': data.get('purchaseType') == 0,
            'google_response': json.dumps(data, indent=2),
        })
        rec._confirm_in_google(data)
        return rec

    def _confirm_in_google(self, data=None):
        """Acknowledge (sin eso Google reembolsa a los 3 días) y consumo (para
        que se pueda volver a regalar). Un fallo no corta: el cron reintenta."""
        self.ensure_one()
        if self.origin != 'purchase' or (self.acknowledged and self.consumed):
            return
        Pass = self.env['lottery.premium.pass']
        path = '/purchases/products/%s/tokens/%s' % (self.product_id, self.purchase_token)
        try:
            if data is None:
                data = Pass._play_request('GET', path)
            self.write({
                'acknowledged': data.get('acknowledgementState') == 1,
                'consumed': data.get('consumptionState') == 1,
            })
            if not self.acknowledged:
                Pass._play_request('POST', path + ':acknowledge', json={})
                self.acknowledged = True
            if not self.consumed:
                Pass._play_request('POST', path + ':consume')
                self.consumed = True
        except PremiumError as e:
            _logger.warning('lottery_api: regalo %s sin confirmar en Google: %s', self.id, e.code)

    @api.model
    def _cron_confirm_pending(self):
        for rec in self.sudo().search([
            ('origin', '=', 'purchase'),
            '|', ('acknowledged', '=', False), ('consumed', '=', False),
        ]):
            rec._confirm_in_google()
            self.env.cr.commit()

    # ── Canje ─────────────────────────────────────────────────────────

    @api.model
    def redeem(self, code, device_id, hardware_id=None):
        """Canjea el código en este teléfono y devuelve el pase. Si el teléfono
        ya tiene Premium de regalo, suma los meses; si el código estaba en otro
        teléfono, Premium se muda acá."""
        if not device_id or not DEVICE_RE.match(device_id):
            raise PremiumError('invalid_device')
        if not hardware_id or not HARDWARE_RE.match(hardware_id):
            hardware_id = None
        name = normalize_code(code)
        rec = name and self.sudo().search([('name', '=', name)], limit=1)
        if not rec:
            raise PremiumError('invalid_code', 404)
        rec.env.cr.execute('SELECT id FROM lottery_premium_gift WHERE id = %s FOR UPDATE', (rec.id,))
        now = fields.Datetime.now()

        if rec.state == 'revoked':
            raise PremiumError('code_revoked')
        if rec.state == 'available' and rec.valid_until and rec.valid_until < now:
            rec.state = 'expired'
        if rec.state == 'expired':
            raise PremiumError('code_expired')

        Pass = self.env['lottery.premium.pass'].sudo()
        if rec.state == 'available':
            # Con un Premium de regalo vigente en este teléfono, los meses se suman.
            premium_pass = Pass.search([
                ('origin', '=', 'gift'),
                ('device_id', '=', device_id),
                ('state', '=', 'active'),
                ('expiry_date', '>', now),
            ], order='expiry_date desc', limit=1)
            if premium_pass:
                premium_pass.write({
                    'expiry_date': premium_pass.expiry_date + rec._delta(),
                    'gift_code': '%s, %s' % (premium_pass.gift_code, rec.name),
                })
                rec.write({'state': 'redeemed', 'pass_id': premium_pass.id, 'redeemed_date': now})
                rec._log_activation(device_id, move=False, hardware_id=hardware_id)
                return premium_pass

            premium_pass = Pass.create({
                'origin': 'gift',
                'state': 'active',
                'expiry_date': now + rec._delta(),
                'base_plan_id': 'trial' if rec.origin == 'trial' else False,
                'product_id': rec.product_id or ('prueba' if rec.origin == 'trial' else 'cortesia'),
                'order_id': rec.order_id,
                'gift_code': rec.name,
                'device_id': device_id,
                'is_test': rec.is_test,
                'acknowledged': True,
            })
            rec.write({'state': 'redeemed', 'pass_id': premium_pass.id, 'redeemed_date': now})
            rec._log_activation(device_id, move=False, hardware_id=hardware_id)
            return premium_pass

        premium_pass = rec.pass_id
        if not premium_pass or not premium_pass.is_premium:
            raise PremiumError('code_used')
        if premium_pass.device_id == device_id:
            return premium_pass
        Activation = self.env['lottery.premium.gift.activation'].sudo()
        # Reinstalar o borrar datos en el mismo teléfono no es mudanza.
        last = Activation.search([('gift_id.pass_id', '=', premium_pass.id)],
                                 order='date desc, id desc', limit=1)
        last_hw = last.hardware_id or (rec.origin == 'trial' and rec.hardware_id)
        if hardware_id and last_hw == hardware_id:
            premium_pass.device_id = device_id
            rec._log_activation(device_id, move=False, hardware_id=hardware_id)
            return premium_pass
        # La prueba no se pasa a otro teléfono.
        if rec.origin == 'trial':
            raise PremiumError('trial_code')
        # El tope es del pase: con códigos sumados no se multiplica.
        moves = Activation.search_count([
            ('gift_id.pass_id', '=', premium_pass.id),
            ('is_move', '=', True),
            ('date', '>=', now - MOVES_WINDOW),
        ])
        if moves >= MAX_MOVES:
            raise PremiumError('too_many_moves', 429)
        premium_pass.device_id = device_id
        rec._log_activation(device_id, move=True, hardware_id=hardware_id)
        return premium_pass

    # ── Prueba gratis ─────────────────────────────────────────────────

    @api.model
    def request_trial(self, device_id, hardware_id, ip=None, test_lab=False):
        """Arma y canjea la prueba gratis de este teléfono. Si ya la pidió y
        sigue vigente (reinstaló), la devuelve en esta instalación."""
        Param = self.env['ir.config_parameter'].sudo()
        if Param.get_param(TRIAL_PARAM) not in ('True', '1'):
            raise PremiumError('trial_disabled', 403)
        if not device_id or not DEVICE_RE.match(device_id):
            raise PremiumError('invalid_device')
        if not hardware_id or not HARDWARE_RE.match(hardware_id):
            raise PremiumError('invalid_hardware')
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ('lottery_trial:' + hardware_id,))

        rec = self.sudo().search([('origin', '=', 'trial'), ('hardware_id', '=', hardware_id)],
                                 order='id desc', limit=1)
        if rec:
            premium_pass = rec.pass_id
            if rec.state != 'redeemed' or not premium_pass or not premium_pass.is_premium:
                raise PremiumError('trial_used', 409)
            if premium_pass.device_id != device_id:
                premium_pass.device_id = device_id
                rec._log_activation(device_id, move=False, hardware_id=hardware_id)
            return rec

        days = max(int(Param.get_param(TRIAL_DAYS_PARAM) or 7), 1)
        rec = self.sudo().create({
            'origin': 'trial',
            'months': 0,
            'days': days,
            'valid_until': fields.Datetime.now() + timedelta(days=1),
            'hardware_id': hardware_id,
            'request_ip': ip,
            'google_robot': bool(test_lab) or is_google_ip(ip),
            'note': 'Prueba gratis pedida desde la app',
        })
        self.redeem(rec.name, device_id, hardware_id)
        return rec

    def _log_activation(self, device_id, move, hardware_id=None):
        self.env['lottery.premium.gift.activation'].sudo().create({
            'gift_id': self.id, 'device_id': device_id, 'is_move': move,
            'hardware_id': hardware_id,
        })

    @api.model
    def _cron_purge_old_gifts(self):
        """Borra los códigos terminados hace más de 2 años, como los pases."""
        cutoff = fields.Datetime.now() - timedelta(days=RETENTION_DAYS)
        old = self.sudo().search([
            '|',
            '&', ('state', '=', 'available'), ('valid_until', '<', cutoff),
            '&', ('state', '!=', 'available'), ('write_date', '<', cutoff),
            '|', ('pass_id', '=', False), ('pass_id.expiry_date', '<', cutoff),
        ])
        old.unlink()

    def unlink(self):
        now = fields.Datetime.now()
        if any(rec.state == 'available' and rec.origin == 'purchase'
               and (not rec.valid_until or rec.valid_until > now) for rec in self):
            raise UserError(_('Un código comprado sin canjear no se borra: anulalo.'))
        # Sin el código, su pase quedaría huérfano dando Premium.
        self.mapped('pass_id').filtered(
            lambda p: p.state not in ('revoked', 'expired')
            and (not p.expiry_date or p.expiry_date > now)).write({'state': 'revoked'})
        return super().unlink()


class LotteryPremiumGiftActivation(models.Model):
    _name = 'lottery.premium.gift.activation'
    _description = 'Teléfono donde se canjeó un código de regalo'
    _order = 'date desc'

    gift_id = fields.Many2one('lottery.premium.gift', required=True, ondelete='cascade', index=True)
    device_id = fields.Char(string='ID de instalación', required=True)
    hardware_id = fields.Char(string='ID del teléfono')
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    is_move = fields.Boolean(string='Mudanza')
