"""
Migración 1.1: amplía las ventanas horarias del scraper Quiniela UY de
10 minutos (15:05–15:15 / 21:05–21:15) a 1 hora (15:00–16:00 / 21:00–22:00).

Se actualizan TODOS los registros que aún tengan los valores estrechos para
garantizar que el singleton usado por el cron quede correcto sin importar
cuál tenga id más bajo.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE lottery_scraper_quiniela_uy
        SET
            vespertina_start = 15.0,
            vespertina_end   = 16.0,
            nocturna_start   = 21.0,
            nocturna_end     = 22.0
        WHERE
            vespertina_end < 15.5
            OR nocturna_end < 21.5
    """)
    cr.execute("SELECT COUNT(*) FROM lottery_scraper_quiniela_uy WHERE vespertina_end >= 15.5")
    updated = cr.fetchone()[0]
    print(f"[migrate 1.1] Ventanas Quiniela UY actualizadas en {updated} registro(s).")
