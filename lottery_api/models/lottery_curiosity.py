# -*- coding: utf-8 -*-
"""Envío manual de push FCM al publicar una curiosidad (LotoAnálisis
informa) desde el formulario. Mismo patrón que lottery_output.py: botón
manual, hilo post-commit, protegido contra doble envío."""

from odoo import fields, models
from odoo.exceptions import UserError

from .fcm_service import lanzar_push
from .lottery_output import _mensajes, _push_worker, _sorteo_con_pais


class LotteryCuriosity(models.Model):
    _inherit = 'lottery.curiosity'

    push_sent = fields.Boolean(string='Notificación enviada', default=False, readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación push para esta curiosidad.')
        if not self.sorteo_id.show_in_app:
            raise UserError('Este sorteo no está habilitado para mostrarse en la app.')
        if not self.published:
            raise UserError('Esta curiosidad todavía no está publicada.')

        messages = _mensajes(self, self.sorteo_id.id)

        lanzar_push(self.env.cr, _push_worker, (self.env.cr.dbname, messages))
        self.write({
            'push_sent': True,
            'push_sent_date': fields.Datetime.now(),
        })

    def _build_push_message(self, cur, lang='es'):
        en = lang == 'en'
        sorteo = _sorteo_con_pais(cur.sorteo_id, lang)
        premium = self.env['ir.config_parameter'].sudo().get_param(
            'lottery_api.informa_premium') == '1'
        if premium:
            if en:
                return '⭐ LotoAnálisis Reports · Premium', (
                    f'Important information for Premium users about {sorteo} has been '
                    f'posted. Check it in the "LotoAnálisis Reports" section.')
            return '⭐ LotoAnálisis informa · Premium', (
                f'Se registró información importante para los usuarios Premium sobre '
                f'{sorteo}. Consúltala en la sección "LotoAnálisis informa".')
        if en:
            return '📰 LotoAnálisis Reports', (
                f'There is a new follow-up report about {sorteo}. Check it in the '
                f'"LotoAnálisis Reports" section.')
        return '📰 LotoAnálisis informa', (
            f'Se registró una información de seguimiento sobre {sorteo}. '
            f'Consúltala en la sección "LotoAnálisis informa".')
