# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    lottery_api_proximo_tabla = fields.Selection(
        [
            ('', 'Sin tabla (ocultar sección)'),
            ('calientes', 'Calientes'),
            ('restantes', 'Restantes'),
            ('frios', 'Fríos'),
        ],
        string='Tabla del Próximo Sorteo (app móvil)',
        default='restantes',
        config_parameter='lottery_api.proximo_sorteo_tabla',
        help="Qué ranking del snapshot se envía a la app LotoAnálisis en la "
             "vista Próximo Sorteo (mejores números por líneas). Dejarlo vacío "
             "oculta la sección en la app mientras evaluás cuál tabla mostrar.",
    )
