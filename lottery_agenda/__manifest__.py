# -*- coding: utf-8 -*-
{
    "name": "Lottery Agenda",
    "version": "1.0",
    "author": "SeuS IT",
    "category": "Loterías",
    "license": "LGPL-3",
    "summary": "Agenda diaria en el calendario con la hora de publicar cada sorteo",
    "description": """
Crea en el calendario de Odoo un evento por sorteo y turno con la hora (de
Uruguay) a la que hay que publicar, con aviso unos minutos antes. Al registrar
la salida, el evento se marca solo como hecho.
""",
    "depends": [
        "calendar",
        "lottery_portal",
    ],
    "data": [
        "views/lottery_sorteo_views.xml",
        "views/calendar_event_views.xml",
        "views/res_config_settings_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
