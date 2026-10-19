# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agenda_user_ids = fields.Many2many(
        related='company_id.agenda_user_ids', readonly=False)
    agenda_aviso_min = fields.Integer(
        related='company_id.agenda_aviso_min', readonly=False)
    agenda_aviso_hora = fields.Boolean(
        related='company_id.agenda_aviso_hora', readonly=False)
