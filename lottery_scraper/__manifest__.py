{
    "name": "Lottery Scraper",
    "version": "1.2",
    "author": "SeuS IT",
    "category": "Tools",
    "summary": "Importación automática de resultados Florida Pick 3 y Pick 2, Quiniela UY y New York Numbers",
    "depends": [
        "lottery_base",
        "lottery_fireball",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "data/lottery_scraper_data.xml",
        "views/lottery_scraper_views.xml",
    ],
    "installable": True,
    "application": False,
}
