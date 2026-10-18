"""Histórico de LoteDom, Quiniela Palé (Leidsa) y Lotería Real a Excel, listo para el wizard.

Uso: python extract_quinielas_rd.py <carpeta_cache> <carpeta_salida> [--refrescar-conectate] [--sin-nacional] [--nacional-desde=YYYY-MM-DD] [--desde=YYYY-MM-DD] [--solo=<sorteo>]

--solo=loteria_real procesa un solo sorteo (así no se le piden a
nacionalloteria páginas de los otros, que comparten el límite de 403).

--desde deja afuera del Excel los sorteos anteriores a esa fecha (los cachés
no se tocan). Se usó --desde=2020-01-01 para importar la Palé sin la isla de
2015-2016 mientras falta 2016-2019.

--sin-nacional arma los Excel solo con lo que ya está en caché, sin pedirle
nada a nacionalloteria ni a enloteria (para cuando siguen bloqueados).

Los cachés quedan en historicos/cache_quinielas_rd/: pasá esa carpeta como
<carpeta_cache> para retomar sin volver a bajar lo que ya está.

Las dos son quinielas de 3 números de 00 a 99 (premio 1 = el fijo, premios
2 y 3 = los corridos), un sorteo por día:
  · LoteDom: 12:00 (hora RD), todos los días → turno Tarde (afternoon).
  · Quiniela Palé: 20:55, domingos 15:55 → turno Noche (evening).
  · Lotería Real (Quiniela Real): 12:55 → turno Tarde (afternoon). conectate
    desde ene-2020, nacionalloteria desde el 29/01/2015. "Real Noche" (20:00)
    arrancó el 07/10/2026 y no tiene histórico: no se incluye.
  nacionalloteria solo se pide para los días que conectate no trae.

Fuentes:
  · conectate (api.conectate.com.do, 10 sorteos por petición): desde 2020.
    Tiene un hueco sistemático entre oct-2022 y jun-2023 (LoteDom sin los
    viernes, Palé sin lunes a jueves).
  · nacionalloteria.com (un día por página): solo Quiniela Palé, desde el
    28/01/2015. Tapa el hueco de conectate y suma 2015-2019.
  · enloteria.com (una página por día, /resultados-<slug>-YYYY-MM-DD): solo
    se pide para los días que les faltan a las otras dos. Tiene desde ~fines
    de 2022. Coincidió 23 de 23 contra conectate. Un día sin sorteo muestra
    el sorteo ANTERIOR con su propia fecha: se descarta si la fecha de la
    página no es la pedida (y por las dudas, si repite el día siguiente).
Si las dos primeras tienen el día y no coinciden, gana conectate (es la que ya se
validó contra fuentes oficiales; ver memoria fuentes-loterias-dominicanas)
y la diferencia queda en Observaciones.

Los cachés (JSON) permiten cortar y retomar sin volver a pedir lo ya bajado.
conectate se baja entero una sola vez (~220 peticiones); para traer los
sorteos nuevos, --refrescar-conectate lo vuelve a bajar.

nacionalloteria BLOQUEA (403 "Request blocked") si se le piden muchas páginas
seguidas: el 12/10/2026 cortó tras ~400. Por eso va lento y, ante un 403,
deja de pedir y guarda lo que tiene; se retoma otro día con el mismo caché.
No intentar saltear el bloqueo.

Estado al 12/10/2026: Quiniela Palé de nacionalloteria bajada del 28/01/2015
al 20/03/2016; falta del 21/03/2016 en adelante.
"""
import html
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta

import requests
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

CONECTATE = 'https://api.conectate.com.do/conectate/site-games/%s'
NACIONAL = 'https://www.nacionalloteria.com/republica-dominicana/%s'

