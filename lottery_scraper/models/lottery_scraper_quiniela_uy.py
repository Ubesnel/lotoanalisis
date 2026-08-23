# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta, datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import build_result_html

_logger = logging.getLogger(__name__)

QUINIELA_URL = "https://www.loteria.gub.uy/ver_resultados.php"


class LotteryScraperQuinielaUy(models.Model):
    _name = 'lottery.scraper.quiniela.uy'
    _description = 'Importador automático Quiniela Uruguay'

    name = fields.Char(default='Quiniela Uruguay', readonly=True)

    # ── Turnos a importar ───────────────────────────────────────────
    import_turns = fields.Selection([
        ('both', 'Ambos turnos'),
        ('afternoon', 'Solo Vespertina'),
        ('evening', 'Solo Nocturna'),
    ], string='Turnos a importar', default='both', required=True,
        help='Limita qué turno se importa, tanto en el cron como en la importación manual.')

    # ── Ventanas horarias (hora Uruguay) ────────────────────────────
    # Vespertina se publica ~15:00, Nocturna ~21:00. Ventana de 1 hora
    # para cubrir variaciones en la publicación del sitio.
    vespertina_start = fields.Float('Inicio ventana Vespertina', default=15.0)   # 15:00
    vespertina_end = fields.Float('Fin ventana Vespertina', default=16.0)         # 16:00
    nocturna_start = fields.Float('Inicio ventana Nocturna', default=21.0)        # 21:00
    nocturna_end = fields.Float('Fin ventana Nocturna', default=22.0)             # 22:00
    uy_offset = fields.Integer('Offset Uruguay desde UTC', default=-3,
                               help='Uruguay no aplica horario de verano desde 2015: siempre UTC-3.')

    # A diferencia de Florida, acá la API no recibe rango: solo una fecha por
    # consulta, y esa fecha devuelve los 20 sorteos de ambos turnos juntos.
    page_load_timeout = fields.Integer('Timeout petición (seg)', default=30)

    date_from = fields.Date('Fecha desde', help='Vacío = detecta automáticamente desde el último día registrado.')
    date_to = fields.Date('Fecha hasta', help='Vacío = usa la fecha de hoy.')

    last_run = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Html('Último resultado', readonly=True, sanitize=False)

    # ── Entry points ──────────────────────────────────────────────

    @api.model
    def cron_import_results(self):
        """Solo hace la petición al sitio dentro de las ventanas horarias en
        que se publican los resultados (Vespertina ~15:00, Nocturna ~21:00,
        hora Uruguay). Fuera de esas ventanas no llama a la web."""
        scraper = self._get_singleton()
        uy_tz = timezone(timedelta(hours=scraper.uy_offset))
        now_uy = datetime.now(tz=uy_tz)
        hour_uy = now_uy.hour + now_uy.minute / 60.0
        today_uy = now_uy.date()

        in_vespertina = (scraper.import_turns in ('both', 'afternoon')
                         and scraper.vespertina_start <= hour_uy <= scraper.vespertina_end)
        in_nocturna = (scraper.import_turns in ('both', 'evening')
                       and scraper.nocturna_start <= hour_uy <= scraper.nocturna_end)

        if not (in_vespertina or in_nocturna):
            _logger.debug('Scraper Quiniela UY: %02d:%02d UY fuera de ventanas.', now_uy.hour, now_uy.minute)
            return

        log_lines = scraper._import_date(today_uy)
        scraper.write({
            'last_run': fields.Datetime.now(),
            'last_result': build_result_html(log_lines),
        })

    def action_import_now(self):
        """Importación manual. Si date_from está configurado usa ese rango
        (recorriendo día por día, ya que la API no acepta rango); si no,
        detecta automáticamente desde el último día registrado hasta hoy."""
        self.ensure_one()
        log_lines = []
        try:
            today = date.today()
            if self.date_from:
                current = self.date_from
                date_to = self.date_to or today
            else:
                current = self._get_next_query_date()
                date_to = today

            while current <= date_to:
                log_lines += self._import_date(current)
                current += timedelta(days=1)

        except Exception as exc:
            log_lines.append(f'[ERROR] {exc}')
            _logger.error('Scraper Quiniela UY: %s', exc, exc_info=True)

        self.write({
            'last_run': fields.Datetime.now(),
            'last_result': build_result_html(log_lines),
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
        last = self.env['lottery.output'].search(
            [('sorteo_id.source_code', '=', 'quiniela_uy')], order='date desc, id desc', limit=1)
        if not last:
            return date.today()
        return min(last.date + timedelta(days=1), date.today())

    # ── Fetch + parseo (mismo criterio que el script de referencia) ────

    def _fetch_quiniela(self, dia, mes, anio):
        """Identifica cada bloque de 20 números por la imagen de cabezal que lo
        precede en el HTML (cabezal_quinielas_vespertina.png / _nocturno.png),
        en vez de inferir el turno por la cantidad total de números encontrados.
        Esto cubre correctamente los 3 casos reales: solo vespertina (días con
        sorteo nocturno suspendido), solo nocturno (ej. sábado) o ambos."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise UserError(
                f'Librería faltante: {exc}.\nInstala con: pip install requests beautifulsoup4'
            ) from exc
        import re

        params = {'vdia': dia, 'vmes': mes, 'vano': anio}
        headers = {'User-Agent': 'Mozilla/5.0'}

        resp = requests.get(QUINIELA_URL, params=params, headers=headers,
                            timeout=self.page_load_timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        blocks = {'afternoon': [], 'evening': []}
        current_turn = None

        for el in soup.descendants:
            if getattr(el, 'name', None) == 'img':
                src = (el.get('src') or '').lower()
                if 'vespertina' in src:
                    current_turn = 'afternoon'
                elif 'nocturno' in src:
                    current_turn = 'evening'
            elif isinstance(el, str):
                text = el.strip()
                if (current_turn and re.fullmatch(r'\d{3}', text)
                        and len(blocks[current_turn]) < 20):
                    blocks[current_turn].append(text)

        result = {}
        for turn, raw in blocks.items():
            if len(raw) == 20:
                result[turn] = raw[0::2] + raw[1::2]
            elif raw:
                _logger.warning(
                    'Scraper Quiniela UY: bloque %s incompleto (%d/20 números) para %02d/%02d/%04d',
                    turn, len(raw), dia, mes, anio)
                result[turn] = []
            else:
                result[turn] = []

        if not result['afternoon'] and not result['evening']:
            return None

        return {'vespertina': result['afternoon'], 'nocturna': result['evening']}

    # ── Importación ──────────────────────────────────────────────

    def _sorteo_by_premio(self):
        """Mapa {1: lottery.sorteo(quiniela_uy_1), ..., 20: lottery.sorteo(quiniela_uy_20)}."""
        sorteos = self.env['lottery.sorteo'].search([('source_code', '=', 'quiniela_uy')])
        result = {}
        for s in sorteos:
            try:
                n = int(s.code.rsplit('_', 1)[-1])
                result[n] = s
            except ValueError:
                continue
        return result

    def _import_date(self, draw_date):
        label = str(draw_date)
        try:
            data = self._fetch_quiniela(draw_date.day, draw_date.month, draw_date.year)
        except Exception as exc:
            return [f'[ERROR] {label} – {exc}']

        if not data or (not data['vespertina'] and not data['nocturna']):
            return [f'[PENDIENTE] {label} – aún no hay resultados publicados.']

        log_lines = []
        if data['vespertina'] and self.import_turns in ('both', 'afternoon'):
            log_lines += self._import_turn(draw_date, 'afternoon', data['vespertina'])
        if data['nocturna'] and self.import_turns in ('both', 'evening'):
            log_lines += self._import_turn(draw_date, 'evening', data['nocturna'])
        return log_lines

    def _import_turn(self, draw_date, turn_day, numeros):
        # Una salida que no es la del día NO se puede validar contra el
        # ranking_snapshot del sorteo, porque ese snapshot es siempre el del
        # PRÓXIMO sorteo: sellarla con las banderas de hoy deja aciertos y
        # fallos que no significan nada y ensucian la vista de Validación.
        # Los importadores de Florida, La Primera y Conectate ya usan este
        # contexto para sus backfills; acá hace falta cada vez que se rellena
        # un hueco con el rango manual (date_from / date_to) o cuando el cron
        # se pone al día con una fecha vieja.
        #
        # Los atrasos y los totales no dependen de esto: se recalculan enteros
        # desde lottery_output ordenando por fecha, así que rellenar huecos
        # viejos los deja bien igual.
        Output = self.env['lottery.output']
        if draw_date != date.today():
            Output = Output.with_context(skip_prediction_validation=True)
        LottoNum = self.env['lottery.number']
        sorteo_by_premio = self._sorteo_by_premio()
        log_lines = []

        for premio, numero_str in enumerate(numeros, start=1):
            label = f'{draw_date} {turn_day} S{premio}'
            sorteo = sorteo_by_premio.get(premio)
            if not sorteo:
                log_lines.append(f'[ERROR] {label} – no existe lottery.sorteo quiniela_uy_{premio}')
                continue

            if Output.search([
                ('date', '=', draw_date), ('turn_day', '=', turn_day),
                ('sorteo_id', '=', sorteo.id),
            ], limit=1):
                log_lines.append(f'[OMITIDO] {label} – ya registrado')
                continue

            try:
                centena_val = int(numero_str[0])
                numero_val = int(numero_str[1:])
            except ValueError:
                log_lines.append(f'[ERROR] {label} – número inválido: {numero_str}')
                continue

            number_rec = LottoNum.search([('name', '=', numero_val)], limit=1)
            hundreds_rec = LottoNum.search([('name', '=', centena_val), ('can_use_hundreds', '=', True)], limit=1)
            if not number_rec or not hundreds_rec:
                log_lines.append(f'[ERROR] {label} – número {numero_str} no existe en el catálogo')
                continue

            Output.create({
                'date': draw_date,
                'turn_day': turn_day,
                'sorteo_id': sorteo.id,
                'number_id': number_rec.id,
                'hundreds_id': hundreds_rec.id,
            })
            log_lines.append(f'[OK] {label} – {numero_str}')

        return log_lines

    # ── Singleton ─────────────────────────────────────────────────

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'Quiniela Uruguay'})
        return rec
