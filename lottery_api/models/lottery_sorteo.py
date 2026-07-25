# -*- coding: utf-8 -*-
from odoo import fields, models


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    def _on_output_registered(self, draw_date, draw_turn):
        """Al registrarse una salida, la tabla configurada para "próximo
        sorteo" quedó desactualizada (era la predicción para el sorteo que
        recién salió) — se oculta la sección en la app hasta que se elija
        de nuevo para el siguiente sorteo."""
        super()._on_output_registered(draw_date, draw_turn)
        self.proximo_tabla_app = False

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
