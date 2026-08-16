# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import date as date_type, datetime, timezone, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SCRAPER_URL    = 'https://floridalottery.com/es/games/draw-games/pick-3'
FLORIDA_API    = 'https://apim-website-prod-eastus.azure-api.net/drawgamesapp/searchgames'
PICK3_GAME_ID  = 104
PICK4_GAME_ID  = 108
PICK2_GAME_ID  = 127

# Qué game id de la API le corresponde a cada juego soportado por este importador.
GAME_IDS = {
    'pick3': PICK3_GAME_ID,
    'pick2': PICK2_GAME_ID,
}

# La API de Florida devuelve JSON SINTÁCTICAMENTE INVÁLIDO cuando un número no
# existe: emite  {"NumberPick": ,"NumberType": "fb"}  sin valor. Pasa en todos
# los sorteos anteriores al 18/01/2021, fecha en que se incorporó la Fireball
# (3.262 casos solo en el histórico de Pick 2). json.loads revienta con eso, así
# que hay que rellenar el hueco con null antes de parsear.
_EMPTY_NUMBER_RE = re.compile(r'"NumberPick":\s*,')

# A partir de esta cantidad de sorteos, la importación manual usa el camino
# masivo en vez de crear de a uno (ver _import_draws_bulk).
_BULK_THRESHOLD = 200

# La API rechaza con 400 los endDate de más de 2 años atrás. Se usa un margen
# holgado sobre los ~730 días reales para no quedar pegado al borde.
API_END_MAX_AGE_DAYS = 700

# Un rango histórico ancho devuelve varios MB y la API tarda más de un minuto
# (el histórico completo de Pick 2 son ~3 MB). El timeout configurado sirve
# para el cron diario, que pide un solo día y conviene que falle rápido; para
# rangos largos se usa este, más holgado.
HISTORIC_SPAN_DAYS = 400
HISTORIC_TIMEOUT   = 300

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/147.0.0.0 Safari/537.36'
    ),
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;'
        'q=0.9,image/avif,image/webp,*/*;q=0.8'
    ),
    'Accept-Language': 'es-US,es;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}

# Headers específicos para la API de Florida Lottery (Azure APIM)
# x-partner: web es la clave que identifica peticiones del sitio oficial
_API_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/147.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Origin': 'https://floridalottery.com',
    'Referer': 'https://floridalottery.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'x-partner': 'web',
}

_ES_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'apr': 4, 'aug': 8, 'dec': 12,
}

_AFTERNOON_KW = ('midday', 'mid', 'tarde', 'afternoon', 'día', 'dia')
_EVENING_KW   = ('evening', 'eve', 'noche', 'night')
_TURN_ORDER   = {'afternoon': 0, 'evening': 1}


