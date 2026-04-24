# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from datetime import datetime
from odoo.addons.lottery_base.models.utils import MONTHS_DICT

class LotteryPortal(http.Controller):

    @http.route('/', type='http', auth='public', website=True)
    def home(self, **kwargs):
        stats = request.env['lottery.stats.service'].sudo()
        response = request.render('website.homepage')
        month = request.env.company.portal_calendar_month
        year = request.env.company.portal_calendar_year
        response.qcontext.update({
            'lottery_data': stats.get_last_results_full(),
            'month_year': stats.get_month_year(month, year),
            'hero_stats': stats.get_hero_stats(),
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
            'categories': categories.read(['name', 'icon']),
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

    @http.route('/estadisticas-pintas', type='http', auth='public', website=True)
    def portal_estadisticas_pintas_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_pintas')

    @http.route('/estadisticas-numeros', type='http', auth='public', website=True)
    def portal_estadisticas_numeros_page(self, **kw):
        return request.render('lottery_portal.portal_estadisticas_numeros')

    @http.route('/estadisticas-numeros/dashboard_data', type='json', auth='public')
    def dashboard_info_numbers(self, month=False):
        today = datetime.today()
        month_filter = month or today.month
        current_year = today.year
        top_numbers = request.env['lottery.stats.service'].sudo().get_top_numbers_month(month_filter, current_year)
        bottom_numbers = request.env['lottery.stats.service'].sudo().get_bottom_numbers_month(month_filter, current_year)
        remaining_numbers = request.env['lottery.stats.service'].sudo().get_remaining_numbers_month(month_filter, current_year)

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
    def dashboard_numbers_week_day_all(self):
        return request.env['lottery.stats.service'].sudo().get_numbers_all_weekdays()

    @http.route('/estadisticas-numeros/numbers-week-all', type='json', auth='public')
    def dashboard_numbers_week_all(self):
        return request.env['lottery.stats.service'].sudo().get_numbers_all_weeks()

    @http.route('/estadisticas-numeros/centena-week-day-all', type='json', auth='public')
    def dashboard_centena_week_day_all(self):
        return request.env['lottery.stats.service'].sudo().get_centenas_all_weekdays()

    @http.route('/estadisticas-numeros/centena-week-all', type='json', auth='public')
    def dashboard_centena_week_all(self):
        return request.env['lottery.stats.service'].sudo().get_centenas_all_weeks()

    @http.route('/estadisticas-numeros/top-number-week-day', type='json', auth='public')
    def dashboard_top_number_week_day(self, day=False):
        top_numbers_by_week_day = request.env['lottery.stats.service'].sudo().get_top_numbers_by_week_day(day)

        return {
            "top_numbers_by_week_day": top_numbers_by_week_day,

        }

    @http.route('/estadisticas-numeros/bottom-number-week-day', type='json', auth='public')
    def dashboard_bottom_number_week_day(self, day=False):
        bottom_numbers_by_week_day = request.env['lottery.stats.service'].sudo().get_bottom_numbers_by_week_day(day)
        return {
            "bottom_numbers_by_week_day": bottom_numbers_by_week_day,
        }

    @http.route('/estadisticas-numeros/top-number-week', type='json', auth='public')
    def dashboard_top_number_week(self, week=False):
        top_numbers_by_week = request.env['lottery.stats.service'].sudo().get_top_numbers_by_week(week)
        return {
            "top_numbers_by_week": top_numbers_by_week,
        }

    @http.route('/estadisticas-numeros/bottom-number-week', type='json', auth='public')
    def dashboard_bottom_number_week(self, week=False):
        bottom_numbers_by_week = request.env['lottery.stats.service'].sudo().get_bottom_numbers_by_week(week)
        return {
            "bottom_numbers_by_week": bottom_numbers_by_week,
        }

    @http.route('/estadisticas-numeros/numeros-socios', type='json', auth='public')
    def get_salidas_numeros_socios_por_numero(self, number_id=False):
        salidas_numeros_despues_numero = request.env['lottery.stats.service'].sudo().get_salidas_numeros_despues_numero(number_id)
        salidas_numeros_antes_numero = request.env['lottery.stats.service'].sudo().get_salidas_numeros_antes_numero(number_id)
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
    def dashboard_top_centena_week_day(self, day=False, field=False):
        top_info_by_week_day = request.env['lottery.stats.service'].sudo().get_top_centenas_by_week_day(day, field)

        return {
            "top_info_by_week_day": top_info_by_week_day,

        }

    @http.route('/estadisticas-numeros/bottom-centena-week-day', type='json', auth='public')
    def dashboard_bottom_centena_week_day(self, day=False, field=False):
        bottom_info_by_week_day = request.env['lottery.stats.service'].sudo().get_bottom_centenas_by_week_day(day, field)
        return {
            "bottom_info_by_week_day": bottom_info_by_week_day,
        }

    @http.route('/estadisticas-numeros/top-centena-week', type='json', auth='public')
    def dashboard_top_centena_week(self, week=False, field=False):
        top_info_by_week = request.env['lottery.stats.service'].sudo().get_top_centenas_by_week(week, field)
        return {
            "top_info_by_week": top_info_by_week,
        }

    @http.route('/estadisticas-numeros/bottom-centena-week', type='json', auth='public')
    def dashboard_bottom_centena_week(self, week=False, field=False):
        bottom_info_by_week = request.env['lottery.stats.service'].sudo().get_bottom_centenas_by_week(week, field)
        return {
            "bottom_info_by_week": bottom_info_by_week,
        }

    @http.route('/estadisticas-numeros/top-repeticiones', type='json', auth='public')
    def dashboard_top_repeticiones(self):
        top_repeticiones = request.env['lottery.stats.service'].sudo().get_top_repeticiones()
        return {
            "top_repeticiones": top_repeticiones,
        }

    @http.route('/estadisticas-numeros/top-pegados', type='json', auth='public')
    def dashboard_top_pegados(self):
        top_pegados = request.env['lottery.stats.service'].sudo().get_top_pegados()
        return {
            "top_pegados": top_pegados,
        }

    @http.route('/estadisticas-grupos/dashboard_data', type='json', auth='public')
    def dashboard_info_groups(self, day=False, week=False, month=False):
        top_6_groups_info = request.env['lottery.stats.service'].sudo().get_top_6_groups('general', day)
        top_6_groups_info_tarde = request.env['lottery.stats.service'].sudo().get_top_6_groups('afternoon', day)
        top_6_groups_info_noche = request.env['lottery.stats.service'].sudo().get_top_6_groups('evening', day)
        groups_analysis = {}
        groups_analysis_tarde = {}
        groups_analysis_noche = {}
        for group in top_6_groups_info:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3)
            groups_analysis[group.get('id')] = data
        for group in top_6_groups_info_tarde:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3)
            groups_analysis_tarde[group.get('id')] = data
        for group in top_6_groups_info_noche:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 3)
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
    def dashboard_info_pintas(self, day=False, week=False, month=False):
        get_top_3_pintas = request.env['lottery.stats.service'].sudo().get_top_3_pintas('general', day)
        get_top_3_pintas_tarde = request.env['lottery.stats.service'].sudo().get_top_3_pintas('afternoon', day)
        get_top_3_pintas_noche = request.env['lottery.stats.service'].sudo().get_top_3_pintas('evening', day)
        groups_analysis = {}
        groups_analysis_tarde = {}
        groups_analysis_noche = {}
        for group in get_top_3_pintas:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8)
            groups_analysis[group.get('id')] = data
        for group in get_top_3_pintas_tarde:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8)
            groups_analysis_tarde[group.get('id')] = data
        for group in get_top_3_pintas_noche:
            data = request.env['lottery.stats.service'].sudo().get_info_group_numbers_analysis(group.get('id'), day, week, month, 8)
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
    def get_group_numbers(self, group_id=False, orden=False, day=False):
        group = request.env['lottery.group'].sudo().browse(group_id)
        group_numbers = request.env['lottery.stats.service'].sudo().get_info_groups_numbers(group, orden, day)
        return group_numbers

    @http.route('/lottery/get_month_text', type='json', auth='public')
    def get_month_text(self, month=False):
        return MONTHS_DICT[str(month)]

    @http.route('/lottery/get_data_chart_general', type='json', auth='public')
    def get_data_chart_general(self, group_id=False):
        general = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id)
        return general

    @http.route('/lottery/get_data_chart_tarde', type='json', auth='public')
    def get_data_chart_tarde(self, group_id=False):
        afternoon = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id, 'afternoon')
        return afternoon

    @http.route('/lottery/get_data_chart_noche', type='json', auth='public')
    def get_data_chart_noche(self, group_id=False):
        evening = request.env['lottery.stats.service'].sudo().get_group_delay_intervals(group_id, 'evening')
        return evening

    @http.route('/lottery/get_data_chart_general_pinta', type='json', auth='public')
    def get_data_chart_general_pinta(self, group_id=False):
        general = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id)
        return general

    @http.route('/lottery/get_data_chart_tarde_pinta', type='json', auth='public')
    def get_data_chart_tarde_pinta(self, group_id=False):
        afternoon = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id, 'afternoon')
        return afternoon

    @http.route('/lottery/get_data_chart_noche_pinta', type='json', auth='public')
    def get_data_chart_noche_pinta(self, group_id=False):
        evening = request.env['lottery.stats.service'].sudo().get_group_delay_intervals_pintas(group_id, 'evening')
        return evening



