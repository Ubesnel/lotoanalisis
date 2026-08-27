# -*- coding: utf-8 -*-
"""Importador automático del Quinielón (Rep. Dominicana).

Mismo sitio oficial y misma respuesta HTTP que La Primera (laprimera.do,
admin-ajax.php, un día por petición): además de "TRIPLETA PRIMERA" (La
Primera) el payload trae "EL QUINIELON", un juego aparte de la misma
lotería (LA PRIMERA / GSTAR) con un solo número de 2 dígitos por turno, sin
centena y sin corridos — mismo formato que Florida Pick 2.

Es un scraper propio y no una extensión de lottery.scraper.la.primera a
propósito: se activa/desactiva y se hace backfill de forma independiente,
sin tocar el importador de La Primera que ya está en producción. El costo
es una petición HTTP diaria de más (liviana), que no vale la pena evitar a
cambio de acoplar los dos.
"""
import json
import logging
import re
import time
from datetime import date as date_type, datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import build_result_html

_logger = logging.getLogger(__name__)

RESULTS_PAGE = 'https://laprimera.do/resultados/'
AJAX_URL     = 'https://laprimera.do/wp-admin/admin-ajax.php'
_NONCE_RE = re.compile(r'primera_js\s*=\s*\{[^}]*"nonce"\s*:\s*"([^"]+)"')

GAME_NAME = 'EL QUINIELON'

# El Quinielón no viene desde el arranque del histórico de La Primera: en
# esta misma fuente el juego recién aparece a partir del 20/05/2024
# (verificado día por día en agosto de 2026; el 19/05/2024 es un día sin
# datos en la fuente y el 18/05/2024 ya no lo trae).
HISTORY_START = date_type(2024, 5, 20)

REQUEST_DELAY = 0.35

_MAX_DETAIL_LINES = 200


