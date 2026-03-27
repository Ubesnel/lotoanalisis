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
        'data/ir_cron.xml',
        'views/lottery_number_view.xml',
    ],
    'installable': True,

}
