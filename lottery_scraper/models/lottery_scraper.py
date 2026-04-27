# -*- coding: utf-8 -*-
import logging
import re
from datetime import date as date_type, datetime, timezone, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SCRAPER_URL = 'https://floridalottery.com/es/games/draw-games/pick-3'

_ES_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'apr': 4, 'aug': 8, 'dec': 12,
}

_AFTERNOON_KW = ('midday', 'mid', 'tarde', 'afternoon', 'día', 'dia')
_EVENING_KW   = ('evening', 'eve', 'noche', 'night')


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

    # ── Configuración Chrome / Chromium ──────────────────────────
    chrome_driver_path = fields.Char(
        'Ruta ChromeDriver (opcional)', default='',
        help='Dejar vacío para detección automática.\n'
             'Windows: C:\\chromedriver\\chromedriver.exe\n'
             'Ubuntu:  /usr/bin/chromedriver')
    chrome_binary_path = fields.Char(
        'Ruta binario Chrome/Chromium (opcional)', default='',
        help='Dejar vacío para detección automática.\n'
             'Ubuntu Chromium: /usr/bin/chromium-browser\n'
             'Ubuntu Chrome:   /usr/bin/google-chrome')
    page_load_timeout = fields.Integer(
        'Timeout carga página (seg)', default=30,
        help='Segundos máximos esperando .draw-date--pick3.')

    # ── Estado ────────────────────────────────────────────────────
    last_run    = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Text('Último resultado',    readonly=True)

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
            'last_result': '\n'.join(log_lines),
        })

    def action_import_now(self):
        """Importación manual sin validar ventana horaria."""
        self.ensure_one()
        log_lines = []
        try:
            draws = self._fetch_draws()
            if not draws:
                log_lines.append('No se encontraron sorteos en la página.')
            for draw in draws:
                log_lines.append(self._import_draw(draw))
        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper manual: %s', exc, exc_info=True)

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': '\n'.join(log_lines),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación completada',
                'message': self.last_result or 'Sin resultados nuevos.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                },
            },
        }

    # ── Scraping con Selenium ─────────────────────────────────────

    def _fetch_draws(self):
        """
        Carga la página con Chrome headless (el contenido es JS-rendered),
        espera a que aparezca .draw-date--pick3 y parsea el HTML resultante.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\n'
                'Instala con: pip install selenium beautifulsoup4\n'
                'Y opcionalmente: pip install webdriver-manager'
            ) from exc

        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        # Silenciar logs de Chrome en consola
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        driver = self._build_driver(options)
        try:
            driver.get(SCRAPER_URL)
            # Esperar hasta que el primer elemento de fecha esté presente en el DOM
            WebDriverWait(driver, self.page_load_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'draw-date--pick3'))
            )
            html = driver.page_source
        except Exception as exc:
            raise UserError(
                f'Error cargando la página ({self.page_load_timeout}s timeout): {exc}\n'
                'Verifica que Chrome y ChromeDriver estén instalados.'
            ) from exc
        finally:
            driver.quit()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        return self._parse_draws(soup)

    def _build_driver(self, options):
        """
        Construye el WebDriver de forma agnóstica al SO.

        Orden de intentos:
          1. Ruta manual (chrome_driver_path configurado en el form)
          2. Selenium Manager integrado en Selenium 4.6+ (descarga automática
             del ChromeDriver correcto para la versión instalada de Chrome)
          3. webdriver-manager → Chromium  (Ubuntu Server sin Chrome)
        """
        import platform
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service

        if self.chrome_binary_path:
            options.binary_location = self.chrome_binary_path

        if platform.system() == 'Linux':
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--single-process')

        # ── 1. Ruta manual del driver ──────────────────────────
        if self.chrome_driver_path:
            _logger.info('Scraper: usando ChromeDriver manual: %s', self.chrome_driver_path)
            return webdriver.Chrome(
                service=Service(self.chrome_driver_path),
                options=options,
            )

        # ── 2. Selenium Manager (Selenium ≥ 4.6) ──────────────
        # Detecta la versión de Chrome instalada y descarga el ChromeDriver
        # correcto automáticamente sin necesidad de webdriver-manager.
        try:
            _logger.info('Scraper: usando Selenium Manager (detección automática).')
            return webdriver.Chrome(options=options)
        except Exception as exc:
            _logger.warning('Scraper: Selenium Manager falló: %s', exc)

        # ── 3. webdriver-manager → Chromium (Ubuntu sin Chrome) ─
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from webdriver_manager.core.os_manager import ChromeType
            _logger.info('Scraper: usando webdriver-manager (Chromium).')
            return webdriver.Chrome(
                service=Service(
                    ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
                ),
                options=options,
            )
        except Exception as exc:
            _logger.warning('Scraper: webdriver-manager Chromium falló: %s', exc)

        raise RuntimeError(
            'No se pudo iniciar ChromeDriver. Instala Chrome/Chromium o configura '
            'la ruta manual en el formulario del scraper.'
        )

    # ── Lógica de importación ─────────────────────────────────────

    def _run_for_turn(self, expected_turn, today_et):
        try:
            draws = self._fetch_draws()
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
            _logger.warning('Scraper: .draw-date--pick3 no encontrado en el HTML renderizado.')
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

            # Bola extra: span.game-numbers__bonus-text dentro de .game-numbers__bonus
            bonus_el = container.find(class_='game-numbers__bonus')
            extra_text = None
            if bonus_el:
                bonus_span = bonus_el.find(class_='game-numbers__bonus-text')
                if bonus_span:
                    extra_text = bonus_span.get_text(strip=True)
            # Fallback: 4° li si la bola extra sigue en la lista principal
            if not extra_text and len(li_items) >= 4:
                extra_text = li_items[3].get_text(strip=True)

            if not extra_text or not extra_text.isdigit():
                _logger.warning('Scraper: bola extra no encontrada o inválida: %r', extra_text)
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
            sun  = scope.find('svg', class_=lambda c: c and 'fa-sun'  in c.split())
            if sun:
                return 'afternoon'
            moon = scope.find('svg', class_=lambda c: c and 'fa-moon' in c.split())
            if moon:
                return 'evening'
            sun_i  = scope.find('i', class_=lambda c: c and 'fa-sun'  in c.split())
            if sun_i:
                return 'afternoon'
            moon_i = scope.find('i', class_=lambda c: c and 'fa-moon' in c.split())
            if moon_i:
                return 'evening'

        text = container.get_text(' ', strip=True).lower()
        for kw in _AFTERNOON_KW:
            if kw in text:
                return 'afternoon'
        for kw in _EVENING_KW:
            if kw in text:
                return 'evening'

        _logger.warning('Scraper: no se detectó ícono de turno, asumiendo "afternoon".')
        return 'afternoon'

    # ── Parsing de fecha ──────────────────────────────────────────

    def _parse_date(self, raw):
        raw = raw.strip()

        # "dom. 26 de abr de 2026" → quitar weekday prefix y conectores "de"
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

        for fmt in ('%B %d, %Y', '%b %d, %Y', '%m/%d/%Y',
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
        return (f'[OK] {label} – '
                f'{draw["centena"]}{draw["numero"]:02d} extra:{draw["extra"]}')

    # ── Singleton ─────────────────────────────────────────────────

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'Florida Pick 3'})
        return rec
