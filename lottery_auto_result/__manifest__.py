# -*- coding: utf-8 -*-
{
    "name": "Lottery Auto Result",
    "version": '1.0',
    "author": "SeuS IT",
    "category": "Tools",
    "summary": "Registro automático de salidas desde fuentes web configurables",
    "depends": [
        "lottery_api",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/result_source_data.xml",
        "views/result_source_views.xml",
        "views/lottery_sorteo_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lottery_auto_result/static/src/scss/auto_result.scss",
        ],
    },
    "installable": True,
    "application": False,
}
