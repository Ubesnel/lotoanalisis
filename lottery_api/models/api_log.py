# -*- coding: utf-8 -*-
"""Registro liviano de consultas a la API pública de la app móvil.

Se escribe desde un único punto (`_json_response` en el controlador), así que
cubre todos los endpoints sin instrumentar cada método. Todo el registro va
envuelto en try/except para que un fallo al loguear NUNCA rompa la respuesta
de la API.

IMPORTANTE: adelante de Odoo hay un `proxy_cache` de nginx. Las respuestas
servidas desde ese cache no llegan a Odoo, por lo que este log solo ve el
tráfico de *cache-miss*. Sirve para tener una idea de IPs distintas, sorteos
consultados y errores, no para un conteo exacto de usuarios.
"""

from datetime import timedelta

from odoo import api, fields, models


class LotteryApiLog(models.Model):
    _name = 'lottery.api.log'
    _description = 'Registro de consultas a la API pública'
    _order = 'create_date desc'
    _rec_name = 'endpoint'

    endpoint = fields.Char(string='Endpoint', index=True)
    ip = fields.Char(string='IP', index=True)
    country_code = fields.Char(string='País (código)')
    country_name = fields.Char(string='País')
    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', ondelete='set null', index=True)
    status = fields.Integer(string='HTTP status')
    user_agent = fields.Char(string='User Agent')
    premium_access = fields.Selection([
        ('granted', 'Con pase'),
        ('locked', 'Bloqueado'),
    ], string='Acceso Premium', index=True,
        help='Solo en respuestas de contenido Premium.')
    pass_sent = fields.Boolean(string='Mandó pase')
    pass_id = fields.Many2one('lottery.premium.pass', string='Pase', ondelete='set null', index=True)
    device_id = fields.Char(string='ID de instalación', index=True)

    @api.model
    def _record(self, request, status, locked=None):
        """Registra una consulta. Silencioso: cualquier error se traga."""
        try:
            req = request.httprequest
            params = request.params or {}

            # Geoip best-effort (disponible si odoo-geoip está instalado).
            country_code = False
            country_name = False
            try:
                geoip = request.geoip
                if geoip:
                    country_code = geoip.get('country_code') or False
                    country_name = geoip.get('country_name') or False
            except Exception:
                pass

            # sorteo_id solo si viene y realmente existe (evita que un valor
            # inválido dispare un error de FK y se pierda toda la fila).
            sorteo_id = False
            raw = params.get('sorteo_id')
            if raw:
                try:
                    sid = int(raw)
                except (TypeError, ValueError):
                    sid = 0
                if sid and self.env['lottery.sorteo'].sudo().browse(sid).exists():
                    sorteo_id = sid

            token = req.headers.get('X-Premium-Pass')
            device = req.headers.get('X-Premium-Device') or False
            pase = self.env['lottery.premium.pass']
            if token:
                pase = pase.sudo()._from_token(token, device)

            self.sudo().create({
                'premium_access': (False if locked is None
                                   else 'locked' if locked else 'granted'),
                'pass_sent': bool(token),
                'pass_id': pase.id or False,
                'device_id': (device or '')[:64] or False,
                'endpoint': req.path,
                'ip': req.remote_addr,
                'country_code': country_code,
                'country_name': country_name,
                'sorteo_id': sorteo_id,
                'status': status,
                'user_agent': (req.user_agent.string or '')[:512],
            })
        except Exception:
            pass

    @api.model
    def _cleanup_old(self, days=3):
        """Elimina registros con más de `days` días. Lo llama el cron diario
        para que la tabla no crezca sin control."""
        limit = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([('create_date', '<', limit)]).unlink()
