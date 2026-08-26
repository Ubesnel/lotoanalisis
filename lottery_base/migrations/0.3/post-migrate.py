# -*- coding: utf-8 -*-
"""
Migración 0.3: lottery.tombola.output pasó de un many2many de 20 números en
una sola fila a una fila por número. El upgrade agrega la columna nueva
(number_id) pero no borra solo lo que quedó de la versión anterior:

- La constraint unique(date, turn_day) de la primera versión (un registro por
  sorteo) ya no aplica: ahora hay 20 filas por fecha+turno a propósito.
- La constraint unique(date, turn_day, number_id) de una versión intermedia
  tampoco: algunos sorteos de 2006 repiten un número dentro de los 20 (ver
  lottery_portal.tombola_stats_start_date) y hay que poder guardarlos así.
- La tabla de relación many2many queda huérfana, sin ningún campo que la use.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE lottery_tombola_output
        DROP CONSTRAINT IF EXISTS lottery_tombola_output_unique_date_turn
    """)
    cr.execute("""
        ALTER TABLE lottery_tombola_output
        DROP CONSTRAINT IF EXISTS lottery_tombola_output_unique_date_turn_number
    """)
    cr.execute("""
        DROP TABLE IF EXISTS lottery_number_lottery_tombola_output_rel
    """)
    print('[migrate lottery_base 0.3] lottery.tombola.output: constraints '
          'viejas y tabla de relación many2many eliminadas.')
