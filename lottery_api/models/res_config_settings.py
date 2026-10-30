# -*- coding: utf-8 -*-
from odoo import fields, models, api

from .premium_pass import DEFAULT_PACKAGE, PLAY_PACKAGE_PARAM, PLAY_SA_PARAM

_SA_PARAM        = 'lottery_api.fcm_service_account'
_HISTORIAL_PARAM = 'lottery_api.historial_desde'
_MIN_BUILD_PARAM = 'lottery_api.min_build_number'
_INFORMA_PARAM   = 'lottery_api.informa_premium'
_PROMO_PARAM     = 'lottery_api.premium_promo'
_PROMO_DAYS_PARAM = 'lottery_api.premium_promo_days'


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
    play_service_account = fields.Text(
        string='Google Play Service Account (JSON)',
        help='JSON de la cuenta de servicio play-premium, que valida las '
             'compras de Premium. NO debe incluirse en el control de versiones.',
    )
    play_package_name = fields.Char(string='Paquete de la app en Play')
    lottery_informa_premium = fields.Boolean(
        string='"LotoAnálisis informa" es Premium',
        help='Si está marcado, /curiosidades manda el texto solo a quien tiene '
             'un pase Premium vigente. Prenderlo cuando la mayoría tenga la '
             'versión con Premium: las anteriores verían las noticias vacías.',
    )
    lottery_premium_promo = fields.Boolean(
        string='Aviso de Premium en la app',
        help='Cada tantos días la app invita a pasarse a Premium. Nunca a '
             'quien ya es Premium ni a quien no puede pagar con Google Play.',
    )
    lottery_premium_promo_days = fields.Integer(
        string='Cada cuántos días',
        help='Días mínimos entre un aviso y el siguiente. Si el usuario lo '
             'descarta, la app lo espacia más por su cuenta.',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res['fcm_service_account'] = params.get_param(_SA_PARAM) or ''
        val = params.get_param(_HISTORIAL_PARAM)
        res['lottery_historial_desde'] = fields.Date.from_string(val) if val else False
        res['lottery_min_build_number'] = int(params.get_param(_MIN_BUILD_PARAM) or 0)
        res['play_service_account'] = params.get_param(PLAY_SA_PARAM) or ''
        res['play_package_name'] = params.get_param(PLAY_PACKAGE_PARAM) or DEFAULT_PACKAGE
        res['lottery_informa_premium'] = params.get_param(_INFORMA_PARAM) == '1'
        res['lottery_premium_promo'] = params.get_param(_PROMO_PARAM) == '1'
        res['lottery_premium_promo_days'] = int(params.get_param(_PROMO_DAYS_PARAM) or 7)
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
        params.set_param(PLAY_SA_PARAM, self.play_service_account or '')
        params.set_param(PLAY_PACKAGE_PARAM, self.play_package_name or DEFAULT_PACKAGE)
        params.set_param(_INFORMA_PARAM, '1' if self.lottery_informa_premium else '')
        params.set_param(_PROMO_PARAM, '1' if self.lottery_premium_promo else '')
        params.set_param(_PROMO_DAYS_PARAM, str(max(self.lottery_premium_promo_days or 7, 1)))
        # Invalidar los tokens cacheados al cambiar las service accounts
        params.set_param('lottery_api.fcm_access_token', '')
        params.set_param('lottery_api.play_access_token', '')
