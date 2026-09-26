# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .exceptions import RifazoApiError

# Tope de números por rifa: con un registro por número, 100.000 sigue siendo
# liviano para PostgreSQL y para /numbers (que solo manda los no disponibles).
MAX_NUMBERS_PER_RAFFLE = 100000
RANGE_FIELDS = ('number_from', 'number_to', 'number_digits')


class RifazoRaffle(models.Model):
    _name = 'rifazo.raffle'
    _description = 'Rifa'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'sequence, draw_date desc, id desc'

    name = fields.Char('Nombre', required=True, tracking=True)
    sequence = fields.Integer('Orden', default=10, help='Orden en el inicio de la app')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'Abierta'),
        ('closed', 'Venta cerrada'),
        ('drawn', 'Sorteada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', required=True, tracking=True, copy=False)
    short_description = fields.Char('Resumen', help='Una línea para la tarjeta del inicio')
    description = fields.Html('Descripción', sanitize=True)
    image_ids = fields.One2many('rifazo.raffle.image', 'raffle_id', string='Galería', copy=True)

    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    price = fields.Monetary('Precio por número', required=True, tracking=True)
    draw_date = fields.Datetime('Fecha del sorteo', tracking=True)
    sale_end_date = fields.Datetime(
        'Cierre de venta', tracking=True,
        help='A esta fecha y hora la venta de números se cierra sola (las reservas '
             'en curso pueden terminar de pagar). Vacío: se cierra a mano.')
    draw_method = fields.Char('Cómo se sortea',
                              help='Ej: "Con la cabeza de la Quiniela nocturna de ese día"')

    number_from = fields.Integer('Desde', default=0, required=True)
    number_to = fields.Integer('Hasta', default=99, required=True)
    number_digits = fields.Integer('Dígitos', compute='_compute_number_digits', store=True,
                                   readonly=False, required=True,
                                   help='Relleno con ceros: 3 dígitos → 007')
    number_example = fields.Char('Números', compute='_compute_number_example')

    # La app no muestra datos bancarios: solo indica adónde ir a pagar.
    payment_instructions = fields.Text(
        'Indicaciones de pago',
        default=lambda self: _('Para realizar el pago, dirigite a nuestro grupo de WhatsApp. '
                               'Ahí te pasamos los datos de la cuenta.'),
        help='Texto que ve el participante en la pantalla de pago. '
             'No pongas datos bancarios: se dan en el grupo de WhatsApp.')
    whatsapp_url = fields.Char('Grupo de WhatsApp',
                               help='Link de invitación al grupo (https://chat.whatsapp.com/…). '
                                    'La app lo muestra como botón en la pantalla de pago.')
    reservation_minutes = fields.Integer('Minutos de reserva', default=60, required=True,
                                         help='Tiempo para subir el comprobante antes de que se liberen los números')
    max_numbers_per_request = fields.Integer('Máx. números por solicitud', default=10, required=True)

    ticket_ids = fields.One2many('rifazo.ticket', 'raffle_id', string='Números')
    request_ids = fields.One2many('rifazo.request', 'raffle_id', string='Solicitudes')

    winning_number = fields.Char('Número ganador', tracking=True, copy=False)
    winner_request_id = fields.Many2one('rifazo.request', string='Solicitud ganadora',
                                        readonly=True, copy=False)
    winner_name = fields.Char(related='winner_request_id.partner_name', string='Ganador')
    winner_phone = fields.Char(related='winner_request_id.phone', string='Teléfono del ganador')

    # Entrega del premio: se publica en "Últimos sorteos" de la app para dar
    # confianza (comprobante de la recarga, foto de la entrega del equipo…).
    prize_delivered = fields.Boolean('Premio entregado', readonly=True, tracking=True, copy=False)
    prize_delivered_date = fields.Datetime('Entregado el', readonly=True, copy=False)
    prize_evidence_image = fields.Image(
        'Evidencia de la entrega', max_width=1920, max_height=1920, attachment=True, copy=False,
        help='Comprobante de la recarga o foto de la entrega. Se muestra en la app.')
    prize_note = fields.Char(
        'Nota de la entrega', copy=False,
        help='Se muestra en la app junto a la evidencia. Ej: "Recarga de 360 CUP realizada".')

    ticket_total = fields.Integer('Total', compute='_compute_ticket_stats')
    ticket_available_count = fields.Integer('Disponibles', compute='_compute_ticket_stats')
    ticket_reserved_count = fields.Integer('Reservados', compute='_compute_ticket_stats')
    ticket_pending_count = fields.Integer('En verificación', compute='_compute_ticket_stats')
    ticket_sold_count = fields.Integer('Vendidos', compute='_compute_ticket_stats')
    sold_percent = fields.Float('% vendido', compute='_compute_ticket_stats')
    request_count = fields.Integer('Solicitudes', compute='_compute_request_stats')
    request_to_verify_count = fields.Integer('Por verificar', compute='_compute_request_stats')
    amount_collected = fields.Monetary('Cobrado (confirmado)', compute='_compute_request_stats')
    amount_to_verify = fields.Monetary('Por verificar ($)', compute='_compute_request_stats')

    @api.depends('number_to')
    def _compute_number_digits(self):
        for rec in self:
            rec.number_digits = len(str(max(rec.number_to, 0)))

    @api.depends('number_from', 'number_to', 'number_digits')
    def _compute_number_example(self):
        for rec in self:
            count = rec.number_to - rec.number_from + 1
            if count <= 0:
                rec.number_example = False
                continue
            rec.number_example = _('%(first)s … %(last)s (%(count)s números)',
                                   first=rec._format_number(rec.number_from),
                                   last=rec._format_number(rec.number_to),
                                   count=count)

    def _compute_ticket_stats(self):
        data = {}
        if self.ids:
            groups = self.env['rifazo.ticket']._read_group(
                [('raffle_id', 'in', self.ids)], ['raffle_id', 'state'], ['__count'])
            for raffle, state, count in groups:
                data.setdefault(raffle.id, {})[state] = count
        for rec in self:
            counts = data.get(rec.id, {})
            total = sum(counts.values())
            rec.ticket_total = total
            rec.ticket_available_count = counts.get('available', 0)
            rec.ticket_reserved_count = counts.get('reserved', 0)
            rec.ticket_pending_count = counts.get('pending', 0)
            rec.ticket_sold_count = counts.get('sold', 0)
            rec.sold_percent = 100.0 * counts.get('sold', 0) / total if total else 0.0

    def _compute_request_stats(self):
        data = {}
        if self.ids:
            groups = self.env['rifazo.request']._read_group(
                [('raffle_id', 'in', self.ids)], ['raffle_id', 'state'], ['__count', 'amount:sum'])
            for raffle, state, count, amount in groups:
                data.setdefault(raffle.id, {})[state] = (count, amount)
        for rec in self:
            by_state = data.get(rec.id, {})
            rec.request_count = sum(c for c, _a in by_state.values())
            rec.request_to_verify_count = by_state.get('submitted', (0, 0))[0]
            rec.amount_collected = by_state.get('confirmed', (0, 0))[1]
            rec.amount_to_verify = by_state.get('submitted', (0, 0))[1]

    @api.constrains('number_from', 'number_to', 'number_digits')
    def _check_number_range(self):
        for rec in self:
            if rec.number_from < 0:
                raise ValidationError(_('El rango no puede empezar en un número negativo.'))
            if rec.number_to < rec.number_from:
                raise ValidationError(_('"Hasta" tiene que ser mayor o igual que "Desde".'))
            if rec.number_to - rec.number_from + 1 > MAX_NUMBERS_PER_RAFFLE:
                raise ValidationError(_('Una rifa puede tener como máximo %s números.',
                                        MAX_NUMBERS_PER_RAFFLE))
            if rec.number_digits < len(str(rec.number_to)):
                raise ValidationError(_('%(to)s no entra en %(digits)s dígitos.',
                                        to=rec.number_to, digits=rec.number_digits))

    @api.constrains('sale_end_date', 'draw_date')
    def _check_sale_end_date(self):
        for rec in self:
            if rec.sale_end_date and rec.draw_date and rec.sale_end_date > rec.draw_date:
                raise ValidationError(_('El cierre de venta tiene que ser antes del sorteo.'))

    @api.constrains('price', 'reservation_minutes', 'max_numbers_per_request')
    def _check_positive_values(self):
        for rec in self:
            if rec.price <= 0:
                raise ValidationError(_('El precio por número tiene que ser mayor que cero.'))
            if rec.reservation_minutes <= 0:
                raise ValidationError(_('Los minutos de reserva tienen que ser mayores que cero.'))
            if rec.max_numbers_per_request <= 0:
                raise ValidationError(_('El máximo de números por solicitud tiene que ser mayor que cero.'))

    def write(self, vals):
        # Con los números ya generados, cambiar el rango o el relleno dejaría
        # números duplicados ("07" y "007") o huérfanos.
        if any(f in vals for f in RANGE_FIELDS):
            locked = self.filtered(lambda r: r.state != 'draft')
            for rec in locked:
                if any(vals[f] != rec[f] for f in RANGE_FIELDS if f in vals):
                    raise UserError(_('El rango de números solo se puede cambiar con la rifa en borrador.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda r: r.state not in ('draft', 'cancelled')):
            raise UserError(_('Solo se pueden borrar rifas en borrador o canceladas.'))

    # ------------------------------------------------------------------
    # Números
    # ------------------------------------------------------------------

    def _format_number(self, value):
        self.ensure_one()
        return str(value).zfill(self.number_digits)

    def _normalize_number(self, value):
        """'7', 7, '007' → '007' si está en rango; None si no es válido."""
        self.ensure_one()
        text = str(value).strip()
        if not text.isdigit():
            return None
        number = int(text)
        if number < self.number_from or number > self.number_to:
            return None
        return self._format_number(number)

    def _generate_tickets(self):
        """Crea los números que falten. SQL directo porque con 10.000+ números
        el create del ORM tarda; ON CONFLICT lo hace idempotente."""
        for rec in self:
            self.env.cr.execute("""
                INSERT INTO rifazo_ticket
                    (raffle_id, number, value, state,
                     create_uid, create_date, write_uid, write_date)
                SELECT %(raffle)s, lpad(n::text, %(digits)s, '0'), n, 'available',
                       %(uid)s, now() at time zone 'UTC', %(uid)s, now() at time zone 'UTC'
                  FROM generate_series(%(start)s, %(stop)s) AS n
                ON CONFLICT (raffle_id, number) DO NOTHING
            """, {
                'raffle': rec.id,
                'digits': rec.number_digits,
                'uid': self.env.uid,
                'start': rec.number_from,
                'stop': rec.number_to,
            })
        self.env['rifazo.ticket'].invalidate_model()
        self.invalidate_recordset(['ticket_ids'])

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------

    def _is_sale_expired(self):
        """Llegó la hora de cierre de venta (aunque el cron todavía no corrió)."""
        self.ensure_one()
        return bool(self.sale_end_date) and self.sale_end_date <= fields.Datetime.now()

    @api.model
    def _cron_close_expired_sales(self):
        expired = self.search([
            ('state', '=', 'open'),
            ('sale_end_date', '!=', False),
            ('sale_end_date', '<=', fields.Datetime.now()),
        ])
        for rec in expired:
            rec.action_close()
            rec.message_post(body=_('Venta cerrada automáticamente: llegó la hora de cierre de venta.'))

    def action_open(self):
        for rec in self:
            if rec.state not in ('draft', 'closed'):
                raise UserError(_('Solo se puede abrir una rifa en borrador o con la venta cerrada.'))
            if rec._is_sale_expired():
                raise UserError(_('La hora de cierre de venta ya pasó: cambiala (o dejala vacía) '
                                  'antes de abrir la rifa.'))
            if rec.state == 'draft':
                rec._generate_tickets()
        self.write({'state': 'open'})

    def action_close(self):
        if self.filtered(lambda r: r.state != 'open'):
            raise UserError(_('Solo se puede cerrar la venta de una rifa abierta.'))
        # Las reservas en curso pueden terminar de subir su comprobante.
        self.write({'state': 'closed'})

    def action_draw(self):
        for rec in self:
            if rec.state != 'closed':
                raise UserError(_('Primero cerrá la venta de la rifa.'))
            if not rec.winning_number:
                raise UserError(_('Cargá el número ganador.'))
            unresolved = rec.request_ids.filtered(lambda r: r.state in ('reserved', 'submitted'))
            if unresolved:
                raise UserError(_('Hay %s solicitudes sin resolver (reservadas o por verificar). '
                                  'Confirmalas, rechazalas o esperá a que venzan.', len(unresolved)))
            number = rec._normalize_number(rec.winning_number)
            if not number:
                raise UserError(_('El número ganador tiene que estar entre %(first)s y %(last)s.',
                                  first=rec._format_number(rec.number_from),
                                  last=rec._format_number(rec.number_to)))
            ticket = self.env['rifazo.ticket'].search(
                [('raffle_id', '=', rec.id), ('number', '=', number), ('state', '=', 'sold')], limit=1)
            rec.write({
                'winning_number': number,
                'winner_request_id': ticket.request_id.id,
                'state': 'drawn',
            })
            if ticket:
                rec.message_post(body=_('Ganador: %(name)s (%(phone)s) con el %(number)s, solicitud %(code)s.',
                                        name=ticket.request_id.partner_name, phone=ticket.request_id.phone,
                                        number=number, code=ticket.request_id.code))
            else:
                rec.message_post(body=_('El %s no estaba vendido: la rifa queda sin ganador.', number))

    def action_mark_prize_delivered(self):
        for rec in self:
            if rec.state != 'drawn' or not rec.winner_request_id:
                raise UserError(_('Solo se marca la entrega en una rifa sorteada con ganador.'))
            if not rec.prize_evidence_image:
                raise UserError(_('Cargá la evidencia de la entrega (comprobante o foto) en la '
                                  'pestaña "Entrega del premio".'))
        self.write({'prize_delivered': True, 'prize_delivered_date': fields.Datetime.now()})

    def action_unmark_prize_delivered(self):
        self.write({'prize_delivered': False, 'prize_delivered_date': False})

    def action_cancel(self):
        for rec in self:
            if rec.state in ('drawn', 'cancelled'):
                raise UserError(_('La rifa ya está sorteada o cancelada.'))
            open_requests = rec.request_ids.filtered(lambda r: r.state in ('reserved', 'submitted'))
            open_requests._release('cancelled')
        self.write({'state': 'cancelled'})

    def action_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Solo una rifa cancelada puede volver a borrador.'))
            if rec.request_ids:
                raise UserError(_('La rifa ya tiene solicitudes: no puede volver a borrador. '
                                  'Duplicala para empezar de nuevo.'))
            rec.ticket_ids.unlink()
        self.write({'state': 'draft', 'winning_number': False, 'winner_request_id': False})

    # ------------------------------------------------------------------
    # Botones inteligentes
    # ------------------------------------------------------------------

    def action_view_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('rifazo.action_rifazo_request')
        action['domain'] = [('raffle_id', '=', self.id)]
        action['context'] = {'default_raffle_id': self.id}
        return action

    def action_view_requests_to_verify(self):
        action = self.action_view_requests()
        action['context'] = dict(action['context'], search_default_to_verify=1)
        return action

    def action_view_tickets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('rifazo.action_rifazo_ticket')
        action['domain'] = [('raffle_id', '=', self.id)]
        action['context'] = {'search_default_not_available': 1}
        return action

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def _reserve_numbers(self, numbers, device_id, ip_address=None):
        """Reserva atómica. Devuelve la solicitud creada o lanza RifazoApiError.

        Se marca primero los tickets con un UPDATE ... WHERE state='available':
        si otra persona reservó alguno en paralelo, PostgreSQL serializa las dos
        transacciones y acá vuelven menos filas de las pedidas → se deshace todo
        y se responde 409 con los números perdidos."""
        self.ensure_one()
        if self.state == 'open' and self._is_sale_expired():
            # Pasó la hora de cierre y el cron todavía no corrió: se cierra ya.
            self.action_close()
        if self.state != 'open':
            raise RifazoApiError('raffle_not_open', _('Esta rifa no está a la venta.'), status=409)
        device_id = (device_id or '').strip()
        if not device_id or len(device_id) > 64:
            raise RifazoApiError('bad_device', _('Falta el identificador del dispositivo.'))
        if not isinstance(numbers, list) or not numbers:
            raise RifazoApiError('no_numbers', _('Elegí al menos un número.'))

        normalized, invalid = [], []
        for value in numbers:
            number = self._normalize_number(value)
            if number is None:
                invalid.append(str(value))
            elif number not in normalized:
                normalized.append(number)
        if invalid:
            raise RifazoApiError('invalid_numbers', _('Hay números fuera de la rifa.'), numbers=invalid)
        if len(normalized) > self.max_numbers_per_request:
            raise RifazoApiError('too_many_numbers',
                                 _('Podés reservar hasta %s números por vez.', self.max_numbers_per_request),
                                 max=self.max_numbers_per_request)

        Request = self.env['rifazo.request']
        params = self.env['ir.config_parameter'].sudo()
        now = fields.Datetime.now()
        active = [('state', '=', 'reserved'), ('reserved_until', '>', now)]
        max_device = int(params.get_param('rifazo.max_active_per_device', 2))
        if Request.search_count(active + [('device_id', '=', device_id)]) >= max_device:
            raise RifazoApiError('too_many_reservations',
                                 _('Ya tenés reservas sin pagar. Terminá o cancelá una antes de reservar otra.'),
                                 status=429)
        max_ip = int(params.get_param('rifazo.max_active_per_ip', 6))
        if ip_address and Request.search_count(active + [('ip_address', '=', ip_address)]) >= max_ip:
            raise RifazoApiError('too_many_reservations',
                                 _('Hay demasiadas reservas abiertas desde esta conexión.'), status=429)

        with self.env.cr.savepoint():
            self.env['rifazo.ticket'].flush_model()
            self.env.cr.execute("""
                UPDATE rifazo_ticket
                   SET state = 'reserved', write_uid = %s, write_date = now() at time zone 'UTC'
                 WHERE raffle_id = %s AND number IN %s AND state = 'available'
             RETURNING id, number
            """, (self.env.uid, self.id, tuple(normalized)))
            rows = self.env.cr.fetchall()
            if len(rows) != len(normalized):
                taken = sorted(set(normalized) - {number for _id, number in rows})
                raise RifazoApiError('numbers_taken',
                                     _('Alguien se adelantó con algunos números.'),
                                     status=409, numbers=taken)
        self.env['rifazo.ticket'].invalidate_model(['state'])

        ordered = sorted(normalized)
        request = Request.create({
            'raffle_id': self.id,
            'device_id': device_id,
            'ip_address': ip_address,
            'number_list': ', '.join(ordered),
            'numbers_count': len(ordered),
            'amount': self.price * len(ordered),
            'reserved_until': now + timedelta(minutes=self.reservation_minutes),
        })
        self.env['rifazo.ticket'].browse([ticket_id for ticket_id, _n in rows]).write(
            {'request_id': request.id})
        return request
