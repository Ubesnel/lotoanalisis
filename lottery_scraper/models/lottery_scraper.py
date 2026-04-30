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
        scraper = self._get_singleton()
        et_tz    = timezone(timedelta(hours=scraper.et_offset))
        now_et   = datetime.now(tz=et_tz)
        hour_et  = now_et.hour + now_et.minute / 60.0
        today_et = now_et.date()

        Output    = self.env['lottery.output']
        log_lines = []

        if scraper.afternoon_start <= hour_et <= scraper.afternoon_end:
            if Output.search([('date', '=', today_et), ('turn_day', '=', 'afternoon')], limit=1):
                _logger.debug('Scraper Tarde %s: ya registrada.', today_et)
                return
            _logger.info('Scraper: ventana Tarde activa.')
            log_lines += scraper._run_for_turn('afternoon', today_et)

        elif scraper.evening_start <= hour_et <= scraper.evening_end:
            if Output.search([('date', '=', today_et), ('turn_day', '=', 'evening')], limit=1):
                _logger.debug('Scraper Noche %s: ya registrada.', today_et)
                return
            _logger.info('Scraper: ventana Noche activa.')
            log_lines += scraper._run_for_turn('evening', today_et)

        else:
            _logger.debug('Scraper: %02d:%02d ET fuera de ventanas.', now_et.hour, now_et.minute)
            return

        scraper.write({
            'last_run':    fields.Datetime.now(),
            'last_result': scraper._build_result_html(log_lines),
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
            [], order='date desc, id desc', limit=1)

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
                _logger.info('Scraper: %d sorteos obtenidos via API oficial.', len(draws))
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

    def _fetch_florida_api(self, session, timeout, date_from=None, date_to=None):
        """
        Llama a la API oficial de Florida Lottery para el rango de fechas indicado.
        URL: https://apim-website-prod-eastus.azure-api.net/drawgamesapp/searchgames
        Params: id=104 (Pick 3), startDate/endDate en formato DD-MMM-YYYY (ej: 29-APR-2026)
        Si no se indican fechas usa la ET de hoy para ambas.
        """
        et_tz = timezone(timedelta(hours=self.et_offset))
        today = datetime.now(tz=et_tz).date()

        if date_from is None:
            date_from = today
        if date_to is None:
            date_to = date_from

        start_str = date_from.strftime('%d-%b-%Y').upper()
        end_str   = date_to.strftime('%d-%b-%Y').upper()
        _logger.info('Scraper: consultando API Florida %s → %s', start_str, end_str)

        resp = session.get(
            FLORIDA_API,
            params={'id': PICK3_GAME_ID, 'startDate': start_str, 'endDate': end_str},
            headers=_API_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            data = [data]

        draws = []
        for item in data:
            draw = self._parse_florida_api_item(item)
            if draw:
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

        if not all(k in wn for k in ('wn1', 'wn2', 'wn3', 'fb')):
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

        if Output.search([('date', '=', draw['date']), ('turn_day', '=', draw['turn'])], limit=1):
            return f'[OMITIDO] {label} – ya registrado'

        LottoNum = self.env['lottery.number']

        number_rec = LottoNum.search([('name', '=', draw['numero'])], limit=1)
        if not number_rec:
            return f'[ERROR] {label} – número {draw["numero"]:02d} no existe'

        hundreds_rec = LottoNum.search([
            ('name', '=', draw['centena']), ('can_use_hundreds', '=', True)], limit=1)
        if not hundreds_rec:
            return f'[ERROR] {label} – centena {draw["centena"]} no existe'

        fireball_rec = LottoNum.search([
            ('name', '=', draw['extra']), ('can_use_hundreds', '=', True)], limit=1)
        if not fireball_rec:
            return f'[ERROR] {label} – bola extra {draw["extra"]} no existe'

        Output.create({
            'date':        draw['date'],
            'turn_day':    draw['turn'],
            'number_id':   number_rec.id,
            'hundreds_id': hundreds_rec.id,
            'fireball_id': fireball_rec.id,
        })
        return f'[OK] {label} – {draw["centena"]}{draw["numero"]:02d} extra:{draw["extra"]}'

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

    # ── Singleton ─────────────────────────────────────────────────

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'Florida Pick 3'})
        return rec
