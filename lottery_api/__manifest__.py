# -*- coding: utf-8 -*-
{
    "name": "Lottery API",
    "version": "1.2",
    "author": "SeuS IT",
    "category": "Tools",
    "summary": "Endpoints REST públicos para la app móvil LotoAnálisis",
    "depends": [
        "lottery_fireball",
        "lottery_portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_api_log.xml",
        "views/lottery_sorteo_views.xml",
        "views/lottery_output_views.xml",
        "views/res_config_settings_views.xml",
        "views/api_log_views.xml",
    ],
    "installable": True,
    "application": False,
}
