"""Histórico de Kentucky (Pick 3 + Pick 4) a Excel, listo para el wizard.

Uso: python extract_kentucky.py <cache.json> <salida.xlsx>

kylottery.com no responde desde Uruguay (timeout de conexión), así que se usan agregadores:
  https://www.lotterycorner.com/ky/pick-3-midday/<año>   (→ Tarde)  desde 1999
  https://www.lotterycorner.com/ky/pick-3-evening/<año>  (→ Noche)  desde 1998
y lo mismo con pick-4. Se cruza con lottery.net (desde 2010, mismo esquema que Maryland):
si las dos fuentes difieren manda lottery.net (en los 3 casos coincide con su página de
cada sorteo) y se anota en Observaciones; si solo una tiene el sorteo, se usa esa.
Si un día trae Pick 3 y Pick 4 idénticos en los dos turnos y lottery.net no lo confirma,
es un turno copiado en lotterycorner y se omite. Kentucky no tiene Fireball.
El Midday no se sorteaba los domingos hasta el 28/02/2016 (esos domingos no son huecos).
Pick 3 da la centena y el número (últimos dos dígitos); Pick 4 da los premios 2 y 3.
El año en curso se vuelve a pedir siempre; los cerrados quedan en el caché JSON.
"""
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta

import requests
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from extract_md_sc_il import parsear as parsear_lnet

URL_LC = 'https://www.lotterycorner.com/ky/pick-%d-%s/%d'
URL_LNET = 'https://www.lottery.net/kentucky/pick-%d-%s/numbers/%d'
PRIMER_ANIO_LC = 1998
PRIMER_ANIO_LNET = 2010
TURNOS = {'midday': ('afternoon', 'Tarde'), 'evening': ('evening', 'Noche')}
DELAY = 2.0
TARDE_DOMINGOS_DESDE = date(2016, 2, 28)
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

RE_FILA_LC = re.compile(r'<time dateTime="(\d{4}-\d{2}-\d{2})"[^>]*>.*?<ul class="lsp-balls"[^>]*>(.*?)</ul>', re.S)
RE_BOLA_LC = re.compile(r'data-ball="standard" aria-label="(\d)"')


def parsear_lc(html, bolas_n):
    """→ {iso_fecha: 'ABC'} con las bolas principales (3 o 4 dígitos)."""
    out = {}
    for fecha, cuerpo in RE_FILA_LC.findall(html):
        bolas = RE_BOLA_LC.findall(cuerpo)
        if len(bolas) == bolas_n:
            out[fecha] = ''.join(bolas)
    return out


def bajar(s, url, parser, juego):
    for intento in range(3):
        try:
            r = s.get(url, timeout=60)
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            return parser(r.text, juego)
        except Exception as exc:
            print('error', url, exc)
            time.sleep(5 * (intento + 1))
    return None


def descargar(cache_path, anio_actual):
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            cache = json.load(f)
    s = requests.Session()
    s.headers['User-Agent'] = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0 Safari/537.36')
    fuentes = (('lc', URL_LC, parsear_lc, PRIMER_ANIO_LC), ('lnet', URL_LNET, parsear_lnet, PRIMER_ANIO_LNET))
    for anio in range(PRIMER_ANIO_LC, anio_actual + 1):
        for fuente, url, parser, primer_anio in fuentes:
            if anio < primer_anio:
                continue
            for juego in (3, 4):
                for turno in TURNOS:
                    k = '%s/p%d/%s/%d' % (fuente, juego, turno, anio)
                    if k in cache and anio < anio_actual:
                        continue
                    datos = bajar(s, url % (juego, turno, anio), parser, juego)
                    if datos is not None:
                        cache[k] = datos
                        print(k, len(datos))
                    time.sleep(DELAY)
        # Se guarda por año para no perder lo bajado si se corta.
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
    return cache


def juntar(cache, fuente, juego, turno):
    out = {}
    pref = '%s/p%d/%s/' % (fuente, juego, turno)
    for k, v in cache.items():
        if k.startswith(pref):
            out.update(v)
    return out


