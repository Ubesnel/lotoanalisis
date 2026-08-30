{
    'name': 'Atrasos de Tómbola',
    'version': '0.1',
    'description': """
Atrasos de números para la Tómbola de la Quiniela Uruguay. Independiente de
los atrasos de las demás loterías: la Tómbola no tiene sorteo_id, es un
juego único con 20 números por sorteo.
""",
    'author': 'SeuS IT',
    'category': 'Loterías',
    'maintainer': 'SeuS IT',
    'license': 'LGPL-3',
    'depends': ['lottery_base'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/lottery_tombola_stat_view.xml',
        'views/lottery_menu_view.xml',
    ],
    'installable': True,
    'post_init_hook': '_initial_recompute',
}
