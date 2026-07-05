{
    "name": "Lottery Scraper",
    "version": "1.1",
    "author": "SeuS IT",
    "category": "Tools",
    "summary": "Importación automática de resultados Florida Pick 3",
    "depends": [
        "lottery_base",
        "lottery_fireball",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/lottery_scraper_views.xml",
    ],
    "installable": True,
    "application": False,
}
