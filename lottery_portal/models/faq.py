# -*- coding: utf-8 -*-

from odoo import models, fields

class WebsiteFAQCategory(models.Model):
    _name = 'website.faq.category'
    _description = 'Categorías FAQ'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)


class WebsiteFAQ(models.Model):
    _name = 'website.faq'
    _description = 'FAQ del Sitio Web'
    _order = 'sequence, id'
    _rec_name = 'question'

    question = fields.Char(string='Pregunta', required=True)
    answer = fields.Text(string='Respuesta', required=True)
    sequence = fields.Integer(string='Secuencia')
    category_id = fields.Many2one('website.faq.category', string='Categoría', required=True)
    active = fields.Boolean(string='Activo', default=True)
