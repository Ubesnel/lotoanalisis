# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.addons.lottery_base.models.utils import MONTHS


class ResCompany(models.Model):
    _inherit = "res.company"

    portal_calendar_year = fields.Integer(string="Año")
    portal_calendar_month = fields.Selection(selection=MONTHS, string="Mes")
