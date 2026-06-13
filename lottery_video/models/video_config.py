# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryVideoConfig(models.Model):
    _name = 'lottery.video.config'
    _description = 'Configuración de personajes para videos de lotería'

    name = fields.Char(default='Configuración Principal', required=True)

    mateo_image = fields.Binary(string='Imagen Mateo', attachment=False)
    mateo_image_filename = fields.Char()
    valeria_image = fields.Binary(string='Imagen Valeria', attachment=False)
    valeria_image_filename = fields.Char()

    video_width = fields.Integer(string='Ancho (px)', default=1080)
    video_height = fields.Integer(string='Alto (px)', default=1920)
    video_fps = fields.Integer(string='FPS', default=24)
    bg_color_hex = fields.Char(string='Color de fondo', default='#0d1b2a')
    accent_color_hex = fields.Char(string='Color acento', default='#f5c518')

    @api.model
    def _get_config(self):
        cfg = self.sudo().search([], limit=1)
        if not cfg:
            cfg = self.sudo().create({'name': 'Configuración Principal'})
        return cfg
