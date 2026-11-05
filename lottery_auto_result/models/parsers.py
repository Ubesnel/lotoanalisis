# -*- coding: utf-8 -*-
"""Parsers de las fuentes web de resultados.

Funciones puras (sin ORM): reciben el texto descargado y devuelven filas
normalizadas, así se pueden probar contra páginas guardadas.

Fila normalizada: {'key': str, 'date': date, 'digits': str}
`digits` son los dígitos tal como los publica la fuente; los premios de
2 cifras van concatenados (La Primera 12-34-56 → '123456').
"""
import html as html_lib
import json
import re
from datetime import date, datetime

MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7,
    'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

_TAG_RE = re.compile(r'<[^>]+>')
_TEXT_DATE_RE = re.compile(r'(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)[\s.,]+(?:de\s+)?(\d{4})', re.I)
_NUM_DATE_RE = re.compile(r'^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*$')


def parse_text_date(raw):
    """'4 de noviembre de 2026', '05 nov, 2026', 'Miércoles 04 de noviembre, 2026'."""
    text = html_lib.unescape(_TAG_RE.sub(' ', raw or ''))
    m = _TEXT_DATE_RE.search(text)
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def parse_num_date(raw):
    """'4/11/2026' o '4-11-2026' (día primero)."""
    m = _NUM_DATE_RE.match(raw or '')
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _two_digits(value):
    """'7' → '07'; vacío, 'Pendiente', '-' o '#N/A' → None."""
    value = str(value or '').strip()
    if not value.isdigit() or len(value) > 2:
        return None
    return value.zfill(2)


# ── DataLoto (datalotosv / datalotohn / datalotocr) ──────────────────

def parse_dataloto(text):
    """JSON estático de los sitios DataLoto.

    La Diaria (SV/HN): {'diaria': [{'fecha': '4/11/2026', 'n11am': '90', ...}]}
    → clave = nombre del campo ('n11am', 'n3pm', 'n6pm', 'n9pm').
    Nuevos Tiempos (CR): {'resultados': [{'fecha': '4 de noviembre de 2026',
    'mediodia': {'nt': '77', ...}, ...}]} → clave = 'mediodia'/'tarde'/'noche'.
    """
    data = json.loads(text)
    rows = []
    for item in data.get('diaria') or []:
        day = parse_num_date(item.get('fecha'))
        if not day:
            continue
        for key, value in item.items():
            if re.fullmatch(r'n\d{1,2}(am|pm)', key):
                num = _two_digits(value)
                if num:
                    rows.append({'key': key, 'date': day, 'digits': num})
    for item in data.get('resultados') or []:
        day = parse_text_date(item.get('fecha'))
        if not day:
            continue
        for key, value in item.items():
            if isinstance(value, dict):
                num = _two_digits(value.get('nt'))
                if num:
                    rows.append({'key': key, 'date': day, 'digits': num})
    return rows


# ── EnLoteria (RD, King Lottery) ──────────────────────────────────────

_EL_CARD_SPLIT = re.compile(r'class="card h-100 result-card"')
_EL_NAME_RE = re.compile(r'class="card-title lottery-name[^"]*"[^>]*>(.*?)</h5>', re.S)
_EL_DATE_RE = re.compile(r'class="result-date(?: small)?" id="[^"]*">(.{0,160}?)</span>\s*(?:</span>|</a>|<img)', re.S)
_EL_NUM_RE = re.compile(r'class="result-number[^"]*">\s*(\d{1,2})\s*<')


def parse_enloteria(text):
    """Tarjetas de resultados de enloteria.com (portada, hoy/ayer y página
    de cada lotería). Clave = nombre de la lotería como lo muestra el sitio
    ('La Primera Noche'). Las tarjetas sin bolas son sorteos pendientes."""
    rows = []
    for card in _EL_CARD_SPLIT.split(text)[1:]:
        name_m = _EL_NAME_RE.search(card)
        date_m = _EL_DATE_RE.search(card)
        if not name_m or not date_m:
            continue
        name = ' '.join(html_lib.unescape(_TAG_RE.sub(' ', name_m.group(1))).split())
        day = parse_text_date(date_m.group(1))
        nums = _EL_NUM_RE.findall(card)
        if not name or not day or not nums:
            continue
        rows.append({'key': name, 'date': day, 'digits': ''.join(n.zfill(2) for n in nums)})
    return rows


# ── LotteryTeller (EEUU) ──────────────────────────────────────────────

_LT_ROW_RE = re.compile(r'<time dateTime="(\d{4}-\d\d-\d\d)">(?:(?!<time ).)*?data-digits="(\d+)"', re.S)


def parse_lotteryteller(text, key):
    """Historial de un juego y turno de lotteryteller.com
    (/es/resultados/us/florida/pick-3/midday): ~30 sorteos verificados.
    `key` es esa ruta ('florida/pick-3/midday')."""
    rows, seen = [], set()
    for raw_date, digits in _LT_ROW_RE.findall(text):
        day = datetime.strptime(raw_date, '%Y-%m-%d').date()
        if day in seen:
            continue
        seen.add(day)
        rows.append({'key': key, 'date': day, 'digits': digits})
    return rows


# ── API oficial Florida Lottery ───────────────────────────────────────

# La API emite {"NumberPick": ,"NumberType": "fb"} cuando falta un número.
_EMPTY_NUMBER_RE = re.compile(r'"NumberPick":\s*,')


def parse_florida_api(text, game):
    """Respuesta de searchgames. Clave = 'MIDDAY'/'EVENING'.
    game 'pick3' → digits = centena + número + Fireball (4 dígitos);
    game 'pick4' → los 4 dígitos (corridos)."""
    data = json.loads(_EMPTY_NUMBER_RE.sub('"NumberPick": null,', text))
    if not isinstance(data, list):
        data = [data]
    order = ('wn1', 'wn2', 'wn3', 'fb') if game == 'pick3' else ('wn1', 'wn2', 'wn3', 'wn4')
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            day = datetime.strptime(str(item.get('DrawDate', '')).split()[0], '%m/%d/%Y').date()
        except ValueError:
            continue
        wn = {n.get('NumberType'): n.get('NumberPick')
              for n in item.get('DrawNumbers') or [] if isinstance(n, dict)}
        if any(wn.get(k) is None for k in order):
            continue
        digits = ''.join(str(wn[k]) for k in order)
        if not digits.isdigit() or len(digits) != 4:
            continue
        rows.append({'key': str(item.get('DrawType', '')).upper(), 'date': day, 'digits': digits})
    return rows
