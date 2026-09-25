# -*- coding: utf-8 -*-
from odoo import fields, models


class RifazoRequestReject(models.TransientModel):
    _name = 'rifazo.request.reject'
    _description = 'Rechazar solicitud de rifa'

    request_ids = fields.Many2many('rifazo.request', string='Solicitudes', required=True)
    reason = fields.Text('Motivo', required=True,
                         help='Lo ve el participante en "Mis rifas"')

    def action_reject(self):
        self.request_ids._reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}
