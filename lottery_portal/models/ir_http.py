# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request
from werkzeug.utils import redirect

_MAINTENANCE_PATH = '/mantenimiento'
_SKIP_PREFIXES = ('/web/', '/lottery/', '/salidas/', '/static/', '/favicon')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        try:
            path = request.httprequest.path
            if (
                request.httprequest.method == 'GET'
                and path != _MAINTENANCE_PATH
                and not any(path.startswith(p) for p in _SKIP_PREFIXES)
                and '/static/' not in path
            ):
                env = request.env
                if env.user._is_public():
                    company = env.company.sudo()
                    if company.maintenance_mode:
                        return redirect(_MAINTENANCE_PATH, 302)
        except Exception:
            pass
        return super()._dispatch(endpoint)
