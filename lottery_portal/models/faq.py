# -*- coding: utf-8 -*-

from odoo import models, fields

class WebsiteFAQCategory(models.Model):
    _name = 'website.faq.category'
    _description = 'Categorías FAQ'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    icon = fields.Char(string='Ícono (Font Awesome)', default='fa-folder',
                       help='Clase de Font Awesome sin el prefijo "fa", ej: fa-users, fa-hourglass-half')


class WebsiteFAQ(models.Model):
    _name = 'website.faq'
    _description = 'FAQ del Sitio Web'
    _order = 'sequence, id'
    _rec_name = 'question'

    question = fields.Char(string='Pregunta', required=True)
    answer = fields.Text(string='Respuesta', required=True)
    sequence = fields.Integer(string='Secuencia')
    category_id = fields.Many2one('website.faq.category', string='Categoría', ondelete='cascade')
    active = fields.Boolean(string='Activo', default=True)
