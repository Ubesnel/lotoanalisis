# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

_DIAS = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}


def _resolve_sorteo_id(sorteo_id):
    """Resuelve el sorteo_id recibido desde el frontend, usando Florida como
    default mientras el selector no envíe un valor explícito."""
    return int(sorteo_id) if sorteo_id else request.env.ref('lottery_base.sorteo_florida').id


def _salida_dict(r):
    """Una salida con la forma que dibuja el buscador público."""
    return {
        'id': r.id,
        'fecha': r.date.strftime('%d/%m'),
        # Para precargar el input de fecha del buscador (YYYY-MM-DD).
        'fecha_iso': r.date.isoformat(),
        'dia_semana': _DIAS[r.date.weekday()],
        'turno': r.turno_id.code,
        'turno_label': r.turno_id.name or '',
        'centena': r.hundreds_id.name if r.hundreds_id else '-',
        'numero': str(r.number_id.name).zfill(2),
        'bola_extra': r.fireball_id.name if r.fireball_id else "-",
        'premio_2': str(r.premio_2_id.name).zfill(2) if r.premio_2_id else None,
        'premio_3': str(r.premio_3_id.name).zfill(2) if r.premio_3_id else None,
    }


class LotteryPortal(http.Controller):
    """Sitio web público: portada con el buscador de salidas, FAQ, páginas
    legales y mantenimiento. Las estadísticas viven en la app (lottery_api)."""

    @http.route('/', type='http', auth='public', website=True)
    def buscador_publico_page(self, **kwargs):
        company = request.env.company.sudo()
        sorteos = request.env['lottery.sorteo'].sudo().search(
            [('show_in_public', '=', True)], order='sequence, id')
        # Franja de Rifazo: sin depender del módulo, solo si está instalado y
        # tiene una versión de la APK publicada.
        rifazo_release = False
        if 'rifazo.app.release' in request.env:
            rifazo_release = request.env['rifazo.app.release']._get_current()
        return request.render('lottery_portal.buscador_publico_page', {
            'facebook_group_url': company.facebook_group_url or '',
            'facebook_page_url': company.facebook_page_url or '',
            'play_store_url': company.play_store_url or '',
            'sorteos_publicos': sorteos,
            'rifazo_release': rifazo_release,
        })

    @http.route('/lottery/sorteos-publicos', type='json', auth='public', website=True)
    def get_sorteos_publicos(self, **kwargs):
        sorteos = request.env['lottery.sorteo'].sudo().search(
            [('show_in_public', '=', True)], order='sequence, id')
        # Pick3 Florida por defecto si es público; si no, el primero por orden.
        florida = request.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)
        default = florida if florida and florida in sorteos else (sorteos[0] if sorteos else None)
        return {
            'sorteos': [{'id': s.id, 'name': s.name, 'code': s.code} for s in sorteos],
            'default_id': default.id if default else False,
        }

    @http.route('/salidas/buscar', type='json', auth='public')
    def buscar_salidas(self, fecha, sorteo_id=False):
        """Salidas del sorteo en esa fecha, una por turno, en orden del día."""
        sorteo_id = _resolve_sorteo_id(sorteo_id)
        if not fecha:
            return []
        salidas = request.env['lottery.output'].sudo().search(
            [('date', '=', fecha), ('sorteo_id', '=', sorteo_id)],
            order='turno_sequence, id')
        return [_salida_dict(r) for r in salidas]

    @http.route('/salidas/ultimas', type='json', auth='public')
    def ultimas_salidas(self, sorteo_id=False, limit=2):
        """Últimas salidas registradas del sorteo (por defecto las 2 más
        recientes). Las muestra el buscador de la portada antes de que se
        elija una fecha."""
        sorteo_id = _resolve_sorteo_id(sorteo_id)
        limit = min(int(limit), 10) if str(limit).isdigit() else 2
        salidas = request.env['lottery.output'].sudo().search(
            [('sorteo_id', '=', sorteo_id)], limit=limit)
        # Se buscan las más recientes, pero se muestran en orden cronológico
        # (la más vieja arriba).
        return [_salida_dict(r) for r in reversed(salidas)]

    @http.route('/mantenimiento', type='http', auth='public', website=True)
    def maintenance_page(self, **kwargs):
        return request.render('lottery_portal.maintenance_page')

    @http.route(['/faq'], type='http', auth="user", website=True)
    def faq_page(self, **kwargs):
        return request.render('lottery_portal.faq_page')

    @http.route('/faq/data', type='json', auth='public', website=True)
    def faq_data(self):
        categories = request.env['website.faq.category'].sudo().search([])
        faqs = request.env['website.faq'].sudo().search([('active', '=', True)])

        return {
            'categories': categories.read(['name', 'icon']),
            'faqs': faqs.read(['question', 'answer', 'category_id'])
        }

    # Páginas legales públicas: Google Play exige que la política de
    # privacidad sea accesible sin iniciar sesión.
    @http.route(['/terminos-condiciones'], type='http', auth="public", website=True)
    def terminos_condiciones_page(self, **kwargs):
        return request.render('lottery_portal.terminos_condiciones_page')

    @http.route(['/politica-privacidad'], type='http', auth="public", website=True)
    def politica_privacidad_page(self, **kwargs):
        return request.render('lottery_portal.politica_privacidad_page')

    # app-ads.txt para AdMob: se sirve en la raíz del dominio declarado como
    # "Sitio web" en la ficha de Google Play. AdMob lo rastrea para verificar
    # que esta cuenta de publisher está autorizada a vender el inventario de
    # la app. El contenido es ajustable sin update via el parámetro de sistema
    # lottery_portal.app_ads_txt (Ajustes → Técnico → Parámetros del sistema),
    # por si más adelante se agregan redes de mediación.
    @http.route('/app-ads.txt', type='http', auth="public", website=False)
    def app_ads_txt(self, **kwargs):
        content = request.env['ir.config_parameter'].sudo().get_param(
            'lottery_portal.app_ads_txt',
            'google.com, pub-9112696506385807, DIRECT, f08c47fec0942fa0',
        )
        return request.make_response(
            content.strip() + '\n',
            headers=[('Content-Type', 'text/plain; charset=utf-8')],
        )
