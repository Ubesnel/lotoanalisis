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
    proximo_tabla_app = fields.Selection(
        [
            ('calientes', 'Calientes'),
            ('restantes', 'Restantes'),
            ('frios', 'Fríos'),
        ],
        string='Tabla del Próximo Sorteo (app móvil)',
        default='restantes',
        help="Ranking que la app muestra en 'Próximo Sorteo · Mejores números "
             "por líneas' para este sorteo: Calientes, Restantes o Fríos. "
             "Cada sorteo puede mostrar una tabla distinta. "
             "Dejarlo vacío oculta la sección en la app.",
    )
