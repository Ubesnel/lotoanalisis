# -*- coding: utf-8 -*-
import re
from datetime import datetime

_BADGE = {
    'OK':        ('bg-success text-white',   '✓ OK'),
    'OMITIDO':   ('bg-secondary text-white', '↩ OMITIDO'),
    'ERROR':     ('bg-danger text-white',    '✗ ERROR'),
    'PENDIENTE': ('bg-warning text-dark',    '⏳ PENDIENTE'),
}


def build_result_html(lines):
    """Convierte una lista de líneas de log (con prefijos [OK]/[OMITIDO]/[ERROR]/
    [PENDIENTE]) en una tabla HTML con badges Bootstrap. Compartido entre todos
    los importadores del scraper (Florida, Quiniela UY, futuros)."""
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

        m_date = re.search(r'(\d{4}-\d{2}-\d{2})', rest)
        date_str = m_date.group(1) if m_date else ''
        try:
            date_disp = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y') if date_str else ''
        except Exception:
            date_disp = date_str

        detail_raw = re.split(r'[–\-]\s*', rest, maxsplit=1)[-1].strip()
        detail_raw = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', detail_raw).strip()

        rows.append(
            f'<tr>'
            f'<td class="align-middle"><span class="badge {css} px-2 py-1">{label}</span></td>'
            f'<td class="align-middle">{date_disp}</td>'
            f'<td class="align-middle">{rest if not date_str else detail_raw}</td>'
            f'</tr>'
        )

    table = ''
    if rows:
        table = (
            '<table class="table table-sm table-hover table-bordered mt-2 mb-0">'
            '<thead class="table-light">'
            '<tr><th>Estado</th><th>Fecha</th><th>Detalle</th></tr>'
            '</thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
        )

    return f'<div class="p-2">{"".join(headers)}{table}</div>'
