# -*- coding: utf-8 -*-
{
    'name': 'Lottery Guion',
    'version': '17.0.1.0.0',
    'summary': 'Generación de guiones para lotería',
    'depends': ['lottery_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/guion_comentario_views.xml',
        'views/guion_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
