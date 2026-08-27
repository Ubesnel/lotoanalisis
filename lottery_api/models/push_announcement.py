# -*- coding: utf-8 -*-
"""Avisos generales (mantenimiento programado, nueva versión en Play Store,
etc.): push a TODOS los usuarios de la app, sin importar qué loterías
sigan — a diferencia de los push de salida/predicción/curiosidad, que van
al topic de un sorteo puntual (ver lottery_output.py, lottery_prediction.py,
lottery_curiosity.py).

Requiere que la app esté suscripta al topic fijo ANNOUNCEMENTS_TOPIC (ver
notification_service.dart, lado Flutter): las instalaciones con una versión
de la app anterior a esa suscripción no reciben estos avisos."""

import logging
import threading

from odoo import SUPERUSER_ID, api, fields, models, registry
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ANNOUNCEMENTS_TOPIC = 'anuncios'


def _push_announcement_worker(dbname, title, body):
    """Envía el push en un hilo aparte, con su propio cursor — mismo patrón
    que _push_worker de lottery_output.py, pero a un topic fijo en vez de
    uno por sorteo."""
    try:
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            try:
                env['lottery.fcm.service'].send_push_to_topic(
                    ANNOUNCEMENTS_TOPIC, title, body)
            except Exception as e:
                _logger.error(
                    'lottery_api: error enviando push de aviso general: %s', e)
            # Persiste el cache del token de acceso escrito por send_push.
            cr.commit()
    except Exception as e:
        _logger.error(
            'lottery_api: error en el hilo de push de aviso general: %s', e)


class LotteryPushAnnouncement(models.Model):
    _name = 'lottery.push.announcement'
    _description = 'Aviso general (push a todos los usuarios de la app)'
    _order = 'create_date desc'

    title = fields.Char(
        string='Título', required=True,
        help='Título de la notificación push.')
    body = fields.Text(
        string='Mensaje', required=True,
        help='Cuerpo de la notificación push. Ej: "El sábado 14 de 02:00 a '
             '04:00 la app va a estar en mantenimiento por tareas '
             'programadas." o "Hay una nueva versión disponible en Play '
             'Store, con mejoras y corrección de errores."')
    sent = fields.Boolean(
        string='Enviado', default=False, readonly=True, copy=False)
    sent_date = fields.Datetime(
        string='Fecha de envío', readonly=True, copy=False)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.sent:
            raise UserError('Ya se envió este aviso.')

        title, body = self.title, self.body
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(
            lambda: threading.Thread(
                target=_push_announcement_worker,
                args=(dbname, title, body),
                daemon=True,
            ).start()
        )
        self.write({
            'sent': True,
            'sent_date': fields.Datetime.now(),
        })
