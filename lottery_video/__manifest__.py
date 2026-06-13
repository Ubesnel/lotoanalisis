# -*- coding: utf-8 -*-
{
    'name': 'Lottery Video',
    'version': '17.0.1.0.0',
    'summary': 'Generación de info y video para redes sociales - Pick 3',
    'depends': ['lottery_base', 'lottery_groups', 'lottery_portal'],
    'data': [
        'security/ir.model.access.csv',
        'views/video_config_views.xml',
        'views/video_info_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
