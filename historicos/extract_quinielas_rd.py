"""Histórico de LoteDom y Quiniela Palé (Leidsa) a Excel, listo para el wizard.

Uso: python extract_quinielas_rd.py <carpeta_cache> <carpeta_salida>

Las dos son quinielas de 3 números de 00 a 99 (premio 1 = el fijo, premios
2 y 3 = los corridos), un sorteo por día:
  · LoteDom: 12:00 (hora RD), todos los días → turno Tarde (afternoon).
  · Quiniela Palé: 20:55, domingos 15:55 → turno Noche (evening).

Fuentes:
  · conectate (api.conectate.com.do, 10 sorteos por petición): desde 2020.
    Tiene un hueco sistemático entre oct-2022 y jun-2023 (LoteDom sin los
    viernes, Palé sin lunes a jueves).
  · nacionalloteria.com (un día por página): solo Quiniela Palé, desde el
    28/01/2015. Tapa el hueco de conectate y suma 2015-2019.
Si las dos tienen el día y no coinciden, gana conectate (es la que ya se
validó contra fuentes oficiales; ver memoria fuentes-loterias-dominicanas)
y la diferencia queda en Observaciones.

Los cachés (JSON) permiten cortar y retomar sin volver a pedir lo ya bajado.
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
        'archivo': 'lotedom.xlsx',
    },
    'quiniela_pale': {
        'turno': 'evening', 'turno_nombre': 'Noche',
        'conectate': '69fd98465e76585b6026956d',   # "Quiniela Leidsa"
        'nacional': ('quiniela-leidsa.php', date(2015, 1, 28)),
        'archivo': 'quiniela_pale.xlsx',
    },
}
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


def bajar_conectate(game_id, cache_path):
    """Recorre hacia atrás desde hoy. Siempre completo: son ~220 peticiones."""
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


def bajar_nacional(pagina, desde, cache_path, hasta):
    cache = leer(cache_path)
    s = requests.Session()
    s.headers['User-Agent'] = UA
    d, n = desde, 0
    while d <= hasta:
        k = d.isoformat()
        if k not in cache or cache[k] == 'error':
            try:
                r = s.get(NACIONAL % pagina, params={'del-dia': k}, timeout=40)
                r.raise_for_status()
                t = html.unescape(r.text)
                fecha = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})"', t)
                i = t.find('Resultados de Quiniela')
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
            time.sleep(0.8)
        d += timedelta(days=1)
    guardar(cache_path, cache)
    return cache


def valido(nums):
    return (isinstance(nums, list) and len(nums) == 3
            and all(n.isdigit() and int(n) <= 99 for n in nums))


def armar(nombre, cfg, cache_dir, salida_dir):
    hasta = date.today() - timedelta(days=1)
    cx = bajar_conectate(cfg['conectate'], os.path.join(cache_dir, f'{nombre}_conectate.json'))
    nc = {}
    if cfg['nacional']:
        pagina, desde = cfg['nacional']
        nc = bajar_nacional(pagina, desde, os.path.join(cache_dir, f'{nombre}_nacional.json'), hasta)

    data, obs = {}, []
    for k, nums in nc.items():
        if valido(nums):
            data[k] = (nums, 'nacionalloteria')
        elif nums == 'error':
            obs.append((k, 'error de descarga en nacionalloteria', ''))
    for k, nums in cx.items():
        if not valido(nums):
            obs.append((k, 'números ilegibles en conectate', ' '.join(map(str, nums))))
            continue
        otro = data.get(k)
        if otro and otro[0] != nums:
            obs.append((k, 'diferencia entre fuentes (se usa conectate)',
                        'nacionalloteria %s · conectate %s' % (' '.join(otro[0]), ' '.join(nums))))
        data[k] = (nums, 'conectate')
    data = {k: v for k, v in data.items() if k <= hasta.isoformat()}

    d = date.fromisoformat(min(data))
    while d <= hasta:
        if d.isoformat() not in data:
            obs.append((d.isoformat(), 'sin sorteo', ''))
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
    for nombre, cfg in SORTEOS.items():
        armar(nombre, cfg, cache_dir, salida_dir)


if __name__ == '__main__':
    main()
