# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryPageVisit(models.Model):
    _name = 'lottery.page.visit'
    _description = 'Visita a página del portal'
    _order = 'visit_date desc'
    _rec_name = 'url'

    url = fields.Char(string='URL', index=True)
    ip = fields.Char(string='IP')
    user_agent = fields.Char(string='User Agent')
    referrer = fields.Char(string='Referrer')
    visit_date = fields.Datetime(string='Fecha y hora', default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', string='Usuario', ondelete='set null')
    is_authenticated = fields.Boolean(string='Autenticado')
    country_code = fields.Char(string='País (código)')
    country_name = fields.Char(string='País')
    session_id = fields.Char(string='Sesión')
    method = fields.Char(string='Método HTTP')
    language = fields.Char(string='Idioma (Accept-Language)')

    @api.model
    def _record_visit(self, request):
        try:
            req = request.httprequest
            env = request.env

            is_auth = not env.user._is_public()
            user_id = env.user.id if is_auth else False

            # Geoip (disponible si odoo-geoip está instalado)
            country_code = False
            country_name = False
            try:
                geoip = request.geoip
                if geoip:
                    country_code = geoip.get('country_code') or False
                    country_name = geoip.get('country_name') or False
            except Exception:
                pass

            env['lottery.page.visit'].sudo().create({
                'url': req.path,
                'ip': req.remote_addr,
                'user_agent': (req.user_agent.string or '')[:512],
                'referrer': (req.referrer or '')[:512],
                'method': req.method,
                'language': (req.headers.get('Accept-Language') or '')[:128],
                'is_authenticated': is_auth,
                'user_id': user_id,
                'country_code': country_code,
                'country_name': country_name,
                'session_id': (request.session.sid or '')[:64],
            })
        except Exception:
            pass
