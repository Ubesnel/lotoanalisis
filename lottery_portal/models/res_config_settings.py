# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.addons.lottery_delays_number.models.lottery_output import (
    MV_DIRTY_PARAM, MV_LAST_REFRESH_PARAM,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    portal_calendar_year = fields.Integer(comodel_name='product.product', related='company_id.portal_calendar_year',
                                          string='Año', readonly=False)
    portal_calendar_month = fields.Selection(related='company_id.portal_calendar_month', string='Mes',
                                             readonly=False)

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
        return res

    def action_force_refresh_materialized_views(self):
        self.env['lottery.output'].action_force_refresh_materialized_views()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
