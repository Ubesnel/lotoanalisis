# -*- coding: utf-8 -*-
"""Migración 1.2: limpia constraints de unicidad huérfanas en
lottery_tabla_acompanantes_cache.

Historial del bug: la constraint de esa tabla se fue ampliando en varias
vueltas (primero sorteo+fecha, después +turno, después +grid_size). Cada
vez que se le cambió el NOMBRE en vez de mantenerlo, Odoo no reconoció que
era "la misma pero modificada" — creó la nueva con el nombre nuevo pero
dejó la vieja huérfana en la base, sin bloquear su creación pero
bloqueando igual los inserts (Postgres aplica TODAS las constraints que
existan, no solo la que Odoo cree que es la vigente).

Se corre en 'pre' (antes de que Odoo sincronice _sql_constraints en
init_models) para no pisarse con la constraint correcta que Odoo va a
crear/actualizar automáticamente después con el nombre único de siempre
('unique_sorteo_fecha'), a partir de _sql_constraints en
lottery_tabla_acompanantes_cache.py.

Nombres huérfanos conocidos, de vueltas anteriores mientras se armaba el
wizard Tabla LotoAnálisis (fuera de producción, solo en bases de
desarrollo donde se fue probando):
- lottery_tabla_acompanantes_cache_unique_sorteo_fecha_turno
"""

ORPHAN_CONSTRAINTS = [
    'lottery_tabla_acompanantes_cache_unique_sorteo_fecha_turno',
]


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'lottery_tabla_acompanantes_cache'
    """)
    if not cr.fetchone():
        return  # instalación nueva: la tabla todavía no existe, nada que limpiar

    for conname in ORPHAN_CONSTRAINTS:
        cr.execute(
            'ALTER TABLE lottery_tabla_acompanantes_cache '
            f'DROP CONSTRAINT IF EXISTS "{conname}"'
        )
    print(f"[migrate lottery_portal 1.2] limpiadas {len(ORPHAN_CONSTRAINTS)} "
          f"constraint(s) huérfana(s) de lottery_tabla_acompanantes_cache.")
