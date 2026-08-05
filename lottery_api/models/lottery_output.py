# -*- coding: utf-8 -*-
"""Envío de push FCM al registrarse una salida nueva reciente."""

import logging
import threading
from datetime import date, timedelta

from odoo import SUPERUSER_ID, api, models, registry

_logger = logging.getLogger(__name__)

TURN_LABELS = {'afternoon': 'Tarde', 'evening': 'Noche'}


def _push_worker(dbname, messages):
    """Envía los push en un hilo aparte, con su propio cursor.

    Se ejecuta fuera del request (post-commit), así el guardado de la salida
    no espera la llamada HTTP a FCM y no se retienen locks durante la red.
    """
    try:
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            FcmService = env['lottery.fcm.service']
            for sorteo_id, title, body in messages:
                try:
                    FcmService.send_push(sorteo_id, title, body)
                except Exception as e:
                    _logger.error(
                        'lottery_api: error enviando push (hilo) sorteo %s: %s',
                        sorteo_id, e
                    )
            # Persiste el cache del token de acceso escrito por send_push.
            cr.commit()
    except Exception as e:
        _logger.error('lottery_api: error en el hilo de push FCM: %s', e)


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._send_fcm_for_new_outputs(records)
        return records

    def _send_fcm_for_new_outputs(self, records):
        today = date.today()
        yesterday = today - timedelta(days=1)
        recent = records.filtered(
            lambda r: r.date >= yesterday and r.sorteo_id.show_in_app
        )
        if not recent:
            return

        # Los mensajes se arman ahora (necesitan datos ORM) pero el envío HTTP
        # se difiere: al hacer commit, se lanza un hilo que hace la llamada a
        # FCM. Así la creación de la salida no bloquea esperando la red y solo
        # se notifica si el create realmente commitea.
        messages = [
            (out.sorteo_id.id, *self._build_push_message(out))
            for out in recent
        ]
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(
            lambda: threading.Thread(
                target=_push_worker,
                args=(dbname, messages),
                daemon=True,
            ).start()
        )

    def _build_push_message(self, out):
        turn_label = TURN_LABELS.get(out.turn_day, out.turn_day.capitalize())
        centena = out.hundreds_id.name if out.hundreds_id else ''
        numero = str(out.number_id.name).zfill(2) if out.number_id else ''
        numero_completo = f'{centena}{numero}'

        partes = [
            f'Turno: {turn_label}',
            f'Número: {numero_completo}',
        ]

        if out.premio_2_id and out.premio_3_id:
            p2 = str(out.premio_2_id.name).zfill(2)
            p3 = str(out.premio_3_id.name).zfill(2)
            partes.append(f'Corridos: {p2} y {p3}')

        if out.fireball_id:
            partes.append(f'Bola extra: {out.fireball_id.name}')

        title = f'🎯 Resultado {out.sorteo_id.name} disponible'
        body = ' · '.join(partes) + '\n📈 Consulta el análisis actualizado para el próximo sorteo'
        return title, body
