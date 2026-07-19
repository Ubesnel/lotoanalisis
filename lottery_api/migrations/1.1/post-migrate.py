# -*- coding: utf-8 -*-
"""
Migración 1.1: la "Tabla del Próximo Sorteo" deja de ser un parámetro global
(ir.config_parameter 'lottery_api.proximo_sorteo_tabla' desde Ajustes) y pasa
a ser un campo por sorteo (lottery.sorteo.proximo_tabla_app), porque cada
sorteo puede mostrar una tabla distinta en la app.

Se copia el valor global vigente a TODOS los sorteos (así la app sigue viendo
exactamente lo mismo que antes) y se elimina el parámetro obsoleto.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT value FROM ir_config_parameter
        WHERE key = 'lottery_api.proximo_sorteo_tabla'
    """)
    row = cr.fetchone()
    valor = row[0] if row else None

    if valor in ('calientes', 'restantes', 'frios'):
        cr.execute("UPDATE lottery_sorteo SET proximo_tabla_app = %s", (valor,))
    elif valor == 'none':
        # 'none' era el truco del selection global para ocultar la sección;
        # en el campo por sorteo eso ahora es simplemente NULL.
        cr.execute("UPDATE lottery_sorteo SET proximo_tabla_app = NULL")
    # Sin parámetro guardado → queda el default del campo ('restantes'),
    # que era también el default del parámetro.

    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key = 'lottery_api.proximo_sorteo_tabla'
    """)
    print(f"[migrate lottery_api 1.1] Tabla Próximo Sorteo por sorteo "
          f"(valor global migrado: {valor!r}).")
