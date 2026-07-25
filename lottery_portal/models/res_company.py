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
        prefetch=False
    )
    facebook_page_url = fields.Char(
        string="URL Página de Facebook",
        help="Enlace a la página de Facebook (@LotoAnalisis) que aparece en la página pública.",
        prefetch=False
    )

    maintenance_mode = fields.Boolean(
        string="Modo mantenimiento",
        default=False,
        prefetch=False,
        help="Cuando está activo, los usuarios públicos ven la página de mantenimiento en lugar del portal.",
    )

    tabla_acompanantes_fecha_referencia = fields.Date(
        string="Tabla LotoAnálisis · fecha de referencia",
        prefetch=False,
        help="Fecha de corte que usa por defecto el wizard Tabla LotoAnálisis "
             "(Predicciones → Tabla LotoAnálisis). Como el resultado con una "
             "fecha ya pasada no cambia, sirve para tener una versión estable "
             "y volver a compararla más adelante (por ejemplo, la misma fecha "
             "dentro de 5 años). Vacío = usa la fecha de hoy.",
    )
