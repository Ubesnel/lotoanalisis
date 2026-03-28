# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.addons.lottery_base.models.utils import MONTHS


class ResCompany(models.Model):
    _inherit = "res.company"

    portal_calendar_year = fields.Integer(string="Año")
    portal_calendar_month = fields.Selection(selection=MONTHS, string="Mes")
