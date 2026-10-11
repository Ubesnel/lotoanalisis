# -*- coding: utf-8 -*-

from odoo import tools, models


class LotteryDigitoAtrasoMV(models.Model):
    """Atraso de cada dígito de centena y de bola extra, por sorteo: general
    (turno_id NULL) y por cada turno con salidas. Reemplaza a las 6 vistas
    fijas top5_centena/bola_extra general/día/noche.

    El atraso se cuenta en sorteos: en la general, sorteos de cualquier turno
    en orden cronológico (fecha + secuencia del turno); por turno, sorteos de
    ESE turno. La bola extra solo cuenta sorteos que la registraron. Un
    dígito que nunca salió no aparece (no hay de dónde anclar el atraso)."""
    _name = 'lottery.digito.atraso.mv'
    _description = 'Atraso de dígitos de centena y bola extra'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'lottery_digito_atraso_mv')
        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW lottery_digito_atraso_mv AS
            WITH base AS (
                SELECT sorteo_id, turno_id, turno_sequence, date, id,
                       'centena'::varchar AS tipo, hundreds_id AS digito_id
                FROM lottery_output
                WHERE hundreds_id IS NOT NULL
                UNION ALL
                SELECT sorteo_id, turno_id, turno_sequence, date, id,
                       'bola_extra'::varchar AS tipo, fireball_id AS digito_id
                FROM lottery_output
                WHERE fireball_id IS NOT NULL
            ),
            numerado AS (
                SELECT sorteo_id, NULL::integer AS turno_id, tipo, digito_id,
                       ROW_NUMBER() OVER (PARTITION BY sorteo_id, tipo
                                          ORDER BY date, turno_sequence, id) AS n
                FROM base
                UNION ALL
                SELECT sorteo_id, turno_id, tipo, digito_id,
                       ROW_NUMBER() OVER (PARTITION BY sorteo_id, turno_id, tipo
                                          ORDER BY date, id) AS n
                FROM base
            ),
            ultima AS (
                SELECT sorteo_id, turno_id, tipo, digito_id, MAX(n) AS ultima_n
                FROM numerado
                GROUP BY sorteo_id, turno_id, tipo, digito_id
            ),
            total AS (
                SELECT sorteo_id, turno_id, tipo, MAX(n) AS total_n
                FROM numerado
                GROUP BY sorteo_id, turno_id, tipo
            )
            SELECT
                u.sorteo_id, u.turno_id, u.tipo,
                num.name AS digito,
                t.total_n - u.ultima_n AS atraso
            FROM ultima u
            JOIN total t ON t.sorteo_id = u.sorteo_id AND t.tipo = u.tipo
                        AND t.turno_id IS NOT DISTINCT FROM u.turno_id
            JOIN lottery_number num ON num.id = u.digito_id;
        """)
        self.env.cr.execute("""
            CREATE INDEX idx_digito_atraso_mv
            ON lottery_digito_atraso_mv (sorteo_id, tipo, turno_id, atraso DESC);
        """)
