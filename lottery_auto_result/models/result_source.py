# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get

from . import parsers

_logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'),
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}
_FLORIDA_HEADERS = {
    'Accept': 'application/json',
    'Origin': 'https://floridalottery.com',
    'Referer': 'https://floridalottery.com/',
    'x-partner': 'web',
}
_FLORIDA_GAME_IDS = {'pick3': 104, 'pick4': 108}

# Tope de salidas por sorteo en una corrida (ponerse al día de varios días).
_MAX_POR_CORRIDA = 100
# Días hacia atrás que se le piden a la API de Florida.
_FLORIDA_DIAS = 30

_TURNO_HORA_RE = re.compile(r'^h(\d{2})(\d{2})$')

_ICONOS = {'ok': '✅', 'wait': '⏳', 'warn': '⚠️', 'error': '❌', 'none': 'ℹ️'}
_TIPOS = [('ok', 'Registrada'), ('wait', 'Esperando'), ('warn', 'Revisar'), ('error', 'Error')]


class _Resultados:
    """Lo que publica una fuente en esta corrida: {clave: {fecha: dígitos}}.
    Cada página se descarga una sola vez y recién cuando se necesita."""

    def __init__(self, source):
        import requests
        self.source = source
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self.urls = [u.strip() for u in (source.urls or '').splitlines() if u.strip()]
        self.data = {}
        self.errores = []
        self._cargado = False
        self._claves = set()

    def _get(self, url, **kw):
        try:
            resp = self.session.get(url, timeout=self.source.timeout or 30, **kw)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 - se informa en la fuente
            self.errores.append('%s: %s' % (url, exc))
            return None

    def _add(self, rows):
        for row in rows:
            self.data.setdefault(row['key'], {}).setdefault(row['date'], row['digits'])

    def _cargar(self, key):
        parser = self.source.parser
        if parser == 'lotteryteller':
            if key in self._claves:
                return
            self._claves.add(key)
            for url in self.urls:
                text = self._get(url.replace('{key}', key))
                if text:
                    self._add(parsers.parse_lotteryteller(text, key))
                    return
            return
        if self._cargado:
            return
        self._cargado = True
        if parser == 'florida_api':
            hoy = datetime.now(pytz.timezone(self.source.tz)).date()
            params = {'startDate': (hoy - timedelta(days=_FLORIDA_DIAS)).strftime('%d-%b-%Y').upper(),
                      'endDate': hoy.strftime('%d-%b-%Y').upper()}
            for game, game_id in _FLORIDA_GAME_IDS.items():
                text = self._get(self.urls[0], params=dict(params, id=game_id),
                                 headers=_FLORIDA_HEADERS) if self.urls else None
                if text:
                    rows = parsers.parse_florida_api(text, game)
                    for row in rows:
                        row['key'] = '%s/%s' % (game, row['key'])
                    self._add(rows)
            return
        parse = parsers.parse_dataloto if parser == 'dataloto' else parsers.parse_enloteria
        for url in self.urls:
            text = self._get(url)
            if text:
                try:
                    self._add(parse(text))
                except Exception as exc:  # noqa: BLE001
                    self.errores.append('%s: no se pudo leer (%s)' % (url, exc))

    def fechas(self, key):
        self._cargar(key)
        return self.data.get(key, {})


