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
# Cuánto dura el evento en la agenda. Es solo el alto del bloque: con menos de
# una hora, según la versión del calendario el bloque queda en una línea (la de
# la hora) y el título no se ve.
DURACION_MIN = 60
# Minutos que pasan desde la hora de publicar para que la tarea figure como
# atrasada (independiente de lo que dure el bloque en la agenda).
ATRASO_MIN = 15
# Cuántos días (hoy incluido) se crean por adelantado.
DIAS_ADELANTE = 2


def _hora_12h(dt_local):
    """datetime local → '7:40 PM'."""
    h12 = dt_local.hour % 12 or 12
    return '%d:%02d %s' % (h12, dt_local.minute, 'AM' if dt_local.hour < 12 else 'PM')


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
    lottery_hora = fields.Char(
        string='Hora (Uruguay)', compute='_compute_lottery_hora',
        help="Hora de publicar, en la hora local de la empresa (Uruguay).")

    _sql_constraints = [
        ('lottery_agenda_unique',
         'unique(lottery_sorteo_id, lottery_turno_id, lottery_date)',
         'Ya hay una tarea de la agenda para ese sorteo, turno y fecha.'),
    ]

    @api.depends('lottery_state')
    def _compute_lottery_color(self):
        for ev in self:
            ev.lottery_color = COLOR.get(ev.lottery_state, 0)

    @api.depends('start', 'lottery_sorteo_id')
    def _compute_lottery_hora(self):
        tz = self._agenda_tz()
        for ev in self:
            ev.lottery_hora = (
                _hora_12h(pytz.utc.localize(ev.start).astimezone(tz))
                if ev.lottery_sorteo_id and ev.start else False)

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
            pasada = ev.start and ev.start < ahora - timedelta(minutes=ATRASO_MIN)
            ev._lottery_set_state('late' if pasada else 'pending')

    # ── Cron: crear los eventos del día y marcar los atrasados ────────────

    @api.model
    def cron_agenda_loteria(self):
        self._agenda_crear_eventos()
        self._agenda_ajustar_eventos()
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
            'name': ('Lotería: %d minutos antes' % minutos) if minutos
                    else 'Lotería: a la hora',
            'alarm_type': 'notification',
            'interval': 'minutes',
            'duration': minutos,
        })

    @api.model
    def _agenda_alarmas(self):
        """Los avisos de cada evento: el anticipado (minutos antes) y, si
        está activo, otro justo a la hora de publicar."""
        empresa = self.env.company
        minutos = set()
        if (empresa.agenda_aviso_min or 0) > 0:
            minutos.add(empresa.agenda_aviso_min)
        if empresa.agenda_aviso_hora:
            minutos.add(0)
        alarmas = self.env['calendar.alarm']
        for m in sorted(minutos, reverse=True):
            alarmas |= self._agenda_alarma(m)
        return alarmas

    @staticmethod
    def _agenda_fin(inicio_utc, tz):
        """Fin (UTC, sin zona) del bloque que arranca en `inicio_utc`: dura
        DURACION_MIN pero no pasa de las 23:59 del mismo día local. Un bloque
        que cruzara la medianoche se dibujaría también en la columna del día
        siguiente, como si la tarea fuera de ahí."""
        inicio = pytz.utc.localize(inicio_utc).astimezone(tz)
        limite = tz.localize(datetime(inicio.year, inicio.month, inicio.day, 23, 59))
        fin = min(inicio + timedelta(minutes=DURACION_MIN), limite)
        if fin <= inicio:
            fin = inicio + timedelta(minutes=1)
        return fin.astimezone(pytz.utc).replace(tzinfo=None)

    @staticmethod
    def _agenda_inicio(slot, dia, tz):
        """Inicio (con zona horaria) de la tarea de `slot` para el sorteo del
        `dia`.

        La hora de publicar es la de Uruguay y la del sorteo es la de su país,
        y Uruguay va por delante (Georgia a las 11:35 PM es la 00:35 AM
        siguiente en Uruguay). Si la hora de publicar es menor que la del
        sorteo, cruzó la medianoche: la tarea cae el día siguiente al del
        sorteo, aunque en el calendario del sorteo se cargue en la fila del
        mismo día."""
        horas, minutos = divmod(round(slot.hora_publicacion * 60), 60)
        cruza = bool(slot.hora_sorteo) and slot.hora_publicacion < slot.hora_sorteo
        dia_ev = dia + timedelta(days=1) if cruza else dia
        return tz.localize(datetime(dia_ev.year, dia_ev.month, dia_ev.day, horas, minutos))

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
        # Ayer también: sus sorteos tardíos pueden tener la tarea pasada la
        # medianoche, o sea hoy (ver _agenda_inicio).
        dias = [hoy - timedelta(days=1)] + [hoy + timedelta(days=i) for i in range(DIAS_ADELANTE)]
        alarmas = self._agenda_alarmas()

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
                    inicio_local = self._agenda_inicio(slot, dia, tz)
                    # De ayer solo las tareas que caen hoy (pasada la medianoche).
                    if dia < hoy and inicio_local.date() <= dia:
                        continue
                    existentes.add(clave)
                    inicio = inicio_local.astimezone(pytz.utc).replace(tzinfo=None)
                    hecha = bool(Output.search_count([
                        ('sorteo_id', '=', sorteo.id), ('turno_id', '=', slot.turno_id.id),
                        ('date', '=', dia)]))
                    estado = 'done' if hecha else 'pending'
                    etiqueta = 'Registrar %s – %s · %s' % (
                        sorteo.name, slot.turno_id.name, _hora_12h(inicio_local))
                    nuevos.append({
                        'name': '%s %s' % (EMOJI[estado], etiqueta),
                        'start': inicio,
                        'stop': self._agenda_fin(inicio, tz),
                        'user_id': usuarios[0].id,
                        'partner_ids': [(6, 0, usuarios.partner_id.ids)],
                        'alarm_ids': [(6, 0, [] if hecha else alarmas.ids)],
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
    def _agenda_ajustar_eventos(self):
        """Deja los eventos ya creados al día con la configuración: la
        duración del bloque y, en los pendientes que todavía no pasaron, los
        avisos (para que un cambio en Ajustes alcance a los de hoy)."""
        ahora = fields.Datetime.now()
        eventos = self.sudo().search([
            ('lottery_sorteo_id', '!=', False),
            ('start', '>=', ahora - timedelta(days=1))])
        alarmas = self._agenda_alarmas()
        tz = self._agenda_tz()
        for ev in eventos:
            # Hora de inicio: una tarea que cruza la medianoche creada el día
            # del sorteo (antes de este arreglo) se pasa al día siguiente.
            slot = ev.lottery_sorteo_id.slot_ids.filtered(
                lambda sl: sl.dow == str(ev.lottery_date.weekday())
                and sl.turno_id == ev.lottery_turno_id)[:1]
            if slot and slot.pub_h and ev.lottery_state != 'done':
                esperado = self._agenda_inicio(slot, ev.lottery_date, tz) \
                    .astimezone(pytz.utc).replace(tzinfo=None)
                if ev.start != esperado:
                    ev.with_context(no_mail_to_attendees=True, mail_notrack=True).write({
                        'start': esperado,
                        'stop': self._agenda_fin(esperado, tz)})
            etiqueta = 'Registrar %s – %s · %s' % (
                ev.lottery_sorteo_id.name, ev.lottery_turno_id.name,
                _hora_12h(pytz.utc.localize(ev.start).astimezone(tz)))
            if ev.lottery_label != etiqueta:
                ev.with_context(no_mail_to_attendees=True, dont_notify=True,
                                mail_notrack=True).write({
                    'lottery_label': etiqueta,
                    'name': '%s %s' % (EMOJI[ev.lottery_state or 'pending'], etiqueta),
                })
            stop = self._agenda_fin(ev.start, tz)
            if ev.stop != stop:
                ev.with_context(no_mail_to_attendees=True, dont_notify=True,
                                mail_notrack=True).write({'stop': stop})
            # Sin dont_notify: al cambiar los avisos Odoo tiene que
            # reprogramarlos. No manda mails (no_mail_to_attendees).
            if (ev.lottery_state == 'pending' and ev.start > ahora
                    and set(ev.alarm_ids.ids) != set(alarmas.ids)):
                ev.with_context(no_mail_to_attendees=True, mail_notrack=True).write(
                    {'alarm_ids': [(6, 0, alarmas.ids)]})

    @api.model
    def _agenda_marcar_atrasados(self):
        atrasados = self.sudo().search([
            ('lottery_state', '=', 'pending'),
            ('start', '<', fields.Datetime.now() - timedelta(minutes=ATRASO_MIN)),
        ])
        atrasados._lottery_set_state('late')
