# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api

# Orden de turnos dentro de un día: primero tarde, luego noche.
TURN_ORDER = ['afternoon', 'evening']


class LotterySorteoSlot(models.Model):
    _name = 'lottery.sorteo.slot'
    _description = 'Slot del calendario de un sorteo (día de semana + turno)'
    _order = 'dow, turn'

    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                ondelete='cascade', index=True)
    dow = fields.Selection([
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
        ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo'),
    ], string='Día de la semana', required=True)
    turn = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno', required=True)

    _sql_constraints = [
        ('lottery_sorteo_slot_unique', 'unique(sorteo_id, dow, turn)',
         'Ese día/turno ya está en el calendario del sorteo.'),
    ]


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

    # ── Calendario semanal ────────────────────────────────────────
    slot_ids = fields.One2many('lottery.sorteo.slot', 'sorteo_id', string='Calendario (días y turnos)',
                               help="Días de la semana y turnos en que este sorteo se juega. "
                                    "Se usa para calcular automáticamente el próximo sorteo. "
                                    "Vacío = se asume todos los días, ambos turnos.")

    # ── Próximo sorteo (fuente de verdad para el portal y la validación) ──
    next_draw_date = fields.Date(string='Próximo sorteo · Fecha',
                                 help="Fecha del próximo sorteo a jugarse. Se recalcula automáticamente "
                                      "a partir de la última salida registrada y el calendario. Editable "
                                      "manualmente para excepciones (feriados, suspensiones).")
    next_draw_turn = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Próximo sorteo · Turno')
    next_draw_manual = fields.Boolean(string='Próximo sorteo definido manualmente', default=False,
                                      help="Si está activo, el próximo sorteo no se recalcula automáticamente "
                                           "hasta que se registre la salida que coincide con lo definido.")

    _sql_constraints = [
        ('lottery_sorteo_code_unique', 'unique(code)', 'El código de sorteo ya existe, debe ser único.')
    ]

    # ── Cálculo del próximo sorteo ─────────────────────────────────

    def _enabled_slots(self):
        """Set de (dow_int, turn) habilitados. Vacío → todos los días, ambos turnos."""
        self.ensure_one()
        if not self.slot_ids:
            return {(d, t) for d in range(7) for t in TURN_ORDER}
        return {(int(s.dow), s.turn) for s in self.slot_ids}

    def _next_slot(self, from_date, from_turn):
        """Dado (fecha, turno), devuelve el próximo (fecha, turno) habilitado en
        el calendario. Avanza tarde→noche mismo día, noche→tarde día siguiente,
        saltando los slots no habilitados (ej. sábado tarde / domingo)."""
        self.ensure_one()
        enabled = self._enabled_slots()
        d, t = from_date, from_turn
        for _ in range(15):  # tope de ~2 semanas para evitar bucle infinito
            if t == 'afternoon':
                t = 'evening'
            else:
                t = 'afternoon'
                d = d + timedelta(days=1)
            if (d.weekday(), t) in enabled:
                return d, t
        return from_date, from_turn

    def _recompute_next_draw(self):
        """Recalcula next_draw desde la última salida registrada (si no es manual)."""
        Output = self.env['lottery.output']
        for sorteo in self:
            if sorteo.next_draw_manual:
                continue
            last = Output.search([('sorteo_id', '=', sorteo.id)],
                                 order='date desc, id desc', limit=1)
            if not last:
                continue
            nd, nt = sorteo._next_slot(last.date, last.turn_day)
            sorteo.with_context(recomputing_next_draw=True).write({
                'next_draw_date': nd,
                'next_draw_turn': nt,
            })

    def _on_output_registered(self, draw_date, draw_turn):
        """Llamado al crear una salida: consume el override manual si coincide,
        luego recalcula el próximo sorteo."""
        for sorteo in self:
            if (sorteo.next_draw_manual
                    and sorteo.next_draw_date == draw_date
                    and sorteo.next_draw_turn == draw_turn):
                sorteo.next_draw_manual = False
            sorteo._recompute_next_draw()

    def get_next_draw(self):
        """(fecha_str, turno) del próximo sorteo. Fuente única para portal y
        validación. Si no está seteado, lo deriva de la última salida."""
        self.ensure_one()
        if self.next_draw_date and self.next_draw_turn:
            return str(self.next_draw_date), self.next_draw_turn
        last = self.env['lottery.output'].search(
            [('sorteo_id', '=', self.id)], order='date desc, id desc', limit=1)
        if last:
            nd, nt = self._next_slot(last.date, last.turn_day)
            return str(nd), nt
        return str(fields.Date.today()), 'afternoon'

    # ── Edición manual: marcar como manual salvo que sea un recálculo ──

    def write(self, vals):
        touches_next = 'next_draw_date' in vals or 'next_draw_turn' in vals
        if touches_next and not self.env.context.get('recomputing_next_draw') \
                and 'next_draw_manual' not in vals:
            vals['next_draw_manual'] = True
        return super().write(vals)
