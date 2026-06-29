{
    'name': 'Atrasos de números',
    'version': '0.1',
    'description': """
Módulo que agrega campos calculados sobre información de atrasos de los números
""",
    'author': 'SeuS IT',
    'category': 'Loterías',
    'maintainer': 'SeuS IT',
    'license': 'LGPL-3',
    'depends': ['lottery_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/lottery_rules.xml',
        'data/ir_cron.xml',
        'data/lottery_number_stat_sorteo_filters_data.xml',
        'views/lottery_number_view.xml',
        'views/lottery_menu_view.xml',
    ],
    'installable': True,

}
