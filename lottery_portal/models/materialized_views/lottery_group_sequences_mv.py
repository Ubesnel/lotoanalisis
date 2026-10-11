# -*- coding: utf-8 -*-

from odoo import models, tools


class LotteryGroupSequencesMV(models.Model):
    """Cuántas veces a una línea (o terminal) le siguió cada otra en el
    sorteo siguiente: en general (turno_id NULL, sorteos de todos los turnos
    en orden fecha + secuencia del turno) y dentro de cada turno."""
    _name = 'lottery.group.sequences.mv'
    _description = 'Lottery Group Sequences Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_group_sequences_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_group_sequences_mv AS
            WITH draws AS (
                SELECT lo.date, lo.id, lo.turno_id, lo.turno_sequence, lo.sorteo_id,
                       lg.code AS grp_code,
                       CASE WHEN lg.code LIKE 'line\\_%' THEN 'line' ELSE 'terminal' END AS grp_type
                FROM lottery_output lo
                JOIN lottery_group_number_rel rel ON rel.number_id = lo.number_id
                JOIN lottery_group lg ON lg.id = rel.group_id
                WHERE lg.code LIKE 'line\\_%' OR lg.code LIKE 'terminal\\_%'
            ),
            pairs AS (
                SELECT sorteo_id, NULL::integer AS turno_id, grp_type, grp_code AS from_code,
                       LEAD(grp_code) OVER (PARTITION BY sorteo_id, grp_type
                                            ORDER BY date, turno_sequence, id) AS to_code
                FROM draws
                UNION ALL
                SELECT sorteo_id, turno_id, grp_type, grp_code,
                       LEAD(grp_code) OVER (PARTITION BY sorteo_id, turno_id, grp_type
                                            ORDER BY date, id)
                FROM draws
            )
            SELECT sorteo_id, turno_id, grp_type, from_code, to_code, COUNT(*) AS total
            FROM pairs
            WHERE to_code IS NOT NULL
            GROUP BY sorteo_id, turno_id, grp_type, from_code, to_code;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_grp_seq_mv_type_from
            ON lottery_group_sequences_mv (sorteo_id, grp_type, from_code);
        """)
