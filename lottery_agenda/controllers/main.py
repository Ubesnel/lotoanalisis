# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class LotteryAgendaController(http.Controller):

    @http.route('/lottery_agenda/calendar_notify', type='json', auth='user')
    def calendar_notify(self):
        """Hace que Odoo mande por el bus las próximas alarmas del usuario.

        El servicio de avisos del calendario de Odoo 17 no las pide al abrir
        la página: solo las recibe por el bus cuando se crea o modifica un
        evento con alarma, y después encadena una a una. Una pestaña abierta
        después de eso (o que se durmió con la PC) se queda sin avisos hasta
        que se cree otro evento. Ver static/src/js/agenda_notify_service.js."""
        request.env['calendar.alarm_manager']._notify_next_alarm(
            request.env.user.partner_id.ids)
        return True
