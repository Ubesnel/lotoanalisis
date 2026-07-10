# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request
from werkzeug.utils import redirect

_MAINTENANCE_PATH = '/mantenimiento'
# /api/ queda fuera del modo mantenimiento: la app móvil debe seguir
# funcionando aunque el sitio web esté en mantenimiento.
_SKIP_PREFIXES = ('/web/', '/lottery/', '/salidas/', '/static/', '/favicon',
                  '/api/')
# Páginas legales siempre accesibles aun en mantenimiento: Google Play
# verifica la política de privacidad en cualquier momento.
_LEGAL_PATHS = ('/politica-privacidad', '/terminos-condiciones')

# Páginas del portal que se rastrean
_TRACK_PREFIXES = (
    '/inicio', '/estadisticas', '/estadisticas-generales', '/estadisticas-pintas',
    '/estadisticas-numeros', '/grupos-por-dia', '/faq', '/noticias', '/buscador',
    '/politica-privacidad', '/terminos-condiciones', '/contactus',
)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        try:
            path = request.httprequest.path
            skip = (
                path == _MAINTENANCE_PATH
                or any(path.startswith(p) for p in _SKIP_PREFIXES)
                or '/static/' in path
            )
            if request.httprequest.method == 'GET' and not skip:
                env = request.env
                if env.user._is_public() and path not in _LEGAL_PATHS:
                    company = env.company.sudo()
                    if company.maintenance_mode:
                        return redirect(_MAINTENANCE_PATH, 302)

                # Registrar visita si la URL es una página rastreable
                if path == '/' or any(path == p or path.startswith(p + '/') for p in _TRACK_PREFIXES):
                    env['lottery.page.visit']._record_visit(request)
        except Exception:
            pass
        return super()._dispatch(endpoint)
