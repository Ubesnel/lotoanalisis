# -*- coding: utf-8 -*-
from odoo import fields, models


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    auto_result = fields.Boolean(
        string='Registrar resultados automáticos', default=False,
        help="El cron consulta las fuentes web configuradas cada 5 minutos y registra "
             "la salida del próximo sorteo apenas se publica.")
    auto_result_push = fields.Boolean(
        string='Enviar notificación al registrar', default=False,
        help="Manda el push de la salida registrada automáticamente (solo si el sorteo "
             "se muestra en la app).")
    auto_result_line_ids = fields.One2many(
        'lottery.result.source.line', 'sorteo_id', string='Fuentes de resultados')
