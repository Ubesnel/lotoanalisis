# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from .utils import MAPPING_WEEK_DATE, MONTHS


class LotteryOutput(models.Model):
    _name = 'lottery.output'
    _description = 'Salida de Números'
    _order = 'date desc, id desc'

    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True, index=True,
                                help="A qué sorteo/juego pertenece esta salida (Florida, Quiniela UY - Sorteo N, etc).")
    number_id = fields.Many2one('lottery.number', string='Número', required=True, index=True)
    hundreds_id = fields.Many2one('lottery.number', string='Centena',
                                  domain="[('can_use_hundreds','=',True)]", index=True,
                                  help="Obligatoria salvo que el sorteo tenga desactivado 'Usa Centena' "
                                       "(sorteos de número de 2 dígitos, sin centena).")
    sorteo_uses_hundreds = fields.Boolean(related='sorteo_id.uses_hundreds', string='Usa Centena')
    date = fields.Date(string='Fecha', default=lambda self: fields.Date.today(), required=True)
    turn_day = fields.Selection([
        ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno del día', required=True, index=True)
    complete_number = fields.Char(string='Número completo', compute='_compute_complete_number', store=True)

    # ── Números corridos (solo sorteos Pick3) ─────────────────────
    premio_2_id = fields.Many2one(
        'lottery.number', string='Premio 2',
        index=True,
        options="{'no_open': True, 'no_create': True}",
    )
    premio_3_id = fields.Many2one(
        'lottery.number', string='Premio 3',
        index=True,
        options="{'no_open': True, 'no_create': True}",
    )
    week_day = fields.Selection([('lu', 'Lunes'), ('ma', 'Martes'), ('mi', 'Miércoles'),
                                 ('ju', 'Jueves'), ('vi', 'Viernes'), ('sa', 'Sábado'), ('do', 'Domingo')],
                                string='Día de la semana', index=True, compute='_compute_week_day', store=True)
    year = fields.Integer(string="Año", compute="_compute_year_month", store=True)
    month = fields.Selection(selection=MONTHS, string="Mes", compute="_compute_year_month", store=True)

    @api.depends('date')
    def _compute_year_month(self):
        for record in self:
            if record.date:
                record.year = record.date.year
                record.month = str(record.date.month)
            else:
                record.year = False
                record.month = False

    _sql_constraints = [
        (
            'unique_date_turn_sorteo',
            'unique(date, turn_day, sorteo_id)',
            'Ya existe una salida registrada para esa fecha, turno y sorteo.'
        )
    ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = self.env.context.get('codigo_sorteo')
        if code:
            sorteo = self.env['lottery.sorteo'].search([('code', '=', code)], limit=1)
            if sorteo:
                res['sorteo_id'] = sorteo.id

        return res

    @api.depends('date', 'turn_day', 'hundreds_id.name', 'number_id', 'sorteo_id.name')
    def _compute_display_name(self):
        for record in self:
            date_str = record.date.strftime('%d-%m-%Y') if record.date else ''
            turn_label = dict(self._fields['turn_day'].selection).get(record.turn_day, '')
            centena = f"{record.hundreds_id.name}" if record.hundreds_id else ''
            numero = f"{record.number_id.name:02d}" if record.number_id else ''
            combinado = f"{centena}{numero}"
            sorteo_label = f" / {record.sorteo_id.name}" if record.sorteo_id else ''
            record.display_name = f"{date_str} / {turn_label} / {combinado}{sorteo_label}"

    @api.constrains('date', 'turn_day', 'sorteo_id')
    def _check_evening_requires_afternoon(self):
        limit_date = date(2008, 5, 19)
        for record in self:
            if not record.sorteo_id.enforce_turn_continuity:
                continue
            if record.date >= limit_date and record.turn_day == 'evening':
                afternoon_exists = self.search_count([
                    ('date', '=', record.date),
                    ('turn_day', '=', 'afternoon'),
                    ('sorteo_id', '=', record.sorteo_id.id),
                    ('id', '!=', record.id),
                ])
                if not afternoon_exists:
                    raise ValidationError(
                        "No se puede registrar una salida de Noche si no existe previamente una salida de Tarde para la misma fecha."
                    )

    @api.constrains('date', 'turn_day', 'sorteo_id')
    def _check_afternoon_requires_evening(self):
        for record in self:
            if not record.sorteo_id.enforce_turn_continuity:
                continue
            if record.date and record.turn_day == 'afternoon':
                fecha_anterior = record.date - timedelta(days=1)
                evening_exists = self.search_count([
                    ('date', '=', fecha_anterior),
                    ('turn_day', '=', 'evening'),
                    ('sorteo_id', '=', record.sorteo_id.id),
                    ('id', '!=', record.id),
                ])
                if not evening_exists:
                    raise ValidationError(
                        "No se puede registrar una salida de Tarde si no existe previamente una salida de Noche para el día anterior."
                    )

    @api.constrains('sorteo_id', 'hundreds_id')
    def _check_hundreds_id(self):
        for record in self:
            if record.sorteo_id.uses_hundreds and not record.hundreds_id:
                raise ValidationError(
                    "Debe registrar un valor para la Centena."
                )

    @api.depends('hundreds_id', 'number_id')
    def _compute_complete_number(self):
        for record in self:
            if not record.number_id:
                record.complete_number = ""
            elif record.hundreds_id:
                record.complete_number = f"{record.hundreds_id.name}{record.number_id.name:02d}"
            else:
                # Sorteos sin centena: el número completo son los 2 dígitos.
                record.complete_number = f"{record.number_id.name:02d}"

    @api.depends('date')
    def _compute_week_day(self):
        for output in self:
            if output.date:
                output.week_day = MAPPING_WEEK_DATE.get(output.date.weekday())
            else:
                output.week_day = False

    # ── Mantenimiento del "próximo sorteo" del sorteo ──────────────
    # La secuencialidad estricta (sin saltos) permite derivar el próximo sorteo
    # de la última salida registrada; autorreparable ante borrado/recarga.

    def init(self):
        # Índices compuestos para los patrones dominantes de consulta:
        # "última salida del sorteo" (sorteo_id + date) y los agregados de
        # atrasos por día de semana (sorteo_id + EXTRACT(DOW) + date).
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS lottery_output_sorteo_date_idx
            ON lottery_output (sorteo_id, date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS lottery_output_sorteo_dow_date_idx
            ON lottery_output (sorteo_id, (EXTRACT(DOW FROM date)), date)
        """)
        # Salidas de un número en un mes concreto (con la fecha para la
        # "última salida"): usado por las 3 tablas de números por mes
        # (calientes/intermedios/fríos) y por los atrasos por mes. Sin este
        # índice, el COUNT por número/mes hace BitmapAnd de number_id +
        # sorteo_id y filtra en el heap (~2,8 ms × 100 números × 3 consultas
        # ≈ 1,2 s en frío). Con él baja a ~13 ms por consulta (Index Only
        # Scan). Medido sobre Florida (20k+ salidas), julio 2026.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS lottery_output_sorteo_num_month_date_idx
            ON lottery_output (sorteo_id, number_id, month, date)
        """)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # skip_next_draw_recompute: lo usa el backfill histórico, que crea miles
        # de salidas de una. Recalcular el próximo sorteo en cada una cuesta un
        # search + write por registro y el resultado se pisa enseguida; el
        # importador lo recalcula una sola vez al terminar.
        if not self.env.context.get('skip_next_draw_recompute'):
            for record in records:
                if record.sorteo_id:
                    record.sorteo_id._on_output_registered(record.date, record.turn_day)
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'date', 'turn_day', 'sorteo_id'} & set(vals):
            self.mapped('sorteo_id')._recompute_next_draw()
        return res

    def unlink(self):
        sorteos = self.mapped('sorteo_id')
        res = super().unlink()
        sorteos._recompute_next_draw()
        return res
