"""Generate cover images for fin_de_semana, secuencias_lineas, secuencias_terminales."""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = r'E:\Trabajo\Odoo\Odoo17\lottery\lottery_portal\static\src\img'
FD  = r'C:\Windows\Fonts\\'

def fnt(name, size):
    return ImageFont.truetype(FD + name, size)

def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def gradient_bg(draw, w, h, top, bottom):
    for y in range(h):
        draw.line([(0, y), (w, y)], fill=lerp(top, bottom, y / h))

def rrect(draw, x1, y1, x2, y2, r, fill, outline=None, ow=0):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill,
                            outline=outline, width=ow)

def centered_text(draw, text, font, y, w, color):
    bb = draw.textbbox((0, 0), text, font=font)
    x = (w - (bb[2] - bb[0])) // 2
    draw.text((x, y), text, fill=color, font=font)

def ball(draw, cx, cy, r, color, label, lf):
    # soft shadow
    draw.ellipse([cx - r + 3, cy - r + 3, cx + r + 3, cy + r + 3],
                 fill=tuple(max(0, c - 60) for c in color))
    # body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # shine
    draw.ellipse([cx - r // 3, cy - r * 2 // 3,
                  cx + r // 4, cy - r // 6], fill=(255, 255, 255, 80))
    bb = draw.textbbox((0, 0), label, font=lf)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th // 2 - 1), label, fill='white', font=lf)

def arrow(draw, cx, cy, color):
    pts = [(cx, cy - 6), (cx + 14, cy), (cx, cy + 6)]
    draw.polygon(pts, fill=color)

W, H = 500, 520

# ── fonts ─────────────────────────────────────────────────────────
F_BADGE  = fnt('arialbd.ttf', 24)
F_TITLE1 = fnt('impact.ttf',  46)
F_TITLE2 = fnt('impact.ttf',  54)
F_SUB    = fnt('arialbd.ttf', 17)
F_BALL   = fnt('impact.ttf',  19)
F_BALL_S = fnt('impact.ttf',  15)
F_BAR_L  = fnt('arialbd.ttf', 13)
F_BOT    = fnt('arialbd.ttf', 19)

# ══════════════════════════════════════════════════════════════════
# 1 – grupos fin semana.png   (orange / amber)
# ══════════════════════════════════════════════════════════════════
img  = Image.new('RGB', (W, H), (255, 255, 255))
draw = ImageDraw.Draw(img, 'RGBA')

gradient_bg(draw, W, H, (255, 253, 240), (255, 237, 200))

# deco blobs
draw.ellipse([-50, -50, 140, 140], fill=(255, 180, 50, 45))
draw.ellipse([W - 130, H - 130, W + 60, H + 60], fill=(240, 100, 30, 30))
draw.ellipse([W - 80, -40, W + 40, 80], fill=(255, 200, 80, 30))

# badge
rrect(draw, 28, 20, W - 28, 78, 16, (220, 80, 10))
centered_text(draw, 'SÁBADO + DOMINGO', F_BADGE, 36, W, 'white')

# titles
centered_text(draw, 'GRUPOS', F_TITLE1, 94, W, (70, 35, 5))
centered_text(draw, 'MÁS FRECUENTES', F_TITLE2, 142, W, (220, 80, 10))

# sub strip
rrect(draw, 65, 204, W - 65, 238, 10, (220, 80, 10, 190))
centered_text(draw, 'FIN DE SEMANA · HISTÓRICO', F_SUB, 212, W, 'white')

# ── bar chart ────────────────────────────────────────────────────
BAR_COLORS = [(139, 92, 246), (220, 80, 10), (234, 179, 8),
              (22, 163, 74), (59, 130, 246)]
BAR_H      = [128, 108, 88, 68, 52]
BAR_LBL    = ['Lin 1', 'Lin 2', 'Lin 3', 'Lin 4', 'Lin 5']
BW, GAP    = 52, 10
total_bw   = 5 * BW + 4 * GAP
sx         = (W - total_bw) // 2
base_y     = 390

for i, (bh, bc, lbl) in enumerate(zip(BAR_H, BAR_COLORS, BAR_LBL)):
    bx = sx + i * (BW + GAP)
    by = base_y - bh
    rrect(draw, bx, by, bx + BW, base_y, 7, bc)
    # rank above bar
    centered_text(draw, str(i + 1), fnt('arialbd.ttf', 14), by - 20, 0, bc)
    draw.text((bx + (BW - draw.textbbox((0, 0), str(i + 1), fnt('arialbd.ttf', 14))[2]) // 2,
               by - 20), str(i + 1), fill=bc, font=fnt('arialbd.ttf', 14))
    # label below
    bb = draw.textbbox((0, 0), lbl, font=F_BAR_L)
    draw.text((bx + (BW - (bb[2] - bb[0])) // 2, base_y + 5), lbl,
              fill=(80, 40, 10), font=F_BAR_L)

# ── lottery balls scattered ───────────────────────────────────────
ball_data = [
    (58,  410, 18, (139, 92, 246), '17'),
    (445, 415, 18, (22, 163, 74),  '06'),
    (30,  280, 14, (59, 130, 246), '50'),
    (472, 270, 14, (220, 80, 10),  '37'),
    (460, 155, 12, (234, 179, 8),  '24'),
    (38,  160, 12, (220, 80, 10),  '81'),
]
for cx, cy, r, c, lbl in ball_data:
    ball(draw, cx, cy, r, c, lbl, F_BALL_S)

# bottom strip
rrect(draw, 0, H - 50, W, H, 0, (220, 80, 10))
centered_text(draw, 'Pick 3 Florida · Análisis Histórico', F_BOT, H - 38, W, 'white')

img.save(os.path.join(OUT, 'grupos fin semana.png'), 'PNG')
print('grupos fin semana.png  OK')


# ══════════════════════════════════════════════════════════════════
# helper: build a secuencias image
# ══════════════════════════════════════════════════════════════════
def make_secuencias(filename, title_word, badge_color, dark_color,
                    bg_top, bg_bot, blob1, blob2, ball_colors, row_labels):

    img  = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img, 'RGBA')

    gradient_bg(draw, W, H, bg_top, bg_bot)

    draw.ellipse([-50, -50, 140, 140], fill=blob1)
    draw.ellipse([W - 130, H - 130, W + 60, H + 60], fill=blob2)
    draw.ellipse([W - 70, -40, W + 40, 90], fill=blob2)

    # badge
    rrect(draw, 28, 20, W - 28, 78, 16, badge_color)
    centered_text(draw, 'SECUENCIAS DE GRUPOS', F_BADGE, 36, W, 'white')

    # title
    centered_text(draw, title_word, F_TITLE1, 94, W, dark_color)
    centered_text(draw, 'QUE SIGUEN', F_TITLE2, 142, W, badge_color)

    # sub strip
    rrect(draw, 65, 204, W - 65, 238, 10, badge_color + (190,))
    centered_text(draw, 'TOP 5 · GENERAL · TARDE · NOCHE', F_SUB, 212, W, 'white')

    # ── two rows of 5 balls with arrows ─────────────────────────
    SPACING = 90
    BAll_R  = 24

    for row_i, (lbls, cy) in enumerate(zip(row_labels, [298, 375])):
        row_x = (W - (5 * SPACING - (SPACING - BAll_R * 2))) // 2
        for i, lbl in enumerate(lbls):
            cx = row_x + i * SPACING
            c = ball_colors[i % len(ball_colors)]
            ball(draw, cx, cy, BAll_R, c, lbl, F_BALL)
            if i < 4:
                arrow(draw, cx + BAll_R + 4, cy, badge_color)

    # ── scattered small balls ────────────────────────────────────
    extras = [
        (38,  160, 14, ball_colors[0], '88'),
        (462, 155, 14, ball_colors[2], '34'),
        (30,  420, 14, ball_colors[1], '13'),
        (470, 425, 14, ball_colors[3], '77'),
    ]
    for cx, cy, r, c, lbl in extras:
        ball(draw, cx, cy, r, c, lbl, F_BALL_S)

    # bottom strip
    rrect(draw, 0, H - 50, W, H, 0, badge_color)
    centered_text(draw, 'Pick 3 Florida · Análisis Histórico', F_BOT, H - 38, W, 'white')

    img.save(os.path.join(OUT, filename), 'PNG')
    print(filename, ' OK')


# ══════════════════════════════════════════════════════════════════
# 2 – secuencias lineas.png   (purple)
# ══════════════════════════════════════════════════════════════════
make_secuencias(
    filename    = 'secuencias lineas.png',
    title_word  = 'LÍNEAS',
    badge_color = (109, 40, 217),
    dark_color  = (60, 20, 120),
    bg_top      = (246, 242, 255),
    bg_bot      = (220, 210, 255),
    blob1       = (139, 92, 246, 50),
    blob2       = (109, 40, 217, 35),
    ball_colors = [(139, 92, 246), (124, 58, 237), (109, 40, 217),
                   (91, 33, 182),  (76,  29, 149)],
    row_labels  = [['00','10','20','30','40'],
                   ['50','60','70','80','90']],
)

# ══════════════════════════════════════════════════════════════════
# 3 – secuencias terminales.png   (teal / emerald)
# ══════════════════════════════════════════════════════════════════
make_secuencias(
    filename    = 'secuencias terminales.png',
    title_word  = 'TERMINALES',
    badge_color = (5, 150, 105),
    dark_color  = (6, 78, 59),
    bg_top      = (236, 253, 245),
    bg_bot      = (209, 250, 229),
    blob1       = (16, 185, 129, 50),
    blob2       = (5, 150, 105, 35),
    ball_colors = [(16, 185, 129), (5, 150, 105), (4, 120, 87),
                   (6,  95,  70),  (2,  77,  55)],
    row_labels  = [['x0', 'x1', 'x2', 'x3', 'x4'],
                   ['x5', 'x6', 'x7', 'x8', 'x9']],
)
