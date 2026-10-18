# -*- coding: utf-8 -*-
"""Envío manual de push FCM al publicar una predicción (Números Mágicos)
desde el formulario. Mismo patrón que lottery_output.py: botón manual,
hilo post-commit, protegido contra doble envío."""

import logging
import threading
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from .lottery_output import _push_worker

_logger = logging.getLogger(__name__)

# Parámetro que marca las vistas materializadas pendientes de refresh
# (lottery_delays_number): mientras vale '1', las stats todavía no están al día.
MV_DIRTY_PARAM = 'lottery.mv_dirty'

# Si pasado este margen sobre los minutos de espera el ranking sigue sin
# recalcularse, se deja constancia en el sorteo en vez de esperar en silencio.
MARGEN_RANKING_MIN = 60


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
        # 'hour' se pisa con la hora real de envío: es lo que la app muestra
        # como "Hora de Uruguay" en Números Mágicos, y hasta ahora se quedaba
        # con la hora en que se había creado/editado el registro, no con la
        # del push. Mismo cálculo que _default_hour en lottery_portal
        # (duplicado acá por lo mismo: no hay utils compartido).
        ahora = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        self.write({
            'push_sent': True,
            'push_sent_date': fields.Datetime.now(),
            'hour': ahora.hour + ahora.minute / 60.0,
        })

    def _build_push_message(self, pred):
        turn_label = pred.turno_id.name or ''
        fecha = pred.date.strftime('%d/%m/%Y') if pred.date else ''

        title = '🔮 Números Mágicos disponibles'
        body = (
            f'Ya fueron registrados en la Aplicación los Números Mágicos '
            f'para el sorteo {pred.sorteo_id.name} del {fecha} ({turn_label}).'
        )
        return title, body

    # ── Predicciones automáticas ────────────────────────────────────────

    @api.model
    def cron_generar_predicciones_automaticas(self):
        """Crea sola la predicción del próximo sorteo en los sorteos con
        "Generar predicciones automáticamente". Cada sorteo va en su propia
        transacción: si uno falla, los demás siguen y el motivo queda en
        `auto_prediction_error` del sorteo."""
        sorteos = self.env['lottery.sorteo'].sudo().search([
            ('auto_prediction', '=', True),
            ('exclude_from_predictions', '=', False),
        ])
        for sorteo in sorteos:
            try:
                with self.env.cr.savepoint():
                    creada = self.sudo()._auto_predecir_sorteo(sorteo)
            except Exception as exc:  # noqa: BLE001 - se informa en el sorteo
                # Un error que no se arregla se repite en cada corrida: se
                # guarda (y se loguea) una sola vez, con su hora de origen.
                mensaje = str(exc)
                if not (sorteo.auto_prediction_error or '').endswith(mensaje):
                    _logger.exception(
                        'lottery_api: predicción automática falló (sorteo %s)', sorteo.name)
                    sorteo.write({'auto_prediction_error': '%s UTC: %s' % (
                        fields.Datetime.now(), mensaje)})
            else:
                if creada and sorteo.auto_prediction_error:
                    sorteo.write({'auto_prediction_error': False})
            self.env.cr.commit()

    def _auto_predecir_sorteo(self, sorteo):
        """Genera la predicción del próximo sorteo si corresponde y la deja
        completa (y publicada con su push si el sorteo lo pide). Devuelve la
        predicción creada, o None si todavía no toca o no hace falta."""
        tz = pytz.timezone(self.env.company.partner_id.tz or 'America/Montevideo')
        ahora = fields.Datetime.now()
        hoy = pytz.utc.localize(ahora).astimezone(tz).date()

        Output = self.env['lottery.output'].sudo()
        last = Output.search(
            [('sorteo_id', '=', sorteo.id)],
            order='date desc, turno_sequence desc, id desc', limit=1)
        # Solo salidas de hoy o ayer: una carga histórica no dispara nada.
        if not last or last.date < hoy - timedelta(days=1):
            return None

        espera = timedelta(minutes=sorteo.auto_prediction_delay or 0)
        if last.create_date > ahora - espera:
            return None

        # Las stats tienen que estar al día con esa salida: sin cola pendiente,
        # sin vistas por refrescar y con el ranking recalculado después de
        # registrarla (la predicción lee el ranking de Restantes).
        pendiente = ('lottery.stats.dirty' in self.env and self.env['lottery.stats.dirty']
                     .sudo().search_count([('sorteo_id', '=', sorteo.id)]))
        mv_sucia = self.env['ir.config_parameter'].sudo().get_param(MV_DIRTY_PARAM) == '1'
        ranking_ok = bool(sorteo.ranking_computed_at
                          and sorteo.ranking_computed_at >= last.create_date)
        if pendiente or mv_sucia or not ranking_ok:
            if last.create_date < ahora - espera - timedelta(minutes=MARGEN_RANKING_MIN):
                raise UserError(
                    'Las estadísticas del sorteo siguen sin actualizarse después de '
                    'registrada la última salida; no se generó la predicción.')
            return None

        fecha_str, turno = sorteo.get_next_draw()
        if not turno:
            return None
        fecha = fields.Date.to_date(fecha_str)
        # El próximo sorteo tiene que ser posterior a la última salida y
        # cercano a ella (el calendario del sorteo puede saltar domingos o
        # feriados: la noche del sábado el próximo es el lunes): si no, el
        # calendario está desfasado.
        if fecha > last.date + timedelta(days=7) or (fecha, turno.sequence) <= (
                last.date, last.turno_sequence):
            return None
        if self.search_count([('sorteo_id', '=', sorteo.id), ('date', '=', fecha),
                              ('turno_id', '=', turno.id)]):
            return None

        # El ranking se calculó con el próximo sorteo de ese momento; si
        # después se movió a mano (un feriado sin sorteo), no coincide con la
        # fecha que se va a predecir. Se recalcula una vez, ahora que ya se
        # sabe que toca generar.
        sorteo.compute_ranking_snapshot()

        numeros = self.numbers_by_temperature(sorteo, turno.code, 'remaining')
        if len(numeros) < 5:
            raise UserError(
                'El ranking de Restantes de %s (%s) trae menos de 5 números; no '
                'alcanza para armar las listas.' % (sorteo.name, turno.name))

        # Con la zona horaria de la empresa en el contexto: `hour` (hora de
        # publicación que muestra la app como "Hora de Uruguay") se calcula
        # con la zona del contexto y en un cron sería UTC.
        pred = self.with_context(tz=tz.zone).create({
            'sorteo_id': sorteo.id,
            'date': fecha,
            'turno_id': turno.id,
            'temperature': 'remaining',
            'number_ids': [(6, 0, numeros.ids)],
        })
        pred.algoritmo = pred._algoritmo_por_ultimas_salidas()
        pred.action_completar_numeros()
        if (len(pred.number_ids_20) != 20 or len(pred.number_ids_10) != 10
                or len(pred.number_ids_5) != 5 or not pred.super_magico_id):
            raise UserError(
                'Las listas de %s (%s) quedaron incompletas (20: %d, 10: %d, 5: %d, '
                'Súper Mágico: %s).' % (
                    sorteo.name, turno.name, len(pred.number_ids_20),
                    len(pred.number_ids_10), len(pred.number_ids_5),
                    'sí' if pred.super_magico_id else 'no'))

        if sorteo.auto_prediction_publish:
            pred.write({'published': True})
            if sorteo.show_in_app:
                pred.action_send_push_notification()
        return pred
