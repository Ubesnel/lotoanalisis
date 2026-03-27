{
    'name': 'Grupos',
    'version': '0.1',
    'description': """º
Estadísticas sobre Grupos de números
""",
    'author': 'SeuS IT',
    'category': 'Loterías',
    'maintainer': 'SeuS IT',
    'license': 'LGPL-3',
    'depends': ['lottery_delays_number'],
    'data': [
        'security/ir.model.access.csv',
        'data/lottery_lines_groups_data.xml',
        'data/lottery_pints_groups_data.xml',
        'data/lottery_terminal_groups_data.xml',
        'data/lottery_restas_groups_data.xml',
        'data/lottery_sumas_groups_data.xml',
        'data/lottery_pares_groups_data.xml',
        'data/lottery_impares_groups_data.xml',
        'data/lottery_acomp_menor_groups_data.xml',
        'data/lottery_acomp_mayor_groups_data.xml',
        'data/ir_cron.xml',
        'views/lottery_groups_view.xml',
        'views/lottery_menu_view.xml',
    ],
    'installable': True,

}
