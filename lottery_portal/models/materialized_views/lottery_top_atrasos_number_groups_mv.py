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
                ns.sorteo_id AS sorteo_id,
                ln.id AS number_id,
                LPAD(ln.name::text, 2, '0') AS name,
                ns.total_atrasadas AS general,
                ns.total_atrasadas_dia AS afternoon,
                ns.total_atrasadas_noche AS evening,
                TO_CHAR(last_out.last_date, 'DD/MM/YYYY') AS last_date,
                last_out.last_turn,
                TO_CHAR(last_out_afternoon.last_date_afternoon, 'DD/MM/YYYY') AS last_date_afternoon,
                TO_CHAR(last_out_evening.last_date_evening, 'DD/MM/YYYY') AS last_date_evening
            FROM lottery_group lg
            JOIN lottery_group_number_rel rel ON rel.group_id = lg.id
            JOIN lottery_number ln ON ln.id = rel.number_id
            JOIN lottery_number_stat ns ON ns.number_id = ln.id
            LEFT JOIN LATERAL (
                SELECT lo.date AS last_date, lo.turn_day AS last_turn
                FROM lottery_output lo
                WHERE lo.number_id = ln.id
                  AND lo.sorteo_id = ns.sorteo_id
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_out ON TRUE
            LEFT JOIN LATERAL (
                SELECT lo.date AS last_date_afternoon
                FROM lottery_output lo
                WHERE lo.number_id = ln.id AND lo.turn_day = 'afternoon'
                  AND lo.sorteo_id = ns.sorteo_id
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_out_afternoon ON TRUE
            LEFT JOIN LATERAL (
                SELECT lo.date AS last_date_evening
                FROM lottery_output lo
                WHERE lo.number_id = ln.id AND lo.turn_day = 'evening'
                  AND lo.sorteo_id = ns.sorteo_id
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_out_evening ON TRUE;
        """)

        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_group_code ON lottery_number_groups_atrasos_mv (sorteo_id, group_code);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_general ON lottery_number_groups_atrasos_mv (sorteo_id, general DESC);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_afternoon ON lottery_number_groups_atrasos_mv (sorteo_id, afternoon DESC);""")
        self.env.cr.execute("""CREATE INDEX idx_number_groups_mv_evening ON lottery_number_groups_atrasos_mv (sorteo_id, evening DESC);""")




