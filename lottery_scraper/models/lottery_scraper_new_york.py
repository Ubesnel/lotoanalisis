# -*- coding: utf-8 -*-
import logging
from datetime import date as date_type, datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import build_result_html

_logger = logging.getLogger(__name__)

# Dataset combinado de data.ny.gov (Socrata):
#   "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"
# Cada fila = una fecha, con hasta 4 campos:
#   midday_daily / evening_daily   → Numbers (3 dígitos)  → Premio 1
#   midday_win_4 / evening_win_4   → Win 4   (4 dígitos)  → Premios 2 y 3
# Cobertura: evening_daily desde 1980-09-02, evening_win_4 desde 1981-07-21,
# midday_* desde 2001-12-02 (antes solo existía el sorteo nocturno).
NY_API_URL    = 'https://data.ny.gov/resource/hsys-3def.json'
NY_FIRST_DRAW = date_type(1980, 9, 2)

# Socrata acepta $limit hasta 50000: todo el histórico (~16.7k filas) entra
# en una sola petición.
NY_API_LIMIT = 50000

_TURN_ORDER = {'afternoon': 0, 'evening': 1}

# Si la importación genera más líneas que esto (backfill histórico), el HTML
# de resultado se resume para no guardar/renderizar decenas de miles de filas.
_MAX_DETAIL_LINES = 400


