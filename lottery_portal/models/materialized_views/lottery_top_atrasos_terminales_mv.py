# -*- coding: utf-8 -*-

from odoo import models, tools

class LotteryTopAtrasosTerminalesMV(models.Model):
    _name = 'lottery.top.atrasos.terminales.mv'
    _description = 'Lottery Top Atrasos Terminales Materialized View'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_top_atrasos_terminales_mv')

        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_top_atrasos_terminales_mv AS
            SELECT
                lg.code,
                CASE lg.code
                    WHEN 'terminal_0' THEN '00-90'
                    WHEN 'terminal_1' THEN '01-91'
                    WHEN 'terminal_2' THEN '02-92'
                    WHEN 'terminal_3' THEN '03-93'
                    WHEN 'terminal_4' THEN '04-94'
                    WHEN 'terminal_5' THEN '05-95'
                    WHEN 'terminal_6' THEN '06-96'
                    WHEN 'terminal_7' THEN '07-97'
                    WHEN 'terminal_8' THEN '08-98'
                    WHEN 'terminal_9' THEN '09-99'
                END AS name,
                lg.salidas_atrasadas AS general,
                lg.salidas_atrasadas_dia AS afternoon,
                lg.salidas_atrasadas_noche AS evening,

                last_gen.last_num                     AS last_num_general,
                to_char(last_gen.last_date,'DD/MM/YY') AS last_date_general,
                last_aft.last_num                     AS last_num_afternoon,
                to_char(last_aft.last_date,'DD/MM/YY') AS last_date_afternoon,
                last_eve.last_num                     AS last_num_evening,
                to_char(last_eve.last_date,'DD/MM/YY') AS last_date_evening,

                LPAD(max_gen.num_name::text, 2, '0') AS max_delay_num_general,
                max_gen.delay_val                    AS max_delay_val_general,
                max_gen.delay_date                   AS max_delay_date_general,
                LPAD(max_aft.num_name::text, 2, '0') AS max_delay_num_afternoon,
                max_aft.delay_val                    AS max_delay_val_afternoon,
                max_aft.delay_date                   AS max_delay_date_afternoon,
                LPAD(max_eve.num_name::text, 2, '0') AS max_delay_num_evening,
                max_eve.delay_val                    AS max_delay_val_evening,
                max_eve.delay_date                   AS max_delay_date_evening

            FROM lottery_group lg

            LEFT JOIN LATERAL (
                SELECT LPAD(ln.name::text, 2, '0') AS last_num, lo.date AS last_date
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_gen ON TRUE

            LEFT JOIN LATERAL (
                SELECT LPAD(ln.name::text, 2, '0') AS last_num, lo.date AS last_date
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                  AND lo.turn_day = 'afternoon'
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_aft ON TRUE

            LEFT JOIN LATERAL (
                SELECT LPAD(ln.name::text, 2, '0') AS last_num, lo.date AS last_date
                FROM lottery_output lo
                JOIN lottery_number ln ON ln.id = lo.number_id
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                  AND lo.turn_day = 'evening'
                ORDER BY lo.date DESC, lo.id DESC
                LIMIT 1
            ) last_eve ON TRUE

            LEFT JOIN LATERAL (
                SELECT ln.name AS num_name, ln.total_atrasadas AS delay_val,
                       to_char((SELECT MAX(lo2.date) FROM lottery_output lo2
                                WHERE lo2.number_id = ln.id), 'DD/MM/YY') AS delay_date
                FROM lottery_number ln
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                ORDER BY ln.total_atrasadas DESC
                LIMIT 1
            ) max_gen ON TRUE

            LEFT JOIN LATERAL (
                SELECT ln.name AS num_name, ln.total_atrasadas_dia AS delay_val,
                       to_char((SELECT MAX(lo2.date) FROM lottery_output lo2
                                WHERE lo2.number_id = ln.id
                                  AND lo2.turn_day = 'afternoon'), 'DD/MM/YY') AS delay_date
                FROM lottery_number ln
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                ORDER BY ln.total_atrasadas_dia DESC
                LIMIT 1
            ) max_aft ON TRUE

            LEFT JOIN LATERAL (
                SELECT ln.name AS num_name, ln.total_atrasadas_noche AS delay_val,
                       to_char((SELECT MAX(lo2.date) FROM lottery_output lo2
                                WHERE lo2.number_id = ln.id
                                  AND lo2.turn_day = 'evening'), 'DD/MM/YY') AS delay_date
                FROM lottery_number ln
                WHERE ln.name % 10 = SUBSTRING(lg.code FROM 10)::int
                ORDER BY ln.total_atrasadas_noche DESC
                LIMIT 1
            ) max_eve ON TRUE

            WHERE lg.code IN (
                'terminal_0','terminal_1','terminal_2','terminal_3','terminal_4',
                'terminal_5','terminal_6','terminal_7','terminal_8','terminal_9'
            );
        """)

        self.env.cr.execute("""CREATE INDEX idx_line_atrasos_mv_terminales ON lottery_top_atrasos_terminales_mv (general DESC);""")

