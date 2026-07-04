# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.addons.lottery_base.models.utils import MONTHS


class ResCompany(models.Model):
    _inherit = "res.company"

    portal_calendar_year = fields.Integer(string="Año")
    portal_calendar_month = fields.Selection(selection=MONTHS, string="Mes")

    facebook_group_url = fields.Char(
        string="URL Grupo de Facebook",
        help="Enlace al grupo de Facebook que aparece en la página pública de búsqueda.",
    )
    facebook_page_url = fields.Char(
        string="URL Página de Facebook",
        help="Enlace a la página de Facebook (@LotoAnalisis) que aparece en la página pública.",
    )
