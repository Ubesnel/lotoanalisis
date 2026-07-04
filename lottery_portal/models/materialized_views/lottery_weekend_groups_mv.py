# -*- coding: utf-8 -*-

from odoo import models, tools


class LotteryWeekendGroupsMV(models.Model):
    _name = 'lottery.weekend.groups.mv'
    _description = 'Lottery Weekend Groups Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_weekend_groups_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_weekend_groups_mv AS
            WITH weekend_draws AS (
                SELECT lo.turn_day, lo.sorteo_id, lg.code AS grp_code,
                       CASE WHEN lg.code LIKE 'line_%' THEN 'line' ELSE 'terminal' END AS grp_type
                FROM lottery_output lo
                JOIN lottery_number ln  ON ln.id  = lo.number_id
                JOIN lottery_group_number_rel rel ON rel.number_id = ln.id
                JOIN lottery_group lg ON lg.id = rel.group_id
                WHERE (lg.code LIKE 'line_%' OR lg.code LIKE 'terminal_%')
                  AND EXTRACT(DOW FROM lo.date) IN (0, 6)
            )
            SELECT
                sorteo_id,
                grp_type,
                grp_code,
                COUNT(*)                                        AS total_general,
                COUNT(*) FILTER (WHERE turn_day = 'afternoon') AS total_afternoon,
                COUNT(*) FILTER (WHERE turn_day = 'evening')   AS total_evening
            FROM weekend_draws
            GROUP BY sorteo_id, grp_type, grp_code;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_weekend_groups_mv_type
            ON lottery_weekend_groups_mv (sorteo_id, grp_type, total_general DESC);
        """)
