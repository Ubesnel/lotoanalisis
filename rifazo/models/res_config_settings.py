# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rifazo_whatsapp_group_url = fields.Char(
        'Grupo de WhatsApp de Rifazo',
        config_parameter='rifazo.whatsapp_group_url',
        help='Link de invitación al grupo general (https://chat.whatsapp.com/…). '
             'Se muestra en la página de descarga /rifazo.')
