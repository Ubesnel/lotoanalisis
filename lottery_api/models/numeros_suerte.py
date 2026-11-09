# -*- coding: utf-8 -*-
"""Números de la Suerte en la app (Premium): un pronóstico del día completo,
igual para todos los sorteos. El sorteo del registro es solo la referencia
del cálculo; a la app viajan los de la lista "5 Números" del publicado del
día vigente, que empieza a la hora configurada en Ajustes."""

import logging
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .fcm_service import lang_topic, lanzar_push, PUSH_LANGS
from .push_announcement import ANNOUNCEMENTS_TOPIC, _push_announcement_worker

_logger = logging.getLogger(__name__)


class LotteryNumerosSuerte(models.Model):
    _inherit = 'lottery.numeros.suerte'

    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='La app muestra los 5 Números del publicado de hoy. Solo puede '
             'haber uno publicado por fecha.')
    published_date = fields.Datetime(string='Publicada el', readonly=True, copy=False)
    push_sent = fields.Boolean(string='Notificación enviada', readonly=True, copy=False)
    push_sent_date = fields.Datetime(string='Fecha de envío', readonly=True, copy=False)

    @api.constrains('published', 'date')
    def _check_un_publicado_por_fecha(self):
        for rec in self.filtered('published'):
            if self.search_count([('date', '=', rec.date), ('published', '=', True),
                                  ('id', '!=', rec.id)]):
                raise ValidationError(
                    'Ya hay unos Números de la Suerte publicados para el %s.'
                    % rec.date.strftime('%d/%m/%Y'))

    def write(self, vals):
        recien_publicadas = self.browse()
        if vals.get('published'):
            recien_publicadas = self.filtered(lambda r: not r.published)
        res = super().write(vals)
        if recien_publicadas:
            recien_publicadas.write({'published_date': fields.Datetime.now()})
        return res

    def action_send_push_notification(self):
        self.ensure_one()
        if self.push_sent:
            raise UserError('Ya se envió la notificación de estos Números de la Suerte.')
        if not self.published:
            raise UserError('Estos Números de la Suerte todavía no están publicados.')
        # Aviso a todos (topic de anuncios): son iguales para todas las loterías.
        dia = self.date.strftime('%d/%m/%Y')
        envios = []
        for lang in PUSH_LANGS:
            if lang == 'en':
                title = f'🍀 Lucky Numbers for {dia}'
                body = ("Today's Premium Lucky Numbers are now in the App, "
                        'for every lottery of the day.')
            else:
                title = f'🍀 Números de la Suerte del {dia}'
                body = ('Ya están en la App los Números de la Suerte Premium de hoy, '
                        'para todas las loterías del día.')
            envios.append(('topic', lang_topic(ANNOUNCEMENTS_TOPIC, lang), title, body))
        lanzar_push(self.env.cr, _push_announcement_worker, (self.env.cr.dbname, envios))
        self.write({'push_sent': True, 'push_sent_date': fields.Datetime.now()})

    @api.model
    def _fecha_vigente(self):
        """Día de los Números de la Suerte: hasta la hora de Ajustes (hora de
        Uruguay) sigue siendo el anterior, así entran los sorteos de la
        madrugada (Georgia a la 1)."""
        params = self.env['ir.config_parameter'].sudo()
        hora = float(params.get_param('lottery_api.suerte_hora') or 6.0)
        tz = pytz.timezone(self.env.company.partner_id.tz or 'America/Montevideo')
        ahora = datetime.now(tz)
        return (ahora - timedelta(hours=hora)).date()

    @api.model
    def _cron_generar_del_dia(self):
        """Genera los del día vigente si todavía no hay ninguno para esa
        fecha (uno cargado a mano no se toca) y los publica si Ajustes lo pide."""
        params = self.env['ir.config_parameter'].sudo()
        fecha = self._fecha_vigente()
        if self.sudo().search_count([('date', '=', fecha)]):
            return
        sorteo = self.env['lottery.sorteo'].sudo().browse(
            int(params.get_param('lottery_api.suerte_sorteo_id') or 0)).exists()
        sorteo = sorteo or self.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)
        if not sorteo:
            return
        try:
            with self.env.cr.savepoint():
                rec = self.sudo().create({
                    'sorteo_id': sorteo.id,
                    'date': fecha,
                    'temperature': params.get_param('lottery_api.suerte_temperature') or 'remaining',
                })
                rec.action_cargar_candidatos()
                rec.action_calcular()
                if params.get_param('lottery_api.suerte_publicar') in ('True', '1'):
                    rec.published = True
        except Exception:  # noqa: BLE001 - se reintenta en la próxima corrida
            _logger.exception('lottery_api: no se pudieron generar los Números de la Suerte del %s', fecha)
