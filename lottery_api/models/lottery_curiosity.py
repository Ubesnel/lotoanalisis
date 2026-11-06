# -*- coding: utf-8 -*-
"""Envío manual de push FCM al publicar una curiosidad (LotoAnálisis
informa) desde el formulario. Mismo patrón que lottery_output.py: botón
manual, hilo post-commit, protegido contra doble envío."""

from odoo import fields, models
from odoo.exceptions import UserError

from .fcm_service import lanzar_push
from .lottery_output import _mensajes, _push_worker


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
        if lang == 'en':
            return '📰 LotoAnálisis Reports', (
                f'There is a new follow-up report in the app, in the '
                f'"LotoAnálisis Reports" section, for {cur.sorteo_id.name}.')
        title = '📰 LotoAnálisis informa'
        body = (
            f'Se ha registrado una información de seguimiento en la APK, '
            f'en la sección "LotoAnálisis informa", para {cur.sorteo_id.name}.'
        )
        return title, body
