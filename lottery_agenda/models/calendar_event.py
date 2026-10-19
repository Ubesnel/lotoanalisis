# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ESTADOS = [
    ('pending', 'Pendiente'),
    ('late', 'Atrasada'),
    ('done', 'Hecha'),
]
# Lo que se antepone al título: se ve igual en la agenda, la lista y el aviso.
EMOJI = {'pending': '🕒', 'late': '⚠️', 'done': '✅'}
# Índice de color del calendario por estado (0-11). Si en pantalla no
# combinan, se cambia acá.
COLOR = {'pending': 4, 'late': 1, 'done': 10}
# Cuánto dura el evento en la agenda.
DURACION_MIN = 15
# Cuántos días (hoy incluido) se crean por adelantado.
DIAS_ADELANTE = 2


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    lottery_sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', index=True, ondelete='cascade', copy=False)
    lottery_turno_id = fields.Many2one(
        'lottery.turno', string='Turno', index=True, ondelete='cascade', copy=False)
    lottery_date = fields.Date(string='Fecha del sorteo', index=True, copy=False)
    lottery_label = fields.Char(string='Tarea', copy=False)
    lottery_state = fields.Selection(
        ESTADOS, string='Estado', index=True, copy=False,
        help="Pendiente: todavía no llegó la hora o no se registró la salida. "
             "Atrasada: pasó la hora y no se registró la salida. Hecha: la "
             "salida ya está registrada.")
    lottery_color = fields.Integer(
        string='Color', compute='_compute_lottery_color', store=True)

    _sql_constraints = [
        ('lottery_agenda_unique',
         'unique(lottery_sorteo_id, lottery_turno_id, lottery_date)',
         'Ya hay una tarea de la agenda para ese sorteo, turno y fecha.'),
    ]

    @api.depends('lottery_state')
    def _compute_lottery_color(self):
        for ev in self:
            ev.lottery_color = COLOR.get(ev.lottery_state, 0)

    # ── Estado ─────────────────────────────────────────────────────────────

    def _lottery_set_state(self, state):
        """Cambia el estado, el título y, si queda hecha, quita el aviso para
        que no suene una tarea ya cumplida. Sin mails a los invitados."""
        for ev in self:
            vals = {
                'lottery_state': state,
                'name': '%s %s' % (EMOJI[state], ev.lottery_label or ev.name),
            }
            if state == 'done':
                vals['alarm_ids'] = [(5, 0, 0)]
            ev.with_context(no_mail_to_attendees=True, dont_notify=True,
                            mail_notrack=True).write(vals)

    def action_lottery_marcar_hecha(self):
        self._lottery_set_state('done')

    def action_lottery_reabrir(self):
        ahora = fields.Datetime.now()
        for ev in self:
            ev._lottery_set_state('late' if ev.stop and ev.stop < ahora else 'pending')

    # ── Cron: crear los eventos del día y marcar los atrasados ────────────

    @api.model
    def cron_agenda_loteria(self):
        self._agenda_crear_eventos()
        self._agenda_marcar_atrasados()

    @api.model
    def _agenda_tz(self):
        return pytz.timezone(self.env.company.partner_id.tz or 'America/Montevideo')

    @api.model
    def _agenda_usuarios(self):
        usuarios = self.env.company.agenda_user_ids
        if not usuarios:
            grupo = self.env.ref('lottery_base.group_lottery_manager', raise_if_not_found=False)
            usuarios = grupo.users if grupo else self.env['res.users']
        return usuarios.filtered('active')

    @api.model
    def _agenda_alarma(self, minutos):
        Alarm = self.env['calendar.alarm'].sudo()
        alarma = Alarm.search([
            ('alarm_type', '=', 'notification'),
            ('interval', '=', 'minutes'),
            ('duration', '=', minutos),
        ], limit=1)
        return alarma or Alarm.create({
            'name': 'Lotería: %d minutos antes' % minutos,
            'alarm_type': 'notification',
            'interval': 'minutes',
            'duration': minutos,
        })

    @api.model
    def _agenda_crear_eventos(self):
        sorteos = self.env['lottery.sorteo'].sudo().search([('agenda_enabled', '=', True)])
        if not sorteos:
            return
        usuarios = self._agenda_usuarios()
        if not usuarios:
            _logger.warning('lottery_agenda: no hay usuarios para la agenda; no se crean eventos.')
            return

        tz = self._agenda_tz()
        hoy = pytz.utc.localize(fields.Datetime.now()).astimezone(tz).date()
        dias = [hoy + timedelta(days=i) for i in range(DIAS_ADELANTE)]
        alarma = self._agenda_alarma(max(self.env.company.agenda_aviso_min or 0, 0))

        Event = self.sudo().with_context(active_test=False)
        # Incluye los archivados: archivar una tarea (un feriado, por ejemplo)
        # es decir "hoy no aplica" y no debe volver a crearse.
        existentes = {
            (e.lottery_sorteo_id.id, e.lottery_turno_id.id, e.lottery_date)
            for e in Event.search([('lottery_sorteo_id', 'in', sorteos.ids),
                                   ('lottery_date', 'in', dias)])
        }
        Output = self.env['lottery.output'].sudo()
        nuevos = []
        for sorteo in sorteos:
            for slot in sorteo.slot_ids.filtered('pub_h'):
                for dia in dias:
                    if str(dia.weekday()) != slot.dow:
                        continue
                    clave = (sorteo.id, slot.turno_id.id, dia)
                    if clave in existentes:
                        continue
                    existentes.add(clave)
                    horas, minutos = divmod(round(slot.hora_publicacion * 60), 60)
                    inicio_local = tz.localize(datetime(dia.year, dia.month, dia.day, horas, minutos))
                    inicio = inicio_local.astimezone(pytz.utc).replace(tzinfo=None)
                    hecha = bool(Output.search_count([
                        ('sorteo_id', '=', sorteo.id), ('turno_id', '=', slot.turno_id.id),
                        ('date', '=', dia)]))
                    estado = 'done' if hecha else 'pending'
                    etiqueta = 'Registrar %s – %s' % (sorteo.name, slot.turno_id.name)
                    nuevos.append({
                        'name': '%s %s' % (EMOJI[estado], etiqueta),
                        'start': inicio,
                        'stop': inicio + timedelta(minutes=DURACION_MIN),
                        'user_id': usuarios[0].id,
                        'partner_ids': [(6, 0, usuarios.partner_id.ids)],
                        'alarm_ids': [(6, 0, [] if hecha else [alarma.id])],
                        'lottery_sorteo_id': sorteo.id,
                        'lottery_turno_id': slot.turno_id.id,
                        'lottery_date': dia,
                        'lottery_label': etiqueta,
                        'lottery_state': estado,
                    })
        if nuevos:
            Event.with_context(no_mail_to_attendees=True, mail_notrack=True).create(nuevos)
            _logger.info('lottery_agenda: %d eventos creados.', len(nuevos))

    @api.model
    def _agenda_marcar_atrasados(self):
        atrasados = self.sudo().search([
            ('lottery_state', '=', 'pending'),
            ('stop', '<', fields.Datetime.now()),
        ])
        atrasados._lottery_set_state('late')