SORTEOS = {
    'lotedom': {
        'turno': 'afternoon', 'turno_nombre': 'Tarde',
        'conectate': '69fd98475e76585b60269638',
        'nacional': None,
        'enloteria': ('resultados-lotedom-%s', 'LoteDom'),
        'archivo': 'lotedom.xlsx',
    },
    'quiniela_pale': {
        'turno': 'evening', 'turno_nombre': 'Noche',
        'conectate': '69fd98465e76585b6026956d',   # "Quiniela Leidsa"
        'nacional': ('quiniela-leidsa.php', date(2015, 1, 28)),
        'enloteria': ('resultados-leidsa-%s', 'Leidsa'),
        'archivo': 'quiniela_pale.xlsx',
    },
    'loteria_real': {
        'turno': 'afternoon', 'turno_nombre': 'Tarde',
        'conectate': '69fd98465e76585b602695a6',   # "Quiniela Real" (12:55)
        'nacional': ('quiniela-real.php', date(2015, 1, 29)),
        'enloteria': ('resultados-real-%s', 'Real'),
        'archivo': 'loteria_real.xlsx',
    },
    # Lotería Nacional (RD): dos sorteos con números propios, uno por turno.
    # Gana Más 14:30 → Tarde; Nacional Noche 21:00 → Noche. conectate desde
    # ene-2020; nacionalloteria desde el 29/01/2015 (Nacional: 28/01/2015).
    # OJO: en nacionalloteria, loteria-nacional.php (la Noche) repite en los
    # días recientes los números de Gana Más (visto 14 y 16/10/2026); antes de
    # 2023-07 coincidió 4/4 con conectate, por eso se limita hasta esa fecha.
    'gana_mas': {
        'turno': 'afternoon', 'turno_nombre': 'Tarde',
        'conectate': '69fd98465e76585b6026958d',
        'nacional': ('gana-mas.php', date(2015, 1, 29), None),
        'enloteria': ('resultados-gana-mas-%s', 'Nacional Gana M.s'),
        'archivo': 'gana_mas.xlsx',
    },
    'loteria_nacional': {
        'turno': 'evening', 'turno_nombre': 'Noche',
        'conectate': '69fd98465e76585b60269589',
        'nacional': ('loteria-nacional.php', date(2015, 1, 28), date(2023, 6, 30)),
        'enloteria': ('resultados-nacional-noche-%s', 'Nacional Noche'),
        'archivo': 'loteria_nacional.xlsx',
    },
}
NACIONAL_DELAY = 4.0
ENLOTERIA = 'https://enloteria.com/%s'
ENLOTERIA_DELAY = 1.5
MESES_ES = {m: i + 1 for i, m in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split())}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0 Safari/537.36')


def leer(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def guardar(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def bajar_conectate(game_id, cache_path, refrescar=False):
    """Recorre hacia atrás desde hoy (~220 peticiones). Con caché y sin
    refrescar, usa el caché."""
    if not refrescar and os.path.exists(cache_path):
        return leer(cache_path)
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Origin': 'https://loterias.conectate.com.do',
                      'Referer': 'https://loterias.conectate.com.do/'})
    out, cursor = {}, date.today()
    while True:
        r = s.get(CONECTATE % game_id, params={'date': cursor.isoformat() + 'T04:00:00.000Z'}, timeout=60)
        r.raise_for_status()
        sesiones = json.loads(r.text)['game'].get('sessions') or []
        if not sesiones:
            break
        for x in sesiones:
            crudo = x.get('score') or []
            nums = crudo[0] if crudo and isinstance(crudo[0], list) else crudo
            out[x['date'][:10]] = [str(n).strip() for n in nums]
        viejo = min(datetime.strptime(x['date'][:10], '%Y-%m-%d').date() for x in sesiones)
        if viejo - timedelta(days=1) >= cursor:
            break
        cursor = viejo - timedelta(days=1)
        time.sleep(0.35)
    guardar(cache_path, out)
    return out


def bajar_nacional(pagina, dias, cache_path):
    """Pide solo `dias` (los que conectate no trae) que no estén en caché."""
    cache = leer(cache_path)
    s = requests.Session()
    s.headers['User-Agent'] = UA
    n = 0
    for k in dias:
        if k not in cache or cache[k] == 'error':
            try:
                r = s.get(NACIONAL % pagina, params={'del-dia': k}, timeout=40)
                if r.status_code == 403:
                    print(f'{pagina}: bloqueado (403) en {k}; se corta y se guarda lo bajado.',
                          flush=True)
                    break
                r.raise_for_status()
                t = html.unescape(r.text)
                fecha = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})"', t)
                i = t.find('Resultados de Quiniela')
                if i < 0:   # Gana Más / Lotería Nacional: "Resultados de <nombre>"
                    i = t.find('Resultados de')
                nums = re.findall(r'label-numero">(\d{1,2})<', t[i:i + 600] if i >= 0 else '')
                if fecha and fecha[0] != k:
                    cache[k] = 'otra_fecha'
                else:
                    cache[k] = nums if len(nums) == 3 else []
            except Exception:
                cache[k] = 'error'
            n += 1
            if n % 50 == 0:
                guardar(cache_path, cache)
                print(pagina, k, n, flush=True)
            time.sleep(NACIONAL_DELAY)
    guardar(cache_path, cache)
    return cache


