# -*- coding: utf-8 -*-
from odoo import models, fields, api

from .guion_comentario import PERSONAJE


class LotteryGuionIntroLine(models.Model):
    _name = 'lottery.guion.intro.line'
    _description = 'Línea de introducción de guión de lotería'
    _order = 'guion_id, sequence'

    guion_id = fields.Many2one(
        'lottery.guion', string='Guión', required=True, ondelete='cascade')
    sequence = fields.Integer(string='#', default=10)
    personaje = fields.Selection(
        PERSONAJE, string='Personaje', required=True, default='valeria')
    comentario_id = fields.Many2one(
        'lottery.guion.comentario.intro', string='Comentario')
    texto_final = fields.Text(string='Texto Final')

    @api.onchange('comentario_id')
    def _onchange_comentario_id(self):
        for line in self:
            if line.comentario_id:
                line.texto_final = line.comentario_id.comentario
                line.personaje = line.comentario_id.personaje
