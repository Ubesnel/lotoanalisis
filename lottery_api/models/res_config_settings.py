# -*- coding: utf-8 -*-
from odoo import fields, models, api

_SA_PARAM = 'lottery_api.fcm_service_account'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fcm_service_account = fields.Text(
        string='FCM Service Account (JSON)',
        help='Pega aquí el contenido completo del archivo JSON de la cuenta '
             'de servicio de Firebase. Se guarda en ir.config_parameter y '
             'NO debe incluirse en el control de versiones.',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res['fcm_service_account'] = (
            self.env['ir.config_parameter'].sudo().get_param(_SA_PARAM) or ''
        )
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            _SA_PARAM, self.fcm_service_account or ''
        )
        # Invalidar el token cacheado al cambiar la service account
        self.env['ir.config_parameter'].sudo().set_param(
            'lottery_api.fcm_access_token', ''
        )
