# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LotteryTurno(models.Model):
    """Turno de sorteo dentro de un día (Tarde, Noche, Mediodía, ...).

    Nomenclador compartido por todos los sorteos: cada sorteo habilita los
    suyos en `lottery.sorteo.turno_ids`. La `sequence` define el orden
    cronológico dentro del día y es la que usan la continuidad entre turnos,
    el cálculo del próximo sorteo y los atrasos (orden de las salidas).

    El `code` es contrato de la API y del scraper: no cambiarlo una vez en uso.
    """
    _name = 'lottery.turno'
    _description = 'Turno de sorteo'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(string='Código', required=True,
                       help="Identificador técnico, usado por la API, la app y el scraper. "
                            "No cambiarlo una vez en uso.")
    sequence = fields.Integer(string='Secuencia', default=10,
                              help="Orden del turno dentro del día: primero el de menor secuencia.")
    active = fields.Boolean(string='Activo', default=True)
    sorteo_ids = fields.Many2many('lottery.sorteo', 'lottery_sorteo_turno_rel', 'turno_id', 'sorteo_id',
                                  string='Sorteos', help="Sorteos que tienen habilitado este turno.")

    _sql_constraints = [
        ('lottery_turno_code_unique', 'unique(code)', 'El código de turno ya existe, debe ser único.'),
        # La secuencia es el orden cronológico dentro del día: dos turnos con
        # la misma secuencia dejarían ambiguo cuál sale primero.
        ('lottery_turno_sequence_unique', 'unique(sequence)',
         'Ya hay un turno con esa secuencia: cada turno debe tener una secuencia distinta.'),
    ]

    @api.model
    def _ids_by_code(self):
        """{code: id} de todos los turnos, archivados incluidos. Para los
        importadores, que identifican el turno de cada fuente por su código."""
        return {t.code: t.id for t in self.with_context(active_test=False).search([])}
