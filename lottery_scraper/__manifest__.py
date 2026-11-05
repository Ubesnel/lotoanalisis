{
    "name": "Lottery Scraper",
    "version": '2.1',
    "author": "SeuS IT",
    "category": "Tools",
    "summary": "Importación de resultados de Quiniela UY y Tómbola",
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
