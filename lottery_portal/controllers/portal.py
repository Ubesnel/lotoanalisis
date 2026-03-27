from odoo import http
from odoo.http import request
from datetime import datetime

class LotteryPortal(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def home(self, **kwargs):
        stats = request.env['lottery.stats.service'].sudo()
        response = request.render('website.homepage')
        month = request.env.company.portal_calendar_month
        year = request.env.company.portal_calendar_year
        response.qcontext.update({
            'lottery_data': stats.get_last_results_full(),
            'month_year': stats.get_month_year(month, year)

        })
        return response

    @http.route(['/faq'], type='http', auth="public", website=True)
    def faq_page(self, **kwargs):
        return request.render('lottery_portal.faq_page')

    @http.route('/faq/data', type='json', auth='public', website=True)
    def faq_data(self):
        categories = request.env['website.faq.category'].sudo().search([])
        faqs = request.env['website.faq'].sudo().search([('active', '=', True)])

        return {
            'categories': categories.read(['name']),
            'faqs': faqs.read(['question', 'answer', 'category_id'])
        }

    @http.route(['/terminos-condiciones'], type='http', auth="public", website=True)
    def terminos_condiciones_page(self, **kwargs):
        return request.render('lottery_portal.terminos_condiciones_page')

    @http.route(['/politica-privacidad'], type='http', auth="public", website=True)
    def politica_privacidad_page(self, **kwargs):
        return request.render('lottery_portal.politica_privacidad_page')

    @http.route('/estadisticas', type='http', auth='public', website=True)
    def portal_estadisticas_grupos_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_grupos')

    @http.route('/estadisticas-numeros', type='http', auth='public', website=True)
    def portal_estadisticas_numeros_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_numeros')

class LotteryController(http.Controller):

    @http.route('/lottery/top10_by_day', type='json', auth='public', website=True)
    def top10_by_day(self, day):
        records = request.env['lottery.stats.service'].sudo().get_top_10_por_dia_semana(day)
        return records

    @http.route('/lottery/top10_atrasos', type='json', auth='public', website=True)
    def top10_atrasos(self, type):
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top_10_{type}'
        return getattr(stats, method, lambda: [])()

    @http.route('/lottery/ultimas_salidas_by_day', type='json', auth='public', website=True)
    def ultimas_salidas_by_day(self, day):
        return request.env['lottery.stats.service'].sudo().get_ultimas_salidas_por_dia(day)

    @http.route('/salidas/buscar', type='json', auth='public')
    def buscar_salidas(self, fecha):
        if not fecha:
            return {}

        salidas = request.env['lottery.output'].sudo().search([('date', '=', fecha)])
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}

        dia_semana = dias[fecha_dt.weekday()]

        data = {
            r.turn_day: {
                'centena': r.hundreds_id.name,
                'numero': str(r.number_id.name).zfill(2),
                'bola_extra': r.fireball_id.name if r.fireball_id else "-"
            }
            for r in salidas
        }
        data.update(
            {'dia_semana': dia_semana}
        )
        return data

    @http.route('/lottery/top5_centenas', type='json', auth='public', website=True)
    def top5_centenas(self, type):
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top5_centenas_{type}'
        return getattr(stats, method, lambda: [])()

    @http.route('/lottery/top_atrasos_lineas', type='json', auth='public', website=True)
    def get_top_atrasos_lineas(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_lineas(type)

    @http.route('/lottery/top_atrasos_terminales', type='json', auth='public', website=True)
    def get_top_atrasos_terminales(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_terminales(type)

    @http.route('/lottery/top_atrasos_parejas', type='json', auth='public', website=True)
    def get_top_atrasos_parejas(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_number_groups(type, groups_code=['resta_0'])

    @http.route('/lottery/top5_bola_extra', type='json', auth='public', website=True)
    def top5_bola_extra(self, type):
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top5_bola_extra_{type}'
        return getattr(stats, method, lambda: [])()