def completar_enloteria(slug, nombre_web, dias, cache_path, siguiente):
    """Pide a enloteria solo `dias` (los que faltan). Devuelve {fecha: nums}.
    `siguiente(fecha)` da los números del día siguiente ya conocidos, para
    descartar una página que repita ese sorteo."""
    cache = leer(cache_path)
    s = requests.Session()
    s.headers['User-Agent'] = UA
    patron = re.compile(nombre_web + r' \w+ (\d{1,2}) de (\w+), (\d{4}) \d{1,2}:\d{2}\s*[AP]M '
                        r'(\d{2}) (\d{2}) (\d{2})', re.I)
    for k in dias:
        if k in cache:
            continue
        r = s.get(ENLOTERIA % (slug % k), timeout=40)
        time.sleep(ENLOTERIA_DELAY)
        if r.status_code == 403:
            print(f'enloteria: bloqueado (403) en {k}; se corta.', flush=True)
            break
        if r.status_code != 200:
            cache[k] = 'sin_pagina'
            continue
        t = re.sub(r'(?s)<(script|style).*?</\1>', '', r.text)
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
        m = patron.search(t)
        if not m:
            cache[k] = 'sin_parsear'
            continue
        fecha = date(int(m.group(3)), MESES_ES[m.group(2).lower()], int(m.group(1))).isoformat()
        cache[k] = [m.group(4), m.group(5), m.group(6)] if fecha == k else 'otra_fecha'
    guardar(cache_path, cache)
    return {k: v for k, v in cache.items()
            if isinstance(v, list) and k in dias and v != siguiente(k)}


def leer_enloteria(cache_path, dias, siguiente):
    cache = leer(cache_path)
    return {k: v for k, v in cache.items()
            if isinstance(v, list) and k in dias and v != siguiente(k)}


def valido(nums):
    return (isinstance(nums, list) and len(nums) == 3
            and all(n.isdigit() and int(n) <= 99 for n in nums))


