# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

# Solo las salidas recientes tocan la agenda: una importación histórica de
# miles de filas no debe buscar un evento por cada una.
DIAS_RECIENTES = 3


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    @api.model_create_multi
    def create(self, vals_list):
        outputs = super().create(vals_list)
        outputs._agenda_cerrar()
        return outputs

    def unlink(self):
        claves = self._agenda_claves()
        res = super().unlink()
        self.env['lottery.output']._agenda_reabrir(claves)
        return res

    def _agenda_claves(self):
        limite = fields.Date.today() - timedelta(days=DIAS_RECIENTES)
        return {(o.sorteo_id.id, o.turno_id.id, o.date)
                for o in self if o.date and o.date >= limite}

    def _agenda_eventos(self, claves, **dominio_extra):
        Event = self.env['calendar.event'].sudo().with_context(active_test=False)
        eventos = Event
        for sorteo_id, turno_id, fecha in claves:
            eventos |= Event.search([
                ('lottery_sorteo_id', '=', sorteo_id),
                ('lottery_turno_id', '=', turno_id),
                ('lottery_date', '=', fecha),
            ] + list(dominio_extra.get('dominio', [])))
        return eventos

    def _agenda_cerrar(self):
        """Marca como hechas las tareas de la agenda de estas salidas."""
        claves = self._agenda_claves()
        if claves:
            self._agenda_eventos(
                claves, dominio=[('lottery_state', '!=', 'done')])._lottery_set_state('done')

    @api.model
    def _agenda_reabrir(self, claves):
        """Si se borró una salida y ya no queda otra para ese sorteo, turno y
        fecha, la tarea vuelve a estar pendiente (o atrasada si ya pasó)."""
        Output = self.env['lottery.output'].sudo()
        sin_salida = {c for c in claves if not Output.search_count([
            ('sorteo_id', '=', c[0]), ('turno_id', '=', c[1]), ('date', '=', c[2])])}
        if sin_salida:
            self._agenda_eventos(
                sin_salida, dominio=[('lottery_state', '=', 'done')]).action_lottery_reabrir()
