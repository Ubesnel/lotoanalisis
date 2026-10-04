# -*- coding: utf-8 -*-
import re
import secrets
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .exceptions import RifazoApiError

# Sin 0/O ni 1/I/L para que el código se pueda dictar por WhatsApp.
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 5

REQUEST_STATES = [
    ('reserved', 'Reservada'),
    ('submitted', 'Por verificar'),
    ('confirmed', 'Confirmada'),
    ('rejected', 'Rechazada'),
    ('expired', 'Vencida'),
    ('cancelled', 'Cancelada'),
]


def normalize_phone(phone):
    """'+598 99 123-456' → '+59899123456'. None si no parece un teléfono."""
    phone = (phone or '').strip()
    digits = re.sub(r'\D', '', phone)
    if not 8 <= len(digits) <= 15:
        return None
    return ('+' if phone.startswith('+') else '') + digits


class RifazoRequest(models.Model):
    _name = 'rifazo.request'
    _description = 'Solicitud de participación'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'code'

    code = fields.Char('Código', readonly=True, copy=False, index=True,
                       help='Código público que ve el participante (RZ-XXXXX)')
    access_token = fields.Char('Token', readonly=True, copy=False, index=True,
                               groups='rifazo.group_rifazo_manager')
    raffle_id = fields.Many2one('rifazo.raffle', string='Rifa', required=True,
                                ondelete='restrict', index=True, readonly=True)
    currency_id = fields.Many2one(related='raffle_id.currency_id')
    state = fields.Selection(REQUEST_STATES, string='Estado', default='reserved',
                             required=True, index=True, readonly=True, tracking=True, copy=False)

    partner_name = fields.Char('Nombre', tracking=True)
    phone = fields.Char('Teléfono', tracking=True, index=True)
    device_id = fields.Char('Dispositivo', readonly=True, index=True)
    ip_address = fields.Char('IP', readonly=True)
    fcm_token = fields.Char('Token push', readonly=True)

    ticket_ids = fields.One2many('rifazo.ticket', 'request_id', string='Números retenidos')
    number_list = fields.Char('Números', readonly=True,
                              help='Foto de los números pedidos; se conserva aunque se liberen')
    numbers_count = fields.Integer('Cantidad', readonly=True)
    amount = fields.Monetary('Importe', readonly=True)

    reserved_until = fields.Datetime('Reservado hasta', readonly=True)
    submitted_date = fields.Datetime('Comprobante subido', readonly=True)
    verified_date = fields.Datetime('Verificado el', readonly=True, copy=False)
    verified_by_id = fields.Many2one('res.users', string='Verificado por', readonly=True, copy=False)
    proof_image = fields.Image('Comprobante', max_width=1920, max_height=1920,
                               attachment=True, readonly=True, copy=False)
    rejection_reason = fields.Text('Motivo del rechazo', readonly=True, tracking=True, copy=False)
    is_winner = fields.Boolean('Ganadora', compute='_compute_is_winner')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código de solicitud ya existe.'),
        ('access_token_uniq', 'unique(access_token)', 'El token ya existe.'),
    ]

    def _compute_is_winner(self):
        for rec in self:
            rec.is_winner = bool(rec.id) and rec.raffle_id.winner_request_id == rec

    @api.model
    def _generate_code(self):
        Request = self.sudo()
        while True:
            code = 'RZ-' + ''.join(secrets.choice(CODE_ALPHABET) for _i in range(CODE_LENGTH))
            if not Request.search_count([('code', '=', code)]):
                return code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('code', self._generate_code())
            vals.setdefault('access_token', secrets.token_urlsafe(24))
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Transiciones
    # ------------------------------------------------------------------

    def _release(self, new_state):
        """Devuelve los números a la venta y deja la solicitud en new_state."""
        self.ticket_ids.write({'state': 'available', 'request_id': False})
        self.write({'state': new_state, 'reserved_until': False})

    def _is_reservation_alive(self):
        self.ensure_one()
        return self.state == 'reserved' and self.reserved_until \
            and self.reserved_until > fields.Datetime.now()

    def action_confirm(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Solo se confirman solicitudes por verificar (%s).', rec.code))
        self.ticket_ids.write({'state': 'sold'})
        self.write({
            'state': 'confirmed',
            'verified_date': fields.Datetime.now(),
            'verified_by_id': self.env.uid,
        })

    def action_open_reject_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar solicitud'),
            'res_model': 'rifazo.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': self.ids},
        }

    def _reject(self, reason):
        if self.filtered(lambda r: r.state not in ('reserved', 'submitted')):
            raise UserError(_('Solo se rechazan solicitudes reservadas o por verificar.'))
        self._release('rejected')
        self.write({
            'rejection_reason': reason,
            'verified_date': fields.Datetime.now(),
            'verified_by_id': self.env.uid,
        })

    def action_cancel(self):
        if self.filtered(lambda r: r.state not in ('reserved', 'submitted')):
            raise UserError(_('Solo se cancelan solicitudes reservadas o por verificar.'))
        self._release('cancelled')

    def action_back_to_verify(self):
        """Deshace una confirmación hecha por error."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Solo se puede volver a verificar una solicitud confirmada.'))
            if rec.raffle_id.state == 'drawn':
                raise UserError(_('La rifa ya se sorteó.'))
        self.ticket_ids.write({'state': 'pending'})
        self.write({'state': 'submitted', 'verified_date': False, 'verified_by_id': False})

    def action_open_whatsapp(self):
        self.ensure_one()
        digits = re.sub(r'\D', '', self.phone or '')
        if not digits:
            raise UserError(_('La solicitud no tiene teléfono.'))
        text = _('Hola %(name)s, te escribimos de Rifazo por tu solicitud %(code)s '
                 '(%(raffle)s, números %(numbers)s).',
                 name=self.partner_name or '', code=self.code,
                 raffle=self.raffle_id.name, numbers=self.number_list)
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://wa.me/%s?text=%s' % (digits, quote(text)),
            'target': 'new',
        }

    @api.model
    def _cron_expire_reservations(self):
        expired = self.search([
            ('state', '=', 'reserved'),
            ('reserved_until', '<', fields.Datetime.now()),
        ])
        if expired:
            expired._release('expired')

    # ------------------------------------------------------------------
    # API (siempre llamadas con sudo desde el controlador)
    # ------------------------------------------------------------------

    def _public_winner_name(self):
        """'Juan Pérez García' → 'Juan P.' (nunca el nombre completo en público)."""
        self.ensure_one()
        parts = (self.partner_name or '').split()
        if not parts:
            return ''
        return parts[0] + (' %s.' % parts[1][0].upper() if len(parts) > 1 else '')

    def _public_phone_masked(self):
        """'+5351234567' → '••••••67'."""
        self.ensure_one()
        digits = re.sub(r'\D', '', self.phone or '')
        return '••••••' + digits[-2:] if len(digits) >= 2 else ''

    def _check_alive_for_api(self):
        self.ensure_one()
        if self.state == 'reserved' and not self._is_reservation_alive():
            # El cron corre cada minuto; no esperamos a que la pase a vencida.
            self._release('expired')
        if self.state != 'reserved':
            raise RifazoApiError('reservation_not_active',
                                 _('La reserva ya no está activa.'), status=409, state=self.state)

    def _api_set_contact(self, name, phone, fcm_token=None):
        self._check_alive_for_api()
        name = ' '.join((name or '').split())
        if not 2 <= len(name) <= 80:
            raise RifazoApiError('bad_name', _('Escribí tu nombre.'))
        normalized = normalize_phone(phone)
        if not normalized:
            raise RifazoApiError('bad_phone', _('El teléfono no es válido.'))
        vals = {'partner_name': name, 'phone': normalized}
        if fcm_token:
            vals['fcm_token'] = str(fcm_token)[:512]
        self.write(vals)

    def _api_submit_proof(self, image_b64):
        self._check_alive_for_api()
        if not self.partner_name or not self.phone:
            raise RifazoApiError('missing_contact', _('Faltan tu nombre y teléfono.'))
        self.write({
            'proof_image': image_b64,
            'state': 'submitted',
            'submitted_date': fields.Datetime.now(),
            'reserved_until': False,
        })
        self.ticket_ids.write({'state': 'pending'})

    def _api_cancel(self):
        self._check_alive_for_api()
        self._release('cancelled')
