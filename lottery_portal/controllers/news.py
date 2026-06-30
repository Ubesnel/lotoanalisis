# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from datetime import datetime

from .portal import _resolve_sorteo_id


class NewsController(http.Controller):

    ARTICLES_PER_PAGE = 12

    def _resolve_sorteo_id(self, sorteo_id):
        return _resolve_sorteo_id(sorteo_id)

    @http.route('/', type='http', auth='public', website=True)
    def news_homepage(self, page=1, category=None, q=None, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        Article = request.env['news.article'].sudo()
        Category = request.env['news.category'].sudo()
        stats = request.env['lottery.stats.service'].sudo()

        categories = Category.search([('active', '=', True)])
        domain = [('is_published', '=', True)]
        active_category = None
        search_query = (q or '').strip()

        if category:
            cat = Category.search([('slug', '=', category)], limit=1)
            if cat:
                domain.append(('category_id', '=', cat.id))
                active_category = cat

        if search_query:
            domain += ['|', '|', '|',
                ('title',    'ilike', search_query),
                ('summary',  'ilike', search_query),
                ('tags',     'ilike', search_query),
                ('raw_html', 'ilike', search_query),
            ]

        total = Article.search_count(domain)
        page = max(1, int(page))
        offset = (page - 1) * self.ARTICLES_PER_PAGE

        articles = Article.search(domain, limit=self.ARTICLES_PER_PAGE, offset=offset,
                                  order='publish_date desc, id desc')

        total_pages = max(1, (total + self.ARTICLES_PER_PAGE - 1) // self.ARTICLES_PER_PAGE)
        page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))

        return request.render('lottery_portal.news_homepage', {
            'articles':        articles,
            'categories':      categories,
            'active_category': active_category,
            'page':            page,
            'total_pages':     total_pages,
            'page_range':      page_range,
            'total':           total,
            'category_slug':   category or '',
            'search_query':    search_query,
            'lottery_data':    stats.get_last_results_full(sorteo_id=sorteo_id),
            'hero_stats':      stats.get_hero_stats(sorteo_id=sorteo_id),
        })

    @http.route('/noticias/buscar', type='json', auth='public', website=True)
    def news_search_ajax(self, q='', **kwargs):
        """Live-search: returns up to 6 article suggestions for the autocomplete."""
        q = (q or '').strip()
        if len(q) < 2:
            return []
        Article = request.env['news.article'].sudo()
        domain = [
            ('is_published', '=', True),
            '|', '|',
            ('title',   'ilike', q),
            ('summary', 'ilike', q),
            ('tags',    'ilike', q),
        ]
        results = Article.search(domain, limit=6, order='publish_date desc')
        return [
            {
                'title': a.title,
                'slug':  a.slug,
                'cat':   a.category_id.name if a.category_id else '',
                'date':  a.publish_date.strftime('%d/%m/%Y') if a.publish_date else '',
            }
            for a in results
        ]

    @http.route('/noticias/<string:slug>', type='http', auth='public', website=True)
    def news_article(self, slug, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        Article = request.env['news.article'].sudo()
        article = Article.search([('slug', '=', slug), ('is_published', '=', True)], limit=1)
        if not article:
            return request.not_found()

        article.increment_views()

        related = Article.search([
            ('is_published', '=', True),
            ('id', '!=', article.id),
            ('category_id', '=', article.category_id.id),
        ], limit=3, order='publish_date desc') if article.category_id else Article

        comments = article.comment_ids.filtered('is_approved').sorted('create_date')
        top_comments = comments.filtered(lambda c: not c.parent_id)
        stats = request.env['lottery.stats.service'].sudo()

        return request.render('lottery_portal.news_article_page', {
            'article': article,
            'related': related,
            'top_comments': top_comments,
            'comment_count': len(comments),
            'comment_submitted': kwargs.get('comment_submitted', False),
            'comment_error': kwargs.get('comment_error', ''),
            'my_comments': request.session.get('my_comments', []),
            'lottery_data': stats.get_last_results_full(sorteo_id=sorteo_id),
        })

    @http.route('/noticias/<string:slug>/comentar', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def news_submit_comment(self, slug, **post):
        Article = request.env['news.article'].sudo()
        article = Article.search([('slug', '=', slug), ('is_published', '=', True)], limit=1)
        if not article or not article.allow_comments:
            return request.not_found()

        name = (post.get('author_name') or '').strip()
        email = (post.get('author_email') or '').strip()
        content = (post.get('content') or '').strip()
        parent_id = int(post.get('parent_id') or 0)

        errors = []
        if not name:
            errors.append('El nombre es requerido.')
        if not email or '@' not in email:
            errors.append('Introduce un correo válido.')
        if not content or len(content) < 5:
            errors.append('El comentario es muy corto.')
        if len(content) > 2000:
            errors.append('El comentario no puede superar 2000 caracteres.')

        if errors:
            return request.redirect(f'/noticias/{slug}?comment_error={errors[0]}')

        vals = {
            'article_id': article.id,
            'author_name': name[:100],
            'author_email': email[:200],
            'content': content[:2000],
            'ip_address': request.httprequest.remote_addr,
        }
        if parent_id:
            parent = request.env['news.comment'].sudo().search(
                [('id', '=', parent_id), ('article_id', '=', article.id)], limit=1)
            if parent:
                vals['parent_id'] = parent.id

        comment = request.env['news.comment'].sudo().create(vals)
        owned = list(request.session.get('my_comments', []))
        owned.append(comment.id)
        request.session['my_comments'] = owned
        return request.redirect(f'/noticias/{slug}?comment_submitted=1#comentarios')

    @http.route('/noticias/<string:slug>/comentario/<int:cid>/editar',
                type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def news_edit_comment(self, slug, cid, **post):
        owned = request.session.get('my_comments', [])
        if cid not in owned:
            return request.redirect(f'/noticias/{slug}#comentarios')
        comment = request.env['news.comment'].sudo().search(
            [('id', '=', cid)], limit=1)
        if not comment:
            return request.redirect(f'/noticias/{slug}#comentarios')
        content = (post.get('content') or '').strip()
        if content and 5 <= len(content) <= 2000:
            comment.write({'content': content, 'is_approved': False})
        return request.redirect(f'/noticias/{slug}?comment_submitted=1#comentarios')

    @http.route('/noticias/<string:slug>/comentario/<int:cid>/eliminar',
                type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def news_delete_comment(self, slug, cid, **post):
        owned = list(request.session.get('my_comments', []))
        if cid not in owned:
            return request.redirect(f'/noticias/{slug}#comentarios')
        comment = request.env['news.comment'].sudo().search(
            [('id', '=', cid)], limit=1)
        if comment:
            comment.unlink()
            owned = [x for x in owned if x != cid]
            request.session['my_comments'] = owned
        return request.redirect(f'/noticias/{slug}#comentarios')

    @http.route('/noticias/categoria/<string:slug>', type='http', auth='public', website=True)
    def news_by_category(self, slug, page=1, **kwargs):
        return request.redirect(f'/?category={slug}&page={page}')
