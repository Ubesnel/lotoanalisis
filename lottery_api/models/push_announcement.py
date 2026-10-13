# -*- coding: utf-8 -*-
"""Avisos generales (mantenimiento programado, nueva versión en Play Store,
etc.): push a TODOS los usuarios de la app, sin importar qué loterías
sigan — a diferencia de los push de salida/predicción/curiosidad, que van
al topic de un sorteo puntual (ver lottery_output.py, lottery_prediction.py,
lottery_curiosity.py).

Si el aviso tiene sorteos elegidos, va solo a quienes siguen alguno de esos
sorteos (sus topics `sorteo_<id>`), en un único mensaje con una condición de
FCM para que a nadie le llegue repetido. FCM admite hasta 5 topics por
condición: con más sorteos se manda en tandas de 5, y quien siga sorteos de
dos tandas distintas lo recibe más de una vez.

Requiere que la app esté suscripta al topic fijo ANNOUNCEMENTS_TOPIC (ver
notification_service.dart, lado Flutter): las instalaciones con una versión
de la app anterior a esa suscripción no reciben estos avisos."""

import logging
import threading

from odoo import SUPERUSER_ID, api, fields, models, registry
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ANNOUNCEMENTS_TOPIC = 'anuncios'
MAX_TOPICS_POR_CONDICION = 5


def _destinos(sorteo_ids):
    """[(tipo, destino)] para FCM: el topic general si no hay sorteos, un
    topic si hay uno solo, y condiciones de hasta 5 topics si hay varios."""
    if not sorteo_ids:
        return [('topic', ANNOUNCEMENTS_TOPIC)]
    destinos = []
    for i in range(0, len(sorteo_ids), MAX_TOPICS_POR_CONDICION):
        tanda = sorteo_ids[i:i + MAX_TOPICS_POR_CONDICION]
        if len(tanda) == 1:
            destinos.append(('topic', f'sorteo_{tanda[0]}'))
        else:
            destinos.append(('condition', ' || '.join(
                f"'sorteo_{sid}' in topics" for sid in tanda)))
    return destinos


def _push_announcement_worker(dbname, destinos, title, body):
    """Envía el push en un hilo aparte, con su propio cursor — mismo patrón
    que _push_worker de lottery_output.py."""
    try:
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            fcm = env['lottery.fcm.service']
            for tipo, destino in destinos:
                try:
                    if tipo == 'condition':
                        fcm.send_push_to_condition(destino, title, body)
                    else:
                        fcm.send_push_to_topic(destino, title, body)
                except Exception as e:
                    _logger.error(
                        'lottery_api: error enviando push de aviso general a %s: %s',
                        destino, e)
            # Persiste el cache del token de acceso escrito por send_push.
            cr.commit()
    except Exception as e:
        _logger.error(
            'lottery_api: error en el hilo de push de aviso general: %s', e)


class LotteryPushAnnouncement(models.Model):
    _name = 'lottery.push.announcement'
    _description = 'Aviso general (push a todos o a los que siguen ciertos sorteos)'
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
    sorteo_ids = fields.Many2many(
        'lottery.sorteo', 'lottery_push_announcement_sorteo_rel',
        'announcement_id', 'sorteo_id', string='Sorteos',
        help='Vacío = el aviso llega a todos los usuarios de la app. Con '
             'sorteos elegidos, llega solo a quienes siguen alguno de ellos '
             '(una sola vez aunque sigan varios, hasta 5 sorteos).')
    # Para la vista: el evaluador de expresiones del cliente no tiene len().
    sorteo_count = fields.Integer(compute='_compute_sorteo_count')
    sent = fields.Boolean(
        string='Enviado', default=False, readonly=True, copy=False)
    sent_date = fields.Datetime(
        string='Fecha de envío', readonly=True, copy=False)

    @api.depends('sorteo_ids')
    def _compute_sorteo_count(self):
        for rec in self:
            rec.sorteo_count = len(rec.sorteo_ids)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.sent:
            raise UserError('Ya se envió este aviso.')

        title, body = self.title, self.body
        destinos = _destinos(self.sorteo_ids.ids)
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(
            lambda: threading.Thread(
                target=_push_announcement_worker,
                args=(dbname, destinos, title, body),
                daemon=True,
            ).start()
        )
        self.write({
            'sent': True,
            'sent_date': fields.Datetime.now(),
        })
