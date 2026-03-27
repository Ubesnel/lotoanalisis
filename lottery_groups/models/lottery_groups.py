# -*- coding: utf-8 -*-
from odoo import models, fields


class LotteryGroup(models.Model):
    _name = 'lottery.group'
    _description = 'Grupos de números'

    code = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)
    number_ids = fields.Many2many('lottery.number', 'lottery_group_number_rel', 'group_id', 'number_id',
                                  string='Números')
    salidas_atrasadas_lunes = fields.Integer(string='Atrasos lunes', help='Salidas atrasadas los Lunes')
    salidas_atrasadas_martes = fields.Integer(string='Atrasos martes', help='Salidas atrasadas los Martes')
    salidas_atrasadas_miercoles = fields.Integer(string='Atrasos miércoles', help='Salidas atrasadas los Miércoles')
    salidas_atrasadas_jueves = fields.Integer(string='Atrasos jueves', help='Salidas atrasadas los Jueves')
    salidas_atrasadas_viernes = fields.Integer(string='Atrasos viernes', help='Salidas atrasadas los Viernes')
    salidas_atrasadas_sabado = fields.Integer(string='Atrasos sábado', help='Salidas atrasadas los Sábados')
    salidas_atrasadas_domingo = fields.Integer(string='Atrasos domingo', help='Salidas atrasadas los Domingos')
    salidas_atrasadas = fields.Integer(string='Atrasos generales')
    salidas_atrasadas_dia = fields.Integer(string='Atrasos tarde')
    salidas_atrasadas_noche = fields.Integer(string='Atrasos noche')
    notes = fields.Text(string='Notas')

    total_salidas = fields.Integer(store=True)
    total_salidas_dia = fields.Integer(store=True)
    total_salidas_noche = fields.Integer(store=True)
    cant_salidas_enero = fields.Integer(store=True)
    cant_salidas_febrero = fields.Integer(store=True)
    cant_salidas_marzo = fields.Integer(store=True)
    cant_salidas_abril = fields.Integer(store=True)
    cant_salidas_mayo = fields.Integer(store=True)
    cant_salidas_junio = fields.Integer(store=True)
    cant_salidas_julio = fields.Integer(store=True)
    cant_salidas_agosto = fields.Integer(store=True)
    cant_salidas_septiembre = fields.Integer(store=True)
    cant_salidas_octubre = fields.Integer(store=True)
    cant_salidas_noviembre = fields.Integer(store=True)
    cant_salidas_diciembre = fields.Integer(store=True)
    total_domingo = fields.Integer(store=True)
    total_lunes = fields.Integer(store=True)
    total_martes = fields.Integer(store=True)
    total_miercoles = fields.Integer(store=True)
    total_jueves = fields.Integer(store=True)
    total_viernes = fields.Integer(store=True)
    total_sabado = fields.Integer(store=True)
    total_semana_1 = fields.Integer(store=True)
    total_semana_2 = fields.Integer(store=True)
    total_semana_3 = fields.Integer(store=True)
    total_semana_4 = fields.Integer(store=True)
    total_semana_5 = fields.Integer(store=True)

    _sql_constraints = [
        ('lottery_number_name_unique',
         'unique(name)',
         'El número ya existe, debe ser único.'),
        ('lottery_number_code_unique',
         'unique(code)',
         'El código ya existe, debe ser único.')
    ]

    def cron_recompute_from_sql(self):
        self.env.cr.execute("""
            SELECT
                rel.group_id,
                MIN(n.total_atrasadas) AS min_total,
                MIN(n.total_atrasadas_dia) AS min_dia,
                MIN(n.total_atrasadas_noche) AS min_noche,
                SUM(n.total_salidas) as total_salidas,
                SUM(n.total_salidas_dia) as total_salidas_dia,
                SUM(n.total_salidas_noche) as total_salidas_noche,
                SUM(n.cant_salidas_enero) as cant_salidas_enero,
                SUM(n.cant_salidas_febrero) as cant_salidas_febrero,
                SUM(n.cant_salidas_marzo) as cant_salidas_marzo,
                SUM(n.cant_salidas_abril) as cant_salidas_abril,
                SUM(n.cant_salidas_mayo) as cant_salidas_mayo,
                SUM(n.cant_salidas_junio) as cant_salidas_junio,
                SUM(n.cant_salidas_julio) as cant_salidas_julio,
                SUM(n.cant_salidas_agosto) as cant_salidas_agosto,
                SUM(n.cant_salidas_septiembre) as cant_salidas_septiembre,
                SUM(n.cant_salidas_octubre) as cant_salidas_octubre,
                SUM(n.cant_salidas_noviembre) as cant_salidas_noviembre,    
                SUM(n.cant_salidas_diciembre) as cant_salidas_diciembre,
                SUM(n.total_domingo) as total_domingo,    
                SUM(n.total_lunes) as total_lunes,
                SUM(n.total_martes) as total_martes,
                SUM(n.total_miercoles) as total_miercoles,
                SUM(n.total_jueves) as total_jueves,
                SUM(n.total_viernes) as total_viernes,
                SUM(n.total_sabado) as total_sabado,
                SUM(n.total_semana_1) as total_semana_1,
                SUM(n.total_semana_2) as total_semana_2,
                SUM(n.total_semana_3) as total_semana_3,
                SUM(n.total_semana_4) as total_semana_4,
                SUM(n.total_semana_5) as total_semana_5,
                MIN(n.salidas_atrasadas_lunes) AS min_salidas_atrasadas_lunes,
                MIN(n.salidas_atrasadas_martes) AS salidas_atrasadas_martes,
                MIN(n.salidas_atrasadas_miercoles) AS salidas_atrasadas_miercoles,
                MIN(n.salidas_atrasadas_jueves) AS salidas_atrasadas_jueves,
                MIN(n.salidas_atrasadas_viernes) AS salidas_atrasadas_viernes,
                MIN(n.salidas_atrasadas_sabado) AS salidas_atrasadas_sabado,
                MIN(n.salidas_atrasadas_domingo) AS salidas_atrasadas_domingo
            FROM lottery_group_number_rel rel
            JOIN lottery_number n
              ON n.id = rel.number_id
            GROUP BY rel.group_id
        """)
        results = self.env.cr.fetchall()

        updates = {
            row[0]: {'salidas_atrasadas': row[1], 'salidas_atrasadas_dia': row[2], 'salidas_atrasadas_noche': row[3],
                     'total_salidas': row[4], 'total_salidas_dia': row[5], 'total_salidas_noche': row[6],
                     'cant_salidas_enero': row[7],
                     'cant_salidas_febrero': row[8], 'cant_salidas_marzo': row[9], 'cant_salidas_abril': row[10],
                     'cant_salidas_mayo': row[11],
                     'cant_salidas_junio': row[12], 'cant_salidas_julio': row[13], 'cant_salidas_agosto': row[14],
                     'cant_salidas_septiembre': row[15],
                     'cant_salidas_octubre': row[16], 'cant_salidas_noviembre': row[17],
                     'cant_salidas_diciembre': row[18], 'total_domingo': row[19],
                     'total_lunes': row[20], 'total_martes': row[21], 'total_miercoles': row[22],
                     'total_jueves': row[23], 'total_viernes': row[24], 'total_sabado': row[25],
                     'total_semana_1': row[26], 'total_semana_2': row[27], 'total_semana_3': row[28],
                     'total_semana_4': row[29], 'total_semana_5': row[30],
                     'salidas_atrasadas_lunes': row[31], 'salidas_atrasadas_martes': row[32],
                     'salidas_atrasadas_miercoles': row[33], 'salidas_atrasadas_jueves': row[34],
                     'salidas_atrasadas_viernes': row[35], 'salidas_atrasadas_sabado': row[36],
                     'salidas_atrasadas_domingo': row[37],
                     }
            for row in
            results}

        for group in self.env['lottery.group'].search([]):
            vals = updates.get(group.id,
                               {'salidas_atrasadas': 0, 'salidas_atrasadas_dia': 0, 'salidas_atrasadas_noche': 0})
            group.write(vals)
