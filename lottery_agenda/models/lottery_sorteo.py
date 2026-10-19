# -*- coding: utf-8 -*-
from odoo import fields, models


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    agenda_enabled = fields.Boolean(
        string='Crear tareas en el calendario',
        default=False,
        help="Cada día se crea en el calendario un evento por turno de este "
             "sorteo, a la hora de publicar que figura en su calendario "
             "(días y turnos). Se marca solo como hecho al registrar la salida.",
    )
