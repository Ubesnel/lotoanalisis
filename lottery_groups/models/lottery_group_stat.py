# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryGroupStat(models.Model):
    """Estadísticas generales de un grupo dentro de un sorteo, derivadas de
    lottery.number.stat: SUMA de sus números para totales, MIN para atrasos
    (el grupo "sale" cuando sale cualquiera de ellos). Lo que depende del
    turno vive en `lottery.group.stat.turno` (turno_stat_ids)."""
    _name = 'lottery.group.stat'
    _description = 'Estadísticas de grupo por sorteo'
    _order = 'sorteo_id, group_id'

    group_id = fields.Many2one('lottery.group', string='Grupo', required=True,
                               index=True, ondelete='cascade')
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True, index=True, ondelete='cascade')
    turno_stat_ids = fields.One2many('lottery.group.stat.turno', 'stat_id', string='Por turno')

    # Atrasos del grupo (MIN entre sus números: el grupo "sale" cuando sale cualquiera de ellos)
    salidas_atrasadas = fields.Integer(string='Atrasos generales', index=True)
    salidas_atrasadas_lunes = fields.Integer(string='Atrasos lunes')
    salidas_atrasadas_martes = fields.Integer(string='Atrasos martes')
    salidas_atrasadas_miercoles = fields.Integer(string='Atrasos miércoles')
    salidas_atrasadas_jueves = fields.Integer(string='Atrasos jueves')
    salidas_atrasadas_viernes = fields.Integer(string='Atrasos viernes')
    salidas_atrasadas_sabado = fields.Integer(string='Atrasos sábado')
    salidas_atrasadas_domingo = fields.Integer(string='Atrasos domingo')

    # Totales del grupo (SUMA de sus números)
    total_salidas = fields.Integer(string='Total salidas')
    cant_salidas_enero = fields.Integer()
    cant_salidas_febrero = fields.Integer()
    cant_salidas_marzo = fields.Integer()
    cant_salidas_abril = fields.Integer()
    cant_salidas_mayo = fields.Integer()
    cant_salidas_junio = fields.Integer()
    cant_salidas_julio = fields.Integer()
    cant_salidas_agosto = fields.Integer()
    cant_salidas_septiembre = fields.Integer()
    cant_salidas_octubre = fields.Integer()
    cant_salidas_noviembre = fields.Integer()
    cant_salidas_diciembre = fields.Integer()
    total_domingo = fields.Integer()
    total_lunes = fields.Integer()
    total_martes = fields.Integer()
    total_miercoles = fields.Integer()
    total_jueves = fields.Integer()
    total_viernes = fields.Integer()
    total_sabado = fields.Integer()
    total_semana_1 = fields.Integer()
    total_semana_2 = fields.Integer()
    total_semana_3 = fields.Integer()
    total_semana_4 = fields.Integer()
    total_semana_5 = fields.Integer()

    _sql_constraints = [
        ('lottery_group_stat_group_sorteo_unique',
         'unique(group_id, sorteo_id)',
         'Ya existe una fila de estadísticas para ese grupo y sorteo.')
    ]

    @api.depends('group_id', 'sorteo_id')
    def _compute_display_name(self):
        for rec in self:
            grupo = rec.group_id.name or ''
            sorteo = rec.sorteo_id.name or ''
            rec.display_name = f"{grupo} · {sorteo}"

    def cron_recompute_from_sql(self):
        """Reconstruye todas las estadísticas de grupo a partir de
        lottery.number.stat (que tiene que estar al día). Las filas por turno
        se van con el DELETE por el ondelete='cascade'."""
        self.env.cr.execute("DELETE FROM lottery_group_stat;")
        self.env.cr.execute("SELECT DISTINCT sorteo_id FROM lottery_number_stat;")
        for (sorteo_id,) in self.env.cr.fetchall():
            self.recompute_for_sorteo(sorteo_id)

    def recompute_for_sorteo(self, sorteo_id):
        """Actualiza las estadísticas de grupos del sorteo: generales y por turno."""
        self.env.cr.execute("""
            INSERT INTO lottery_group_stat (
                group_id, sorteo_id,
                salidas_atrasadas, total_salidas,
                cant_salidas_enero, cant_salidas_febrero, cant_salidas_marzo, cant_salidas_abril,
                cant_salidas_mayo, cant_salidas_junio, cant_salidas_julio, cant_salidas_agosto,
                cant_salidas_septiembre, cant_salidas_octubre, cant_salidas_noviembre, cant_salidas_diciembre,
                total_domingo, total_lunes, total_martes, total_miercoles,
                total_jueves, total_viernes, total_sabado,
                total_semana_1, total_semana_2, total_semana_3, total_semana_4, total_semana_5,
                salidas_atrasadas_lunes, salidas_atrasadas_martes, salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves, salidas_atrasadas_viernes, salidas_atrasadas_sabado,
                salidas_atrasadas_domingo
            )
            SELECT
                rel.group_id, ns.sorteo_id,
                MIN(ns.total_atrasadas), SUM(ns.total_salidas),
                SUM(ns.cant_salidas_enero), SUM(ns.cant_salidas_febrero), SUM(ns.cant_salidas_marzo),
                SUM(ns.cant_salidas_abril), SUM(ns.cant_salidas_mayo), SUM(ns.cant_salidas_junio),
                SUM(ns.cant_salidas_julio), SUM(ns.cant_salidas_agosto), SUM(ns.cant_salidas_septiembre),
                SUM(ns.cant_salidas_octubre), SUM(ns.cant_salidas_noviembre), SUM(ns.cant_salidas_diciembre),
                SUM(ns.total_domingo), SUM(ns.total_lunes), SUM(ns.total_martes), SUM(ns.total_miercoles),
                SUM(ns.total_jueves), SUM(ns.total_viernes), SUM(ns.total_sabado),
                SUM(ns.total_semana_1), SUM(ns.total_semana_2), SUM(ns.total_semana_3),
                SUM(ns.total_semana_4), SUM(ns.total_semana_5),
                MIN(ns.salidas_atrasadas_lunes), MIN(ns.salidas_atrasadas_martes), MIN(ns.salidas_atrasadas_miercoles),
                MIN(ns.salidas_atrasadas_jueves), MIN(ns.salidas_atrasadas_viernes), MIN(ns.salidas_atrasadas_sabado),
                MIN(ns.salidas_atrasadas_domingo)
            FROM lottery_group_number_rel rel
            JOIN lottery_number_stat ns ON ns.number_id = rel.number_id
            WHERE ns.sorteo_id = %(sorteo_id)s
            GROUP BY rel.group_id, ns.sorteo_id
            ON CONFLICT (group_id, sorteo_id) DO UPDATE SET
                salidas_atrasadas = EXCLUDED.salidas_atrasadas,
                total_salidas = EXCLUDED.total_salidas,
                cant_salidas_enero = EXCLUDED.cant_salidas_enero,
                cant_salidas_febrero = EXCLUDED.cant_salidas_febrero,
                cant_salidas_marzo = EXCLUDED.cant_salidas_marzo,
                cant_salidas_abril = EXCLUDED.cant_salidas_abril,
                cant_salidas_mayo = EXCLUDED.cant_salidas_mayo,
                cant_salidas_junio = EXCLUDED.cant_salidas_junio,
                cant_salidas_julio = EXCLUDED.cant_salidas_julio,
                cant_salidas_agosto = EXCLUDED.cant_salidas_agosto,
                cant_salidas_septiembre = EXCLUDED.cant_salidas_septiembre,
                cant_salidas_octubre = EXCLUDED.cant_salidas_octubre,
                cant_salidas_noviembre = EXCLUDED.cant_salidas_noviembre,
                cant_salidas_diciembre = EXCLUDED.cant_salidas_diciembre,
                total_domingo = EXCLUDED.total_domingo,
                total_lunes = EXCLUDED.total_lunes,
                total_martes = EXCLUDED.total_martes,
                total_miercoles = EXCLUDED.total_miercoles,
                total_jueves = EXCLUDED.total_jueves,
                total_viernes = EXCLUDED.total_viernes,
                total_sabado = EXCLUDED.total_sabado,
                total_semana_1 = EXCLUDED.total_semana_1,
                total_semana_2 = EXCLUDED.total_semana_2,
                total_semana_3 = EXCLUDED.total_semana_3,
                total_semana_4 = EXCLUDED.total_semana_4,
                total_semana_5 = EXCLUDED.total_semana_5,
                salidas_atrasadas_lunes = EXCLUDED.salidas_atrasadas_lunes,
                salidas_atrasadas_martes = EXCLUDED.salidas_atrasadas_martes,
                salidas_atrasadas_miercoles = EXCLUDED.salidas_atrasadas_miercoles,
                salidas_atrasadas_jueves = EXCLUDED.salidas_atrasadas_jueves,
                salidas_atrasadas_viernes = EXCLUDED.salidas_atrasadas_viernes,
                salidas_atrasadas_sabado = EXCLUDED.salidas_atrasadas_sabado,
                salidas_atrasadas_domingo = EXCLUDED.salidas_atrasadas_domingo;
        """, {'sorteo_id': sorteo_id})
        # Al final: necesita las filas generales ya creadas para enlazar stat_id.
        self.env['lottery.group.stat.turno']._recompute_for_sorteo(sorteo_id)


