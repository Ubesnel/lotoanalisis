# -*- coding: utf-8 -*-
"""Refactor de turnos (turn_day → lottery.turno), paso previo.

Las vistas materializadas viejas leen lottery_output.turn_day y tienen el
día/noche como columnas. Se tiran todas antes de cargar los módulos: las 4
que siguen existiendo las vuelve a crear su init() con el esquema nuevo, y
las otras 15 dejaron de existir."""

OLD_MVS = [
    'lottery_centena_week_mv',
    'lottery_centena_weekday_mv',
    'lottery_group_analysis_mv',
    'lottery_group_sequences_mv',
    'lottery_number_groups_atrasos_mv',
    'lottery_top10_afternoon_mv',
    'lottery_top10_dia_semana_mv',
    'lottery_top10_evening_mv',
    'lottery_top10_mv',
    'lottery_top5_bola_extra_dia_mv',
    'lottery_top5_bola_extra_general_mv',
    'lottery_top5_bola_extra_noche_mv',
    'lottery_top5_centena_dia_mv',
    'lottery_top5_centena_general_mv',
    'lottery_top5_centena_noche_mv',
    'lottery_top_atrasos_lineas_mv',
    'lottery_top_atrasos_terminales_mv',
    'lottery_ultima_salida_dia_semana_mv',
    'lottery_weekend_groups_mv',
]


# Opciones de Selection que dejan de existir. Odoo las borra al final del -u
# y en dos casos revienta: si el campo pasó a Char ('Char' object has no
# attribute 'ondelete') o si el modelo ya no existe (KeyError: 'news.article').
# Se borran antes; los campos y modelos los limpia Odoo después.
# (modelo, campo); campo None = todos los del modelo.
SELECCIONES_ELIMINADAS = [
    ('lottery.tabla.acompanantes.cache', 'turno'),   # Selection → Char
    ('lottery.tabla.acompanantes', 'turno'),
    ('lottery.output', 'turn_day'),
    ('lottery.tombola.output', 'turn_day'),
    ('lottery.prediction', 'turn_day'),
    ('lottery.prediction.tombola.uy', 'turn_day'),
    ('lottery.quiniela.uy.resultados', 'turn_day'),
    ('lottery.quiniela.uy.ternas', 'turn_day'),
    ('lottery.sorteo', 'next_draw_turn'),
    ('lottery.sorteo.slot', 'turn'),
    ('news.article', None),
    ('news.category', None),
    ('news.comment', None),
]


def migrate(cr, version):
    if not version:
        return
    for mv in OLD_MVS:
        cr.execute(f'DROP MATERIALIZED VIEW IF EXISTS {mv} CASCADE')

    for model, field in SELECCIONES_ELIMINADAS:
        cr.execute("""
            SELECT s.id FROM ir_model_fields_selection s
            JOIN ir_model_fields f ON f.id = s.field_id
            WHERE f.model = %s AND (%s IS NULL OR f.name = %s)
        """, (model, field, field))
        ids = tuple(r[0] for r in cr.fetchall())
        if ids:
            cr.execute("DELETE FROM ir_model_data "
                       "WHERE model = 'ir.model.fields.selection' AND res_id IN %s", (ids,))
            cr.execute("DELETE FROM ir_model_fields_selection WHERE id IN %s", (ids,))
