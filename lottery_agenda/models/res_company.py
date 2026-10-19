# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    agenda_user_ids = fields.Many2many(
        'res.users', 'lottery_agenda_company_user_rel', 'company_id', 'user_id',
        string='Usuarios de la agenda',
        help="Quienes reciben los eventos de la agenda de loterías. Vacío = los "
             "usuarios del grupo Administrador de Lotería.")
    agenda_aviso_min = fields.Integer(
        string='Aviso (minutos antes)', default=10,
        help="Cuántos minutos antes de la hora de publicar suena el aviso.")
    agenda_aviso_hora = fields.Boolean(
        string='Aviso también a la hora', default=True,
        help="Además del aviso anticipado, suena otro justo a la hora de publicar.")
