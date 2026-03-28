# -*- coding: utf-8 -*-

from odoo import models, tools
from odoo.tools import create_index


class LotteryTopAtrasosNumberGroupsMV(models.Model):
    _name = 'lottery.top.atrasos.number.groups.mv'
    _description = 'Lottery Top Atrasos Number Groups Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_number_groups_atrasos_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_number_groups_atrasos_mv AS
             SELECT
                lg.code AS group_code,
                ln.id AS number_id,
                LPAD(ln.name::text, 2, '0') AS name,
                ln.total_atrasadas AS general,
                ln.total_atrasadas_dia AS afternoon,
                ln.total_atrasadas_noche AS evening
            FROM lottery_group lg
            JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
            JOIN lottery_number ln ON ln.id = rel.number_id;          
        """)

        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_group_code ON lottery_number_groups_atrasos_mv (group_code);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_general ON lottery_number_groups_atrasos_mv (general DESC);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_afternoon ON lottery_number_groups_atrasos_mv (afternoon DESC);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_evening ON lottery_number_groups_atrasos_mv (evening DESC);""")




