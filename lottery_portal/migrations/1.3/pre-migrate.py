# -*- coding: utf-8 -*-
"""Migración 1.3: `terna` en lottery.prediction.terna pasa de Integer a
Char (un Integer se comía el 0 a la izquierda: 098 quedaba guardado y
mostrado como 98).

Antes de que Odoo haga el ALTER COLUMN de integer a varchar, hay que tirar
la constraint CHECK vieja (terna_range, escrita para el tipo integer:
CHECK(terna >= 0 AND terna <= 999)). Postgres no puede revalidarla contra
varchar al cambiar el tipo de columna ("operator does not exist: character
varying >= integer") y el ALTER falla. La validación de formato (3 dígitos)
ahora la hace un @api.constrains en Python, así que esta constraint no se
vuelve a crear.

Se corre en 'pre' por el mismo motivo que la migración 1.2 de este módulo:
antes de que Odoo sincronice _sql_constraints en init_models.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'lottery_prediction_terna'
    """)
    if not cr.fetchone():
        return  # instalación nueva: la tabla todavía no existe, nada que limpiar

    cr.execute("""
        ALTER TABLE lottery_prediction_terna
        DROP CONSTRAINT IF EXISTS lottery_prediction_terna_terna_range
    """)
    print("[migrate lottery_portal 1.3] tirada la constraint CHECK vieja de "
          "terna (integer) antes de convertir la columna a varchar.")
