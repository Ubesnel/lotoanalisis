# -*- coding: utf-8 -*-
"""Envío de push FCM al registrarse una salida nueva reciente."""

import logging
from datetime import date, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)

TURN_LABELS = {'afternoon': 'Tarde', 'evening': 'Noche'}


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

        FcmService = self.env['lottery.fcm.service']
        for out in recent:
            title, body = self._build_push_message(out)
            try:
                FcmService.send_push(out.sorteo_id.id, title, body)
            except Exception as e:
                _logger.error(
                    'lottery_api: excepción en push para salida %s: %s',
                    out.id, e
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
