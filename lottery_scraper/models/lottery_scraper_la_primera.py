# -*- coding: utf-8 -*-
import json
import logging
import re
import time
from datetime import date as date_type, datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import build_result_html

_logger = logging.getLogger(__name__)

# Fuente OFICIAL de La Primera (GSTAR Services). Es un WordPress: la página de
# resultados trae un nonce y los datos se piden por admin-ajax, un día por
# petición. No hay endpoint de rango.
RESULTS_PAGE = 'https://laprimera.do/resultados/'
AJAX_URL     = 'https://laprimera.do/wp-admin/admin-ajax.php'

# El nonce viaja en   var primera_js = {..., "nonce":"36016fd06d", ...}
_NONCE_RE = re.compile(r'primera_js\s*=\s*\{[^}]*"nonce"\s*:\s*"([^"]+)"')

# De todos los juegos que devuelve la API (LOTO5M, EL QUINIELON, …) el único
# que interesa es la quiniela de 3 números. Ojo: viene con espacio doble.
QUINIELA_GAME = 'TRIPLETA PRIMERA'

# Primer día del histórico continuo, verificado día por día en agosto de 2026.
# OJO: hay una isla suelta de 2 sorteos el 18 y 19 de febrero de 2023 y después
# ~80 días vacíos hasta acá; arrancar en febrero solo gasta peticiones al pedo.
# Y ojo también: el histórico tiene huecos reales (el 13/05/2023 está vacío),
# así que un día sin datos NO significa que la fuente esté fallando.
HISTORY_START = date_type(2023, 5, 11)

# Pausa entre peticiones del backfill. Son ~900 días, uno por request, contra
# un WordPress chico: conviene no atropellarlo.
REQUEST_DELAY = 0.35

_MAX_DETAIL_LINES = 200