class LotteryController(http.Controller):

    @http.route('/lottery/top10_by_day', type='json', auth='public', website=True)
    def top10_by_day(self, day):
        records = request.env['lottery.stats.service'].sudo().get_top_10_por_dia_semana(day)
        return records

    @http.route('/lottery/top10_by_day_all', type='json', auth='public', website=True)
    def top10_by_day_all(self):
        stats = request.env['lottery.stats.service'].sudo()
        days = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']
        return {day: stats.get_top_10_por_dia_semana(day) for day in days}

    @http.route('/lottery/top10_atrasos', type='json', auth='public', website=True)
    def top10_atrasos(self, type):
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top_10_{type}'
        return getattr(stats, method, lambda: [])()

    @http.route('/lottery/top10_atrasos_all', type='json', auth='public', website=True)
    def top10_atrasos_all(self):
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top_10_general(),
            'dia': stats.get_top_10_dia(),
            'noche': stats.get_top_10_noche(),
        }

    @http.route('/lottery/ultimas_salidas_by_day', type='json', auth='public', website=True)
    def ultimas_salidas_by_day(self, day):
        return request.env['lottery.stats.service'].sudo().get_ultimas_salidas_por_dia(day)

    @http.route('/lottery/ultimas_salidas_by_day_all', type='json', auth='public', website=True)
    def ultimas_salidas_by_day_all(self):
        stats = request.env['lottery.stats.service'].sudo()
        days = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']
        return {day: stats.get_ultimas_salidas_por_dia(day) for day in days}

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

    @http.route('/lottery/top5_centenas_all', type='json', auth='public', website=True)
    def top5_centenas_all(self):
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top5_centenas_general(),
            'afternoon': stats.get_top5_centenas_afternoon(),
            'evening': stats.get_top5_centenas_evening(),
        }

    @http.route('/lottery/top_atrasos_lineas', type='json', auth='public', website=True)
    def get_top_atrasos_lineas(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_lineas(type)

    @http.route('/lottery/top_atrasos_lineas_all', type='json', auth='public', website=True)
    def get_top_atrasos_lineas_all(self):
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_lineas()

    @http.route('/lottery/top_atrasos_terminales', type='json', auth='public', website=True)
    def get_top_atrasos_terminales(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_terminales(type)

    @http.route('/lottery/top_atrasos_terminales_all', type='json', auth='public', website=True)
    def get_top_atrasos_terminales_all(self):
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_terminales()

    @http.route('/lottery/top_atrasos_parejas', type='json', auth='public', website=True)
    def get_top_atrasos_parejas(self, type):
        return request.env['lottery.stats.service'].sudo().get_top_atrasos_number_groups(type, groups_code=['resta_0'])

    @http.route('/lottery/top_atrasos_parejas_all', type='json', auth='public', website=True)
    def get_top_atrasos_parejas_all(self):
        return request.env['lottery.stats.service'].sudo().get_all_atrasos_parejas()

    @http.route('/lottery/top5_bola_extra', type='json', auth='public', website=True)
    def top5_bola_extra(self, type):
        stats = request.env['lottery.stats.service'].sudo()
        method = f'get_top5_bola_extra_{type}'
        return getattr(stats, method, lambda: [])()

    @http.route('/lottery/top5_bola_extra_all', type='json', auth='public', website=True)
    def top5_bola_extra_all(self):
        stats = request.env['lottery.stats.service'].sudo()
        return {
            'general': stats.get_top5_bola_extra_general(),
            'afternoon': stats.get_top5_bola_extra_afternoon(),
            'evening': stats.get_top5_bola_extra_evening(),
        }

    @http.route('/lottery/numeros-calientes', type='json', auth='public', website=True)
    def get_numeros_calientes(self, turn_day='afternoon', **kwargs):
        from datetime import date
        if turn_day not in ('afternoon', 'evening'):
            turn_day = 'afternoon'
        stats = request.env['lottery.stats.service'].sudo()
        return stats.get_numeros_calientes(turn_day, str(date.today()))

    @http.route('/lottery/calientes-all', type='json', auth='public', website=True)
    def get_calientes_all(self, **kwargs):
        from datetime import date
        return request.env['lottery.stats.service'].sudo().get_calientes_all(str(date.today()))
