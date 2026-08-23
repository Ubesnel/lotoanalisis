# -*- coding: utf-8 -*-
"""Piezas de presentación compartidas por los informes de Quiniela Uruguay.

Acá viven la paleta, el cabezal verde con las caras y el logo de LotoAnálisis,
y las bolas. Las usan el informe de resultados
(`lottery.quiniela.uy.resultados`) y la Tómbola
(`lottery.prediction.tombola.uy`): las dos piezas se publican con la misma
identidad, así que el color o el cabezal se tocan en un solo lugar y las dos
cambian juntas.

Las bolas siguen la misma receta que el widget `Ball` de la app
(lib/widgets/result_card.dart): degradé radial del claro al oscuro más un
reflejo especular arriba a la izquierda.
"""

# En la quiniela uruguaya los turnos no se llaman Tarde/Noche.
TURN_LABEL = {'afternoon': 'Vespertina', 'evening': 'Nocturna'}

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado',
        'Domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

IMG = '/lottery_portal/static/src/img/'
FUENTE = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
          "'Helvetica Neue',Arial,sans-serif")

# ── Verde y dorado de la marca Quiniela, sólo para el cabezal ─────────────
VERDE_HONDO = '#12602C'
VERDE_VIVO = '#33B457'
DORADO = '#FFC93C'

# ── Color de la bola según el turno ───────────────────────────────────────
# Los mismos de lib/theme.dart, para que una bola de Vespertina se vea igual
# acá que en Últimas salidas de la app.
COLOR_TURNO = {
    'afternoon': (0xF5, 0x9E, 0x0B),   # AppColors.tarde
    'evening': (0x23, 0x39, 0x5B),     # AppColors.noche
}
# Las bolas de la Tómbola van en rojo con el número en blanco, como las de
# una tómbola de verdad, y así no se confunden con las de las salidas.
COLOR_TOMBOLA = (0xD3, 0x2F, 0x2F)

# El cuerpo no es blanco puro: lleva un verde muy suave y lo enmarca un
# borde verde grueso, para que la pieza se lea como una tarjeta de Quiniela
# y no como un rectángulo blanco.
CUERPO_FONDO = '#F4FBF6'
CUERPO_BORDE = '#2FA850'
CUERPO_BORDE_PX = 3
TEXTO = '#2D2440'
TEXTO_SUAVE = '#7A7290'


def _mezcla(color, destino, t):
    """Interpola dos RGB, como el Color.lerp de Flutter."""
    return tuple(round(c + (d - c) * t) for c, d in zip(color, destino))


def _rgb(color):
    return 'rgb(%d,%d,%d)' % color


def _px(valor):
    """Tamaño de fuente derivado del diámetro, sin el '.0' de más: 12.0 se
    escribe 12 y 18.5 queda 18.5."""
    valor = round(valor, 1)
    return int(valor) if valor == int(valor) else valor


def ball_shades(color):
    """(claro, base, oscuro) de una bola, con la misma receta que el widget
    Ball de la app: el claro es un 45% hacia el blanco y el oscuro un 28%
    hacia el negro."""
    return (_mezcla(color, (255, 255, 255), 0.45), color,
            _mezcla(color, (0, 0, 0), 0.28))


def fecha_larga(date):
    """'Jueves 14 de agosto de 2026'."""
    return '%s %d de %s de %d' % (
        DIAS[date.weekday()], date.day, MESES[date.month - 1], date.year)


