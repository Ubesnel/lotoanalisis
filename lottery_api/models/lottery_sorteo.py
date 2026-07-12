# -*- coding: utf-8 -*-
from odoo import fields, models


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    show_in_app = fields.Boolean(
        string='Mostrar en apk LotoAnálisis',
        default=False,
        help="Si está activo, este sorteo aparece en el selector de sorteos "
             "de la app móvil LotoAnálisis y sus análisis quedan disponibles "
             "vía la API pública.",
    )
