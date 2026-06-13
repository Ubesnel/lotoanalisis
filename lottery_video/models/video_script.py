# -*- coding: utf-8 -*-
from odoo import models, fields


class LotteryVideoScriptLine(models.Model):
    _name = 'lottery.video.script.line'
    _description = 'Línea de guión para video de lotería'
    _order = 'video_info_id, sequence'

    video_info_id = fields.Many2one(
        'lottery.video.info', string='Video', required=True, ondelete='cascade')
    sequence = fields.Integer(string='#', default=10)
    character = fields.Selection([
        ('valeria', 'Valeria'),
        ('mateo',   'Mateo'),
    ], string='Personaje', required=True, default='valeria')
    text = fields.Text(string='Texto', required=True)
