# -*- coding: utf-8 -*-
from odoo import models, fields

TIPO_GUION = [
    ('estadisticas_generales', 'Estadísticas Generales'),
    ('estadisticas_tarde', 'Estadísticas Tarde'),
    ('estadisticas_noche', 'Estadísticas Noche'),
    ('grupos_atrasados_general', 'Grupos Atrasados General'),
    ('grupos_atrasados_tarde', 'Grupos Atrasados Tarde'),
    ('grupos_atrasados_noche', 'Grupos Atrasados Noche'),
    ('informacion_caliente', 'Información Caliente'),
]

PERSONAJE = [
    ('valeria', 'Valeria'),
    ('mateo', 'Mateo'),
]


class LotteryGuionComentario(models.Model):
    _name = 'lottery.guion.comentario'
    _description = 'Comentario de guión de lotería'
    _order = 'tipo_guion, sequence'
    _rec_name = 'comentario'

    sequence = fields.Integer(string='Secuencia', default=10)
    tipo_guion = fields.Selection(
        TIPO_GUION, string='Tipo de Guión', required=True)
    personaje = fields.Selection(
        PERSONAJE, string='Personaje', required=True, default='valeria')
    comentario = fields.Text(string='Comentario', required=True)