class LotteryScraperQuinielon(models.Model):
    _name = 'lottery.scraper.quinielon'
    _description = 'Importador automático Quinielón (RD)'

    name = fields.Char(default='Quinielón', readonly=True)
    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=lambda self: self._get_sorteo().id,
        help="A qué lottery.sorteo se le asignan las salidas importadas.")

    auto_import = fields.Boolean(
        string='Importación automática', default=False,
        help="Si está desactivado el cron ignora este importador y solo se "
             "importa a mano. Arranca apagado: activar tras validar.")

    rd_offset = fields.Integer(
        'Offset UTC→Rep. Dominicana', default=-4,
        help='República Dominicana no aplica horario de verano: siempre -4.')

    page_load_timeout = fields.Integer('Timeout petición (seg)', default=30)

    max_days_per_run = fields.Integer(
        'Máx. días por corrida', default=60,
        help="La API entrega un día por petición: cada corrida procesa como "
             "mucho esta cantidad de días pendientes y avisa cuántos "
             "quedan: se vuelve a apretar el botón hasta terminar.")

    # ── Importación manual por rango ──────────────────────────────
    date_from = fields.Date(
        'Fecha desde',
        help='Vacío = sigue desde la última salida registrada, y si no hay '
             'ninguna arranca en el 20/05/2024, primer día con Quinielón en '
             'esta fuente.')
    date_to = fields.Date('Fecha hasta', help='Vacío = hoy (hora RD).')

    backfill_until = fields.Date(
        'Backfill completado hasta', readonly=True,
        help="Hasta qué día ya se recorrió el histórico. Avanza aunque el "
             "día venga vacío, para no volver a pedir siempre los mismos "
             "huecos. Vaciar este campo para rehacer el backfill.")

    # ── Estado ────────────────────────────────────────────────────
    last_run    = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Html('Último resultado', readonly=True, sanitize=False)

    # ── Entry points ──────────────────────────────────────────────

    @api.model
    def cron_import_results(self):
        for scraper in self.search([('auto_import', '=', True)]):
            try:
                scraper._run(days_back=3)
            except Exception:
                _logger.exception('Scraper Quinielón: error en la corrida automática.')

    def action_import_now(self):
        self.ensure_one()
        self._run()

    def action_reset_backfill(self):
        self.write({'backfill_until': False})

    # ── Núcleo ────────────────────────────────────────────────────

    def _today_rd(self):
        return datetime.now(tz=timezone(timedelta(hours=self.rd_offset))).date()

    def _pending_dates(self, days_back=None):
        self.ensure_one()
        today = self._today_rd()

        if days_back is not None:
            desde, hasta = today - timedelta(days=days_back), today
        else:
            desde = HISTORY_START
            if self.date_from:
                desde = max(desde, self.date_from)
            if self.backfill_until and self.backfill_until >= desde:
                desde = self.backfill_until + timedelta(days=1)
            hasta = self.date_to or today

        hasta = min(hasta, today)
        if desde > hasta:
            return [], 0

        completos = {}
        for rec in self.env['lottery.output'].search_read([
                ('sorteo_id', '=', self.sorteo_id.id),
                ('date', '>=', desde), ('date', '<=', hasta)], ['date', 'turn_day']):
            completos.setdefault(fields.Date.to_date(rec['date']), set()).add(rec['turn_day'])

        dias, cur = [], desde
        while cur <= hasta:
            if completos.get(cur, set()) != {'afternoon', 'evening'}:
                dias.append(cur)
            cur += timedelta(days=1)
        return dias, (hasta - desde).days + 1

    def _run(self, days_back=None):
        self.ensure_one()
        log_lines = []
        try:
            dias, total = self._pending_dates(days_back=days_back)
            if not dias:
                log_lines.append('No hay días pendientes en el rango.')
                if days_back is None:
                    log_lines.append('El backfill está al día.')
            else:
                tope = max(self.max_days_per_run or 60, 1)
                lote = dias[:tope]
                log_lines.append(
                    f'{total} día(s) en el rango, {len(dias)} por consultar; '
                    f'procesando {len(lote)} (del {lote[0]} al {lote[-1]}) …')

                draws, fallos = self._fetch_days(lote)
                log_lines += self._import_draws(draws)
                log_lines += fallos

                if days_back is None:
                    self.backfill_until = lote[-1]
                    restantes = len(dias) - len(lote)
                    if restantes:
                        log_lines.append(
                            f'Quedan {restantes} día(s): volvé a apretar '
                            f'"Importar ahora" para seguir desde {lote[-1] + timedelta(days=1)}.')
                    else:
                        log_lines.append('Backfill terminado.')
        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper Quinielón: %s', exc, exc_info=True)

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(self._summarize_log(log_lines)),
        })

    # ── Fuente ────────────────────────────────────────────────────

    def _session_and_nonce(self):
        try:
            import requests
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\nInstalar con: pip install requests') from exc

        session = requests.Session()
        session.headers.update({
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/147.0.0.0 Safari/537.36'),
            'Accept-Language': 'es-DO,es;q=0.9',
        })
        resp = session.get(RESULTS_PAGE, timeout=self.page_load_timeout)
        resp.raise_for_status()
        match = _NONCE_RE.search(resp.text)
        if not match:
            raise UserError(
                'No se pudo obtener el nonce de %s. Es probable que el sitio '
                'haya cambiado la página de resultados.' % RESULTS_PAGE)
        return session, match.group(1)

    def _fetch_days(self, dias):
        """A diferencia de lottery.scraper.la.primera (misma fuente), acá NO
        se descartan valores repetidos en días consecutivos como "fantasmas".
        Esa lógica solo tiene sentido cuando la firma es una combinación de
        varios números (para La Primera, 3 números → repetirlos juntos por
        azar es ~1 en un millón); acá la firma es UN SOLO número de 2 dígitos
        (00-99), así que un mismo turno puede repetir valor de un día para el
        otro por pura casualidad con frecuencia real (~1 en 100) — de hecho
        pasa: el 03/06/2024 y el 04/06/2024 dieron 70 en el turno Día, los
        dos verificados como reales contra la web pública. Además, en el
        histórico revisado (ver HISTORY_START) el contador `sorteo_numero`
        de la fuente sube de a uno todos los días sin huecos, así que este
        juego no parece tener "días sin sorteo" que la fuente rellene con
        datos inventados — el problema que resolvía _descartar_fantasmas en
        La Primera no está confirmado que exista acá."""
        session, nonce = self._session_and_nonce()
        draws, fallos = [], []
        for i, dia in enumerate(dias):
            if i:
                time.sleep(REQUEST_DELAY)
            try:
                draws += self._fetch_day(session, nonce, dia)
            except Exception as exc:
                fallos.append(f'[ERROR] {dia} – no se pudo consultar: {exc}')
                _logger.warning('Scraper Quinielón: %s falló: %s', dia, exc)
        draws.sort(key=lambda d: (d['date'], 0 if d['turn'] == 'afternoon' else 1))
        return draws, fallos

    def _fetch_day(self, session, nonce, dia):
        resp = session.post(
            AJAX_URL,
            data={'action': 'get_lotteries_results', 'nonce': nonce,
                  'date': dia.isoformat()},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': RESULTS_PAGE},
            timeout=self.page_load_timeout,
        )
        resp.raise_for_status()
        payload = json.loads(resp.text)

        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return []
        juegos = (data.get('lotteries') or {}).get('la_primera') or []

        draws = []
        for juego in juegos:
            if not isinstance(juego, dict):
                continue
            nombre = ' '.join(str(juego.get('juego_nombre', '')).split()).upper()
            if nombre != GAME_NAME:
                continue
            turn = self._turn_from_hour(juego.get('hora_sorteo', ''))
            if not turn:
                _logger.warning('Scraper Quinielón: hora no reconocida %r en %s',
                                juego.get('hora_sorteo'), dia)
                continue
            numero = self._parse_numero(juego.get('resultado'))
            if numero is None:
                continue
            draws.append({'date': dia, 'turn': turn, 'numero': numero})
        return draws

    @staticmethod
    def _turn_from_hour(raw):
        m = re.match(r'\s*(\d{1,2}):(\d{2})\s*([ap])\.?m', str(raw).lower())
        if not m:
            return None
        hora = int(m.group(1)) % 12
        if m.group(3) == 'p':
            hora += 12
        return 'afternoon' if hora < 16 else 'evening'

    @staticmethod
    def _parse_numero(resultado):
        """['58'] → 58. Un solo número de 2 dígitos, sin centena."""
        if not isinstance(resultado, (list, tuple)) or not resultado:
            return None
        try:
            return int(str(resultado[0]).strip())
        except (TypeError, ValueError):
            return None

    # ── Importación ───────────────────────────────────────────────

    def _import_draws(self, draws):
        if not draws:
            return ['No hay sorteos nuevos para importar.']

        Output = self.env['lottery.output']
        by_name = {n['name']: n['id']
                   for n in self.env['lottery.number'].search_read([], ['name'])}

        existing = {
            (fields.Date.to_date(rec['date']), rec['turn_day'])
            for rec in Output.search_read([
                ('sorteo_id', '=', self.sorteo_id.id),
                ('date', '>=', draws[0]['date']),
                ('date', '<=', draws[-1]['date']),
            ], ['date', 'turn_day'])
        }

        log_lines, vals_list = [], []
        for draw in draws:
            turn_label = 'Tarde' if draw['turn'] == 'afternoon' else 'Noche'
            label = f"{draw['date']} {turn_label}"
            clave = (draw['date'], draw['turn'])
            if clave in existing:
                log_lines.append(f'[OMITIDO] {label} – ya registrado')
                continue
            existing.add(clave)

            number_id = by_name.get(draw['numero'])
            if not number_id:
                log_lines.append(
                    f'[ERROR] {label} – número {draw["numero"]:02d} no existe en el catálogo')
                continue

            vals_list.append({
                'date':      draw['date'],
                'turn_day':  draw['turn'],
                'sorteo_id': self.sorteo_id.id,
                'number_id': number_id,
            })
            log_lines.append(f'[OK] {label} – {draw["numero"]:02d}')

        if vals_list:
            Output.with_context(skip_next_draw_recompute=True,
                                skip_prediction_validation=True).create(vals_list)
            self.sorteo_id._recompute_next_draw()
            _logger.info('Scraper Quinielón: %d salidas creadas.', len(vals_list))

        return log_lines

    @staticmethod
    def _summarize_log(log_lines):
        if len(log_lines) <= _MAX_DETAIL_LINES:
            return log_lines
        oks    = [l for l in log_lines if l.startswith('[OK]')]
        skips  = [l for l in log_lines if l.startswith('[OMITIDO]')]
        errors = [l for l in log_lines if l.startswith('[ERROR]')]
        otros  = [l for l in log_lines
                  if not l.startswith(('[OK]', '[OMITIDO]', '[ERROR]'))]
        resumen = otros[:5]
        resumen.append(f'{len(oks)} salida(s) importada(s), '
                       f'{len(skips)} ya registrada(s), {len(errors)} con error.')
        if oks:
            resumen += [oks[0], oks[-1]] if len(oks) > 1 else [oks[0]]
        return resumen + errors[:100]

    # ── Sorteo e instancia ────────────────────────────────────────

    @api.model
    def _get_sorteo(self):
        return self.env.ref('lottery_base.sorteo_quinielon')

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'Quinielón',
                               'sorteo_id': self._get_sorteo().id})
        return rec
