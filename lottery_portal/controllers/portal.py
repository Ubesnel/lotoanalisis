# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from datetime import datetime
from odoo.addons.lottery_base.models.utils import MONTHS_DICT


def _resolve_sorteo_id(sorteo_id):
    """Resuelve el sorteo_id recibido desde el frontend, usando Florida como
    default mientras el selector OWL no envíe un valor explícito."""
    return int(sorteo_id) if sorteo_id else request.env.ref('lottery_base.sorteo_florida').id


class LotteryPortal(http.Controller):

    def _resolve_sorteo_id(self, sorteo_id):
        return _resolve_sorteo_id(sorteo_id)

    @http.route('/lottery/sorteos', type='json', auth='public', website=True)
    def get_sorteos(self, **kwargs):
        sorteos = request.env['lottery.sorteo'].sudo().search([], order='sequence, id')
        default = request.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)
        return {
            'sorteos': [{'id': s.id, 'name': s.name, 'code': s.code} for s in sorteos],
            'default_id': default.id if default else (sorteos[0].id if sorteos else False),
        }

    @http.route('/lottery/sorteos-publicos', type='json', auth='public', website=True)
    def get_sorteos_publicos(self, **kwargs):
        sorteos = request.env['lottery.sorteo'].sudo().search(
            [('show_in_public', '=', True)], order='sequence, id')
        default = sorteos[0] if sorteos else None
        return {
            'sorteos': [{'id': s.id, 'name': s.name, 'code': s.code} for s in sorteos],
            'default_id': default.id if default else False,
        }

    @http.route('/lottery/ultimos-resultados', type='json', auth='public', website=True)
    def get_ultimos_resultados(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        return stats.get_last_results_full(sorteo_id=sorteo_id)

    @http.route('/estadisticas-generales', type='http', auth='user', website=True)
    def estadisticas_generales(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        month = request.env.company.portal_calendar_month
        year = request.env.company.portal_calendar_year
        return request.render('lottery_portal.estadisticas_generales', {
            'lottery_data': stats.get_last_results_full(sorteo_id=sorteo_id),
            'month_year': stats.get_month_year(month, year),
            'hero_stats': stats.get_hero_stats(sorteo_id=sorteo_id),
        })

    @http.route('/grupos-por-dia', type='http', auth='user', website=True)
    def grupos_por_dia(self, **kw):
        return request.render('lottery_portal.portal_grupos_por_dia')

    @http.route('/grupos-por-dia/dashboard_data', type='json', auth='user')
    def grupos_por_dia_dashboard_data(self, day=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        data = request.env['lottery.stats.service'].sudo().get_grupos_por_dia(day, sorteo_id=sorteo_id)
        return data

    @http.route('/grupos-por-dia/probables', type='json', auth='user')
    def grupos_por_dia_probables(self, sorteo_id=False, **kw):
        """3 líneas y 3 terminales más probables para el próximo sorteo."""
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        sorteo = request.env['lottery.sorteo'].sudo().browse(sorteo_id)
        date_str, turn = sorteo.get_next_draw()
        if turn not in ('afternoon', 'evening'):
            turn = 'afternoon'
        return request.env['lottery.stats.service'].sudo().get_lineas_terminales_probables(
            turn, date_str, sorteo_id=sorteo_id)

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

    @http.route('/estadisticas', type='http', auth='user', website=True)
    def portal_estadisticas_grupos_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_grupos')

    @http.route('/estadisticas-pintas', type='http', auth='user', website=True)
    def portal_estadisticas_pintas_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_pintas')

    @http.route('/estadisticas-numeros', type='http', auth='user', website=True)
    def portal_estadisticas_numeros_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_numeros')

    @http.route('/estadisticas-numeros/dashboard_data', type='json', auth='public')
    def dashboard_info_numbers(self, month=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        today = datetime.today()
        month_filter = month or today.month
        current_year = today.year
        top_numbers = request.env['lottery.stats.service'].sudo().get_top_numbers_month(month_filter, current_year, sorteo_id=sorteo_id)
        bottom_numbers = request.env['lottery.stats.service'].sudo().get_bottom_numbers_month(month_filter, current_year, sorteo_id=sorteo_id)
        remaining_numbers = request.env['lottery.stats.service'].sudo().get_remaining_numbers_month(month_filter, current_year, sorteo_id=sorteo_id)

        return {
            "kpis": {
                "month": MONTHS_DICT[str(month_filter)],
                "year": current_year,
            },
            "top_numbers": top_numbers,
            "bottom_numbers": bottom_numbers,
            "remaining_numbers": remaining_numbers,
        }

    @http.route('/estadisticas-numeros/numbers-week-day-all', type='json', auth='public')
    def dashboard_numbers_week_day_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_numbers_all_weekdays(sorteo_id=sorteo_id)

    @http.route('/estadisticas-numeros/numbers-week-all', type='json', auth='public')
    def dashboard_numbers_week_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_numbers_all_weeks(sorteo_id=sorteo_id)

    @http.route('/estadisticas-numeros/centena-week-day-all', type='json', auth='public')
    def dashboard_centena_week_day_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_centenas_all_weekdays(sorteo_id=sorteo_id)

    @http.route('/estadisticas-numeros/centena-week-all', type='json', auth='public')
    def dashboard_centena_week_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_centenas_all_weeks(sorteo_id=sorteo_id)

    @http.route('/estadisticas-numeros/top-number-week-day', type='json', auth='public')
    def dashboard_top_number_week_day(self, day=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_numbers_by_week_day = request.env['lottery.stats.service'].sudo().get_top_numbers_by_week_day(day, sorteo_id=sorteo_id)

        return {
            "top_numbers_by_week_day": top_numbers_by_week_day,

        }

    @http.route('/estadisticas-numeros/bottom-number-week-day', type='json', auth='public')
    def dashboard_bottom_number_week_day(self, day=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        bottom_numbers_by_week_day = request.env['lottery.stats.service'].sudo().get_bottom_numbers_by_week_day(day, sorteo_id=sorteo_id)
        return {
            "bottom_numbers_by_week_day": bottom_numbers_by_week_day,
        }

    @http.route('/estadisticas-numeros/top-number-week', type='json', auth='public')
    def dashboard_top_number_week(self, week=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_numbers_by_week = request.env['lottery.stats.service'].sudo().get_top_numbers_by_week(week, sorteo_id=sorteo_id)
        return {
            "top_numbers_by_week": top_numbers_by_week,
        }

    @http.route('/estadisticas-numeros/bottom-number-week', type='json', auth='public')
    def dashboard_bottom_number_week(self, week=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        bottom_numbers_by_week = request.env['lottery.stats.service'].sudo().get_bottom_numbers_by_week(week, sorteo_id=sorteo_id)
        return {
            "bottom_numbers_by_week": bottom_numbers_by_week,
        }

    @http.route('/estadisticas-numeros/numeros-socios', type='json', auth='public')
    def get_salidas_numeros_socios_por_numero(self, number_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        salidas_numeros_despues_numero = request.env['lottery.stats.service'].sudo().get_salidas_numeros_despues_numero(number_id, sorteo_id=sorteo_id)
        salidas_numeros_antes_numero = request.env['lottery.stats.service'].sudo().get_salidas_numeros_antes_numero(number_id, sorteo_id=sorteo_id)
        return {
            "salidas_numeros_despues_numero": salidas_numeros_despues_numero,
            "salidas_numeros_antes_numero": salidas_numeros_antes_numero,
        }

    @http.route('/estadisticas-numeros/search_number', type='json', auth='public')
    def get_search_numeros(self, term=False):
        numbers = request.env['lottery.number'].sudo().search([
            ('name', 'ilike', term)
        ])

        return numbers.read(['id', 'name'])

    @http.route('/estadisticas-grupos/search_grupos', type='json', auth='public')
    def get_search_grupos(self, term=False):
        numbers = request.env['lottery.group'].sudo().search([
            ('name', 'ilike', term), ('code', 'not in', ['pinta_0', 'pinta_1', 'pinta_2', 'pinta_3',
                                                         'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7',
                                                         'pinta_8', 'pinta_9'
                                                         ])
        ])

        return numbers.read(['id', 'name'])

    @http.route('/estadisticas-grupos/search_pintas', type='json', auth='public')
    def get_search_pintas(self, term=False):
        numbers = request.env['lottery.group'].sudo().search([
            ('name', 'ilike', term), ('code', 'in', ['pinta_0', 'pinta_1', 'pinta_2', 'pinta_3',
                                                         'pinta_4', 'pinta_5', 'pinta_6', 'pinta_7',
                                                         'pinta_8', 'pinta_9'
                                                         ])
        ])

        return numbers.read(['id', 'name'])

    @http.route('/estadisticas-numeros/top-centena-week-day', type='json', auth='public')
    def dashboard_top_centena_week_day(self, day=False, field=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_info_by_week_day = request.env['lottery.stats.service'].sudo().get_top_centenas_by_week_day(day, field, sorteo_id=sorteo_id)

        return {
            "top_info_by_week_day": top_info_by_week_day,

        }

    @http.route('/estadisticas-numeros/bottom-centena-week-day', type='json', auth='public')
    def dashboard_bottom_centena_week_day(self, day=False, field=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        bottom_info_by_week_day = request.env['lottery.stats.service'].sudo().get_bottom_centenas_by_week_day(day, field, sorteo_id=sorteo_id)
        return {
            "bottom_info_by_week_day": bottom_info_by_week_day,
        }

    @http.route('/estadisticas-numeros/top-centena-week', type='json', auth='public')
    def dashboard_top_centena_week(self, week=False, field=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_info_by_week = request.env['lottery.stats.service'].sudo().get_top_centenas_by_week(week, field, sorteo_id=sorteo_id)
        return {
            "top_info_by_week": top_info_by_week,
        }

    @http.route('/estadisticas-numeros/bottom-centena-week', type='json', auth='public')
    def dashboard_bottom_centena_week(self, week=False, field=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        bottom_info_by_week = request.env['lottery.stats.service'].sudo().get_bottom_centenas_by_week(week, field, sorteo_id=sorteo_id)
        return {
            "bottom_info_by_week": bottom_info_by_week,
        }

    @http.route('/estadisticas-numeros/top-repeticiones', type='json', auth='public')
    def dashboard_top_repeticiones(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_repeticiones = request.env['lottery.stats.service'].sudo().get_top_repeticiones(sorteo_id=sorteo_id)
        return {
            "top_repeticiones": top_repeticiones,
        }

    @http.route('/estadisticas-numeros/top-pegados', type='json', auth='public')
    def dashboard_top_pegados(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_pegados = request.env['lottery.stats.service'].sudo().get_top_pegados(sorteo_id=sorteo_id)
        return {
            "top_pegados": top_pegados,
        }

    @http.route('/estadisticas-grupos/dashboard_data', type='json', auth='public')
    def dashboard_info_groups(self, day=False, week=False, month=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        top_6_groups_info = request.env['lottery.stats.service'].sudo().get_top_6_groups('general', day, sorteo_id=sorteo_id)
        top_6_groups_info_tarde = request.env['lottery.stats.service'].sudo().get_top_6_groups('afternoon', day, sorteo_id=sorteo_id)
        top_6_groups_info_noche = request.env['lottery.stats.service'].sudo().get_top_6_groups('evening', day, sorteo_id=sorteo_id)
        groups_analysis = {}
        groups_analysis_tarde = {}
        groups_analysis_noche = {}
        for group in top_6_groups_info:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3, sorteo_id=sorteo_id)
            groups_analysis[group.get('id')] = data
        for group in top_6_groups_info_tarde:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3, sorteo_id=sorteo_id)
            groups_analysis_tarde[group.get('id')] = data
        for group in top_6_groups_info_noche:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3, sorteo_id=sorteo_id)
            groups_analysis_noche[group.get('id')] = data

        return {
            "top_6_groups_info": top_6_groups_info,
            "top_6_groups_info_tarde": top_6_groups_info_tarde,
            "top_6_groups_info_noche": top_6_groups_info_noche,
            "groups_analysis": groups_analysis,
            "groups_analysis_tarde": groups_analysis_tarde,
            "groups_analysis_noche": groups_analysis_noche,
        }

    @http.route('/estadisticas-pintas/dashboard_data', type='json', auth='public')
    def dashboard_info_pintas(self, day=False, week=False, month=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        get_top_3_pintas = request.env['lottery.stats.service'].sudo().get_top_3_pintas('general', day, sorteo_id=sorteo_id)
        get_top_3_pintas_tarde = request.env['lottery.stats.service'].sudo().get_top_3_pintas('afternoon', day, sorteo_id=sorteo_id)
        get_top_3_pintas_noche = request.env['lottery.stats.service'].sudo().get_top_3_pintas('evening', day, sorteo_id=sorteo_id)
        groups_analysis = {}
        groups_analysis_tarde = {}
        groups_analysis_noche = {}
        for group in get_top_3_pintas:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8, sorteo_id=sorteo_id)
            groups_analysis[group.get('id')] = data
        for group in get_top_3_pintas_tarde:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8, sorteo_id=sorteo_id)
            groups_analysis_tarde[group.get('id')] = data
        for group in get_top_3_pintas_noche:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8, sorteo_id=sorteo_id)
            groups_analysis_noche[group.get('id')] = data

        return {
                "get_top_3_pintas": get_top_3_pintas,
                "get_top_3_pintas_tarde": get_top_3_pintas_tarde,
                "get_top_3_pintas_noche": get_top_3_pintas_noche,
                "groups_analysis": groups_analysis,
                "groups_analysis_tarde": groups_analysis_tarde,
                "groups_analysis_noche": groups_analysis_noche,
            }

    @http.route('/lottery/get_group_numbers', type='json', auth='public')
    def get_group_numbers(self, group_id=False, orden=False, day=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        group = request.env['lottery.group'].sudo().browse(group_id)
        group_numbers = request.env['lottery.stats.service'].sudo().get_info_groups_numbers(group, orden, day, sorteo_id=sorteo_id)
        return group_numbers

    @http.route('/lottery/get_month_text', type='json', auth='public')
    def get_month_text(self, month=False):
        return MONTHS_DICT[str(month)]

    @http.route('/lottery/get_data_chart_general', type='json', auth='public')
    def get_data_chart_general(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        general = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id, sorteo_id=sorteo_id)
        return general

    @http.route('/lottery/get_data_chart_tarde', type='json', auth='public')
    def get_data_chart_tarde(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        afternoon = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id, 'afternoon', sorteo_id=sorteo_id)
        return afternoon

    @http.route('/lottery/get_data_chart_noche', type='json', auth='public')
    def get_data_chart_noche(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        evening = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id, 'evening', sorteo_id=sorteo_id)
        return evening

    @http.route('/lottery/get_data_chart_general_pinta', type='json', auth='public')
    def get_data_chart_general_pinta(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        general = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id, sorteo_id=sorteo_id)
        return general

    @http.route('/lottery/get_data_chart_tarde_pinta', type='json', auth='public')
    def get_data_chart_tarde_pinta(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        afternoon = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id, 'afternoon', sorteo_id=sorteo_id)
        return afternoon

    @http.route('/lottery/get_data_chart_noche_pinta', type='json', auth='public')
    def get_data_chart_noche_pinta(self, group_id=False, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        evening = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id, 'evening', sorteo_id=sorteo_id)
        return evening



class LotteryController(http.Controller):

    def _resolve_sorteo_id(self, sorteo_id):
        return _resolve_sorteo_id(sorteo_id)

    @http.route('/lottery/top10_by_day', type='json', auth='public', website=True)
    def top10_by_day(self, day, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        records = request.env['lottery.stats.service'].sudo().get_top_10_por_dia_semana(day, sorteo_id=sorteo_id)
        return records

    @http.route('/lottery/top10_by_day_all', type='json', auth='public', website=True)
    def top10_by_day_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        days = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']
        return {day: stats.get_top_10_por_dia_semana(day, sorteo_id=sorteo_id) for day in days}

    @http.route('/lottery/top10_atrasos', type='json', auth='public', website=True)
    def top10_atrasos(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top_10_{type}'
        return getattr(stats, method, lambda **kw: [])(sorteo_id=sorteo_id)

    @http.route('/lottery/top10_atrasos_all', type='json', auth='public', website=True)
    def top10_atrasos_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top_10_general(sorteo_id=sorteo_id),
            'dia': stats.get_top_10_dia(sorteo_id=sorteo_id),
            'noche': stats.get_top_10_noche(sorteo_id=sorteo_id),
        }

    @http.route('/lottery/ultimas_salidas_by_day', type='json', auth='public', website=True)
    def ultimas_salidas_by_day(self, day, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_ultimas_salidas_por_dia(day, sorteo_id=sorteo_id)

    @http.route('/lottery/ultimas_salidas_by_day_all', type='json', auth='public', website=True)
    def ultimas_salidas_by_day_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        days = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']
        return {day: stats.get_ultimas_salidas_por_dia(day, sorteo_id=sorteo_id) for day in days}

    @http.route('/lottery/ultimas_salidas_consecutivas', type='json', auth='public', website=True)
    def ultimas_salidas_consecutivas(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_ultimas_salidas_consecutivas(sorteo_id=sorteo_id)

    @http.route('/lottery/ultimas_salidas_col1', type='json', auth='public', website=True)
    def ultimas_salidas_col1(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_ultimas_salidas_col1(sorteo_id=sorteo_id)

    @http.route('/salidas/buscar', type='json', auth='public')
    def buscar_salidas(self, fecha, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        if not fecha:
            return {}

        salidas = request.env['lottery.output'].sudo().search([('date', '=', fecha), ('sorteo_id', '=', sorteo_id)])
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}

        dia_semana = dias[fecha_dt.weekday()]

        data = {
            r.turn_day: {
                'centena': r.hundreds_id.name,
                'numero': str(r.number_id.name).zfill(2),
                'bola_extra': r.fireball_id.name if r.fireball_id else "-",
                'premio_2': str(r.premio_2_id.name).zfill(2) if r.premio_2_id else None,
                'premio_3': str(r.premio_3_id.name).zfill(2) if r.premio_3_id else None,
            }
            for r in salidas
        }
        data.update(
            {'dia_semana': dia_semana}
        )
        return data

    @http.route('/lottery/top5_centenas', type='json', auth='public', website=True)
    def top5_centenas(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top5_centenas_{type}'
        return getattr(stats, method, lambda **kw: [])(sorteo_id=sorteo_id)

    @http.route('/lottery/top5_centenas_all', type='json', auth='public', website=True)
    def top5_centenas_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top5_centenas_general(sorteo_id=sorteo_id),
            'afternoon': stats.get_top5_centenas_afternoon(sorteo_id=sorteo_id),
            'evening': stats.get_top5_centenas_evening(sorteo_id=sorteo_id),
        }

    @http.route('/lottery/top_atrasos_lineas', type='json', auth='public', website=True)
    def get_top_atrasos_lineas(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_lineas(type, sorteo_id=sorteo_id)

    @http.route('/lottery/top_atrasos_lineas_all', type='json', auth='public', website=True)
    def get_top_atrasos_lineas_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_lineas(sorteo_id=sorteo_id)

    @http.route('/lottery/top_atrasos_terminales', type='json', auth='public', website=True)
    def get_top_atrasos_terminales(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_terminales(type, sorteo_id=sorteo_id)

    @http.route('/lottery/top_atrasos_terminales_all', type='json', auth='public', website=True)
    def get_top_atrasos_terminales_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_terminales(sorteo_id=sorteo_id)

    @http.route('/lottery/weekend-groups', type='json', auth='public', website=True)
    def get_weekend_groups(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_weekend_groups(sorteo_id=sorteo_id)

    @http.route('/lottery/group-sequences', type='json', auth='public', website=True)
    def get_group_sequences(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_all_group_sequences(sorteo_id=sorteo_id)

    @http.route('/lottery/top_atrasos_parejas', type='json', auth='public', website=True)
    def get_top_atrasos_parejas(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_number_groups(type, groups_code=['resta_0'], sorteo_id=sorteo_id)

    @http.route('/lottery/top_atrasos_parejas_all', type='json', auth='public', website=True)
    def get_top_atrasos_parejas_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_parejas(sorteo_id=sorteo_id)

    @http.route('/lottery/top5_bola_extra', type='json', auth='public', website=True)
    def top5_bola_extra(self, type, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top5_bola_extra_{type}'
        return getattr(stats, method, lambda **kw: [])(sorteo_id=sorteo_id)

    @http.route('/lottery/top5_bola_extra_all', type='json', auth='public', website=True)
    def top5_bola_extra_all(self, sorteo_id=False):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top5_bola_extra_general(sorteo_id=sorteo_id),
            'afternoon': stats.get_top5_bola_extra_afternoon(sorteo_id=sorteo_id),
            'evening': stats.get_top5_bola_extra_evening(sorteo_id=sorteo_id),
        }

    @http.route('/lottery/numeros-calientes', type='json', auth='public', website=True)
    def get_numeros_calientes(self, turn_day='afternoon', sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'
        stats = request.env['lottery.stats.service'].sudo()
        return stats.get_numeros_calientes(turn_day, self._next_draw_date_str(sorteo_id), sorteo_id=sorteo_id)

    @http.route('/lottery/calientes-all', type='json', auth='public', website=True)
    def get_calientes_all(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        sorteo = request.env['lottery.sorteo'].sudo().browse(sorteo_id)
        snapshot = sorteo._get_ranking_snapshot()
        if not snapshot:
            return {}
        return snapshot

    @http.route('/lottery/calientes-next', type='json', auth='public', website=True)
    def get_calientes_next_turn(self, sorteo_id=False, **kwargs):
        sorteo_id = self._resolve_sorteo_id(sorteo_id)
        sorteo = request.env['lottery.sorteo'].sudo().browse(sorteo_id)
        snapshot = sorteo._get_ranking_snapshot()
        if not snapshot:
            return {}
        _date_str, turn = sorteo.get_next_draw()
        if turn not in ('afternoon', 'evening'):
            turn = 'afternoon'
        return {'turn': turn, 'data': snapshot.get(turn, {})}

    def _next_draw_date_str(self, sorteo_id=False):
        """Fecha del próximo sorteo. Fuente única: el campo next_draw del sorteo
        (auto-calculado desde la última salida y el calendario, o manual)."""
        from datetime import date
        if sorteo_id:
            return request.env['lottery.sorteo'].sudo().browse(sorteo_id).get_next_draw()[0]
        return str(date.today())
