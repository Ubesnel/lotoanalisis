# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    portal_calendar_year = fields.Integer(comodel_name='product.product', related='company_id.portal_calendar_year',
                                          string='Año', readonly=False)
    portal_calendar_month = fields.Selection(related='company_id.portal_calendar_month', string='Mes',
                                             readonly=False)
