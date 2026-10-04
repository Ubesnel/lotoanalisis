{
    'name': 'Base',
    'version': '2.0',
    'description': """º
Configuraciones iniciales
""",
    'author': 'SeuS IT',
    'category': 'Loterías',
    'maintainer': 'SeuS IT',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/lottery_rules.xml',
        'data/lottery_turno_data.xml',
        'data/lottery_sorteo_data.xml',
        'data/lottery_number_data.xml',
        'views/lottery_number_view.xml',
        'views/lottery_turno_view.xml',
        'views/lottery_sorteo_view.xml',
        'views/lottery_output_view.xml',
        'views/lottery_tombola_output_view.xml',
        'views/lottery_menu_view.xml',
        'views/res_users_view.xml',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',

}
