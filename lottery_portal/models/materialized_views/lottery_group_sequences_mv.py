# -*- coding: utf-8 -*-

from odoo import models, tools


class LotteryGroupSequencesMV(models.Model):
    _name = 'lottery.group.sequences.mv'
    _description = 'Lottery Group Sequences Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_group_sequences_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_group_sequences_mv AS
            WITH line_draws AS (
                SELECT lo.date, lo.id, lo.turn_day, lo.sorteo_id, lg.code AS grp_code
                FROM lottery_output lo
                JOIN lottery_number ln  ON ln.id  = lo.number_id
                JOIN lottery_group_number_rel rel ON rel.number_id = ln.id
                JOIN lottery_group lg ON lg.id = rel.group_id
                WHERE lg.code LIKE 'line_%'
            ),
            terminal_draws AS (
                SELECT lo.date, lo.id, lo.turn_day, lo.sorteo_id, lg.code AS grp_code
                FROM lottery_output lo
                JOIN lottery_number ln  ON ln.id  = lo.number_id
                JOIN lottery_group_number_rel rel ON rel.number_id = ln.id
                JOIN lottery_group lg ON lg.id = rel.group_id
                WHERE lg.code LIKE 'terminal_%'
            ),
            line_gen AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM line_draws
                ) s WHERE to_code IS NOT NULL
            ),
            line_aft AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM line_draws WHERE turn_day = 'afternoon'
                ) s WHERE to_code IS NOT NULL
            ),
            line_eve AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM line_draws WHERE turn_day = 'evening'
                ) s WHERE to_code IS NOT NULL
            ),
            term_gen AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM terminal_draws
                ) s WHERE to_code IS NOT NULL
            ),
            term_aft AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM terminal_draws WHERE turn_day = 'afternoon'
                ) s WHERE to_code IS NOT NULL
            ),
            term_eve AS (
                SELECT sorteo_id, from_code, to_code FROM (
                    SELECT sorteo_id, grp_code AS from_code,
                           LEAD(grp_code) OVER (PARTITION BY sorteo_id ORDER BY date, id) AS to_code
                    FROM terminal_draws WHERE turn_day = 'evening'
                ) s WHERE to_code IS NOT NULL
            ),
            all_pairs AS (
                SELECT sorteo_id, 'line'     AS grp_type, from_code, to_code, 'general'   AS turn FROM line_gen
                UNION ALL
                SELECT sorteo_id, 'line',     from_code, to_code, 'afternoon' FROM line_aft
                UNION ALL
                SELECT sorteo_id, 'line',     from_code, to_code, 'evening'   FROM line_eve
                UNION ALL
                SELECT sorteo_id, 'terminal', from_code, to_code, 'general'   FROM term_gen
                UNION ALL
                SELECT sorteo_id, 'terminal', from_code, to_code, 'afternoon' FROM term_aft
                UNION ALL
                SELECT sorteo_id, 'terminal', from_code, to_code, 'evening'   FROM term_eve
            )
            SELECT
                sorteo_id,
                grp_type,
                from_code,
                to_code,
                COUNT(*) FILTER (WHERE turn = 'general')   AS total_general,
                COUNT(*) FILTER (WHERE turn = 'afternoon') AS total_afternoon,
                COUNT(*) FILTER (WHERE turn = 'evening')   AS total_evening
            FROM all_pairs
            GROUP BY sorteo_id, grp_type, from_code, to_code;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_grp_seq_mv_type_from
            ON lottery_group_sequences_mv (sorteo_id, grp_type, from_code);
        """)
