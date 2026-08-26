# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.addons.lottery_delays_number.models.lottery_output import (
    MV_DIRTY_PARAM, MV_LAST_REFRESH_PARAM,
)

_TOMBOLA_STATS_START_PARAM = 'lottery_portal.tombola_stats_start_date'


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    portal_calendar_year = fields.Integer(comodel_name='product.product', related='company_id.portal_calendar_year',
                                          string='Año', readonly=False)
    portal_calendar_month = fields.Selection(related='company_id.portal_calendar_month', string='Mes',
                                             readonly=False)

    facebook_group_url = fields.Char(related='company_id.facebook_group_url', readonly=False,
                                     string='URL Grupo de Facebook')
    facebook_page_url = fields.Char(related='company_id.facebook_page_url', readonly=False,
                                    string='URL Página de Facebook')
    play_store_url = fields.Char(related='company_id.play_store_url', readonly=False,
                                 string='URL de la app en Google Play')

    maintenance_mode = fields.Boolean(related='company_id.maintenance_mode', readonly=False,
                                      string='Modo mantenimiento')

    tabla_acompanantes_fecha_referencia = fields.Date(
        related='company_id.tabla_acompanantes_fecha_referencia', readonly=False,
        string='Fecha de referencia')

    tombola_stats_start_date = fields.Date(
        string='Tómbola: estadísticas desde',
        help='Los sorteos de Tómbola anteriores a esta fecha se pueden '
             'seguir consultando, pero no se usan para calcular atrasos ni '
             'frecuencias (los primeros meses publicados, ago-dic 2006, '
             'tienen varios sorteos con un número repetido en vez de uno '
             'distinto). Vacío = usa todo el historial.')

    # ── Estado de las estadísticas (vistas materializadas) ────────────────
    # Campos simples (no computados): se poblan en get_values() en cada apertura
    # de Ajustes leyendo directo de la BD, evitando el ormcache por proceso de
    # ir.config_parameter (el flag lo actualiza el worker de cron, otro proceso).
    lottery_stats_up_to_date = fields.Boolean(string='Estadísticas actualizadas')
    lottery_stats_last_refresh = fields.Datetime(string='Último refresh de estadísticas')

    @api.model
    def get_values(self):
        res = super().get_values()
        self.env.cr.execute(
            "SELECT key, value FROM ir_config_parameter WHERE key IN %s",
            ((MV_DIRTY_PARAM, MV_LAST_REFRESH_PARAM),))
        params = dict(self.env.cr.fetchall())
        res.update(
            lottery_stats_up_to_date=params.get(MV_DIRTY_PARAM) != '1',
            lottery_stats_last_refresh=params.get(MV_LAST_REFRESH_PARAM) or False,
        )
        val = self.env['ir.config_parameter'].sudo().get_param(_TOMBOLA_STATS_START_PARAM)
        res['tombola_stats_start_date'] = fields.Date.from_string(val) if val else False
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            _TOMBOLA_STATS_START_PARAM,
            self.tombola_stats_start_date.isoformat() if self.tombola_stats_start_date else '',
        )

    def action_force_refresh_materialized_views(self):
        self.env['lottery.output'].action_force_refresh_materialized_views()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
