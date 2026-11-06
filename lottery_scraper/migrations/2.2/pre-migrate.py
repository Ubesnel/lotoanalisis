# -*- coding: utf-8 -*-
"""Baja de los importadores reemplazados por lottery_auto_result.

Odoo no puede borrar solo las opciones de un Selection de un modelo que ya
no existe (KeyError en _process_ondelete), ni los crons noupdate de esos
modelos: se sacan acá y el resto lo limpia la actualización."""

MODELOS = (
    'lottery.scraper',
    'lottery.scraper.new.york',
    'lottery.scraper.la.primera',
    'lottery.scraper.quinielon',
    'lottery.scraper.conectate',
)


def migrate(cr, version):
    # Crons de los modelos borrados (con su acción de servidor).
    cr.execute("""
        SELECT c.id, c.ir_actions_server_id
          FROM ir_cron c
          JOIN ir_act_server a ON a.id = c.ir_actions_server_id
          JOIN ir_model m ON m.id = a.model_id
         WHERE m.model IN %s
    """, (MODELOS,))
    rows = cr.fetchall()
    if rows:
        cron_ids = tuple(r[0] for r in rows)
        action_ids = tuple(r[1] for r in rows)
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.cron' AND res_id IN %s", (cron_ids,))
        cr.execute("DELETE FROM ir_cron WHERE id IN %s", (cron_ids,))
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.actions.server' AND res_id IN %s",
                   (action_ids,))
        cr.execute("DELETE FROM ir_act_server WHERE id IN %s", (action_ids,))

    # Opciones de los Selection de esos modelos (game_code).
    cr.execute("""
        SELECT s.id
          FROM ir_model_fields_selection s
          JOIN ir_model_fields f ON f.id = s.field_id
         WHERE f.model IN %s
    """, (MODELOS,))
    sel_ids = tuple(r[0] for r in cr.fetchall())
    if sel_ids:
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.model.fields.selection' "
                   "AND res_id IN %s", (sel_ids,))
        cr.execute("DELETE FROM ir_model_fields_selection WHERE id IN %s", (sel_ids,))

    # Registros noupdate de esos modelos (las tablas se van con el modelo).
    cr.execute("DELETE FROM ir_model_data WHERE model IN %s", (MODELOS,))
