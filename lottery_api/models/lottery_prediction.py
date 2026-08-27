# -*- coding: utf-8 -*-
"""Envío manual de push FCM al publicar una predicción (Números Mágicos)
desde el formulario. Mismo patrón que lottery_output.py: botón manual,
hilo post-commit, protegido contra doble envío."""

import threading

from odoo import fields, models
from odoo.exceptions import UserError

from .lottery_output import TURN_LABELS, _push_worker


class LotteryPrediction(models.Model):
    _inherit = 'lottery.prediction'

    push_sent = fields.Boolean(string='Notificación enviada', default=False, readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación push para esta predicción.')
        if not self.sorteo_id.show_in_app:
            raise UserError('Este sorteo no está habilitado para mostrarse en la app.')
        if not self.published:
            raise UserError('Esta predicción todavía no está publicada.')

        title, body = self._build_push_message(self)
        sorteo_id = self.sorteo_id.id

        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(
            lambda: threading.Thread(
                target=_push_worker,
                args=(dbname, [(sorteo_id, title, body)]),
                daemon=True,
            ).start()
        )
        self.write({
            'push_sent': True,
            'push_sent_date': fields.Datetime.now(),
        })

    def _build_push_message(self, pred):
        turn_label = TURN_LABELS.get(pred.turn_day, pred.turn_day.capitalize())
        fecha = pred.date.strftime('%d/%m/%Y') if pred.date else ''

        title = '🔮 Números Mágicos disponibles'
        body = (
            f'Ya fueron registrados en la Aplicación los Números Mágicos '
            f'para el sorteo {pred.sorteo_id.name} del {fecha} ({turn_label}).'
        )
        return title, body
