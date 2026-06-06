# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import unicodedata


def slugify(text):
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)


class NewsCategory(models.Model):
    _name = 'news.category'
    _description = 'Categoría de Noticias'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True)
    slug = fields.Char(string='URL amigable', required=True, copy=False)
    description = fields.Text(string='Descripción')
    color = fields.Char(string='Color (hex)', default='#6f4a8e', help='Color hexadecimal, ej: #6f4a8e')
    icon = fields.Char(string='Ícono Font Awesome', default='fa-tag', help='ej: fa-chart-bar, fa-newspaper-o')
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
    article_ids = fields.One2many('news.article', 'category_id', string='Artículos')
    article_count = fields.Integer(string='Artículos publicados', compute='_compute_article_count')

    @api.depends('article_ids')
    def _compute_article_count(self):
        for rec in self:
            rec.article_count = len(rec.article_ids.filtered('is_published'))

    @api.constrains('slug')
    def _check_slug_unique(self):
        for rec in self:
            domain = [('slug', '=', rec.slug), ('id', '!=', rec.id)]
            if self.search_count(domain):
                raise ValidationError('El URL amigable ya está en uso. Elige otro.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('slug') and vals.get('name'):
                vals['slug'] = slugify(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and not vals.get('slug'):
            vals['slug'] = slugify(vals['name'])
        return super().write(vals)


class NewsArticle(models.Model):
    _name = 'news.article'
    _description = 'Artículo de Noticias'
    _order = 'publish_date desc, id desc'
    _rec_name = 'title'

    title = fields.Char(string='Título', required=True)
    slug = fields.Char(string='URL amigable', required=True, copy=False)
    summary = fields.Text(string='Resumen', help='Texto corto que aparece en la tarjeta del artículo')
    raw_html = fields.Text(string="HTML crudo")
    content = fields.Html(string='Contenido', sanitize=False, compute="_compute_content_html")
    cover_image = fields.Binary(string='Imagen de portada', attachment=True)
    cover_image_filename = fields.Char(string='Nombre imagen')
    cover_image_alt = fields.Char(string='Texto alternativo imagen')
    category_id = fields.Many2one('news.category', string='Categoría', ondelete='restrict')

    # ── Calientes ─────────────────────────────────────────────────────────
    is_calientes_article = fields.Boolean(
        string='Es artículo de calientes', default=False,
        help='Activa la ficha de selección manual y el botón Actualizar datos.')

    hot_number_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_num_tarde_rel', 'article_id', 'number_id',
        string='Números calientes · Tarde')
    hot_number_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_num_noche_rel', 'article_id', 'number_id',
        string='Números calientes · Noche')
    hot_centena_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_cen_tarde_rel', 'article_id', 'number_id',
        string='Centenas calientes · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    hot_centena_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_cen_noche_rel', 'article_id', 'number_id',
        string='Centenas calientes · Noche',
        domain=[('can_use_hundreds', '=', True)])
    hot_extra_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_ext_tarde_rel', 'article_id', 'number_id',
        string='Bola extra caliente · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    hot_extra_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_hot_ext_noche_rel', 'article_id', 'number_id',
        string='Bola extra caliente · Noche',
        domain=[('can_use_hundreds', '=', True)])

    # ── Fríos ──────────────────────────────────────────────────────────────
    cold_number_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_num_tarde_rel', 'article_id', 'number_id',
        string='Números fríos · Tarde')
    cold_number_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_num_noche_rel', 'article_id', 'number_id',
        string='Números fríos · Noche')
    cold_centena_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_cen_tarde_rel', 'article_id', 'number_id',
        string='Centenas frías · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    cold_centena_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_cen_noche_rel', 'article_id', 'number_id',
        string='Centenas frías · Noche',
        domain=[('can_use_hundreds', '=', True)])
    cold_extra_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_ext_tarde_rel', 'article_id', 'number_id',
        string='Bola extra fría · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    cold_extra_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_cold_ext_noche_rel', 'article_id', 'number_id',
        string='Bola extra fría · Noche',
        domain=[('can_use_hundreds', '=', True)])

    # ── Restantes ──────────────────────────────────────────────────────────
    rem_number_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_num_tarde_rel', 'article_id', 'number_id',
        string='Números restantes · Tarde')
    rem_number_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_num_noche_rel', 'article_id', 'number_id',
        string='Números restantes · Noche')
    rem_centena_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_cen_tarde_rel', 'article_id', 'number_id',
        string='Centenas restantes · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    rem_centena_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_cen_noche_rel', 'article_id', 'number_id',
        string='Centenas restantes · Noche',
        domain=[('can_use_hundreds', '=', True)])
    rem_extra_tarde_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_ext_tarde_rel', 'article_id', 'number_id',
        string='Bola extra restante · Tarde',
        domain=[('can_use_hundreds', '=', True)])
    rem_extra_noche_ids = fields.Many2many(
        'lottery.number', 'news_article_rem_ext_noche_rel', 'article_id', 'number_id',
        string='Bola extra restante · Noche',
        domain=[('can_use_hundreds', '=', True)])

    # ── Intercambio ────────────────────────────────────────────────────────
    swap_selection = fields.Selection([
        ('hot_rem',  'Calientes ↔ Restantes'),
        ('hot_cold', 'Calientes ↔ Fríos'),
        ('rem_cold', 'Restantes ↔ Fríos'),
    ], string='Intercambiar', help='Selecciona la combinación y pulsa "Intercambiar números"')

    author_id = fields.Many2one('res.users', string='Autor', default=lambda self: self.env.user)
    author_name = fields.Char(string='Nombre autor visible', help='Si vacío, se usa el nombre del usuario')
    publish_date = fields.Datetime(string='Fecha de publicación', default=fields.Datetime.now)
    is_published = fields.Boolean(string='Publicado', default=False)
    is_featured = fields.Boolean(string='Destacado', default=False, help='Aparece como artículo principal en el inicio')
    allow_comments = fields.Boolean(string='Permitir comentarios', default=True)
    views_count = fields.Integer(string='Visitas', default=0, readonly=True)
    comment_ids = fields.One2many('news.comment', 'article_id', string='Comentarios')
    comment_count = fields.Integer(string='Comentarios aprobados', compute='_compute_comment_count')
    meta_title = fields.Char(string='Meta título SEO')
    meta_description = fields.Text(string='Meta descripción SEO')
    tags = fields.Char(string='Etiquetas', help='Separadas por coma')

    @api.depends('comment_ids')
    def _compute_comment_count(self):
        for rec in self:
            rec.comment_count = len(rec.comment_ids.filtered('is_approved'))

    @api.constrains('slug')
    def _check_slug_unique(self):
        for rec in self:
            domain = [('slug', '=', rec.slug), ('id', '!=', rec.id)]
            if self.search_count(domain):
                raise ValidationError('El URL amigable ya está en uso. Elige otro.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('slug') and vals.get('title'):
                vals['slug'] = slugify(vals['title'])
        return super().create(vals_list)

    def write(self, vals):
        if 'title' in vals and not vals.get('slug'):
            vals['slug'] = slugify(vals['title'])
        return super().write(vals)

    def action_publish(self):
        self.write({'is_published': True})

    def action_unpublish(self):
        self.write({'is_published': False})

    def get_author_display(self):
        return self.author_name or (self.author_id.name if self.author_id else 'Redacción')

    def get_cover_url(self):
        if self.cover_image:
            return f'/web/image/news.article/{self.id}/cover_image'
        return '/lottery_portal/static/src/img/news_placeholder.svg'

    def increment_views(self):
        self.sudo().write({'views_count': self.views_count + 1})

    def action_view_comments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Comentarios: {self.title}',
            'res_model': 'news.comment',
            'view_mode': 'tree,form',
            'domain': [('article_id', '=', self.id)],
            'context': {'default_article_id': self.id},
        }

    @api.depends('raw_html')
    def _compute_content_html(self):
        for rec in self:
            rec.content = rec.raw_html or ''


class NewsComment(models.Model):
    _name = 'news.comment'
    _description = 'Comentario de Artículo'
    _order = 'create_date asc'
    _rec_name = 'author_name'

    article_id = fields.Many2one('news.article', string='Artículo', required=True, ondelete='cascade')
    author_name = fields.Char(string='Nombre', required=True)
    author_email = fields.Char(string='Correo electrónico', required=True)
    content = fields.Text(string='Comentario', required=True)
    is_approved = fields.Boolean(string='Aprobado', default=False)
    parent_id = fields.Many2one('news.comment', string='Respuesta a', ondelete='cascade')
    reply_ids = fields.One2many('news.comment', 'parent_id', string='Respuestas')
    create_date = fields.Datetime(string='Fecha', readonly=True)
    ip_address = fields.Char(string='IP', readonly=True)
