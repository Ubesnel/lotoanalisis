# -*- coding: utf-8 -*-
"""Envío manual de push FCM al confirmar una salida desde el formulario.

El envío es manual (botón) y no automático al crear la salida: un error de
carga con un número ganador inválido ya generó falsas expectativas entre los
jugadores dos veces, así que se prefiere depender de una confirmación humana
antes de notificar.
"""

import logging
import threading

from odoo import SUPERUSER_ID, api, fields, models, registry
from odoo.exceptions import UserError

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

    push_sent = fields.Boolean(string='Notificación enviada', default=False, readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)

    def action_send_push_notification(self):
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación push para esta salida.')
        if not self.sorteo_id.show_in_app:
            raise UserError('Este sorteo no está habilitado para mostrarse en la app.')

        title, body = self._build_push_message(self)
        sorteo_id = self.sorteo_id.id

        # El envío HTTP se difiere: al hacer commit, se lanza un hilo que hace
        # la llamada a FCM, para no bloquear la UI esperando la red.
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

        tabla_magicos = self._tabla_numeros_magicos(out)
        if tabla_magicos == 'general':
            partes.append('🔮 El fijo estuvo en el total de Números Mágicos')
        elif tabla_magicos:
            partes.append(f'🔮 El fijo estuvo en la tabla de {tabla_magicos} Números Mágicos')

        title = f'🎯 Resultado {out.sorteo_id.name} disponible'
        body = ' · '.join(partes) + '\n📈 Consulta el análisis actualizado para el próximo sorteo'
        return title, body

    def _tabla_numeros_magicos(self, out):
        """En qué lista de Números Mágicos estaba el número salido — siempre
        la más chica (más específica) en la que estaba, ya que 5 ⊂ 10 ⊂ 20 ⊂
        Total por construcción (ver lottery.prediction.action_completar_numeros).

        Devuelve '5', '10', '20', 'general' (solo en la lista completa de
        Números a predecir, sin llegar al 20) o None.

        Lee los booleanos `cumplida*` que `_check_predictions()` (lottery_portal)
        ya dejó marcados en la predicción al registrar esta salida — no
        recalcula nada. None si no hay predicción publicada para esa fecha/
        turno/sorteo, o si el número no estaba en ninguna lista."""
        prediction = self.env['lottery.prediction'].sudo().search([
            ('sorteo_id', '=', out.sorteo_id.id),
            ('date', '=', out.date),
            ('turn_day', '=', out.turn_day),
            ('published', '=', True),
        ], limit=1)
        if not prediction:
            return None
        if prediction.cumplida_5:
            return '5'
        if prediction.cumplida_10:
            return '10'
        if prediction.cumplida_20:
            return '20'
        if prediction.cumplida:
            return 'general'
        return None
