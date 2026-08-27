# -*- coding: utf-8 -*-
from odoo import fields, models, api

_SA_PARAM        = 'lottery_api.fcm_service_account'
_HISTORIAL_PARAM = 'lottery_api.historial_desde'
_MIN_BUILD_PARAM = 'lottery_api.min_build_number'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fcm_service_account = fields.Text(
        string='FCM Service Account (JSON)',
        help='Pega aquí el contenido completo del archivo JSON de la cuenta '
             'de servicio de Firebase. Se guarda en ir.config_parameter y '
             'NO debe incluirse en el control de versiones.',
    )
    lottery_historial_desde = fields.Date(
        string='Historial de predicciones desde',
        help='Solo se muestran en la app las predicciones a partir de esta '
             'fecha. Dejá en blanco para mostrar todas.',
    )
    lottery_min_build_number = fields.Integer(
        string='Build mínimo requerido',
        help='Versión mínima (versionCode/buildNumber de Android) que debe '
             'tener la app instalada. Un usuario con una versión menor ve '
             'una pantalla de actualización obligatoria hasta que la '
             'actualice desde Play Store. Dejá en 0 para no exigir ninguna '
             'versión mínima.',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res['fcm_service_account'] = params.get_param(_SA_PARAM) or ''
        val = params.get_param(_HISTORIAL_PARAM)
        res['lottery_historial_desde'] = fields.Date.from_string(val) if val else False
        res['lottery_min_build_number'] = int(params.get_param(_MIN_BUILD_PARAM) or 0)
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(_SA_PARAM, self.fcm_service_account or '')
        params.set_param(
            _HISTORIAL_PARAM,
            self.lottery_historial_desde.isoformat()
            if self.lottery_historial_desde else '',
        )
        params.set_param(
            _MIN_BUILD_PARAM, str(self.lottery_min_build_number or 0))
        # Invalidar el token cacheado al cambiar la service account
        params.set_param('lottery_api.fcm_access_token', '')
