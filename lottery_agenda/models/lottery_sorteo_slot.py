# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LotterySorteoSlot(models.Model):
    _inherit = 'lottery.sorteo.slot'

    # Misma forma que la hora del sorteo (Hora, Min, AM/PM) para que el
    # calendario se cargue igual. A diferencia de esa, esta es la hora de
    # Uruguay a la que hay que publicar, no la hora en que se juega.
    pub_h = fields.Selection(
        [(str(h), str(h)) for h in range(1, 13)], string='Publicar hora',
        help="Hora de Uruguay (formato de 12 horas) a la que hay que publicar este "
             "sorteo y turno. Vacía = no se crea tarea en la agenda.")
    pub_min = fields.Integer(string='Publicar min', default=0)
    pub_ampm = fields.Selection(
        [('am', 'AM'), ('pm', 'PM')], string='Publicar AM/PM', default='pm')
    hora_publicacion = fields.Float(
        string='Hora de publicar (24 h)', compute='_compute_hora_publicacion',
        store=True,
        help="Hora de Uruguay a la que se publica, como horas desde la medianoche "
             "(19.5 = 19:30). Con la hora vacía queda en 0 y significa sin tarea.")

    @api.depends('pub_h', 'pub_min', 'pub_ampm')
    def _compute_hora_publicacion(self):
        for slot in self:
            if not slot.pub_h:
                slot.hora_publicacion = 0.0
                continue
            # 12 AM = 00:xx y 12 PM = 12:xx.
            h = int(slot.pub_h) % 12 + (12 if slot.pub_ampm == 'pm' else 0)
            slot.hora_publicacion = h + (slot.pub_min or 0) / 60.0

    @api.constrains('pub_min')
    def _check_pub_min(self):
        for slot in self:
            if not 0 <= slot.pub_min <= 59:
                raise ValidationError("Los minutos de publicación deben estar entre 0 y 59.")