def main():
    cache_path, salida = sys.argv[1], sys.argv[2]
    hoy = date.today()
    cache = descargar(cache_path, hoy.year)

    filas, obs = [], []
    # Turnos copiados en lotterycorner: mismo Pick 3 y Pick 4 en Midday y Evening.
    copiados = {}
    for juego in (3, 4):
        m, e = juntar(cache, 'lc', juego, 'midday'), juntar(cache, 'lc', juego, 'evening')
        copiados[juego] = {k for k in m if e.get(k) == m[k]}
    lnet_ok = set(juntar(cache, 'lnet', 3, 'midday')) & set(juntar(cache, 'lnet', 3, 'evening'))
    descartar = set()
    for k in sorted((copiados[3] & copiados[4]) - lnet_ok):
        d = date.fromisoformat(k)
        sin_tarde = d.weekday() == 6 and d < TARDE_DOMINGOS_DESDE
        turnos = ('midday',) if sin_tarde else ('midday', 'evening')
        for t in turnos:
            descartar.add((t, k))
            obs.append((d, TURNOS[t][0], 'turno copiado en lotterycorner (se omite)',
                        'Pick 3 y Pick 4 iguales en Midday y Evening'))
    for turno, (codigo, nombre) in TURNOS.items():
        res = {}
        for juego in (3, 4):
            lc, lnet = juntar(cache, 'lc', juego, turno), juntar(cache, 'lnet', juego, turno)
            for k in sorted(set(lc) & set(lnet)):
                if lc[k] != lnet[k]:
                    obs.append((date.fromisoformat(k), codigo, 'lotterycorner y lottery.net difieren (queda lottery.net)',
                                'Pick %d: %s / %s' % (juego, lc[k], lnet[k])))
            for k in sorted(set(lnet) - set(lc)):
                obs.append((date.fromisoformat(k), codigo, 'solo en lottery.net (se completa con esa fuente)',
                            'Pick %d' % juego))
            res[juego] = dict(lc, **lnet)
        datos, datos4 = res[3], res[4]
        if not datos:
            continue
        d = date.fromisoformat(min(min(datos), min(datos4)))
        while d <= hoy:
            k = d.isoformat()
            if (turno, k) in descartar:
                pass
            elif turno == 'midday' and d.weekday() == 6 and d < TARDE_DOMINGOS_DESDE and k not in datos:
                pass
            elif k in datos and k in datos4:
                filas.append((d, codigo, nombre, datos[k], datos4[k]))
            elif k in datos or k in datos4:
                obs.append((d, codigo, 'sorteo incompleto en la fuente (se omite el turno)',
                            'falta Pick 4' if k in datos else 'falta Pick 3'))
            elif d < hoy:
                obs.append((d, codigo, 'sin resultado en la fuente (se omite el turno)', DIAS[d.weekday()]))
            d += timedelta(days=1)

    filas.sort(key=lambda r: (r[0], r[1] != 'afternoon'))
    wb = Workbook()
    ws = wb.active
    ws.title = 'Kentucky'
    ws.append(['Fecha', 'Turno', 'Turno (nombre)', 'Pick 3', 'Pick 4', 'Centena', 'Número',
               'Premio 2', 'Premio 3', 'Fuente'])
    for fecha, codigo, nombre, p3, p4 in filas:
        ws.append([fecha, codigo, nombre, p3, p4, int(p3[0]), p3[1:], p4[:2], p4[2:], 'lotterycorner.com'])
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = 'yyyy-mm-dd'
    for col in (4, 5, 7, 8, 9):
        for row in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            row[0].number_format = '@'
    for i, w in enumerate([12, 10, 15, 8, 8, 9, 9, 9, 9, 16], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'

    wo = wb.create_sheet('Observaciones')
    wo.append(['Fecha', 'Turno', 'Observación', 'Detalle'])
    for c in wo[1]:
        c.font = Font(bold=True)
    for o in sorted(obs, key=lambda x: (x[0], x[1])):
        wo.append(list(o))
    for row in wo.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = 'yyyy-mm-dd'
    for i, w in enumerate([12, 10, 56, 22], 1):
        wo.column_dimensions[get_column_letter(i)].width = w
    wb.save(salida)

    print('filas', len(filas), 'desde', filas[0][0], 'hasta', filas[-1][0])
    for codigo in ('afternoon', 'evening'):
        fs = [r[0] for r in filas if r[1] == codigo]
        print(codigo, len(fs), fs[0], fs[-1], 'dup', len(fs) - len(set(fs)))
    print('observaciones', Counter(o[2] for o in obs))
    print('huecos por año', sorted(Counter((o[0].year, o[1]) for o in obs if o[2].startswith('sin')).items()))


if __name__ == '__main__':
    main()
