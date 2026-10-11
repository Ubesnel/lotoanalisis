# -*- coding: utf-8 -*-
"""Refactor de turnos (turn_day → lottery.turno), sobre una base con datos.

Corre al final del -u, con todos los módulos ya cargados: las columnas
turno_id nuevas existen y las viejas (turn_day y compañía) todavía no se
borraron. Pasa el turno viejo al nuevo por código ('afternoon'/'evening'
son los mismos códigos), deja las estadísticas vacías y los sorteos marcados
para recálculo, y borra las columnas viejas.

Después del -u hay que recalcular (setup\\migracion_turnos\\
recalcular_stats_shell.py), igual que en una base nueva con datos copiados.

Cualquier inconsistencia levanta una excepción: el -u entero se revierte."""
import logging

_logger = logging.getLogger(__name__)

# tabla: (columna vieja, tiene turno_sequence)
TURNO_TABLES = {
    'lottery_output': ('turn_day', True),
    'lottery_tombola_output': ('turn_day', True),
    'lottery_prediction': ('turn_day', True),
    'lottery_prediction_tombola_uy': ('turn_day', True),
    'lottery_sorteo_slot': ('turn', False),
}

# Asistentes (TransientModel): no guardan nada que valga la pena migrar.
TRANSIENT_TABLES = {
    'lottery_quiniela_uy_resultados': 'turn_day',
    'lottery_quiniela_uy_ternas': 'turn_day',
    'lottery_tabla_acompanantes': 'turno',
}

# Estadísticas: el día/noche pasa a filas por turno (tablas *_turno). Se
# vacían y se recalculan enteras con el código nuevo.
STAT_TABLES = {
    'lottery_number_stat': ['total_atrasadas_dia', 'total_atrasadas_noche',
                            'total_salidas_dia', 'total_salidas_noche'],
    'lottery_group_stat': ['salidas_atrasadas_dia', 'salidas_atrasadas_noche',
                           'total_salidas_dia', 'total_salidas_noche'],
    'lottery_tombola_number_stat': ['total_atrasadas_dia', 'total_atrasadas_noche',
                                    'total_salidas_dia', 'total_salidas_noche'],
}


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT code, id, sequence FROM lottery_turno")
    turnos = {code: (tid, seq) for code, tid, seq in cr.fetchall()}
    for code in ('afternoon', 'evening'):
        if code not in turnos:
            raise Exception(f"Falta el turno '{code}' (data de lottery_base)")

    # ── Turno de cada registro, por código ──────────────────────────────
    for table, (old, has_seq) in TURNO_TABLES.items():
        if not _column_exists(cr, table, old):
            continue
        cr.execute(f"SELECT DISTINCT {old} FROM {table} WHERE {old} IS NOT NULL")
        desconocidos = [c for (c,) in cr.fetchall() if c not in turnos]
        if desconocidos:
            raise Exception(f"{table}.{old} tiene turnos sin equivalente: {desconocidos}")
        seq_set = ", turno_sequence = t.sequence" if has_seq else ""
        cr.execute(f"""
            UPDATE {table} x SET turno_id = t.id{seq_set}
            FROM lottery_turno t
            WHERE t.code = x.{old}
        """)
        _logger.info("Turnos: %s registros de %s", cr.rowcount, table)
        cr.execute(f"SELECT count(*) FROM {table} WHERE turno_id IS NULL")
        sin_turno = cr.fetchone()[0]
        if sin_turno:
            raise Exception(f"{table}: {sin_turno} registros quedaron sin turno")
        cr.execute(f'ALTER TABLE {table} ALTER COLUMN turno_id SET NOT NULL')
        cr.execute(f'ALTER TABLE {table} DROP COLUMN {old}')

    # ── Turnos habilitados de los sorteos que ya existían ───────────────
    # Los sorteos vienen de data noupdate: a los existentes el -u no les
    # carga turno_ids. Se habilitan los turnos que ya usan (salidas,
    # calendario, predicciones) y, si no usan ninguno, tarde y noche.
    cr.execute("""
        INSERT INTO lottery_sorteo_turno_rel (sorteo_id, turno_id)
        SELECT s.id, u.turno_id
        FROM lottery_sorteo s
        JOIN (
            SELECT sorteo_id, turno_id FROM lottery_output
            UNION SELECT sorteo_id, turno_id FROM lottery_sorteo_slot
            UNION SELECT sorteo_id, turno_id FROM lottery_prediction
        ) u ON u.sorteo_id = s.id
        WHERE NOT EXISTS (SELECT 1 FROM lottery_sorteo_turno_rel r WHERE r.sorteo_id = s.id)
        ON CONFLICT DO NOTHING
    """)
    cr.execute("""
        INSERT INTO lottery_sorteo_turno_rel (sorteo_id, turno_id)
        SELECT s.id, t.id
        FROM lottery_sorteo s, lottery_turno t
        WHERE t.code IN ('afternoon', 'evening')
          AND NOT EXISTS (SELECT 1 FROM lottery_sorteo_turno_rel r WHERE r.sorteo_id = s.id)
    """)

    if _column_exists(cr, 'lottery_sorteo', 'next_draw_turn'):
        cr.execute("""
            UPDATE lottery_sorteo s SET next_draw_turno_id = t.id
            FROM lottery_turno t WHERE t.code = s.next_draw_turn
        """)
        cr.execute('ALTER TABLE lottery_sorteo DROP COLUMN next_draw_turn')

    for table, old in TRANSIENT_TABLES.items():
        if _column_exists(cr, table, old):
            cr.execute(f'DELETE FROM {table}')
            cr.execute(f'ALTER TABLE {table} DROP COLUMN {old}')

    # ── Estadísticas: vacías y pendientes de recálculo ──────────────────
    for table, old_cols in STAT_TABLES.items():
        cr.execute(f'DELETE FROM {table}')  # cascade: tablas *_turno
        for col in old_cols:
            if _column_exists(cr, table, col):
                cr.execute(f'ALTER TABLE {table} DROP COLUMN {col}')

    # Noticias (borradas del código) y la m2m vieja de la tómbola: Odoo saca
    # los modelos pero deja las tablas.
    cr.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND (table_name LIKE 'news\\_%%' OR table_name = 'lottery_prediction_tombola_number_rel')
    """)
    for (table,) in cr.fetchall():
        cr.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    cr.execute('DELETE FROM lottery_stats_dirty')
    cr.execute("""
        INSERT INTO lottery_stats_dirty (sorteo_id)
        SELECT DISTINCT sorteo_id FROM lottery_output
    """)
    _logger.info("Sorteos marcados para recálculo: %s", cr.rowcount)
