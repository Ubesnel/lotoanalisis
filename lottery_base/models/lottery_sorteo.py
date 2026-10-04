# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LotterySorteoSlot(models.Model):
    _name = 'lottery.sorteo.slot'
    _description = 'Slot del calendario de un sorteo (día de semana + turno)'
    _order = 'dow, turno_id'

    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                ondelete='cascade', index=True)
    dow = fields.Selection([
        ('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'),
        ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo'),
    ], string='Día de la semana', required=True)
    turno_id = fields.Many2one('lottery.turno', string='Turno', required=True, ondelete='restrict',
                               domain="[('id', 'in', sorteo_turno_ids)]")
    sorteo_turno_ids = fields.Many2many(related='sorteo_id.turno_ids', string='Turnos del sorteo')

    _sql_constraints = [
        ('lottery_sorteo_slot_unique', 'unique(sorteo_id, dow, turno_id)',
         'Ese día/turno ya está en el calendario del sorteo.'),
    ]

    @api.constrains('turno_id', 'sorteo_id')
    def _check_turno_del_sorteo(self):
        for slot in self:
            if slot.turno_id not in slot.sorteo_id.turno_ids:
                raise ValidationError(
                    "El turno %s no está habilitado en el sorteo %s."
                    % (slot.turno_id.name, slot.sorteo_id.name))


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
    country_id = fields.Many2one(
        'res.country', string='País',
        help="País de la lotería. La app agrupa los sorteos por país en el "
             "selector. Se envía solo el código ISO: el nombre y la bandera "
             "los resuelve la app, que ya es bilingüe.")
    country_code = fields.Char(related='country_id.code', string='Código ISO', store=False)

    uses_hundreds = fields.Boolean(string='Usa Centena', default=True,
                                   help="Indica si este sorteo registra Centena. Desactivalo para sorteos "
                                        "cuyo número es de 2 dígitos (00-99) y no tienen centena, como "
                                        "La Primera, La Suerte o los Pick 2. Con el campo desactivado la "
                                        "centena no se pide al registrar la salida ni se muestra en el "
                                        "portal ni en la app.")
    enforce_turn_continuity = fields.Boolean(string='Exigir continuidad entre turnos', default=False,
                                             help="Si está activo, no se puede registrar el turno Noche sin "
                                                  "Tarde el mismo día, ni Tarde sin Noche del día anterior. "
                                                  "Pensado para sorteos con calendario diario fijo (ej. Florida).")
    source_code = fields.Char(string='Código de origen (scraper)',
                              help="Identifica qué proveedor/parser del scraper alimenta este sorteo.")
    show_in_public = fields.Boolean(
        string='Mostrar en búsqueda pública',
        default=False,
        help="Si está activo, este sorteo aparece en el selector de la página pública de búsqueda de salidas históricoas.",
    )
    is_pick3 = fields.Boolean(
        string='Números corridos',
        default=False,
        help="Indica que este sorteo es de tipo Pick3 (3 premios). Habilita los campos Premio 2 y Premio 3 en el registro de salidas.",
    )

    # ── Turnos y calendario semanal ───────────────────────────────
    turno_ids = fields.Many2many('lottery.turno', 'lottery_sorteo_turno_rel', 'sorteo_id', 'turno_id',
                                 string='Turnos',
                                 help="Turnos en que se juega este sorteo. El orden lo da la secuencia "
                                      "de cada turno.")
    slot_ids = fields.One2many('lottery.sorteo.slot', 'sorteo_id', string='Calendario (días y turnos)',
                               help="Días de la semana y turnos en que este sorteo se juega. "
                                    "Se usa para calcular automáticamente el próximo sorteo. "
                                    "Vacío = todos los días, todos los turnos del sorteo.")

    # ── Próximo sorteo (fuente de verdad para el portal y la validación) ──
    next_draw_date = fields.Date(string='Próximo sorteo · Fecha',
                                 help="Fecha del próximo sorteo a jugarse. Se recalcula automáticamente "
                                      "a partir de la última salida registrada y el calendario. Editable "
                                      "manualmente para excepciones (feriados, suspensiones).")
    next_draw_turno_id = fields.Many2one('lottery.turno', string='Próximo sorteo · Turno',
                                         ondelete='set null',
                                         domain="[('id', 'in', turno_ids)]")
    next_draw_manual = fields.Boolean(string='Próximo sorteo definido manualmente', default=False,
                                      help="Si está activo, el próximo sorteo no se recalcula automáticamente "
                                           "hasta que se registre la salida que coincide con lo definido.")

    _sql_constraints = [
        ('lottery_sorteo_code_unique', 'unique(code)', 'El código de sorteo ya existe, debe ser único.')
    ]

    @api.constrains('turno_ids')
    def _check_turno_ids(self):
        for sorteo in self:
            if not sorteo.turno_ids:
                raise ValidationError("El sorteo %s debe tener al menos un turno." % sorteo.name)

    # ── Orden de los turnos y calendario ──────────────────────────

    def _ordered_turnos(self):
        """Turnos del sorteo en orden cronológico dentro del día."""
        self.ensure_one()
        return self.turno_ids.sorted(lambda t: (t.sequence, t.id))

    def _enabled_slots(self):
        """Set de (dow_int, turno_id) habilitados. Sin calendario → todos los
        días con todos los turnos del sorteo."""
        self.ensure_one()
        if not self.slot_ids:
            return {(d, t.id) for d in range(7) for t in self.turno_ids}
        return {(int(s.dow), s.turno_id.id) for s in self.slot_ids}

    def _step_slot(self, from_date, from_turno, forward=True):
        """Dado (fecha, turno), devuelve el (fecha, turno) habilitado siguiente
        (o el anterior, con forward=False): recorre los turnos del sorteo en
        orden de secuencia y, al pasar el último (o el primero), cambia de
        día, saltando los slots que el calendario no habilita. Devuelve
        (False, turno vacío) si no encuentra ninguno."""
        self.ensure_one()
        turnos = self._ordered_turnos()
        if not turnos:
            return False, self.env['lottery.turno']
        enabled = self._enabled_slots()
        ids = turnos.ids
        if from_turno.id in ids:
            idx = ids.index(from_turno.id)
        else:
            idx = -1 if forward else len(ids)
        d = from_date
        # Tope de dos semanas de slots: evita un bucle infinito si el
        # calendario quedó sin ningún slot de los turnos actuales.
        for _ in range(14 * len(ids)):
            idx += 1 if forward else -1
            if idx >= len(ids):
                idx = 0
                d = d + timedelta(days=1)
            elif idx < 0:
                idx = len(ids) - 1
                d = d - timedelta(days=1)
            if (d.weekday(), ids[idx]) in enabled:
                return d, turnos[idx]
        return False, self.env['lottery.turno']

    def _next_slot(self, from_date, from_turno):
        return self._step_slot(from_date, from_turno, forward=True)

    def _prev_slot(self, from_date, from_turno):
        return self._step_slot(from_date, from_turno, forward=False)

    # ── Cálculo del próximo sorteo ─────────────────────────────────

    def _recompute_next_draw(self):
        """Recalcula next_draw desde la última salida registrada (si no es manual)."""
        Output = self.env['lottery.output']
        for sorteo in self:
            if sorteo.next_draw_manual:
                continue
            # El _order de lottery.output (fecha, secuencia del turno) deja
            # primero la última salida.
            last = Output.search([('sorteo_id', '=', sorteo.id)], limit=1)
            if not last:
                continue
            nd, nt = sorteo._next_slot(last.date, last.turno_id)
            if not nd:
                continue
            sorteo.with_context(recomputing_next_draw=True).write({
                'next_draw_date': nd,
                'next_draw_turno_id': nt.id,
            })

    def _on_output_registered(self, draw_date, draw_turno):
        """Llamado al crear una salida: consume el override manual si coincide,
        luego recalcula el próximo sorteo."""
        for sorteo in self:
            if (sorteo.next_draw_manual
                    and sorteo.next_draw_date == draw_date
                    and sorteo.next_draw_turno_id == draw_turno):
                sorteo.next_draw_manual = False
            sorteo._recompute_next_draw()

    def get_next_draw(self):
        """(fecha_str, turno) del próximo sorteo, con `turno` como registro de
        lottery.turno. Fuente única para portal y validación. Si no está
        seteado lo deriva de la última salida; sin salidas, hoy y el primer
        turno del sorteo."""
        self.ensure_one()
        if self.next_draw_date and self.next_draw_turno_id:
            return str(self.next_draw_date), self.next_draw_turno_id
        last = self.env['lottery.output'].search([('sorteo_id', '=', self.id)], limit=1)
        if last:
            nd, nt = self._next_slot(last.date, last.turno_id)
            if nd:
                return str(nd), nt
        return str(fields.Date.today()), self._ordered_turnos()[:1]

    # ── Edición manual: marcar como manual salvo que sea un recálculo ──

    def write(self, vals):
        touches_next = 'next_draw_date' in vals or 'next_draw_turno_id' in vals
        if touches_next and not self.env.context.get('recomputing_next_draw') \
                and 'next_draw_manual' not in vals:
            vals['next_draw_manual'] = True
        return super().write(vals)