class LotteryScraperNewYork(models.Model):
    _name = 'lottery.scraper.new.york'
    _description = 'Importador automático New York Numbers / Win 4'

    name = fields.Char(default='New York Numbers', readonly=True)
    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=lambda self: self._get_ny_sorteo().id,
        help="A qué lottery.sorteo se le asignan las salidas importadas por "
             "este importador.")

    et_offset = fields.Integer(
        'Offset ET desde UTC', default=-4,
        help='-4 en verano EDT (mar-nov), -5 en invierno EST (nov-mar).')

    page_load_timeout = fields.Integer(
        'Timeout petición (seg)', default=60,
        help='Segundos máximos esperando respuesta de data.ny.gov. El backfill '
             'histórico completo baja ~1 MB en una sola petición.')

    # ── Importación manual por rango de fechas ─────────────────────
    date_from = fields.Date(
        'Fecha desde',
        help='Inicio del rango para la importación manual.\n'
             'Vacío = detecta automáticamente desde el último sorteo registrado.\n'
             'Para el backfill histórico completo usar 1980-09-02.')
    date_to = fields.Date(
        'Fecha hasta',
        help='Fin del rango para la importación manual.\n'
             'Vacío = usa la fecha de hoy (ET).')

    # ── Estado ────────────────────────────────────────────────────
    last_run    = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Html('Último resultado', readonly=True, sanitize=False)

    # ── Entry points ──────────────────────────────────────────────

    @api.model
    def cron_import_results(self):
        """A diferencia de Florida, data.ny.gov publica los resultados con
        retraso variable (horas, a veces recién al día siguiente), así que no
        se usan ventanas horarias: el cron corre cada hora, consulta desde el
        último sorteo registrado hasta hoy ET e importa lo que falte
        (una sola petición por corrida)."""
        scraper = self._get_singleton()
        et_tz    = timezone(timedelta(hours=scraper.et_offset))
        today_et = datetime.now(tz=et_tz).date()

        last = self.env['lottery.output'].search(
            [('sorteo_id', '=', scraper.sorteo_id.id)],
            order='date desc, id desc', limit=1)
        if last and last.date == today_et and last.turn_day == 'evening':
            _logger.debug('Scraper NY: %s ya está completo.', today_et)
            return

        date_from = scraper._get_next_query_date()
        log_lines = [f'Consultando sorteos del {date_from} al {today_et} …']
        try:
            draws = scraper._fetch_draws(date_from=date_from, date_to=today_et)
            log_lines += scraper._import_draws(draws)
        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper NY cron: %s', exc, exc_info=True)

        scraper.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(scraper._summarize_log(log_lines)),
        })

    def action_import_now(self):
        """Importación manual. Si date_from está configurado usa ese rango;
        si no, detecta automáticamente desde el último sorteo registrado
        hasta hoy ET."""
        self.ensure_one()
        log_lines = []
        try:
            et_tz    = timezone(timedelta(hours=self.et_offset))
            today_et = datetime.now(tz=et_tz).date()

            if self.date_from:
                date_from = self.date_from
                date_to   = self.date_to or today_et
            else:
                date_from = self._get_next_query_date()
                date_to   = today_et

            log_lines.append(f'Consultando sorteos del {date_from} al {date_to} …')
            draws = self._fetch_draws(date_from=date_from, date_to=date_to)

            if not draws:
                log_lines.append('No se encontraron sorteos para ese período.')
            else:
                log_lines.append(f'{len(draws)} sorteo(s) encontrado(s) — importando …')
                log_lines += self._import_draws(draws)

        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper NY manual: %s', exc, exc_info=True)

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(self._summarize_log(log_lines)),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    # ── Detección de próxima fecha a consultar ─────────────────────

    def _get_next_query_date(self):
        """Sin registros → hoy ET. Último fue tarde → misma fecha (falta la
        noche). Último fue noche → día siguiente. Nunca una fecha futura."""
        et_tz    = timezone(timedelta(hours=self.et_offset))
        today_et = datetime.now(tz=et_tz).date()

        last = self.env['lottery.output'].search(
            [('sorteo_id', '=', self.sorteo_id.id)], order='date desc, id desc', limit=1)
        if not last:
            return today_et
        if last.turn_day == 'afternoon':
            return last.date
        return min(last.date + timedelta(days=1), today_et)

    # ── Fetch + parseo ────────────────────────────────────────────

    def _fetch_draws(self, date_from, date_to):
        """Consulta la API Socrata de data.ny.gov para el rango indicado.
        Retorna lista de dicts ordenada por fecha+turno:
          {'date', 'turn', 'centena', 'numero', 'premio2', 'premio3'}"""
        try:
            import requests
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\nInstala con: pip install requests'
            ) from exc

        params = {
            '$where': (f"draw_date >= '{date_from}T00:00:00' "
                       f"AND draw_date <= '{date_to}T00:00:00'"),
            '$order': 'draw_date',
            '$limit': NY_API_LIMIT,
        }
        _logger.info('Scraper NY: consultando API %s → %s', date_from, date_to)
        resp = requests.get(NY_API_URL, params=params,
                            timeout=self.page_load_timeout)
        resp.raise_for_status()
        rows = resp.json()
        if not isinstance(rows, list):
            raise UserError(f'Respuesta inesperada de la API: {rows!r:.200}')
        if len(rows) >= NY_API_LIMIT:
            _logger.warning('Scraper NY: respuesta alcanzó el límite de %d filas; '
                            'puede haber datos faltantes.', NY_API_LIMIT)

        draws = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            draw_date = self._parse_date(row.get('draw_date', ''))
            if not draw_date:
                _logger.warning('Scraper NY: fecha no reconocida: %r', row.get('draw_date'))
                continue
            for daily_key, win4_key, turn in (
                ('midday_daily', 'midday_win_4', 'afternoon'),
                ('evening_daily', 'evening_win_4', 'evening'),
            ):
                draw = self._parse_turn(row, draw_date, daily_key, win4_key, turn)
                if draw:
                    draws.append(draw)

        draws.sort(key=lambda d: (d['date'], _TURN_ORDER.get(d['turn'], 0)))
        return draws

    @staticmethod
    def _parse_turn(row, draw_date, daily_key, win4_key, turn):
        """Extrae un turno de una fila del dataset. El Numbers (3 dígitos) es
        obligatorio; el Win 4 (4 dígitos) es opcional (no existe en el
        histórico previo a 1981/2001).

        OJO: el dataset guarda los números como enteros, sin ceros a la
        izquierda ('56' = 056, '2' = 002, '497' = 0497) → se rellena con
        zfill antes de trocear."""
        daily = str(row.get(daily_key) or '').strip()
        if not daily:
            return None
        if not daily.isdigit() or len(daily) > 3:
            _logger.warning('Scraper NY: %s %s inválido: %r', draw_date, daily_key, daily)
            return None
        daily = daily.zfill(3)

        draw = {
            'date':    draw_date,
            'turn':    turn,
            'centena': int(daily[0]),
            'numero':  int(daily[1:]),
            'premio2': None,
            'premio3': None,
        }

        win4 = str(row.get(win4_key) or '').strip()
        if win4:
            if win4.isdigit() and len(win4) <= 4:
                win4 = win4.zfill(4)
                # Mismo criterio que el Pick 4 de Florida:
                # Premio 2 = primer par de dígitos, Premio 3 = segundo par.
                draw['premio2'] = int(win4[:2])
                draw['premio3'] = int(win4[2:])
            else:
                _logger.warning('Scraper NY: %s %s inválido: %r', draw_date, win4_key, win4)
        return draw

    @staticmethod
    def _parse_date(raw):
        """'1980-09-02T00:00:00.000' → date."""
        try:
            return datetime.fromisoformat(str(raw).replace('Z', '')).date()
        except ValueError:
            return None

    # ── Importación ───────────────────────────────────────────────

    def _import_draws(self, draws):
        """Importa una lista de draws ya ordenada. Para soportar el backfill
        histórico (~33k sorteos) evita búsquedas por registro: precarga el
        catálogo lottery.number y las salidas ya existentes del rango."""
        if not draws:
            return ['No hay sorteos nuevos para importar.']

        Output = self.env['lottery.output']

        # Catálogo de números: name → id (y aparte los que sirven de centena)
        by_name, hundreds_by_name = {}, {}
        for num in self.env['lottery.number'].search_read(
                [], ['name', 'can_use_hundreds']):
            by_name[num['name']] = num['id']
            if num['can_use_hundreds']:
                hundreds_by_name[num['name']] = num['id']

        # Salidas ya registradas en el rango: (date, turn) → existe
        existing = {
            (rec['date'], rec['turn_day'])
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

            # `existing` también deduplica dentro de la misma corrida: el
            # dataset trae alguna fila repetida y la constraint unique
            # (date, turn_day, sorteo_id) tumbaría el create en lote.
            if (draw['date'], draw['turn']) in existing:
                log_lines.append(f'[OMITIDO] {label} – ya registrado')
                continue
            existing.add((draw['date'], draw['turn']))

            number_id   = by_name.get(draw['numero'])
            hundreds_id = hundreds_by_name.get(draw['centena'])
            if not number_id or not hundreds_id:
                log_lines.append(
                    f'[ERROR] {label} – número {draw["centena"]}{draw["numero"]:02d} '
                    f'no existe en el catálogo')
                continue

            vals = {
                'date':        draw['date'],
                'turn_day':    draw['turn'],
                'sorteo_id':   self.sorteo_id.id,
                'number_id':   number_id,
                'hundreds_id': hundreds_id,
            }
            p2_str = p3_str = ''
            if draw['premio2'] is not None:
                premio2_id = by_name.get(draw['premio2'])
                if premio2_id:
                    vals['premio_2_id'] = premio2_id
                    p2_str = f' | P2:{draw["premio2"]:02d}'
                else:
                    _logger.warning('Scraper NY: Premio2 %02d no existe en lottery.number',
                                    draw['premio2'])
            if draw['premio3'] is not None:
                premio3_id = by_name.get(draw['premio3'])
                if premio3_id:
                    vals['premio_3_id'] = premio3_id
                    p3_str = f' P3:{draw["premio3"]:02d}'
                else:
                    _logger.warning('Scraper NY: Premio3 %02d no existe en lottery.number',
                                    draw['premio3'])

            vals_list.append(vals)
            log_lines.append(
                f'[OK] {label} – {draw["centena"]}{draw["numero"]:02d}{p2_str}{p3_str}')

        if vals_list:
            Output.create(vals_list)
            _logger.info('Scraper NY: %d salidas creadas.', len(vals_list))

        return log_lines

    @staticmethod
    def _summarize_log(log_lines):
        """En backfills grandes el detalle completo es inmanejable como HTML:
        se resume en totales + errores (máx. 100) + primera/última línea OK."""
        if len(log_lines) <= _MAX_DETAIL_LINES:
            return log_lines

        oks      = [l for l in log_lines if l.startswith('[OK]')]
        skips    = [l for l in log_lines if l.startswith('[OMITIDO]')]
        errors   = [l for l in log_lines if l.startswith('[ERROR]')]
        others   = [l for l in log_lines
                    if not l.startswith(('[OK]', '[OMITIDO]', '[ERROR]'))]

        summary = others[:5]
        summary.append(
            f'Resumen: {len(oks)} importados · {len(skips)} omitidos · '
            f'{len(errors)} errores.')
        if oks:
            summary.append(oks[0])
            if len(oks) > 1:
                summary.append(oks[-1])
        summary += errors[:100]
        if len(errors) > 100:
            summary.append(f'… y {len(errors) - 100} errores más (ver log del servidor).')
        return summary

    # ── Singleton ─────────────────────────────────────────────────

    @api.model
    def _get_ny_sorteo(self):
        """Devuelve el sorteo New York. Si el xml_id de lottery_base todavía
        no fue cargado (el data vive en lottery_base y actualizar ese módulo
        es pesado), lo crea acá mismo junto con su ir.model.data, de modo que
        una futura actualización de lottery_base lo encuentre y no lo
        duplique (la sección es noupdate)."""
        sorteo = self.env.ref('lottery_base.sorteo_new_york', raise_if_not_found=False)
        if sorteo:
            return sorteo

        # sudo(): la record rule "Sorteos: solo los permitidos al usuario"
        # ocultaría un sorteo existente y provocaría un duplicado.
        Sorteo = self.env['lottery.sorteo'].sudo()
        sorteo = Sorteo.search([('code', '=', 'new_york')], limit=1)
        if not sorteo:
            sorteo = Sorteo.create({
                'name': 'New York',
                'code': 'new_york',
                'sequence': 2,
                'uses_fireball': False,
                # Histórico 1980-2001 solo tiene turno Noche: la continuidad
                # Tarde→Noche rompería la importación de esos años.
                'enforce_turn_continuity': False,
                'is_pick3': True,
                'source_code': 'new_york',
            })
            _logger.info('Scraper NY: sorteo New York creado (id=%d).', sorteo.id)
        self.env['ir.model.data'].sudo().create({
            'module': 'lottery_base',
            'name': 'sorteo_new_york',
            'model': 'lottery.sorteo',
            'res_id': sorteo.id,
            'noupdate': True,
        })
        return sorteo

    @api.model
    def _get_singleton(self):
        new_york = self._get_ny_sorteo()
        rec = self.search([('sorteo_id', '=', new_york.id)], limit=1)
        if not rec:
            rec = self.create({'name': 'New York Numbers', 'sorteo_id': new_york.id})
        return rec
