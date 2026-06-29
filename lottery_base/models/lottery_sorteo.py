# -*- coding: utf-8 -*-
from odoo import models, fields


class LotterySorteo(models.Model):
    _name = 'lottery.sorteo'
    _description = 'Sorteo / Juego de lotería'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True,
                       help="Identificador técnico único, usado por el scraper y por las reglas de acceso.")
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)

    uses_fireball = fields.Boolean(string='Usa Bola Extra', default=False,
                                   help="Indica si este sorteo registra número de Bola Extra.")
    enforce_turn_continuity = fields.Boolean(string='Exigir continuidad entre turnos', default=False,
                                             help="Si está activo, no se puede registrar el turno Noche sin "
                                                  "Tarde el mismo día, ni Tarde sin Noche del día anterior. "
                                                  "Pensado para sorteos con calendario diario fijo (ej. Florida).")
    source_code = fields.Char(string='Código de origen (scraper)',
                              help="Identifica qué proveedor/parser del scraper alimenta este sorteo.")

    _sql_constraints = [
        ('lottery_sorteo_code_unique', 'unique(code)', 'El código de sorteo ya existe, debe ser único.')
    ]