class LotteryGroupStatTurno(models.Model):
    """Estadísticas de un grupo en UN turno de un sorteo: una fila por
    (grupo, sorteo, turno), derivada de lottery.number.stat.turno con la misma
    regla que la general (SUMA de salidas, MIN de atrasos, MAX de la última
    fecha). Reemplaza a los antiguos campos fijos *_dia / *_noche.

    Se reconstruye entero por sorteo (DELETE + INSERT); no se edita a mano."""
    _name = 'lottery.group.stat.turno'
    _description = 'Estadísticas de grupo por sorteo y turno'
    _order = 'sorteo_id, group_id, turno_sequence'
    _log_access = False

    stat_id = fields.Many2one('lottery.group.stat', string='Estadística general',
                              index=True, ondelete='cascade')
    group_id = fields.Many2one('lottery.group', string='Grupo', required=True,
                               index=True, ondelete='cascade')
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                index=True, ondelete='cascade')
    turno_id = fields.Many2one('lottery.turno', string='Turno', required=True,
                               index=True, ondelete='cascade')
    turno_sequence = fields.Integer(string='Secuencia del turno', index=True)

    total_salidas = fields.Integer(string='Salidas', index=True,
                                   help="Suma de las salidas de los números del grupo en este turno.")
    salidas_atrasadas = fields.Integer(string='Atraso', index=True,
                                       help="Sorteos de este turno desde que salió cualquier número del grupo en él.")
    ultima_fecha = fields.Date(string='Última salida',
                               help="Última fecha en que salió algún número del grupo en este turno.")

    _sql_constraints = [
        ('lottery_group_stat_turno_unique',
         'unique(group_id, sorteo_id, turno_id)',
         'Ya existe una fila de estadísticas para ese grupo, sorteo y turno.')
    ]

    @api.depends('group_id', 'sorteo_id', 'turno_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.group_id.name or ''} · {rec.sorteo_id.name or ''} · {rec.turno_id.name or ''}"

    def _recompute_for_sorteo(self, sorteo_id):
        p = {'sorteo_id': sorteo_id}
        self.env.cr.execute(
            "DELETE FROM lottery_group_stat_turno WHERE sorteo_id = %(sorteo_id)s;", p)
        self.env.cr.execute("""
            INSERT INTO lottery_group_stat_turno (
                stat_id, group_id, sorteo_id, turno_id, turno_sequence,
                total_salidas, salidas_atrasadas, ultima_fecha
            )
            SELECT
                gs.id, rel.group_id, nst.sorteo_id, nst.turno_id, MIN(nst.turno_sequence),
                SUM(nst.total_salidas), MIN(nst.total_atrasadas), MAX(nst.ultima_fecha)
            FROM lottery_group_number_rel rel
            JOIN lottery_number_stat_turno nst ON nst.number_id = rel.number_id
            LEFT JOIN lottery_group_stat gs
                ON gs.group_id = rel.group_id AND gs.sorteo_id = nst.sorteo_id
            WHERE nst.sorteo_id = %(sorteo_id)s
            GROUP BY gs.id, rel.group_id, nst.sorteo_id, nst.turno_id;
        """, p)
