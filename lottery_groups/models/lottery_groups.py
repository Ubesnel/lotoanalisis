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
            WITH data AS (
                SELECT
                    rel.group_id,
                    MIN(n.total_atrasadas) AS salidas_atrasadas,
                    MIN(n.total_atrasadas_dia) AS salidas_atrasadas_dia,
                    MIN(n.total_atrasadas_noche) AS salidas_atrasadas_noche,
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

                    MIN(n.salidas_atrasadas_lunes) AS salidas_atrasadas_lunes,
                    MIN(n.salidas_atrasadas_martes) AS salidas_atrasadas_martes,
                    MIN(n.salidas_atrasadas_miercoles) AS salidas_atrasadas_miercoles,
                    MIN(n.salidas_atrasadas_jueves) AS salidas_atrasadas_jueves,
                    MIN(n.salidas_atrasadas_viernes) AS salidas_atrasadas_viernes,
                    MIN(n.salidas_atrasadas_sabado) AS salidas_atrasadas_sabado,
                    MIN(n.salidas_atrasadas_domingo) AS salidas_atrasadas_domingo

                FROM lottery_group_number_rel rel
                JOIN lottery_number n ON n.id = rel.number_id
                GROUP BY rel.group_id
            )

            UPDATE lottery_group lg
            SET
                salidas_atrasadas = d.salidas_atrasadas,
                salidas_atrasadas_dia = d.salidas_atrasadas_dia,
                salidas_atrasadas_noche = d.salidas_atrasadas_noche,

                total_salidas = d.total_salidas,
                total_salidas_dia = d.total_salidas_dia,
                total_salidas_noche = d.total_salidas_noche,

                cant_salidas_enero = d.cant_salidas_enero,
                cant_salidas_febrero = d.cant_salidas_febrero,
                cant_salidas_marzo = d.cant_salidas_marzo,
                cant_salidas_abril = d.cant_salidas_abril,
                cant_salidas_mayo = d.cant_salidas_mayo,
                cant_salidas_junio = d.cant_salidas_junio,
                cant_salidas_julio = d.cant_salidas_julio,
                cant_salidas_agosto = d.cant_salidas_agosto,
                cant_salidas_septiembre = d.cant_salidas_septiembre,
                cant_salidas_octubre = d.cant_salidas_octubre,
                cant_salidas_noviembre = d.cant_salidas_noviembre,
                cant_salidas_diciembre = d.cant_salidas_diciembre,

                total_domingo = d.total_domingo,
                total_lunes = d.total_lunes,
                total_martes = d.total_martes,
                total_miercoles = d.total_miercoles,
                total_jueves = d.total_jueves,
                total_viernes = d.total_viernes,
                total_sabado = d.total_sabado,

                total_semana_1 = d.total_semana_1,
                total_semana_2 = d.total_semana_2,
                total_semana_3 = d.total_semana_3,
                total_semana_4 = d.total_semana_4,
                total_semana_5 = d.total_semana_5,

                salidas_atrasadas_lunes = d.salidas_atrasadas_lunes,
                salidas_atrasadas_martes = d.salidas_atrasadas_martes,
                salidas_atrasadas_miercoles = d.salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves = d.salidas_atrasadas_jueves,
                salidas_atrasadas_viernes = d.salidas_atrasadas_viernes,
                salidas_atrasadas_sabado = d.salidas_atrasadas_sabado,
                salidas_atrasadas_domingo = d.salidas_atrasadas_domingo

            FROM data d
            WHERE lg.id = d.group_id
        """)


