# -*- coding: utf-8 -*-
from odoo import fields, models

TICKET_STATES = [
    ('available', 'Disponible'),
    ('reserved', 'Reservado'),
    ('pending', 'En verificación'),
    ('sold', 'Vendido'),
]


class RifazoTicket(models.Model):
    """Un registro por número de la rifa. Se generan todos al abrirla, así la
    reserva es un UPDATE atómico sobre filas existentes y el constraint único
    garantiza que un número no se venda dos veces."""
    _name = 'rifazo.ticket'
    _description = 'Número de rifa'
    _order = 'raffle_id, value'
    _rec_name = 'number'

    raffle_id = fields.Many2one('rifazo.raffle', string='Rifa', required=True,
                                ondelete='cascade', index=True, readonly=True)
    number = fields.Char('Número', required=True, readonly=True)
    value = fields.Integer('Valor', readonly=True, help='Número como entero, para ordenar')
    state = fields.Selection(TICKET_STATES, string='Estado', default='available',
                             required=True, index=True, readonly=True)
    request_id = fields.Many2one('rifazo.request', string='Solicitud',
                                 ondelete='set null', index=True, readonly=True)
    partner_name = fields.Char(related='request_id.partner_name', string='Participante')
    phone = fields.Char(related='request_id.phone', string='Teléfono')

    _sql_constraints = [
        ('raffle_number_uniq', 'unique(raffle_id, number)',
         'El número ya existe en esta rifa.'),
    ]
