# -*- coding: utf-8 -*-
"""Genera el PNG de la Tabla LotoAnálisis a partir de la grilla ya armada
(ver tabla_acompanantes_grid.build_grid). Usa las fuentes Lato empaquetadas
con el módulo 'web' de Odoo (mismo resultado en Windows/dev y Linux/
producción, sin depender de fuentes del sistema operativo)."""
import io

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from odoo.tools import file_path

from .charada_data import DECADE_COLORS

CELL = 46
MARGIN = 26
HEADER_H = 180
FOOTER_H = 40
LOGO_W = 250

_FACES = ('mateo_cara.png', 'valeria_cara.png')

# Estrellitas del header, en fracción del ancho/alto del header (como el
# .bp-stars del sitio): (x, y, radio, alpha, color).
_STARS = [
    (0.08, 0.20, 1.6, 210, (255, 255, 255)),
    (0.14, 0.55, 1.2, 160, (251, 191, 36)),
    (0.06, 0.80, 1.8, 150, (255, 255, 255)),
    (0.92, 0.18, 1.4, 200, (251, 191, 36)),
    (0.88, 0.50, 1.8, 150, (255, 255, 255)),
    (0.94, 0.78, 1.3, 170, (255, 255, 255)),
    (0.18, 0.90, 1.2, 130, (251, 191, 36)),
    (0.82, 0.90, 1.5, 140, (255, 255, 255)),
]


def _font(name, size):
    return ImageFont.truetype(file_path(f'web/static/fonts/lato/{name}'), size)


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _gradient_bg(draw, x1, y1, x2, y2, top, bottom):
    h = y2 - y1
    for i in range(h):
        t = i / max(h, 1)
        draw.line([(x1, y1 + i), (x2, y1 + i)], fill=_lerp(top, bottom, t))


def _add_orb(img, cx, cy, r, color, alpha=70, blur=30):
    """Mancha de luz difusa (como los .bp-orb del sitio): un círculo de
    color desenfocado, para darle profundidad al fondo del header."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r],
                                   fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    rgba = img.convert('RGBA')
    rgba.alpha_composite(layer)
    return rgba.convert('RGB')


def _stars(draw, x0, y0, w, h):
    for fx, fy, r, alpha, color in _STARS:
        x, y = x0 + fx * w, y0 + fy * h
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color + (alpha,))


def _centered_text(draw, text, font, cx, y, color):
    bb = draw.textbbox((0, 0), text, font=font)
    x = cx - (bb[2] - bb[0]) // 2
    draw.text((x, y), text, fill=color, font=font)


def _pill_badge(draw, text, font, cx, y, pad_x=18, pad_y=8):
    """Pastilla translúcida con borde, texto centrado adentro. Devuelve el
    borde inferior (para seguir apilando debajo)."""
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x0, y1_ = cx - tw // 2 - pad_x, y + th + pad_y * 2
    x1, y0 = cx + tw // 2 + pad_x, y
    draw.rounded_rectangle([x0, y0, x1, y1_], radius=(y1_ - y0) // 2,
                            fill=(255, 255, 255, 35),
                            outline=(255, 255, 255, 150), width=1)
    draw.text((cx - tw // 2, y + pad_y - bb[1]), text, fill='white', font=font)
    return y1_


def _circle_mask(size):
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    return mask


def _gradient_disc(size, light, dark):
    """Círculo con degradé diagonal (135°) de light a dark, con canal alfa
    circular — mismo estilo que las bolas .ball del sitio (linear-gradient
    135deg), no un radial plano."""
    grad = Image.linear_gradient('L').resize((size * 2, size * 2))
    grad = grad.rotate(135, resample=Image.BICUBIC)
    gw, gh = grad.size
    left, top = (gw - size) // 2, (gh - size) // 2
    grad = grad.crop((left, top, left + size, top + size))
    disc = ImageOps.colorize(grad, black=dark, white=light).convert('RGBA')
    disc.putalpha(_circle_mask(size))
    return disc


def _ball(img, draw, cx, cy, r, color, label, font):
    size = r * 2
    light = tuple(min(255, v + 35) for v in color)
    dark = tuple(max(0, v - 35) for v in color)

    # sombra
    draw.ellipse([cx - r + 2, cy - r + 3, cx + r + 2, cy + r + 3],
                 fill=dark + (110,))
    disc = _gradient_disc(size, light, dark)
    img.paste(disc, (cx - r, cy - r), disc)
    # brillo
    draw.ellipse([cx - r // 3, cy - r * 2 // 3, cx + r // 4, cy - r // 6],
                 fill=(255, 255, 255, 90))
    bb = draw.textbbox((0, 0), label, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th // 2 - 1), label, fill='white', font=font)


def _face_disc(name, size):
    im = Image.open(file_path(f'lottery_portal/static/src/img/{name}')).convert('RGBA')
    im = ImageOps.fit(im, (size, size), Image.LANCZOS)
    im.putalpha(_circle_mask(size))
    return im


def render_png(grid, size, sorteo_name):
    """grid: {(row, col): numero}. size: dimensión de la grilla (12 → 12x12).
    Devuelve bytes PNG."""
    grid_px = size * CELL
    w = grid_px + MARGIN * 2
    h = HEADER_H + grid_px + MARGIN + FOOTER_H

    img = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img, 'RGBA')

    _gradient_bg(draw, 0, 0, w, HEADER_H, (0x6D, 0x28, 0xD9), (0x8B, 0x5C, 0xF6))
    img = _add_orb(img, int(w * 0.06), int(HEADER_H * 0.1), 90,
                    (0xF9, 0x73, 0x16), alpha=70, blur=35)
    img = _add_orb(img, int(w * 0.96), int(HEADER_H * 0.95), 80,
                    (0xFB, 0xBF, 0x24), alpha=55, blur=30)
    draw = ImageDraw.Draw(img, 'RGBA')
    _stars(draw, 0, 0, w, HEADER_H)

    f_badge = _font('Lato-Bla-webfont.ttf', 17)
    f_ball = _font('Lato-Bla-webfont.ttf', 15)
    f_foot = _font('Lato-Bol-webfont.ttf', 13)

    logo = Image.open(file_path('lottery_portal/static/src/img/logo.png')).convert('RGBA')
    logo_h = int(LOGO_W * logo.height / logo.width)
    logo = logo.resize((LOGO_W, logo_h), Image.LANCZOS)
    img.paste(logo, ((w - LOGO_W) // 2, 16), logo)

    _pill_badge(draw, sorteo_name, f_badge, w // 2, 16 + logo_h + 14)

    r_ball = CELL // 2 - 4
    face_discs = [_face_disc(name, int(r_ball * 1.8)) for name in _FACES]
    face_i = 0
    for row in range(size):
        for col in range(size):
            cx = MARGIN + col * CELL + CELL // 2
            cy = HEADER_H + MARGIN // 2 + row * CELL + CELL // 2
            n = grid.get((row, col))
            if n is not None:
                color = DECADE_COLORS[n // 10]
                _ball(img, draw, cx, cy, r_ball, color, f'{n:02d}', f_ball)
            else:
                disc = face_discs[face_i % 2]
                face_i += 1
                dr = disc.width // 2
                img.paste(disc, (cx - dr, cy - dr), disc)

    draw.rectangle([0, h - FOOTER_H, w, h], fill=(0x4C, 0x1D, 0x95))
    _centered_text(draw, 'LotoAnálisis · Análisis Predictivo', f_foot,
                    w // 2, h - FOOTER_H + 11, 'white')

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()