def armar(nombre, cfg, cache_dir, salida_dir, refrescar=False, sin_nacional=False, desde_excel=None,
          nacional_desde=None):
    hasta = date.today() - timedelta(days=1)
    cx = bajar_conectate(cfg['conectate'], os.path.join(cache_dir, f'{nombre}_conectate.json'),
                         refrescar)
    nc, dias_nc = {}, []
    if cfg['nacional']:
        pagina, desde, *tope = cfg['nacional']
        tope = tope[0] if tope and tope[0] else None
        if nacional_desde:
            desde = max(desde, date.fromisoformat(nacional_desde))
        # Los días que conectate ya trae no se le piden a nacionalloteria.
        d = desde
        while d <= (tope or hasta):
            if not valido(cx.get(d.isoformat())):
                dias_nc.append(d.isoformat())
            d += timedelta(days=1)
        cache_nc = os.path.join(cache_dir, f'{nombre}_nacional.json')
        nc = leer(cache_nc) if sin_nacional else bajar_nacional(pagina, dias_nc, cache_nc)

    data, obs = {}, []
    pendientes = 0
    for k, nums in nc.items():
        if valido(nums):
            data[k] = (nums, 'nacionalloteria')
        elif nums == 'error':
            pendientes += 1
    if cfg['nacional']:
        faltan = sum(1 for k in dias_nc if nc.get(k, 'error') == 'error')
        if faltan > 0:
            print(f'{nombre}: nacionalloteria INCOMPLETO, faltan {faltan} días por bajar.')
    for k, nums in cx.items():
        if not valido(nums):
            obs.append((k, 'números ilegibles en conectate', ' '.join(map(str, nums))))
            continue
        otro = data.get(k)
        if otro and otro[0] != nums:
            obs.append((k, 'diferencia entre fuentes (se usa conectate)',
                        'nacionalloteria %s · conectate %s' % (' '.join(otro[0]), ' '.join(nums))))
        data[k] = (nums, 'conectate')
    data = {k: v for k, v in data.items()
            if k <= hasta.isoformat() and (not desde_excel or k >= desde_excel)}

    # enloteria solo para los días que faltan desde que arranca conectate.
    if cfg.get('enloteria') and cx:
        faltan, d = [], date.fromisoformat(min(cx))
        while d <= hasta:
            if d.isoformat() not in data:
                faltan.append(d.isoformat())
            d += timedelta(days=1)

        def siguiente(k):
            sig = (date.fromisoformat(k) + timedelta(days=1)).isoformat()
            return data.get(sig, (None,))[0]

        slug, nombre_web = cfg['enloteria']
        cache_en = os.path.join(cache_dir, f'{nombre}_enloteria.json')
        extra = (leer_enloteria(cache_en, faltan, siguiente) if sin_nacional
                 else completar_enloteria(slug, nombre_web, faltan, cache_en, siguiente))
        for k, nums in extra.items():
            data[k] = (nums, 'enloteria')

    # Un día sin sorteo solo se anota si alguna fuente lo cubre: los días que
    # nacionalloteria todavía no bajó no son huecos, son pendientes.
    cubierto = set(cx) | {k for k, v in nc.items() if v != 'error'}
    sin_sorteo_confirmado = set()
    if cfg.get('enloteria'):
        cache_en = leer(os.path.join(cache_dir, f'{nombre}_enloteria.json'))
        sin_sorteo_confirmado = {k for k, v in cache_en.items() if v == 'otra_fecha'}
    desde_cx = min(cx) if cx else hasta.isoformat()
    d = date.fromisoformat(min(data))
    while d <= hasta:
        k = d.isoformat()
        if k not in data and (k in cubierto or k >= desde_cx):
            if k in sin_sorteo_confirmado:
                obs.append((k, 'no hubo sorteo (confirmado en enloteria)', ''))
            else:
                obs.append((k, 'sin sorteo', ''))
        d += timedelta(days=1)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Salidas'
    ws.append(['Fecha', 'Turno', 'Turno (nombre)', 'Número', 'Premio 2', 'Premio 3', 'Fuente'])
    for k in sorted(data):
        nums, fuente = data[k]
        ws.append([date.fromisoformat(k), cfg['turno'], cfg['turno_nombre'],
                   nums[0].zfill(2), nums[1].zfill(2), nums[2].zfill(2), fuente])
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = 'yyyy-mm-dd'
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=6):
        for c in row:
            c.number_format = '@'
    for i, w in enumerate([12, 10, 15, 9, 9, 9, 16], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'

    wo = wb.create_sheet('Observaciones')
    wo.append(['Fecha', 'Observación', 'Detalle'])
    for c in wo[1]:
        c.font = Font(bold=True)
    for k, o, det in sorted(obs):
        wo.append([date.fromisoformat(k), o, det])
    for row in wo.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = 'yyyy-mm-dd'
    for i, w in enumerate([12, 44, 40], 1):
        wo.column_dimensions[get_column_letter(i)].width = w
    wb.save(os.path.join(salida_dir, cfg['archivo']))

    print(nombre, 'salidas', len(data), 'desde', min(data), 'hasta', max(data),
          'fuentes', Counter(v[1] for v in data.values()), 'obs', Counter(o[1] for o in obs))


def main():
    cache_dir, salida_dir = sys.argv[1], sys.argv[2]
    refrescar = '--refrescar-conectate' in sys.argv[3:]
    sin_nacional = '--sin-nacional' in sys.argv[3:]
    desde_excel = next((a.split('=', 1)[1] for a in sys.argv[3:] if a.startswith('--desde=')), None)
    nacional_desde = next((a.split('=', 1)[1] for a in sys.argv[3:] if a.startswith('--nacional-desde=')), None)
    solo = next((a.split('=', 1)[1] for a in sys.argv[3:] if a.startswith('--solo=')), None)
    for nombre, cfg in SORTEOS.items():
        if solo and nombre != solo:
            continue
        armar(nombre, cfg, cache_dir, salida_dir, refrescar, sin_nacional, desde_excel, nacional_desde)


if __name__ == '__main__':
    main()