def cabezal(turn_day, date, titulo='Quiniela Uruguay'):
    """Banner verde de Quiniela con el logo, las caras, el turno y la fecha.

    `titulo` es el cintillo chico de arriba: distingue de qué informe es la
    tarjeta sin cambiarle la identidad."""
    cara = ('<img src="%s%s" alt="" style="position:relative;width:40px;'
            'height:40px;border-radius:50%%;object-fit:cover;'
            'background:#fff;border:2px solid rgba(255,255,255,.85);'
            'box-shadow:0 2px 6px rgba(0,0,0,.3);%s"/>')
    claro, base, _oscuro = ball_shades(COLOR_TURNO[turn_day])
    return (
        '<div style="background:linear-gradient(135deg,%s,%s);'
        'border-radius:18px 18px 0 0;padding:20px 16px 16px;'
        'position:relative;overflow:hidden;text-align:center;">'
        # Resplandores dorado y verde claro, como en la Tabla LotoAnálisis
        '<div style="position:absolute;top:-30px;left:-20px;width:120px;'
        'height:120px;border-radius:50%%;background:radial-gradient('
        'circle,rgba(255,201,60,.40),transparent 70%%);"></div>'
        '<div style="position:absolute;bottom:-34px;right:-22px;'
        'width:115px;height:115px;border-radius:50%%;'
        'background:radial-gradient(circle,rgba(163,230,53,.32),'
        'transparent 70%%);"></div>'
        '<div style="position:relative;display:flex;align-items:center;'
        'justify-content:center;gap:12px;">'
        '<div style="display:flex;align-items:center;">%s%s</div>'
        '<img src="%slogo.png" alt="LotoAnálisis" style="height:52px;"/>'
        '</div>'
        '<div style="position:relative;display:inline-block;margin-top:12px;'
        'background:rgba(255,255,255,.14);'
        'border:1px solid rgba(255,255,255,.40);color:#fff;'
        'font:800 13px/1 %s;padding:7px 20px;border-radius:50px;'
        'letter-spacing:1.6px;text-transform:uppercase;">%s</div>'
        # El turno lleva el mismo color que las bolas: se lee de un vistazo.
        '<div style="position:relative;margin-top:12px;">'
        '<span style="display:inline-block;'
        'background:linear-gradient(135deg,%s,%s);color:#fff;'
        'font:900 25px/1 %s;letter-spacing:3.5px;padding:11px 26px;'
        'border-radius:50px;text-transform:uppercase;'
        'box-shadow:0 4px 12px rgba(0,0,0,.30);'
        'text-shadow:0 1px 3px rgba(0,0,0,.35);">%s</span></div>'
        '<div style="position:relative;margin-top:11px;font:700 12.5px/1 %s;'
        'color:rgba(255,255,255,.92);">%s</div>'
        '</div>' % (
            VERDE_HONDO, VERDE_VIVO,
            cara % (IMG, 'mateo_cara.png', ''),
            cara % (IMG, 'valeria_cara.png', 'margin-left:-13px;'),
            IMG, FUENTE, titulo, _rgb(claro), _rgb(base), FUENTE,
            TURN_LABEL[turn_day], FUENTE, fecha_larga(date))
    )


def bola(numero, color, diam=56):
    """Bola con degradé radial y reflejo. `numero` va tal cual, así que el
    que llama decide si lo muestra en dos cifras o en tres."""
    claro, base, oscuro = ball_shades(color)
    return (
        '<div style="position:relative;width:%dpx;height:%dpx;'
        'border-radius:50%%;'
        'background:radial-gradient(circle at 30%% 25%%,%s 0%%,%s 55%%,'
        '%s 100%%);'
        'box-shadow:0 4px 7px rgba(%d,%d,%d,.45);'
        'display:flex;align-items:center;justify-content:center;">'
        '<div style="position:absolute;top:10%%;left:18%%;width:34%%;'
        'height:20%%;border-radius:50%%;background:linear-gradient('
        'to bottom,rgba(255,255,255,.55),rgba(255,255,255,0));"></div>'
        '<span style="position:relative;font:800 %spx/1 %s;color:#fff;'
        'letter-spacing:.5px;text-shadow:0 1px 2px rgba(0,0,0,.35);">'
        '%s</span></div>'
        % (diam, diam, _rgb(claro), _rgb(base), _rgb(oscuro),
           oscuro[0], oscuro[1], oscuro[2], _px(diam * 0.33), FUENTE,
           numero)
    )


def hueco(diam=56):
    """Bola vacía: ese premio no está cargado."""
    return ('<div style="width:%dpx;height:%dpx;border-radius:50%%;'
            'border:2px dashed #BCDCC6;"></div>' % (diam, diam))


def badge(texto, lado=26):
    """Cuadradito blanco con el número de premio (o de combinación)."""
    return (
        '<div style="width:%dpx;height:%dpx;border-radius:8px;'
        'background:#FFFFFF;border:1px solid #C6E4CF;'
        'font:800 %spx/%dpx %s;color:%s;text-align:center;">%s</div>'
        % (lado, lado, _px(lado * 0.46), lado - 2, FUENTE, TEXTO_SUAVE,
           texto)
    )


def tarjeta(cabezal_html, cuerpo_html, ancho=452):
    """Envuelve cabezal + cuerpo en la tarjeta verde centrada."""
    return (
        '<div style="display:flex;justify-content:center;'
        'padding:4px 0 12px;">'
        '<div style="width:%dpx;max-width:100%%;border-radius:20px;'
        'background:%s;border:%dpx solid %s;overflow:hidden;'
        'box-shadow:0 12px 30px rgba(18,96,44,.22);">%s%s</div></div>'
        % (ancho, CUERPO_FONDO, CUERPO_BORDE_PX, CUERPO_BORDE,
           cabezal_html, cuerpo_html)
    )