class LotteryResultSource(models.Model):
    _name = 'lottery.result.source'
    _description = 'Fuente web de resultados'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activa', default=True)
    parser = fields.Selection([
        ('dataloto', 'DataLoto (JSON)'),
        ('enloteria', 'EnLoteria (HTML)'),
        ('lotteryteller', 'LotteryTeller (HTML por juego y turno)'),
        ('florida_api', 'API oficial Florida Lottery'),
    ], string='Formato', required=True,
        help="Cómo se lee la página. Cambiar la URL no requiere tocar código "
             "mientras el sitio nuevo publique en el mismo formato.")
    urls = fields.Text(
        string='URLs', required=True,
        help="Una por línea. En LotteryTeller, {key} se reemplaza por la clave del "
             "mapeo (florida/pick-3/midday). En EnLoteria y DataLoto se leen todas y se juntan.")
    tz = fields.Selection(
        _tz_get, string='Zona horaria', required=True, default='America/New_York',
        help="Zona de las horas del calendario de los sorteos de esta fuente. Solo "
             "decide desde qué hora se empieza a consultar; se puede ajustar por línea.")
    timeout = fields.Integer(string='Timeout (seg)', default=30)
    line_ids = fields.One2many('lottery.result.source.line', 'source_id', string='Mapeo')
    last_run = fields.Datetime(string='Última consulta', readonly=True)
    last_error = fields.Text(string='Último error', readonly=True)
    auto_count = fields.Integer(string='Sorteos automáticos', compute='_compute_counts')
    issue_count = fields.Integer(
        string='Para revisar', compute='_compute_counts',
        help="Líneas de sorteos automáticos en estado Revisar o Error.")

    @api.depends('line_ids.status_type', 'line_ids.sorteo_id.auto_result')
    def _compute_counts(self):
        for source in self:
            lines = source.line_ids.filtered('sorteo_id.auto_result')
            source.auto_count = len(lines.mapped('sorteo_id'))
            source.issue_count = len(lines.filtered(lambda l: l.status_type in ('warn', 'error')))

    # ── Cron ──────────────────────────────────────────────────────

    @api.model
    def cron_registrar_resultados(self):
        for source in self.search([]):
            try:
                source._run(commit=True)
            except Exception as exc:  # noqa: BLE001 - una fuente no frena a las demás
                self.env.cr.rollback()
                _logger.exception('lottery_auto_result: fuente %s', source.name)
                source.write({'last_run': fields.Datetime.now(), 'last_error': str(exc)})
            self.env.cr.commit()

    def action_run_now(self):
        """Consulta ya, sin esperar la hora del sorteo, y avisa qué hizo."""
        self.ensure_one()
        resumen = self._run(force=True)
        tipos = {r['tipo'] for r in resumen}
        tipo = ('danger' if 'error' in tipos else 'warning' if tipos & {'warn', 'none'}
                else 'success' if 'ok' in tipos else 'info')
        texto = '\n'.join('%s %s: %s' % (_ICONOS[r['tipo']], r['sorteo'], r['texto'])
                          for r in resumen).replace('%', '％')  # el aviso pasa por sprintf
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.name,
                'message': texto,
                'type': tipo,
                'sticky': tipo != 'success',
                'className': 'o_auto_result_notification',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ── Corrida ───────────────────────────────────────────────────

    def _run(self, force=False, commit=False):
        """Lista de {'sorteo', 'tipo', 'texto'}: qué pasó con cada sorteo."""
        self.ensure_one()
        self._lineas_activas()._marcar_manuales()
        if not self._lineas_activas():
            return [{'sorteo': 'Sin sorteos', 'tipo': 'none',
                     'texto': 'ningún sorteo de esta fuente tiene marcado '
                              '"Registrar resultados automáticos".'}]
        sorteos = self._sorteos_pendientes(force)
        if not sorteos:
            return [{'sorteo': 'Nada pendiente', 'tipo': 'wait',
                     'texto': 'ningún sorteo de esta fuente tiene un resultado por registrar.'}]
        resultados = _Resultados(self)
        numeros = self.env['lottery.number']._auto_result_ids()
        resumen = []
        for sorteo in sorteos:
            resumen.append(self._registrar_sorteo(sorteo, resultados, numeros, force))
            if commit:
                self.env.cr.commit()
        self.write({'last_run': fields.Datetime.now(),
                    'last_error': '\n'.join(resultados.errores) or False})
        if resultados.errores:
            resumen.append({'sorteo': 'Fuente', 'tipo': 'error',
                            'texto': 'no respondió: %s' % '; '.join(resultados.errores)})
        return resumen

    def _lineas_activas(self):
        return self.line_ids.filtered(lambda l: l.sorteo_id.auto_result and l.sorteo_id.active)

    def _sorteos_pendientes(self, force):
        """Sorteos con registro automático cuyo próximo sorteo es de esta
        fuente y ya se jugó según el calendario."""
        lines = self._lineas_activas()
        por_slot = {(l.sorteo_id.id, l.turno_id.id): l for l in lines}
        ahora = datetime.now(pytz.utc)
        res = self.env['lottery.sorteo']
        for sorteo in lines.mapped('sorteo_id'):
            fecha_str, turno = sorteo.get_next_draw()
            line = por_slot.get((sorteo.id, turno.id))
            if line and (force or line._draw_time(fields.Date.to_date(fecha_str)) <= ahora):
                res |= sorteo
        return res

    def _registrar_sorteo(self, sorteo, resultados, numeros, force):
        """Registra en orden las salidas que falten, siempre la del próximo
        sorteo del calendario: si la fuente no la tiene, se espera."""
        por_turno = {l.turno_id.id: l for l in self._lineas_activas() if l.sorteo_id == sorteo}
        ahora = datetime.now(pytz.utc)
        # Al ponerse al día solo se notifica lo reciente, no cada salida vieja.
        desde_push = datetime.now(pytz.timezone(self.tz)).date() - timedelta(days=1)
        registradas = []
        tipo, texto = 'wait', ''
        for _ in range(_MAX_POR_CORRIDA):
            fecha_str, turno = sorteo.get_next_draw()
            fecha = fields.Date.to_date(fecha_str)
            label = '%s %s' % (fecha.strftime('%d/%m'), turno.name)
            line = por_turno.get(turno.id)
            if not line:
                tipo, texto = 'wait', 'el próximo (%s) no se toma de esta fuente' % label
                break
            if not force and line._draw_time(fecha) > ahora:
                tipo, texto = 'wait', 'el próximo (%s) todavía no se jugó' % label
                break
            espera = self._stats_pendientes(sorteo)
            if espera:
                self._reintentar_pronto()
                if registradas:
                    tipo = 'ok'
                    texto = ('el %s se registra cuando se actualicen las estadísticas '
                             '(el cron sigue solo)' % label)
                else:
                    tipo = 'warn' if espera == 'demorada' else 'wait'
                    texto = ('Esperando que se actualicen las estadísticas para registrar el %s'
                             % label) if tipo == 'wait' else (
                        'Las estadísticas no se actualizan desde la última salida; '
                        'revisá el cron "Recalcular estadísticas de sorteos pendientes"')
                    line._set_status(texto, tipo)
                break
            tipo, estado, vals = line._vals_salida(fecha, resultados, numeros)
            if not vals:
                line._set_status(estado, tipo)
                texto = estado
                break
            try:
                with self.env.cr.savepoint():
                    out = self.env['lottery.output'].create(vals)
            except Exception as exc:  # noqa: BLE001 - se informa en la línea
                _logger.warning('lottery_auto_result: %s %s %s: %s',
                                sorteo.name, fecha, turno.name, exc)
                tipo, texto = 'error', 'error al registrar el %s: %s' % (label, exc)
                line._set_status(texto, tipo)
                break
            line._set_status('Registrada el %s: %s' % (fecha.strftime('%d/%m/%Y'), out.complete_number), 'ok')
            registradas.append('%s → %s' % (label, out.complete_number))
            if sorteo.auto_result_push and sorteo.show_in_app and fecha >= desde_push:
                try:
                    with self.env.cr.savepoint():
                        out.action_send_push_notification()
                except Exception as exc:  # noqa: BLE001 - la salida queda igual
                    _logger.warning('lottery_auto_result: push %s: %s', out.display_name, exc)
        else:
            tipo, texto = 'warn', ('llegó al tope de %d salidas en una consulta; '
                                   'volvé a consultar para seguir' % _MAX_POR_CORRIDA)
            line._set_status(texto, tipo)
        if registradas:
            partes = ['registradas %d (%s)' % (len(registradas), ', '.join(registradas))]
            if tipo in ('warn', 'error') or texto.startswith('el '):
                partes.append(texto)
            if tipo not in ('warn', 'error'):
                tipo = 'ok'
            texto = '; '.join(partes)
        return {'sorteo': sorteo.display_name, 'tipo': tipo, 'texto': texto}

    def _stats_pendientes(self, sorteo):
        """False si el ranking ya incluye la última salida del sorteo; si no,
        'esperando' o 'demorada' (más de una hora sin actualizarse). Cada
        salida se evalúa contra el ranking del sorteo anterior: registrar dos
        seguidas evaluaría la segunda contra un ranking que no le corresponde."""
        last = self.env['lottery.output'].sudo().search([('sorteo_id', '=', sorteo.id)], limit=1)
        if not last:
            return False
        pendiente = ('lottery.stats.dirty' in self.env and self.env['lottery.stats.dirty']
                     .sudo().search_count([('sorteo_id', '=', sorteo.id)]))
        ahora = fields.Datetime.now()
        if not pendiente:
            if sorteo.ranking_computed_at and sorteo.ranking_computed_at >= last.create_date:
                return False
            # Estadísticas al día y ranking viejo: se recalcula acá.
            if last.create_date < ahora - timedelta(minutes=10):
                sorteo.compute_ranking_snapshot()
                return False
        if last.create_date < ahora - timedelta(hours=1):
            return 'demorada'
        return 'esperando'

    def _reintentar_pronto(self):
        """Vuelve a correr el cron apenas terminen las estadísticas, sin
        esperar los 5 minutos (ponerse al día de varios turnos)."""
        cron = self.env.ref('lottery_auto_result.cron_registrar_resultados',
                            raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger(fields.Datetime.now() + timedelta(seconds=90))


class LotteryResultSourceLine(models.Model):
    _name = 'lottery.result.source.line'
    _description = 'Mapeo de una fuente: sorteo y turno'
    _order = 'source_id, sorteo_id, turno_id'

    source_id = fields.Many2one('lottery.result.source', string='Fuente', required=True,
                                ondelete='cascade', index=True)
    parser = fields.Selection(related='source_id.parser')
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True,
                                ondelete='cascade', index=True)
    sorteo_turno_ids = fields.Many2many(related='sorteo_id.turno_ids')
    turno_id = fields.Many2one('lottery.turno', string='Turno', required=True, ondelete='cascade',
                               domain="[('id', 'in', sorteo_turno_ids)]")
    key = fields.Char(
        string='Clave', required=True,
        help="Cómo identifica la fuente a este sorteo y turno: el nombre en EnLoteria "
             "('La Primera Noche'), el campo en DataLoto ('n3pm', 'tarde'), la ruta en "
             "LotteryTeller ('florida/pick-3/midday') o 'pick3/MIDDAY' en la API de Florida.")
    key_extra = fields.Char(
        string='Clave corridos',
        help="Juego de 4 dígitos que da el Premio 2 y 3 ('florida/pick-4/midday', "
             "'pick4/MIDDAY'). Vacío si la fuente ya trae los 3 premios juntos.")
    tz = fields.Selection(_tz_get, string='Zona horaria',
                          help="Vacía = la de la fuente. Ej. Texas usa hora del centro.")
    auto_result = fields.Boolean(related='sorteo_id.auto_result')
    status = fields.Char(string='Estado', readonly=True)
    status_type = fields.Selection(_TIPOS, string='Tipo de estado', readonly=True)
    status_date = fields.Datetime(string='Fecha del estado', readonly=True)

    _sql_constraints = [
        ('source_sorteo_turno_unique', 'unique(source_id, sorteo_id, turno_id)',
         'Ese sorteo y turno ya está mapeado en esta fuente.'),
    ]

    def _set_status(self, status, tipo):
        """Solo escribe si cambió: el cron corre cada 5 minutos."""
        self.ensure_one()
        if self.status != status or self.status_type != tipo:
            self.write({'status': status, 'status_type': tipo,
                        'status_date': fields.Datetime.now()})

    def _marcar_manuales(self):
        """Líneas sin registrar cuya salida se cargó a mano después del estado."""
        Output = self.env['lottery.output'].sudo()
        for line in self.filtered(lambda l: l.status_type != 'ok' and l.status_date):
            out = Output.search([('sorteo_id', '=', line.sorteo_id.id),
                                 ('turno_id', '=', line.turno_id.id),
                                 ('create_date', '>=', line.status_date)],
                                order='date desc, id desc', limit=1)
            if out:
                line._set_status('Registrada manualmente el %s: %s' % (
                    out.date.strftime('%d/%m/%Y'), out.complete_number), 'ok')

    def _draw_time(self, fecha):
        """Hora UTC del sorteo según el calendario: la del slot o, si no
        tiene, la del código del turno (h1500). Sin hora, la medianoche."""
        self.ensure_one()
        dow = str(fecha.weekday())
        slot = self.sorteo_id.slot_ids.filtered(
            lambda s: s.dow == dow and s.turno_id == self.turno_id)[:1]
        hora = slot.hora_sorteo or 0.0
        if not hora:
            m = _TURNO_HORA_RE.match(self.turno_id.code or '')
            if m:
                hora = int(m.group(1)) + int(m.group(2)) / 60.0
        tz = pytz.timezone(self.tz or self.source_id.tz or 'UTC')
        local = tz.localize(datetime.combine(fecha, datetime.min.time()) + timedelta(hours=hora))
        return local.astimezone(pytz.utc)

    def _vals_salida(self, fecha, resultados, numeros):
        """(tipo, estado, vals) de la salida de `fecha`; vals vacío si
        todavía no se puede registrar, con el motivo en estado."""
        self.ensure_one()
        sorteo = self.sorteo_id
        label = fecha.strftime('%d/%m/%Y')
        publicados = resultados.fechas(self.key)
        main = publicados.get(fecha)
        if not main:
            posteriores = [d for d in publicados if d > fecha]
            if posteriores:
                return 'warn', ('La fuente no trae el %s y ya tiene el %s. Si ese día no hubo '
                                'sorteo, corregí el Próximo sorteo.'
                                % (label, min(posteriores).strftime('%d/%m/%Y'))), {}
            return 'wait', 'Esperando el resultado del %s' % label, {}

        rest, centena, fireball = main, None, None
        if sorteo.uses_hundreds:
            if len(main) < 3:
                return 'error', 'La clave %s no trae centena' % self.key, {}
            centena, rest = int(main[0]), main[1:]
        numero, corridos = rest[:2], rest[2:]
        if sorteo.uses_fireball and self.parser == 'florida_api':
            fireball, corridos = (int(corridos[0]) if corridos else None), corridos[1:]
        if self.key_extra:
            corridos = resultados.fechas(self.key_extra).get(fecha) or ''
        # Georgia lleva corridos sin tener marcado "Números corridos".
        con_corridos = sorteo.is_pick3 or bool(self.key_extra)
        if con_corridos and len(corridos) < 4:
            return 'wait', 'Esperando los corridos del %s' % label, {}
        if sorteo.uses_fireball and fireball is None:
            return 'error', 'La fuente no trae la bola extra', {}

        vals = {
            'sorteo_id': sorteo.id,
            'date': fecha,
            'turno_id': self.turno_id.id,
            'number_id': numeros['n'].get(int(numero)),
        }
        if centena is not None:
            vals['hundreds_id'] = numeros['c'].get(centena)
        if fireball is not None:
            vals['fireball_id'] = numeros['c'].get(fireball)
        if con_corridos:
            vals['premio_2_id'] = numeros['n'].get(int(corridos[:2]))
            vals['premio_3_id'] = numeros['n'].get(int(corridos[2:4]))
        if not all(vals.values()):
            return 'error', 'Número fuera de rango en el %s: %s' % (label, main), {}
        return 'ok', '', vals


class LotteryNumber(models.Model):
    _inherit = 'lottery.number'

    @api.model
    def _auto_result_ids(self):
        """{'n': {00-99: id}, 'c': {0-9: id}}"""
        recs = self.search_read([], ['name', 'can_use_hundreds'])
        return {
            'n': {r['name']: r['id'] for r in recs},
            'c': {r['name']: r['id'] for r in recs if r['can_use_hundreds']},
        }