class LotteryScraperLaPrimera(models.Model):
    _name = 'lottery.scraper.la.primera'
    _description = 'Importador automático La Primera (RD)'

    name = fields.Char(default='La Primera', readonly=True)
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
        help="La API entrega un día por petición, así que el backfill completo "
             "son ~900 peticiones y no entra en el tiempo de un request. Cada "
             "corrida procesa como mucho esta cantidad de días pendientes y "
             "avisa cuántos quedan: se vuelve a apretar el botón hasta terminar.")

    # ── Importación manual por rango ──────────────────────────────
    date_from = fields.Date(
        'Fecha desde',
        help='Vacío = sigue desde la última salida registrada, y si no hay '
             'ninguna arranca en el 18/02/2023, primer día con datos en la '
             'fuente oficial.')
    date_to = fields.Date('Fecha hasta', help='Vacío = hoy (hora RD).')

    backfill_until = fields.Date(
        'Backfill completado hasta', readonly=True,
        help="Hasta qué día ya se recorrió el histórico. Avanza aunque el día "
             "venga vacío: el histórico tiene huecos reales y sin este cursor "
             "cada corrida volvería a pedir los mismos días vacíos para "
             "siempre. Vaciar este campo para rehacer el backfill.")

    # ── Estado ────────────────────────────────────────────────────
    last_run    = fields.Datetime('Última ejecución', readonly=True)
    last_result = fields.Html('Último resultado', readonly=True, sanitize=False)

    # ── Entry points ──────────────────────────────────────────────

    @api.model
    def cron_import_results(self):
        """Importa lo que falte de los últimos días. No usa ventanas horarias:
        pide el día completo y la API devuelve los turnos que ya se sortearon,
        así que da igual a qué hora corra."""
        for scraper in self.search([('auto_import', '=', True)]):
            try:
                scraper._run(days_back=3)
            except Exception:
                _logger.exception('Scraper La Primera: error en la corrida automática.')

    def action_import_now(self):
        # Sin retorno a propósito: devolver un act_window hace que Odoo apile
        # una entrada nueva en el breadcrumb en cada clic, y este botón se
        # aprieta muchas veces seguidas durante el backfill.
        self.ensure_one()
        self._run()

    def action_purge_phantoms(self):
        """Borra de la base las salidas fantasma que dejó esta fuente.

        Misma regla que _descartar_fantasmas, pero aplicada a lo ya importado:
        en una racha de valores idénticos consecutivos del mismo turno, la
        ÚLTIMA fecha es la real y las anteriores son inventos de la fuente.
        """
        self.ensure_one()
        Output = self.env['lottery.output']
        registros = Output.search([('sorteo_id', '=', self.sorteo_id.id)],
                                  order='date desc, id desc')

        por_turno, a_borrar, detalle = {}, Output, []
        for rec in registros:      # ya viene de más nuevo a más viejo
            firma = (rec.turn_day, rec.number_id.id,
                     rec.premio_2_id.id, rec.premio_3_id.id)
            if por_turno.get(rec.turn_day) == firma:
                a_borrar |= rec
                detalle.append(
                    f'[OK] {rec.date} '
                    f'{"Tarde" if rec.turn_day == "afternoon" else "Noche"} – '
                    f'{rec.number_id.name:02d} (repetía el sorteo siguiente)')
            else:
                por_turno[rec.turn_day] = firma

        log = [f'{len(registros)} salida(s) revisada(s).']
        if a_borrar:
            log.append(f'{len(a_borrar)} fantasma(s) encontrada(s) y borrada(s):')
            log += detalle
            a_borrar.unlink()
            self.sorteo_id._recompute_next_draw()
        else:
            log.append('No se encontraron salidas fantasma.')

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(self._summarize_log(log)),
        })

    def action_reset_backfill(self):
        """Vuelve a recorrer desde el principio.

        Hace falta porque el cursor avanza y los días que quedan detrás no se
        vuelven a mirar: si otra fuente rellenó huecos después de que el cursor
        pasó por ahí, sin reiniciar no se completarían nunca. No borra nada de
        lo importado — el alta saltea las salidas que ya existen.
        """
        self.write({'backfill_until': False})

    # ── Núcleo ────────────────────────────────────────────────────

    def _today_rd(self):
        return datetime.now(tz=timezone(timedelta(hours=self.rd_offset))).date()

    def _pending_dates(self, days_back=None):
        """Días a consultar, en orden. Devuelve (lista, total_del_rango).

        El backfill avanza con un cursor (backfill_until) en vez de recalcular
        "lo que falta": el histórico tiene días sin sorteos que NUNCA se van a
        completar, así que basarse en "le falta un turno" haría que cada corrida
        volviera a pedir los mismos días vacíos y el lote nunca avanzara.
        Los días ya registrados con sus dos turnos igual se saltan sin gastar
        petición.
        """
        self.ensure_one()
        today = self._today_rd()

        if days_back is not None:
            # Camino del cron: mira solo los últimos días y no toca el cursor.
            desde, hasta = today - timedelta(days=days_back), today
        else:
            desde = HISTORY_START
            if self.date_from:
                desde = max(desde, self.date_from)
            # El cursor manda mientras vaya por delante del piso.
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
                    # El cursor avanza aunque los días vinieran vacíos: es lo
                    # que evita quedar girando sobre los huecos del histórico.
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
            _logger.error('Scraper La Primera: %s', exc, exc_info=True)

        self.write({
            'last_run':    fields.Datetime.now(),
            'last_result': build_result_html(self._summarize_log(log_lines)),
        })

    # ── Fuente ────────────────────────────────────────────────────

    def _session_and_nonce(self):
        """Abre sesión y saca el nonce de la página de resultados. El nonce es
        obligatorio: sin él admin-ajax rechaza la consulta."""
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
        """Un POST por día. Devuelve (draws, líneas de error)."""
        session, nonce = self._session_and_nonce()
        draws, fallos = [], []
        for i, dia in enumerate(dias):
            if i:
                time.sleep(REQUEST_DELAY)
            try:
                draws += self._fetch_day(session, nonce, dia)
            except Exception as exc:
                fallos.append(f'[ERROR] {dia} – no se pudo consultar: {exc}')
                _logger.warning('Scraper La Primera: %s falló: %s', dia, exc)
        draws.sort(key=lambda d: (d['date'], 0 if d['turn'] == 'afternoon' else 1))
        return self._descartar_fantasmas(draws), fallos

    @staticmethod
    def _descartar_fantasmas(draws):
        """Saca los resultados inventados por la fuente.

        Para un día SIN sorteo la API no devuelve vacío: devuelve los números
        del PRÓXIMO sorteo, estampados con la fecha que se pidió (el campo
        'fecha' del registro también repite la fecha pedida, así que no sirve
        para detectarlo). Verificado contra dos fuentes independientes en
        agosto y noviembre de 2023, julio de 2024 y octubre de 2025.

        Como el fantasma siempre queda ANTES del real, en una racha de valores
        idénticos consecutivos del mismo turno se conserva solo la última
        fecha. Que una quiniela repita los tres números de un día al siguiente
        tiene probabilidad ~1 en un millón, así que el riesgo de descartar un
        resultado legítimo es despreciable frente al de meter datos falsos.
        """
        limpias, por_turno = [], {}
        # De más nuevo a más viejo: el primero que se ve de cada racha es el real.
        for draw in sorted(draws, key=lambda d: d['date'], reverse=True):
            firma = (draw['numero'], draw.get('premio2'), draw.get('premio3'))
            anterior = por_turno.get(draw['turn'])
            if anterior == firma:
                _logger.warning(
                    'Scraper La Primera: descartado %s %s por repetir los números '
                    'del sorteo siguiente (%s) — día sin sorteo en la fuente.',
                    draw['date'], draw['turn'], firma)
                continue
            por_turno[draw['turn']] = firma
            limpias.append(draw)
        limpias.sort(key=lambda d: (d['date'], 0 if d['turn'] == 'afternoon' else 1))
        return limpias

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

        # Cuando no hay datos la API devuelve el entero 0, no un dict.
        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return []
        juegos = (data.get('lotteries') or {}).get('la_primera') or []

        draws = []
        for juego in juegos:
            if not isinstance(juego, dict):
                continue
            nombre = ' '.join(str(juego.get('juego_nombre', '')).split()).upper()
            if nombre != QUINIELA_GAME:
                continue
            turn = self._turn_from_hour(juego.get('hora_sorteo', ''))
            if not turn:
                _logger.warning('Scraper La Primera: hora no reconocida %r en %s',
                                juego.get('hora_sorteo'), dia)
                continue
            premios = self._parse_premios(juego.get('resultado'))
            if not premios:
                continue
            draws.append({'date': dia, 'turn': turn,
                          'numero': premios[0],
                          'premio2': premios[1], 'premio3': premios[2]})
        return draws

    @staticmethod
    def _turn_from_hour(raw):
        """'12:00pm' → tarde · '07:00pm'/'08:00pm' → noche.

        No se cablea la hora exacta a propósito: el sorteo nocturno era a las
        08:00pm en 2023 y hoy es a las 07:00pm, así que el histórico trae las
        dos y una comparación exacta perdería los años viejos.
        """
        m = re.match(r'\s*(\d{1,2}):(\d{2})\s*([ap])\.?m', str(raw).lower())
        if not m:
            return None
        hora = int(m.group(1)) % 12
        if m.group(3) == 'p':
            hora += 12
        return 'afternoon' if hora < 16 else 'evening'

    @staticmethod
    def _parse_premios(resultado):
        """['30','84','46'] → (30, 84, 46). Los tres son de 2 dígitos."""
        if not isinstance(resultado, (list, tuple)) or len(resultado) < 3:
            return None
        try:
            return tuple(int(str(x).strip()) for x in resultado[:3])
        except (TypeError, ValueError):
            return None

    # ── Importación ───────────────────────────────────────────────

    def _import_draws(self, draws):
        """Alta en lote. La Primera no usa centena ni bola extra: el premio 1
        va en number_id y los premios 2 y 3 en los corridos."""
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

            # Segundo cerrojo contra los fantasmas: el filtro del lote solo ve
            # los días que se pidieron, y el importador pide únicamente los
            # incompletos. Si el sorteo real ya está en la base (y por eso no
            # se pidió), el fantasma pasaba igual. Acá se compara contra el
            # PRÓXIMO sorteo ya registrado de ese turno.
            siguiente = Output.search([
                ('sorteo_id', '=', self.sorteo_id.id),
                ('turn_day', '=', draw['turn']),
                ('date', '>', draw['date']),
            ], order='date asc', limit=1)
            if siguiente and (
                    siguiente.number_id.id == number_id
                    and siguiente.premio_2_id.id == (by_name.get(draw.get('premio2')) or False)
                    and siguiente.premio_3_id.id == (by_name.get(draw.get('premio3')) or False)):
                log_lines.append(
                    f'[OMITIDO] {label} – repite el sorteo del {siguiente.date} '
                    f'(día sin sorteo en la fuente)')
                continue

            vals = {
                'date':      draw['date'],
                'turn_day':  draw['turn'],
                'sorteo_id': self.sorteo_id.id,
                'number_id': number_id,
            }
            extra = ''
            for src, campo, etiqueta in (('premio2', 'premio_2_id', 'P2'),
                                         ('premio3', 'premio_3_id', 'P3')):
                valor = draw.get(src)
                if valor is None:
                    continue
                pid = by_name.get(valor)
                if pid:
                    vals[campo] = pid
                    extra += f' {etiqueta}:{valor:02d}'
                else:
                    _logger.warning('Scraper La Primera: %s %02d no existe en lottery.number',
                                    etiqueta, valor)

            vals_list.append(vals)
            log_lines.append(f'[OK] {label} – {draw["numero"]:02d}{extra}')

        if vals_list:
            # skip_next_draw_recompute: el próximo sorteo se recalcula una sola
            # vez al final; por registro serían miles de writes pisándose.
            # skip_prediction_validation: son salidas históricas, evaluarlas
            # contra la predicción vigente daría aciertos inventados.
            Output.with_context(skip_next_draw_recompute=True,
                                skip_prediction_validation=True).create(vals_list)
            self.sorteo_id._recompute_next_draw()
            _logger.info('Scraper La Primera: %d salidas creadas.', len(vals_list))

        return log_lines

    @staticmethod
    def _summarize_log(log_lines):
        """En backfills grandes el detalle completo es inmanejable como HTML."""
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
        return self.env.ref('lottery_base.sorteo_la_primera')

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({'name': 'La Primera',
                               'sorteo_id': self._get_sorteo().id})
        return rec
