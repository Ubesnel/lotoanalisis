# -*- coding: utf-8 -*-

from odoo import tools, models

class LotteryCentenaWeekMV(models.Model):
    _name = 'lottery.centena.week.mv'
    _description = 'Lottery Centena and Bola Extra by Week Segment Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_centena_week_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_centena_week_mv AS
            SELECT
                lo.sorteo_id,
                CASE
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 1 AND 7 THEN 'sem_1'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 8 AND 14 THEN 'sem_2'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 15 AND 21 THEN 'sem_3'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 22 AND 28 THEN 'sem_4'
                    ELSE 'sem_5'
                END AS week_segment,
                'hundreds_id' AS field_type,
                ln.name AS centena,
                COUNT(*) AS total_salidas
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.hundreds_id
            GROUP BY lo.sorteo_id, week_segment, lo.hundreds_id, ln.name
            UNION ALL
            SELECT
                lo.sorteo_id,
                CASE
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 1 AND 7 THEN 'sem_1'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 8 AND 14 THEN 'sem_2'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 15 AND 21 THEN 'sem_3'
                    WHEN EXTRACT(DAY FROM lo.date) BETWEEN 22 AND 28 THEN 'sem_4'
                    ELSE 'sem_5'
                END AS week_segment,
                'fireball_id' AS field_type,
                ln.name AS centena,
                COUNT(*) AS total_salidas
            FROM lottery_output lo
            JOIN lottery_number ln ON ln.id = lo.fireball_id
            WHERE lo.fireball_id IS NOT NULL
            GROUP BY lo.sorteo_id, week_segment, lo.fireball_id, ln.name;
        """)

        self.env.cr.execute("""
            CREATE INDEX idx_centena_week_mv
            ON lottery_centena_week_mv (sorteo_id, week_segment, field_type, total_salidas DESC);
        """)
