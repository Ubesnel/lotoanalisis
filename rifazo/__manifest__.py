# -*- coding: utf-8 -*-
{
    "name": "Rifazo",
    "version": "1.1",
    "author": "SeuS IT",
    "category": "Sales",
    "summary": "Gestión de rifas y solicitudes de participación para la app Rifazo",
    "depends": [
        "mail",
    ],
    "data": [
        "security/rifazo_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "wizard/rifazo_request_reject_views.xml",
        "views/rifazo_raffle_views.xml",
        "views/rifazo_request_views.xml",
        "views/rifazo_ticket_views.xml",
        "views/rifazo_app_release_views.xml",
        "views/rifazo_download_page.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