class LotteryScraper(models.Model):
    _name = 'lottery.scraper'
    _description = 'Importador automático Florida Pick 3'

    name = fields.Char(default='Florida Pick 3', readonly=True)
    auto_import = fields.Boolean(
        string='Importación automática', default=True,
        help="Si está desactivado, el cron ignora este importador y solo se puede "
             "importar a mano con el botón. Pensado para dejar un importador nuevo "
             "en observación hasta validarlo, sin frenar a los demás.")
    game_code = fields.Selection([
        ('pick3', 'Pick 3 (+ Pick 4 para los corridos)'),
        ('pick2', 'Pick 2 (2 dígitos, sin centena)'),
    ], string='Juego', default='pick3', required=True,
        help="Qué juego de Florida consulta este importador. Define el id que se le pide "
             "a la API y cómo se arma el número:\n"
             "· Pick 3 → centena + número de 2 dígitos + bola extra, y se enriquece con "
             "Pick 4 para los corridos (Premio 2 y 3).\n"
             "· Pick 2 → solo el número de 2 dígitos. Sin centena, sin corridos y sin bola "
             "extra (Florida sortea una sola Fireball, que ya queda registrada en Pick 3).")
    sorteo_id = fields.Many2one('lottery.sorteo', string='Sorteo', required=True, index=True,
                                default=lambda self: self.env.ref('lottery_base.sorteo_florida').id,
                                help="A qué lottery.sorteo se le asignan las salidas importadas por este "
                                     "scraper. Cada proveedor de datos (Florida, Quiniela UY, etc.) tendrá "
                                     "su propio modelo/registro de importador, todos apuntando a su "
                                     "sorteo correspondiente.")

    # ── Ventanas horarias (hora ET como decimal, ej. 14.5 = 2:30 PM) ──
    afternoon_start = fields.Float('Inicio ventana Tarde (ET)', default=14.0)
    afternoon_end   = fields.Float('Fin ventana Tarde (ET)',    default=15.5)
    evening_start   = fields.Float('Inicio ventana Noche (ET)', default=22.0)
    evening_end     = fields.Float('Fin ventana Noche (ET)',    default=23.5)
    et_offset       = fields.Integer(
        'Offset ET desde UTC', default=-4,
        help='-4 en verano EDT (mar-nov), -5 en invierno EST (nov-mar).')

    # ── Conexión HTTP ──────────────────────────────────────────────
    page_load_timeout = fields.Integer(
        'Timeout petición (seg)', default=30,
        help='Segundos máximos esperando respuesta del servidor.')
    api_url = fields.Char(
        'URL de API (opcional)', default='',
        help='URL directa de la API JSON del sitio.\n'
             'Dejar vacío para usar la página principal.\n'
             'Ejemplo: https://floridalottery.com/api/v1/pick3/results')

    # ── Importación manual por rango de fechas ─────────────────────
    date_from = fields.Date(
        'Fecha desde',
        help='Inicio del rango para la importación manual.\n'
             'Vacío = detecta automáticamente desde el último sorteo registrado.')
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
        """Corre los importadores de Florida con la automática habilitada, no
        solo el de Pick 3. Cada registro tiene su propio sorteo y sus propias
        ventanas horarias, así que se evalúan por separado y que uno falle no
        frena a los demás. Pick 2 y Pick 3 publican a la misma hora, así que en
        la práctica corren juntos."""
        # Si la base no tiene ningún importador todavía, crear el de Pick 3
        # (comportamiento histórico). Después se corren solo los habilitados.
        if not self.search_count([]):
            self._get_singleton()
        for scraper in self.search([('auto_import', '=', True)]):
            try:
                scraper._cron_import_one()
            except Exception:
                _logger.exception('Scraper %s (%s): error en la corrida automática.',
                                  scraper.name, scraper.game_code)

    def _cron_import_one(self):
        """Corrida automática de UN importador, respetando su ventana horaria."""
        self.ensure_one()
        et_tz    = timezone(timedelta(hours=self.et_offset))
        now_et   = datetime.now(tz=et_tz)
        hour_et  = now_et.hour + now_et.minute / 60.0
        today_et = now_et.date()

        Output    = self.env['lottery.output']
        log_lines = []

        if self.afternoon_start <= hour_et <= self.afternoon_end:
            if Output.search([('date', '=', today_et), ('turn_day', '=', 'afternoon'),
                              ('sorteo_id', '=', self.sorteo_id.id)], limit=1):
                _logger.debug('Scraper %s Tarde %s: ya registrada.', self.game_code, today_et)
                return
            _logger.info('Scraper %s: ventana Tarde activa.', self.game_code)
            log_lines += self._run_for_turn('afternoon', today_et)

        elif self.evening_start <= hour_et <= self.evening_end:
            if Output.search([('date', '=', today_et), ('turn_day', '=', 'evening'),
                              ('sorteo_id', '=', self.sorteo_id.id)], limit=1):
                _logger.debug('Scraper %s Noche %s: ya registrada.', self.game_code, today_et)
                return
            _logger.info('Scraper %s: ventana Noche activa.', self.game_code)
            log_lines += self._run_for_turn('evening', today_et)

        else:
            _logger.debug('Scraper %s: %02d:%02d ET fuera de ventanas.',
                          self.game_code, now_et.hour, now_et.minute)
            return

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': self._build_result_html(log_lines),
        })

    def action_import_now(self):
        """
        Importación manual sin validar ventana horaria.
        Si date_from está configurado usa ese rango; si no, detecta automáticamente
        desde el último sorteo registrado hasta hoy ET.
        Ordena todos los sorteos por fecha+turno y crea los que faltan.
        """
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
                # Ordenar por fecha y turno (tarde antes que noche)
                draws.sort(key=lambda d: (d['date'], _TURN_ORDER.get(d['turn'], 0)))
                log_lines.append(f'{len(draws)} sorteo(s) encontrado(s) — importando …')
                if len(draws) > _BULK_THRESHOLD:
                    log_lines += self._import_draws_bulk(draws)
                else:
                    for draw in draws:
                        log_lines.append(self._import_draw(draw))

        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper manual: %s', exc, exc_info=True)

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': self._build_result_html(log_lines),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    # ── Scraping con requests (sin Selenium) ─────────────────────

    def _get_next_query_date(self):
        """
        Determina qué fecha consultar en la API según el último sorteo registrado:
          - Sin registros        → hoy ET
          - Último fue tarde     → misma fecha  (falta noche de ese día)
          - Último fue noche     → día siguiente (falta tarde del próximo día)
        Nunca retorna una fecha futura a hoy ET.
        """
        et_tz    = timezone(timedelta(hours=self.et_offset))
        today_et = datetime.now(tz=et_tz).date()

        last = self.env['lottery.output'].search(
            [('sorteo_id', '=', self.sorteo_id.id)], order='date desc, id desc', limit=1)

        if not last:
            return today_et

        if last.turn_day == 'afternoon':
            return last.date                          # pedir noche del mismo día
        else:
            return min(last.date + timedelta(days=1), today_et)  # pedir tarde del día siguiente

    def _fetch_draws(self, date_from=None, date_to=None):
        """
        Obtiene sorteos via HTTP requests, sin Selenium ni WebDriver.
        Estrategias en orden:
          1. API oficial de Florida Lottery (Azure APIM) con fecha ET dinámica
          2. URL de API personalizada (campo api_url)
          3. GET de la página + parse HTML (SSR fallback)
        """
        try:
            import requests
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\n'
                'Instala con: pip install requests beautifulsoup4'
            ) from exc

        session = requests.Session()
        session.headers.update(_HEADERS)
        timeout = self.page_load_timeout

        errors = []

        # ── 1. API oficial Florida Lottery ─────────────────────
        try:
            draws = self._fetch_florida_api(session, timeout,
                                            date_from=date_from, date_to=date_to)
            if draws:
                _logger.info('Scraper %s: %d sorteos obtenidos via API oficial.',
                             self.game_code, len(draws))
                # Enriquecer con datos de Pick 4 (Premio 2 y Premio 3).
                # Solo Pick 3: Pick 2 no tiene corridos.
                if self.game_code == 'pick3':
                    ef = date_from or draws[0]['date']
                    et = date_to or draws[-1]['date']
                    pick4_index = self._fetch_pick4_index(session, timeout, ef, et)
                    for draw in draws:
                        p4 = pick4_index.get((draw['date'], draw['turn']), {})
                        draw['premio2'] = p4.get('premio2')
                        draw['premio3'] = p4.get('premio3')
                return draws
            errors.append('API oficial: no retornó sorteos para la fecha consultada.')
        except Exception as exc:
            errors.append(f'API oficial: {exc}')
            _logger.warning('Scraper: API oficial falló: %s', exc, exc_info=True)

        # ── 2. URL de API personalizada ────────────────────────
        if self.api_url:
            try:
                resp = session.get(self.api_url, timeout=timeout)
                resp.raise_for_status()
                draws = self._extract_draws_from_json(resp.json())
                if draws:
                    _logger.info('Scraper: %d sorteos obtenidos via API personalizada.', len(draws))
                    return draws
                errors.append('API personalizada: no retornó sorteos.')
            except Exception as exc:
                errors.append(f'API personalizada: {exc}')
                _logger.warning('Scraper: API personalizada falló: %s', exc, exc_info=True)

        # ── 3. GET página principal (SSR fallback) ─────────────
        try:
            from bs4 import BeautifulSoup
            resp = session.get(SCRAPER_URL, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            if soup.find(class_='draw-date--pick3'):
                _logger.info('Scraper: datos encontrados en HTML (SSR).')
                return self._parse_draws(soup)
            draws = self._parse_json_scripts(soup)
            if draws:
                return draws
            errors.append('Fallback HTML: sin datos de sorteo en la página.')
        except Exception as exc:
            errors.append(f'Fallback HTML: {exc}')
            _logger.warning('Scraper: fallback HTML falló: %s', exc, exc_info=True)

        raise UserError('No se pudieron obtener los sorteos:\n\n' + '\n'.join(errors))

    @staticmethod
    def _api_json(resp):
        """json de la API de Florida, reparando los "NumberPick" vacíos.

        No se usa resp.json() a propósito: la API emite JSON inválido para los
        sorteos sin Fireball (anteriores al 18/01/2021) y el parser estándar
        falla con 'Expecting value'. Ver _EMPTY_NUMBER_RE.
        """
        data = json.loads(_EMPTY_NUMBER_RE.sub('"NumberPick": null,', resp.text))
        return data if isinstance(data, list) else [data]

    def _fetch_pick4_index(self, session, timeout, date_from, date_to):
        """
        Consulta la API de Pick 4 (ID=108) para el rango de fechas indicado.
        Retorna dict keyed por (date, turn) → {'premio2': int, 'premio3': int}.
        Premio 2 = wn1·wn2 (primer par), Premio 3 = wn3·wn4 (segundo par).
        """
        start_str = date_from.strftime('%d-%b-%Y').upper()
        end_str   = date_to.strftime('%d-%b-%Y').upper()
        try:
            resp = session.get(
                FLORIDA_API,
                params={'id': PICK4_GAME_ID, 'startDate': start_str, 'endDate': end_str},
                headers=_API_HEADERS,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = self._api_json(resp)
        except Exception as exc:
            _logger.warning('Scraper Pick4: API falló: %s', exc)
            return {}

        index = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            draw_date = self._parse_date(item.get('DrawDate', ''))
            if not draw_date:
                continue
            draw_type = str(item.get('DrawType', '')).upper()
            turn = 'afternoon' if draw_type == 'MIDDAY' else 'evening'
            numbers = item.get('DrawNumbers', [])
            wn = {n['NumberType']: n['NumberPick']
                  for n in numbers if isinstance(n, dict) and 'NumberType' in n}
            if not all(k in wn for k in ('wn1', 'wn2', 'wn3', 'wn4')):
                continue
            try:
                premio2 = int(str(wn['wn1']) + str(wn['wn2']))
                premio3 = int(str(wn['wn3']) + str(wn['wn4']))
            except (ValueError, KeyError):
                continue
            index[(draw_date, turn)] = {'premio2': premio2, 'premio3': premio3}
            _logger.info('Scraper Pick4: %s %s → P2=%02d P3=%02d',
                         draw_date, turn, premio2, premio3)
        return index

    def _fetch_florida_api(self, session, timeout, date_from=None, date_to=None):
        """
        Llama a la API oficial de Florida Lottery para el rango de fechas indicado.
        URL: https://apim-website-prod-eastus.azure-api.net/drawgamesapp/searchgames
        Params: id según el juego (104 Pick 3 · 127 Pick 2), startDate/endDate en
        formato DD-MMM-YYYY (ej: 29-APR-2026).
        Si no se indican fechas usa la ET de hoy para ambas.

        OJO con el endDate: la API rechaza con 400 cualquier endDate de más de
        dos años atrás ("endDate cannot be before 2 years"). El límite es SOLO
        del endDate: el startDate puede ser tan viejo como se quiera. Por eso,
        cuando se pide un rango histórico cerrado (ej. agosto de 2016), se le
        pide a la API hasta HOY y el rango se recorta acá.
        """
        et_tz = timezone(timedelta(hours=self.et_offset))
        today = datetime.now(tz=et_tz).date()

        if date_from is None:
            date_from = today
        if date_to is None:
            date_to = date_from

        # endDate seguro: si el pedido cae fuera de la ventana que acepta la API,
        # se consulta hasta hoy y después se filtra al rango real.
        api_end = date_to
        if api_end < today - timedelta(days=API_END_MAX_AGE_DAYS):
            _logger.info('Scraper %s: endDate %s excede la ventana de la API; '
                         'se consulta hasta hoy (%s) y se recorta localmente.',
                         self.game_code, date_to, today)
            api_end = today

        start_str = date_from.strftime('%d-%b-%Y').upper()
        end_str   = api_end.strftime('%d-%b-%Y').upper()
        game_id   = GAME_IDS.get(self.game_code, PICK3_GAME_ID)

        # Rango ancho = varios MB y más de un minuto de espera: el timeout del
        # cron diario (30 s por defecto) no alcanza.
        if (api_end - date_from).days > HISTORIC_SPAN_DAYS:
            timeout = max(timeout, HISTORIC_TIMEOUT)

        _logger.info('Scraper %s (id=%s): consultando API Florida %s → %s (timeout %ss)',
                     self.game_code, game_id, start_str, end_str, timeout)

        resp = session.get(
            FLORIDA_API,
            params={'id': game_id, 'startDate': start_str, 'endDate': end_str},
            headers=_API_HEADERS,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            # El cuerpo trae el motivo real (ej. "endDate cannot be before 2
            # years"); raise_for_status solo deja el código y no se ve nunca.
            raise UserError('La API de Florida respondió %s: %s'
                            % (resp.status_code, (resp.text or '').strip()[:300]))

        data = self._api_json(resp)

        draws = []
        for item in data:
            draw = self._parse_florida_api_item(item)
            if draw and date_from <= draw['date'] <= date_to:
                draws.append(draw)
        return draws

    def _parse_florida_api_item(self, item):
        """
        Parsea un resultado de la API oficial.
        Estructura esperada:
          DrawType:    "MIDDAY" | "EVENING"
          DrawDate:    "04/29/2026 12:00:00 AM"
          DrawNumbers: [
            {"NumberPick": 3, "NumberType": "wn1"},
            {"NumberPick": 8, "NumberType": "wn2"},
            {"NumberPick": 7, "NumberType": "wn3"},
            {"NumberPick": 0, "NumberType": "fb"},
          ]
        """
        if not isinstance(item, dict):
            return None

        draw_date = self._parse_date(item.get('DrawDate', ''))
        if not draw_date:
            _logger.warning('Scraper API: fecha no reconocida: %r', item.get('DrawDate'))
            return None

        draw_type = str(item.get('DrawType', '')).upper()
        turn = 'afternoon' if draw_type == 'MIDDAY' else 'evening'

        numbers = item.get('DrawNumbers', [])
        wn = {n['NumberType']: n['NumberPick']
              for n in numbers if isinstance(n, dict) and 'NumberType' in n}

        # Pick 2: solo wn1 y wn2 → número de 2 dígitos. Sin centena y sin bola
        # extra (la Fireball que trae la API es la misma de Pick 3, ya registrada
        # en ese sorteo; guardarla acá sería duplicar el dato).
        if self.game_code == 'pick2':
            if wn.get('wn1') is None or wn.get('wn2') is None:
                _logger.warning('Scraper API Pick2: números incompletos: %s', wn)
                return None
            try:
                numero = int(str(wn['wn1']) + str(wn['wn2']))
            except (ValueError, TypeError) as exc:
                _logger.warning('Scraper API Pick2: error convirtiendo números: %s', exc)
                return None
            _logger.info('Scraper API Pick2: %s %s → N=%02d', draw_date, turn, numero)
            return {'date': draw_date, 'turn': turn, 'numero': numero}

        if any(wn.get(k) is None for k in ('wn1', 'wn2', 'wn3', 'fb')):
            _logger.warning('Scraper API: números incompletos: %s', wn)
            return None

        try:
            centena = int(wn['wn1'])
            numero  = int(str(wn['wn2']) + str(wn['wn3']))
            extra   = int(wn['fb'])
        except (ValueError, KeyError) as exc:
            _logger.warning('Scraper API: error convirtiendo números: %s', exc)
            return None

        _logger.info('Scraper API: %s %s → C=%d N=%02d FB=%d',
                     draw_date, turn, centena, numero, extra)
        return {'date': draw_date, 'turn': turn,
                'centena': centena, 'numero': numero, 'extra': extra}

    def _parse_json_scripts(self, soup):
        """
        Busca datos de sorteo en <script> del HTML.
        Cubre Next.js (__NEXT_DATA__), scripts application/json e inline patterns.
        """
        # Next.js: <script id="__NEXT_DATA__" type="application/json">
        tag = soup.find('script', id='__NEXT_DATA__')
        if tag and tag.string:
            try:
                draws = self._extract_draws_from_json(json.loads(tag.string))
                if draws:
                    _logger.info('Scraper: datos obtenidos de __NEXT_DATA__.')
                    return draws
            except Exception as exc:
                _logger.debug('Scraper: __NEXT_DATA__ sin datos útiles: %s', exc)

        # Scripts type="application/json" genéricos
        for tag in soup.find_all('script', type='application/json'):
            if not tag.string:
                continue
            try:
                draws = self._extract_draws_from_json(json.loads(tag.string))
                if draws:
                    _logger.info('Scraper: datos obtenidos de script JSON genérico.')
                    return draws
            except Exception:
                pass

        # Patrones inline: window.__X__ = {...}
        for tag in soup.find_all('script'):
            text = tag.string or ''
            for pattern in (
                r'__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;',
                r'window\.__DATA__\s*=\s*(\{.+?\})\s*;',
                r'window\.__STATE__\s*=\s*(\{.+?\})\s*;',
                r'window\.__NUXT__\s*=\s*(\{.+?\})\s*;',
            ):
                m = re.search(pattern, text, re.DOTALL)
                if m:
                    try:
                        draws = self._extract_draws_from_json(json.loads(m.group(1)))
                        if draws:
                            _logger.info('Scraper: datos obtenidos de inline script.')
                            return draws
                    except Exception:
                        pass

        return []

    def _extract_draws_from_json(self, data, depth=0):
        """
        Recorre recursivamente un JSON buscando estructuras de sorteo.
        Retorna lista de dicts con: date, turn, centena, numero, extra.
        """
        if depth > 8:
            return []

        draws = []

        if isinstance(data, list):
            for item in data:
                result = self._try_parse_json_item(item)
                if result:
                    draws.append(result)
                elif isinstance(item, (dict, list)):
                    draws.extend(self._extract_draws_from_json(item, depth + 1))

        elif isinstance(data, dict):
            result = self._try_parse_json_item(data)
            if result:
                draws.append(result)
            else:
                for v in data.values():
                    if isinstance(v, (dict, list)):
                        draws.extend(self._extract_draws_from_json(v, depth + 1))

        return draws

    def _try_parse_json_item(self, item):
        """
        Intenta extraer un sorteo de un dict JSON.
        Busca campos típicos de APIs de lotería.
        """
        if not isinstance(item, dict):
            return None

        # ── Números ganadores ──────────────────────────────────
        numbers = None
        for key in ('winningNumbers', 'winning_numbers', 'numbers', 'drawNumbers',
                    'draw_numbers', 'results', 'picks'):
            val = item.get(key)
            if isinstance(val, list) and len(val) >= 3:
                nums = [str(v).strip() for v in val if str(v).strip().isdigit()]
                if len(nums) >= 3:
                    numbers = nums
                    break
            elif isinstance(val, str):
                nums = re.findall(r'\d+', val)
                if len(nums) >= 3:
                    numbers = nums
                    break
        if not numbers:
            return None

        # ── Fecha ──────────────────────────────────────────────
        draw_date = None
        for key in ('drawDate', 'draw_date', 'date', 'drawDateTime', 'draw_datetime'):
            val = item.get(key)
            if val:
                draw_date = self._parse_date(str(val))
                if draw_date:
                    break
        if not draw_date:
            return None

        # ── Turno ──────────────────────────────────────────────
        turn = 'afternoon'
        for key in ('drawTime', 'draw_time', 'time', 'turn', 'period', 'drawName', 'name'):
            val = str(item.get(key, '')).lower()
            if any(kw in val for kw in _EVENING_KW):
                turn = 'evening'
                break
            if any(kw in val for kw in _AFTERNOON_KW):
                turn = 'afternoon'
                break

        # ── Bola extra / Fireball ──────────────────────────────
        extra = None
        for key in ('fireball', 'bonus', 'extra', 'bonusNumber', 'bonus_number',
                    'fireballNumber', 'fireball_number'):
            val = item.get(key)
            if val is not None and str(val).strip().isdigit():
                extra = int(str(val).strip())
                break
        if extra is None and len(numbers) >= 4:
            extra = int(numbers[3])
        if extra is None:
            return None  # fireball requerido

        try:
            centena = int(numbers[0])
            numero  = int(numbers[1] + numbers[2])
            return {'date': draw_date, 'turn': turn,
                    'centena': centena, 'numero': numero, 'extra': extra}
        except (ValueError, IndexError):
            return None

    # ── Lógica de importación ─────────────────────────────────────

    def _run_for_turn(self, expected_turn, today_et):
        try:
            draws = self._fetch_draws(date_from=today_et, date_to=today_et)
        except Exception as exc:
            msg = f'[ERROR] al obtener datos: {exc}'
            _logger.error('Scraper: %s', msg)
            return [msg]

        matched = [d for d in draws
                   if d['turn'] == expected_turn and d['date'] == today_et]
        if not matched:
            turn_label = 'Tarde' if expected_turn == 'afternoon' else 'Noche'
            msg = f'[PENDIENTE] Sorteo {turn_label} del {today_et} aún no disponible.'
            _logger.info('Scraper: %s', msg)
            return [msg]

        return [self._import_draw(d) for d in matched]

    # ── Parsing HTML ──────────────────────────────────────────────

    def _parse_draws(self, soup):
        draws = []
        date_elements = soup.find_all(class_='draw-date--pick3')

        if not date_elements:
            _logger.warning('Scraper: .draw-date--pick3 no encontrado en el HTML.')
            return draws

        for date_el in date_elements:
            container = self._find_draw_container(date_el)
            if not container:
                continue

            numbers_ul = container.find(class_='game-numbers--pick3')
            if not numbers_ul:
                continue

            li_items = [li for li in numbers_ul.find_all('li')
                        if li.get_text(strip=True).isdigit()]
            if len(li_items) < 3:
                _logger.warning('Scraper: esperaba ≥3 li numéricos, encontró %d', len(li_items))
                continue

            bonus_el = container.find(class_='game-numbers__bonus')
            extra_text = None
            if bonus_el:
                bonus_span = bonus_el.find(class_='game-numbers__bonus-text')
                if bonus_span:
                    extra_text = bonus_span.get_text(strip=True)
            if not extra_text and len(li_items) >= 4:
                extra_text = li_items[3].get_text(strip=True)

            if not extra_text or not extra_text.isdigit():
                _logger.warning('Scraper: bola extra inválida: %r', extra_text)
                continue

            draw_date = self._parse_date(date_el.get_text(strip=True))
            if not draw_date:
                _logger.warning('Scraper: fecha no reconocida: %r', date_el.get_text(strip=True))
                continue

            try:
                centena = int(li_items[0].get_text(strip=True))
                numero  = int(li_items[1].get_text(strip=True) + li_items[2].get_text(strip=True))
                extra   = int(extra_text)
            except ValueError as exc:
                _logger.warning('Scraper: dígitos inválidos %s: %s', draw_date, exc)
                continue

            turn = self._detect_turn(container)
            draws.append({
                'date': draw_date, 'turn': turn,
                'centena': centena, 'numero': numero, 'extra': extra,
            })
            _logger.info('Scraper: %s %s → C=%d N=%02d FB=%d',
                         draw_date, turn, centena, numero, extra)

        return draws

    def _find_draw_container(self, date_el):
        node = date_el.parent
        for _ in range(8):
            if node is None:
                break
            if node.find(class_='game-numbers--pick3'):
                return node
            node = node.parent
        return None

    def _detect_turn(self, container):
        for scope in (container, container.parent if container.parent else None):
            if scope is None:
                continue
            if scope.find('svg', class_=lambda c: c and 'fa-sun' in c.split()):
                return 'afternoon'
            if scope.find('svg', class_=lambda c: c and 'fa-moon' in c.split()):
                return 'evening'
            if scope.find('i', class_=lambda c: c and 'fa-sun' in c.split()):
                return 'afternoon'
            if scope.find('i', class_=lambda c: c and 'fa-moon' in c.split()):
                return 'evening'

        text = container.get_text(' ', strip=True).lower()
        for kw in _AFTERNOON_KW:
            if kw in text:
                return 'afternoon'
        for kw in _EVENING_KW:
            if kw in text:
                return 'evening'

        _logger.warning('Scraper: turno no detectado, asumiendo "afternoon".')
        return 'afternoon'

    # ── Parsing de fecha ──────────────────────────────────────────

    def _parse_date(self, raw):
        raw = raw.strip()

        # "dom. 26 de abr de 2026" → quitar weekday y conectores "de"
        clean = re.sub(r'^[a-záéíóúü]+\.?\s+', '', raw.lower())
        clean = re.sub(r'\bde\b', ' ', clean).strip()
        clean = re.sub(r'\s+', ' ', clean)
        parts = clean.split()
        if len(parts) >= 3:
            month_val = _ES_MONTHS.get(parts[1])
            if month_val:
                try:
                    return date_type(int(parts[2]), month_val, int(parts[0]))
                except (ValueError, IndexError):
                    pass

        for fmt in ('%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M:%S',
                    '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y',
                    '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                pass

        digits = re.findall(r'\d+', raw)
        if len(digits) == 3:
            d, m, y = int(digits[0]), int(digits[1]), int(digits[2])
            if y < 100:
                y += 2000
            try:
                return date_type(y, m, d) if m <= 12 else date_type(y, d, m)
            except ValueError:
                pass

        return None

    # ── Creación del registro ─────────────────────────────────────

    def _import_draw(self, draw):
        Output = self.env['lottery.output']
        turn_label = 'Tarde' if draw['turn'] == 'afternoon' else 'Noche'
        label = f"{draw['date']} {turn_label}"

        if Output.search([('date', '=', draw['date']), ('turn_day', '=', draw['turn']),
                          ('sorteo_id', '=', self.sorteo_id.id)], limit=1):
            return f'[OMITIDO] {label} – ya registrado'

        LottoNum = self.env['lottery.number']

        number_rec = LottoNum.search([('name', '=', draw['numero'])], limit=1)
        if not number_rec:
            return f'[ERROR] {label} – número {draw["numero"]:02d} no existe'

        # Centena y bola extra solo si el juego las trae (Pick 2 no).
        hundreds_rec = False
        if draw.get('centena') is not None:
            hundreds_rec = LottoNum.search([
                ('name', '=', draw['centena']), ('can_use_hundreds', '=', True)], limit=1)
            if not hundreds_rec:
                return f'[ERROR] {label} – centena {draw["centena"]} no existe'

        fireball_rec = False
        if draw.get('extra') is not None:
            fireball_rec = LottoNum.search([
                ('name', '=', draw['extra']), ('can_use_hundreds', '=', True)], limit=1)
            if not fireball_rec:
                return f'[ERROR] {label} – bola extra {draw["extra"]} no existe'

        premio2_rec = False
        premio3_rec = False
        if draw.get('premio2') is not None:
            premio2_rec = LottoNum.search([('name', '=', draw['premio2'])], limit=1)
            if not premio2_rec:
                _logger.warning('Scraper: Premio2 %02d no existe en lottery.number', draw['premio2'])
        if draw.get('premio3') is not None:
            premio3_rec = LottoNum.search([('name', '=', draw['premio3'])], limit=1)
            if not premio3_rec:
                _logger.warning('Scraper: Premio3 %02d no existe en lottery.number', draw['premio3'])

        Output.create({
            'date':        draw['date'],
            'turn_day':    draw['turn'],
            'sorteo_id':   self.sorteo_id.id,
            'number_id':   number_rec.id,
            'hundreds_id': hundreds_rec.id if hundreds_rec else False,
            'fireball_id': fireball_rec.id if fireball_rec else False,
            'premio_2_id': premio2_rec.id if premio2_rec else False,
            'premio_3_id': premio3_rec.id if premio3_rec else False,
        })
        p2_str = f' | P2:{draw["premio2"]:02d}' if draw.get('premio2') is not None else ''
        p3_str = f' P3:{draw["premio3"]:02d}' if draw.get('premio3') is not None else ''
        cen_str = f'{draw["centena"]}' if draw.get('centena') is not None else ''
        fb_str  = f' extra:{draw["extra"]}' if draw.get('extra') is not None else ''
        return f'[OK] {label} – {cen_str}{draw["numero"]:02d}{fb_str}{p2_str}{p3_str}'

    def _import_draws_bulk(self, draws):
        """Alta masiva para el backfill histórico.

        Con el camino de a uno (_import_draw) cada sorteo cuesta un search de
        duplicado + uno a tres search de lottery.number + el recálculo del
        próximo sorteo: con el histórico completo de Pick 2 (7.332 sorteos) son
        decenas de miles de consultas y el botón se pasa del timeout del worker.
        Acá se resuelve con dos consultas de contexto, creates por lotes y un
        único recálculo al final.
        """
        self.ensure_one()
        Output   = self.env['lottery.output']
        LottoNum = self.env['lottery.number']

        # Mapas nombre → id, una sola lectura.
        by_name, by_name_hundreds = {}, {}
        for n in LottoNum.search_read([], ['name', 'can_use_hundreds']):
            by_name.setdefault(n['name'], n['id'])
            if n['can_use_hundreds']:
                by_name_hundreds.setdefault(n['name'], n['id'])

        # Claves ya registradas para este sorteo, una sola lectura.
        existing = {
            (fields.Date.to_date(r['date']), r['turn_day'])
            for r in Output.search_read([('sorteo_id', '=', self.sorteo_id.id)],
                                        ['date', 'turn_day'])
        }

        vals_list, omitidos, errores = [], 0, []
        importadas = set()   # claves (fecha, turno) efectivamente creadas
        for draw in draws:
            key = (draw['date'], draw['turn'])
            if key in existing:
                omitidos += 1
                continue

            turn_label = 'Tarde' if draw['turn'] == 'afternoon' else 'Noche'
            label = f"{draw['date']} {turn_label}"

            number_id = by_name.get(draw['numero'])
            if not number_id:
                errores.append(f'[ERROR] {label} – número {draw["numero"]:02d} no existe')
                continue

            vals = {
                'date':      draw['date'],
                'turn_day':  draw['turn'],
                'sorteo_id': self.sorteo_id.id,
                'number_id': number_id,
            }

            if draw.get('centena') is not None:
                hundreds_id = by_name_hundreds.get(draw['centena'])
                if not hundreds_id:
                    errores.append(f'[ERROR] {label} – centena {draw["centena"]} no existe')
                    continue
                vals['hundreds_id'] = hundreds_id

            if draw.get('extra') is not None:
                fireball_id = by_name_hundreds.get(draw['extra'])
                if not fireball_id:
                    errores.append(f'[ERROR] {label} – bola extra {draw["extra"]} no existe')
                    continue
                vals['fireball_id'] = fireball_id

            for src, dest in (('premio2', 'premio_2_id'), ('premio3', 'premio_3_id')):
                if draw.get(src) is not None:
                    pid = by_name.get(draw[src])
                    if pid:
                        vals[dest] = pid
                    else:
                        _logger.warning('Scraper: %s %02d no existe en lottery.number',
                                        src, draw[src])

            vals_list.append(vals)
            existing.add(key)
            importadas.add(key)

        creados = 0
        if vals_list:
            Out = Output.with_context(skip_next_draw_recompute=True,
                                      skip_prediction_validation=True)
            for i in range(0, len(vals_list), 500):
                Out.create(vals_list[i:i + 500])
                creados += len(vals_list[i:i + 500])

            # Cierre del próximo sorteo, una sola vez y con todo cargado.
            # Replica lo que _on_output_registered hace por registro: si alguna
            # de las salidas importadas es la que estaba definida a mano, se
            # consume esa marca; si no, _recompute_next_draw no haría nada.
            sorteo = self.sorteo_id
            if sorteo.next_draw_manual and \
                    (sorteo.next_draw_date, sorteo.next_draw_turn) in importadas:
                sorteo.next_draw_manual = False
            sorteo._recompute_next_draw()

        fechas = [v['date'] for v in vals_list]
        log = [f'[OK] {creados} salida(s) creada(s)'
               + (f' — de {min(fechas)} a {max(fechas)}' if fechas else '')]
        if omitidos:
            log.append(f'[OMITIDO] {omitidos} ya estaban registradas')
        # Solo las primeras, para no generar un HTML gigante
        log += errores[:20]
        if len(errores) > 20:
            log.append(f'[ERROR] … y {len(errores) - 20} error(es) más (ver el log del servidor)')
        return log

    # ── Formato HTML del resultado ────────────────────────────────

    @staticmethod
    def _build_result_html(lines):
        """
        Convierte la lista de líneas de log en HTML con tabla y badges Bootstrap.
        Prefijos reconocidos: [OK] [OMITIDO] [ERROR] [PENDIENTE]
        """
        _BADGE = {
            'OK':        ('bg-success text-white',        '✓ OK'),
            'OMITIDO':   ('bg-secondary text-white',      '↩ OMITIDO'),
            'ERROR':     ('bg-danger text-white',         '✗ ERROR'),
            'PENDIENTE': ('bg-warning text-dark',         '⏳ PENDIENTE'),
        }
        _TURN_ICON = {'Tarde': '☀', 'Noche': '🌙'}

        headers, rows = [], []

        for line in lines:
            m = re.match(r'^\[(\w+)\]\s+(.*)', line)
            if not m:
                headers.append(
                    f'<p class="mb-1 text-muted" style="font-size:0.85em">{line}</p>'
                )
                continue

            status_key, rest = m.group(1), m.group(2)
            css, label = _BADGE.get(status_key, ('bg-secondary text-white', status_key))

            # Extraer fecha (YYYY-MM-DD) y turno (Tarde|Noche)
            m_date = re.search(r'(\d{4}-\d{2}-\d{2})', rest)
            m_turn = re.search(r'(Tarde|Noche)', rest)
            date_str = m_date.group(1) if m_date else ''
            turn     = m_turn.group(1) if m_turn else ''

            # Formatear fecha como DD/MM/YYYY
            try:
                date_disp = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                date_disp = date_str

            # Detalle: lo que viene después del guion largo o "aún"
            detail_raw = re.split(r'[–\-]\s*', rest, maxsplit=1)[-1].strip()
            detail_raw = re.sub(r'^\d{4}-\d{2}-\d{2}\s*(Tarde|Noche)?\s*', '', detail_raw).strip()

            # Para [OK]: "804 extra:5" → "8 · 04  🔥 5"
            detail_html = detail_raw
            if status_key == 'OK':
                m2 = re.match(r'(\d)(\d{2})\s+extra:(\d+)', detail_raw)
                if m2:
                    c, n, e = m2.groups()
                    detail_html = (
                        f'<strong style="font-size:1.1em">'
                        f'<span class="text-primary">{c}</span>'
                        f'<span class="text-muted mx-1">·</span>'
                        f'<span class="text-primary">{n}</span>'
                        f'</strong>'
                        f'&nbsp;&nbsp;🔥&nbsp;<strong>{e}</strong>'
                    )

            turn_cell = f'{_TURN_ICON.get(turn, "")} {turn}' if turn else ''
            rows.append(
                f'<tr>'
                f'<td class="align-middle"><span class="badge {css} px-2 py-1">{label}</span></td>'
                f'<td class="align-middle">{date_disp}</td>'
                f'<td class="align-middle">{turn_cell}</td>'
                f'<td class="align-middle">{detail_html}</td>'
                f'</tr>'
            )

        table = ''
        if rows:
            table = (
                '<table class="table table-sm table-hover table-bordered mt-2 mb-0">'
                '<thead class="table-light">'
                '<tr><th>Estado</th><th>Fecha</th><th>Turno</th><th>Resultado</th></tr>'
                '</thead>'
                f'<tbody>{"".join(rows)}</tbody>'
                '</table>'
            )

        return f'<div class="p-2">{"".join(headers)}{table}</div>'

    def action_backfill_pick4(self):
        """
        Rellena premio_2_id y premio_3_id en registros de lottery.output existentes
        consultando la API de Pick 4. Respeta date_from / date_to si están definidos.
        """
        self.ensure_one()
        try:
            import requests
        except ImportError as exc:
            raise UserError(f'Librería faltante: {exc}') from exc

        session = requests.Session()
        session.headers.update(_HEADERS)
        timeout = self.page_load_timeout

        et_tz = timezone(timedelta(hours=self.et_offset))
        today_et = datetime.now(tz=et_tz).date()

        Output = self.env['lottery.output']
        LottoNum = self.env['lottery.number']
        log_lines = []

        # Dominio base: sorteo + rango de fechas si está definido
        domain = [('sorteo_id', '=', self.sorteo_id.id)]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))

        outputs = Output.search(domain, order='date asc')

        if not outputs:
            log_lines.append('No hay registros en el rango seleccionado.')
        else:
            dates = sorted({o.date for o in outputs})
            date_min, date_max = dates[0], min(dates[-1], today_et)
            rango = f'{date_min} → {date_max}'
            log_lines.append(f'{len(outputs)} registros en el rango ({rango}) …')

            # Consultar Pick 4 en bloques de 90 días
            pick4_index = {}
            current = date_min
            while current <= date_max:
                block_end = min(current + timedelta(days=89), date_max)
                block = self._fetch_pick4_index(session, timeout, current, block_end)
                pick4_index.update(block)
                current = block_end + timedelta(days=1)

            updated = skipped = 0
            for output in outputs:
                key = (output.date, output.turn_day)
                p4 = pick4_index.get(key)
                if not p4:
                    skipped += 1
                    continue
                vals = {}
                p2 = LottoNum.search([('name', '=', p4['premio2'])], limit=1)
                p3 = LottoNum.search([('name', '=', p4['premio3'])], limit=1)
                if p2:
                    vals['premio_2_id'] = p2.id
                if p3:
                    vals['premio_3_id'] = p3.id
                if vals:
                    output.write(vals)
                    updated += 1
                else:
                    skipped += 1

            log_lines.append(f'[OK] {updated} registros actualizados, {skipped} sin datos Pick 4.')

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': self._build_result_html(log_lines),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    # ── Singleton ─────────────────────────────────────────────────

    @api.model
    def _get_singleton(self):
        """Importador de Pick 3. Solo se usa como respaldo: el cron recorre
        todos los registros (ver cron_import_results)."""
        florida = self.env.ref('lottery_base.sorteo_florida')
        rec = self.search([('sorteo_id', '=', florida.id)], limit=1)
        if not rec:
            rec = self.create({'name': 'Florida Pick 3', 'sorteo_id': florida.id,
                               'game_code': 'pick3'})
        return rec
