# -*- coding: utf-8 -*-
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import build_result_html

_logger = logging.getLogger(__name__)

# API que alimenta el sitio de conectate. Se descubrió capturando lo que
# dispara el selector de fecha del sitio: no hay documentación ni rutas REST
# adivinables (probamos /games, /results, /draws… todas 404).
#
# GET  <API>/site-games/<gameId>?date=<ISO con hora 04:00Z = medianoche RD>
# devuelve el juego y, dentro, game.sessions: LOS 10 SORTEOS que terminan en
# esa fecha, cada uno con score y date. Diez por petición es el máximo: ni
# limit, ni per_page, ni size lo mueven.
#
# Cada TURNO es un gameId distinto (La Primera Día ≠ Primera Noche).
CONECTATE_API = 'https://api.conectate.com.do/conectate/site-games'
SESSIONS_PER_CALL = 10

# Pausa entre peticiones: es un tercero, no conviene atropellarlo.
REQUEST_DELAY = 0.35

_MAX_DETAIL_LINES = 200


class LotteryScraperConectate(models.Model):
    _name = 'lottery.scraper.conectate'
    _description = 'Importador de quinielas dominicanas (fuente conectate)'
    _rec_name = 'sorteo_id'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        help="A qué lottery.sorteo se le asignan las salidas importadas.")

    game_id_afternoon = fields.Char(
        'gameId turno Tarde', required=True,
        help="ObjectId del juego en conectate para el turno de la tarde.")
    game_id_evening = fields.Char(
        'gameId turno Noche', required=True,
        help="ObjectId del juego en conectate para el turno de la noche.\n"
             "Ojo con los nombres de la fuente: en La Suerte el segundo turno "
             "figura como 'Tarde' pero es el de las 18:00, que acá va como "
             "Noche. Lo que manda es el gameId, no el nombre.")

    auto_import = fields.Boolean(
        string='Importación automática', default=False,
        help="Si está desactivado el cron ignora este importador. Arranca "
             "apagado: activar tras validar.")

    rd_offset = fields.Integer(
        'Offset UTC→Rep. Dominicana', default=-4,
        help='República Dominicana no aplica horario de verano: siempre -4.')

    page_load_timeout = fields.Integer('Timeout petición (seg)', default=45)

    max_calls_per_run = fields.Integer(
        'Máx. peticiones por corrida', default=40,
        help="Cada petición trae 10 sorteos, así que 40 son ~400 sorteos por "
             "corrida. Se sube o baja según lo que aguante el worker.")

    date_floor = fields.Date(
        'No bajar de',
        help="Piso del backfill: cuando el recorrido hacia atrás llega acá, "
             "se detiene. Vacío = seguir hasta que la fuente no devuelva más.")
    date_to = fields.Date(
        'Empezar desde (hacia atrás)',
        help="Fecha desde la cual arranca el recorrido hacia atrás. "
             "Vacío = hoy. Solo se usa si el cursor está vacío.")

    backfill_oldest = fields.Date(
        'Backfill llegó hasta', readonly=True,
        help="Sorteo más viejo alcanzado por el recorrido hacia atrás. La "
             "próxima corrida sigue desde ahí. Vaciar para rehacerlo.")
    backfill_done = fields.Boolean(
        'Backfill terminado', readonly=True,
        help="Se marca cuando la fuente dejó de devolver sorteos más viejos "
             "o se alcanzó el piso.")

    last_run    = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Html('Último resultado', readonly=True, sanitize=False)

    # ── Entry points ──────────────────────────────────────────────

    @api.model
    def cron_import_results(self):
        """Trae los últimos sorteos de cada turno. Una petición por turno
        alcanza: la fuente devuelve los últimos 10 de cada uno."""
        for scraper in self.search([('auto_import', '=', True)]):
            try:
                scraper._run_recientes()
            except Exception:
                _logger.exception('Scraper conectate (%s): error en la corrida automática.',
                                  scraper.sorteo_id.display_name)

    def action_import_now(self):
        """Trae los últimos sorteos, sin tocar el backfill."""
        self.ensure_one()
        self._run_recientes()
        return self._reload()

    def action_backfill(self):
        """Sigue el recorrido hacia atrás desde donde quedó."""
        self.ensure_one()
        self._run_backfill()
        return self._reload()

    def _reload(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    # ── Corridas ──────────────────────────────────────────────────

    def _today_rd(self):
        return datetime.now(tz=timezone(timedelta(hours=self.rd_offset))).date()

    def _run_recientes(self):
        self.ensure_one()
        log = []
        try:
            session = self._session()
            draws = []
            for turn, gid in self._turnos():
                draws += [dict(d, turn=turn)
                          for d in self._fetch(session, gid, self._today_rd())]
            log += self._import_draws(draws)
        except Exception as exc:
            log.append(f'[ERROR] {exc}')
            _logger.error('Scraper conectate: %s', exc, exc_info=True)
        self._write_result(log)

    def _run_backfill(self):
        self.ensure_one()
        log = []
        try:
            if self.backfill_done:
                log.append('El backfill ya está terminado. '
                           'Vaciá "Backfill llegó hasta" para rehacerlo.')
            else:
                session = self._session()
                desde = (self.backfill_oldest - timedelta(days=1)
                         if self.backfill_oldest else (self.date_to or self._today_rd()))
                draws, mas_viejo, agotado = [], None, True

                # El presupuesto de peticiones se reparte entre los dos turnos.
                por_turno = max(1, (self.max_calls_per_run or 40) // 2)
                for turn, gid in self._turnos():
                    d, viejo, sigue = self._walk_back(session, gid, desde, por_turno)
                    draws += [dict(x, turn=turn) for x in d]
                    if viejo and (mas_viejo is None or viejo < mas_viejo):
                        mas_viejo = viejo
                    if sigue:
                        agotado = False

                log.append(f'Recorriendo hacia atrás desde {desde} …')
                log += self._import_draws(draws)

                if mas_viejo:
                    self.backfill_oldest = mas_viejo
                    log.append(f'Alcanzado hasta {mas_viejo}.')
                if agotado:
                    self.backfill_done = True
                    log.append('La fuente no devolvió sorteos más viejos: '
                               'backfill terminado.')
                elif self.date_floor and mas_viejo and mas_viejo <= self.date_floor:
                    self.backfill_done = True
                    log.append(f'Alcanzado el piso configurado ({self.date_floor}): '
                               'backfill terminado.')
                else:
                    log.append('Volvé a apretar "Seguir backfill" para continuar.')
        except Exception as exc:
            log.append(f'[ERROR] {exc}')
            _logger.error('Scraper conectate backfill: %s', exc, exc_info=True)
        self._write_result(log)

    def _write_result(self, log):
        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(self._summarize_log(log)),
        })

    def _turnos(self):
        return (('afternoon', self.game_id_afternoon),
                ('evening',   self.game_id_evening))

    # ── Fuente ────────────────────────────────────────────────────

    def _session(self):
        try:
            import requests
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\nInstalar con: pip install requests') from exc
        s = requests.Session()
        s.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/147.0.0.0 Safari/537.36'),
            'Accept': 'application/json',
            'Origin': 'https://loterias.conectate.com.do',
            'Referer': 'https://loterias.conectate.com.do/',
        })
        return s

    def _fetch(self, session, game_id, hasta):
        """Los 10 sorteos que terminan en `hasta` para ese gameId."""
        if not game_id:
            return []
        resp = session.get(
            '%s/%s' % (CONECTATE_API, game_id),
            params={'date': '%sT04:00:00.000Z' % hasta.isoformat()},
            timeout=self.page_load_timeout,
        )
        resp.raise_for_status()
        data = json.loads(resp.text)
        sesiones = ((data.get('game') or {}).get('sessions') or []
                    if isinstance(data, dict) else [])

        salidas = []
        for s in sesiones:
            if not isinstance(s, dict):
                continue
            crudo = s.get('score') or []
            # score viene anidado: [["30","84","46"]]
            nums = crudo[0] if crudo and isinstance(crudo[0], list) else crudo
            if not isinstance(nums, list) or len(nums) < 3:
                continue
            try:
                premios = tuple(int(str(n).strip()) for n in nums[:3])
            except (TypeError, ValueError):
                continue
            try:
                fecha = datetime.strptime(s['date'][:10], '%Y-%m-%d').date()
            except (KeyError, TypeError, ValueError):
                continue
            salidas.append({'date': fecha, 'numero': premios[0],
                            'premio2': premios[1], 'premio3': premios[2]})
        return salidas

    def _walk_back(self, session, game_id, desde, max_calls):
        """Recorre hacia atrás pidiendo tandas de 10. Devuelve
        (salidas, fecha_mas_vieja, quedan_mas)."""
        salidas, cursor, mas_viejo = [], desde, None
        for i in range(max_calls):
            if i:
                time.sleep(REQUEST_DELAY)
            tanda = self._fetch(session, game_id, cursor)
            if not tanda:
                return salidas, mas_viejo, False   # fuente agotada
            salidas += tanda
            viejo = min(x['date'] for x in tanda)
            mas_viejo = viejo if mas_viejo is None else min(mas_viejo, viejo)
            if self.date_floor and viejo <= self.date_floor:
                return salidas, mas_viejo, False
            nuevo_cursor = viejo - timedelta(days=1)
            if nuevo_cursor >= cursor:      # no avanzó: cortar para no ciclar
                return salidas, mas_viejo, False
            cursor = nuevo_cursor
        return salidas, mas_viejo, True

    # ── Importación ───────────────────────────────────────────────

    def _import_draws(self, draws):
        if not draws:
            return ['No hay sorteos nuevos para importar.']

        Output = self.env['lottery.output']
        by_name = {n['name']: n['id']
                   for n in self.env['lottery.number'].search_read([], ['name'])}

        draws.sort(key=lambda d: (d['date'], 0 if d['turn'] == 'afternoon' else 1))
        existing = {
            (fields.Date.to_date(r['date']), r['turn_day'])
            for r in Output.search_read([
                ('sorteo_id', '=', self.sorteo_id.id),
                ('date', '>=', draws[0]['date']),
                ('date', '<=', draws[-1]['date']),
            ], ['date', 'turn_day'])
        }

        log, vals_list = [], []
        for d in draws:
            etiqueta = 'Tarde' if d['turn'] == 'afternoon' else 'Noche'
            label = f"{d['date']} {etiqueta}"
            clave = (d['date'], d['turn'])
            if clave in existing:
                log.append(f'[OMITIDO] {label} – ya registrado')
                continue
            existing.add(clave)

            number_id = by_name.get(d['numero'])
            if not number_id:
                log.append(f'[ERROR] {label} – número {d["numero"]:02d} no existe')
                continue

            vals = {'date': d['date'], 'turn_day': d['turn'],
                    'sorteo_id': self.sorteo_id.id, 'number_id': number_id}
            extra = ''
            for src, campo, et in (('premio2', 'premio_2_id', 'P2'),
                                   ('premio3', 'premio_3_id', 'P3')):
                pid = by_name.get(d.get(src))
                if pid:
                    vals[campo] = pid
                    extra += f' {et}:{d[src]:02d}'
            vals_list.append(vals)
            log.append(f'[OK] {label} – {d["numero"]:02d}{extra}')

        if vals_list:
            Output.with_context(skip_next_draw_recompute=True,
                                skip_prediction_validation=True).create(vals_list)
            self.sorteo_id._recompute_next_draw()
            _logger.info('Scraper conectate (%s): %d salidas creadas.',
                         self.sorteo_id.display_name, len(vals_list))
        return log

    @staticmethod
    def _summarize_log(log_lines):
        if len(log_lines) <= _MAX_DETAIL_LINES:
            return log_lines
        oks    = [l for l in log_lines if l.startswith('[OK]')]
        skips  = [l for l in log_lines if l.startswith('[OMITIDO]')]
        errors = [l for l in log_lines if l.startswith('[ERROR]')]
        otros  = [l for l in log_lines
                  if not l.startswith(('[OK]', '[OMITIDO]', '[ERROR]'))]
        resumen = otros[:6]
        resumen.append(f'{len(oks)} salida(s) importada(s), '
                       f'{len(skips)} ya registrada(s), {len(errors)} con error.')
        if oks:
            resumen += [oks[0], oks[-1]] if len(oks) > 1 else [oks[0]]
        return resumen + errors[:100]
