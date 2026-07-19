# -*- coding: utf-8 -*-
"""
Migración 1.1: se agrega el campo 'published' a lottery.prediction (y al
nuevo lottery.curiosity.day). La API de Números Mágicos ahora solo devuelve
predicciones publicadas, así que las predicciones existentes se marcan como
publicadas para que la app siga mostrando exactamente lo mismo que antes.
Las nuevas nacen sin publicar y se publican a mano cuando estén listas.
"""


def migrate(cr, version):
    cr.execute("UPDATE lottery_prediction SET published = TRUE")
    print(f"[migrate lottery_portal 1.1] {cr.rowcount} predicción(es) "
          f"existente(s) marcadas como publicadas.")
