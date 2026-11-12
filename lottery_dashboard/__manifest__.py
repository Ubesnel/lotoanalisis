# -*- coding: utf-8 -*-
{
    "name": "Lottery Dashboard",
    "version": "1.0",
    "author": "SeuS IT",
    "category": "Loterías",
    "license": "LGPL-3",
    "summary": "Tablero de control: tareas del día, predicciones, códigos de regalo, números y consultas",
    "description": """
Vista principal de control para la operación diaria de LotoAnálisis:
tareas de la agenda, predicciones normales y Premium por sorteo, números del
día (líneas, terminales y pintas), códigos de regalo por país y consultas a la
API.
""",
    "depends": [
        "lottery_agenda",
        "lottery_api",
    ],
    "data": [
        "views/lottery_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lottery_dashboard/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
