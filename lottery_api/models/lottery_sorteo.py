# -*- coding: utf-8 -*-
from odoo import fields, models


class LotterySorteo(models.Model):
    _inherit = 'lottery.sorteo'

    show_in_app = fields.Boolean(
        string='Mostrar en apk LotoAnálisis',
        default=False,
        help="Si está activo, este sorteo aparece en el selector de sorteos "
             "de la app móvil LotoAnálisis y sus análisis quedan disponibles "
             "vía la API pública.",
    )
    auto_prediction = fields.Boolean(
        string='Generar predicciones automáticamente',
        default=False,
        help="Un cron revisa cada pocos minutos: cuando se registró una salida "
             "hace más de los minutos de espera y todavía no existe la "
             "predicción del próximo sorteo, la crea sola con la temperatura "
             "Restantes, completa los números y elige el algoritmo según las "
             "dos últimas salidas (comparten dígito → Algoritmo 1; no → 2). "
             "Si ya hay una predicción cargada a mano, no la toca.",
    )
    auto_prediction_publish = fields.Boolean(
        string='Publicar y notificar',
        default=False,
        help="Activo: la predicción automática se publica y manda la "
             "notificación push (si el sorteo se muestra en la app). "
             "Apagado: queda creada y sin publicar para revisarla.",
    )
    auto_prediction_delay = fields.Integer(
        string='Minutos de espera',
        default=30,
        help="Minutos que deben pasar desde que se registró la última "
             "salida antes de generar la predicción.",
    )
    auto_prediction_error = fields.Text(
        string='Último error automático',
        readonly=True,
        copy=False,
        help="Por qué no pudo generarse la última predicción automática. "
             "Se borra solo cuando una sale bien.",
    )
    proximo_tabla_app = fields.Selection(
        [
            ('calientes', 'Calientes'),
            ('restantes', 'Restantes'),
            ('frios', 'Fríos'),
        ],
        string='Tabla del Próximo Sorteo (app móvil)',
        default='restantes',
        help="Ranking de referencia para el próximo sorteo de este sorteo: "
             "Calientes, Restantes o Fríos. La app móvil ya no lo consume "
             "(la sección 'Próximo Sorteo' se retiró); queda como dato de "
             "referencia en la ficha.",
    )
