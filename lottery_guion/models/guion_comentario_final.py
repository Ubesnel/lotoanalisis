# -*- coding: utf-8 -*-
from odoo import models, fields

from .guion_comentario import PERSONAJE


class LotteryGuionComentarioFinal(models.Model):
    _name = 'lottery.guion.comentario.final'
    _description = 'Comentario final de guión de lotería'
    _order = 'sequence'
    _rec_name = 'comentario'

    sequence = fields.Integer(string='Secuencia', default=10)
    personaje = fields.Selection(
        PERSONAJE, string='Personaje', required=True, default='valeria')
    comentario = fields.Text(string='Comentario', required=True)
