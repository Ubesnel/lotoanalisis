"""Generate cover images for numeros-calientes and numeros-frios articles."""
from PIL import Image, ImageDraw, ImageFont
import os, math

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
    shadow = tuple(max(0, c - 55) for c in color)
    draw.ellipse([cx - r + 3, cy - r + 3, cx + r + 3, cy + r + 3], fill=shadow)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # shine
    draw.ellipse([cx - r//3, cy - r*2//3, cx + r//4, cy - r//6],
                 fill=(255, 255, 255, 70))
    bb = draw.textbbox((0, 0), label, font=lf)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx - tw//2, cy - th//2 - 1), label, fill='white', font=lf)

W, H = 500, 520

F_BADGE  = fnt('arialbd.ttf', 24)
F_T1     = fnt('impact.ttf',  48)
F_T2     = fnt('impact.ttf',  56)
F_SUB    = fnt('arialbd.ttf', 17)
F_BALL   = fnt('impact.ttf',  17)
F_BALL_S = fnt('impact.ttf',  14)
F_BOT    = fnt('arialbd.ttf', 19)

# ══════════════════════════════════════════════════════════════════
# 1 – numeros calientes.png   (fire: dark-red → orange)
# ══════════════════════════════════════════════════════════════════
img  = Image.new('RGB', (W, H))
draw = ImageDraw.Draw(img, 'RGBA')

gradient_bg(draw, W, H, (255, 250, 240), (255, 225, 190))

# deco blobs
draw.ellipse([-55, -55, 140, 140], fill=(220, 38, 38, 45))
draw.ellipse([W-130, H-130, W+60, H+60], fill=(249, 115, 22, 35))
draw.ellipse([W-70, -45, W+40, 85], fill=(251, 191, 36, 30))

# top badge
rrect(draw, 28, 20, W-28, 78, 16, (185, 28, 28))
centered_text(draw, '🔥 NÚMEROS CALIENTES', F_BADGE, 35, W, 'white')

# titles
centered_text(draw, 'TOP 30', F_T1, 93, W, (120, 20, 10))
centered_text(draw, 'CALIENTES', F_T2, 142, W, (185, 28, 28))

# sub strip
rrect(draw, 65, 204, W-65, 238, 10, (185, 28, 28, 185))
centered_text(draw, '17 CRITERIOS · TARDE Y NOCHE', F_SUB, 212, W, 'white')

# ── 3 rows of 6 balls (simulating top-30 grid) ───────────────────
BALL_COLORS = [
    # row 1: top-10 → deep red
    [(180, 20, 20), (190, 25, 25), (200, 30, 20),
     (185, 28, 28), (175, 18, 18), (195, 32, 22)],
    # row 2: 11-20 → orange
    [(220, 90, 10), (225, 100, 15), (230, 105, 12),
     (215, 85, 10), (235, 110, 18), (210, 80, 8)],
    # row 3: 21-30 → amber
    [(200, 140, 10), (205, 145, 15), (210, 150, 12),
     (195, 135, 8),  (215, 155, 18), (200, 142, 10)],
]
BALL_NUMS = [
    ['88', '34', '50', '17', '06', '37'],
    ['24', '81', '13', '77', '92', '42'],
    ['55', '29', '68', '03', '71', '46'],
]

row_y    = [290, 350, 410]
spacing  = 74
start_x  = (W - 5 * spacing) // 2 + spacing // 2

for ri, (row_colors, row_nums, cy) in enumerate(zip(BALL_COLORS, BALL_NUMS, row_y)):
    for ci, (color, num) in enumerate(zip(row_colors, row_nums)):
        cx = start_x + ci * spacing - spacing // 2 + 10
        r  = 24 if ri == 0 else 21 if ri == 1 else 18
        ball(draw, cx, cy, r, color, num, F_BALL if ri == 0 else F_BALL_S)

# scattered accent balls
for cx, cy, r, c, lbl in [(35, 175, 14, (180,20,20), '05'),
                            (466, 170, 14, (220,90,10), '99'),
                            (30,  450, 13, (200,140,10),'62')]:
    ball(draw, cx, cy, r, c, lbl, F_BALL_S)

# bottom strip
rrect(draw, 0, H-50, W, H, 0, (185, 28, 28))
centered_text(draw, 'Pick 3 Florida · Análisis Predictivo', F_BOT, H-38, W, 'white')

img.save(os.path.join(OUT, 'numeros calientes.png'), 'PNG')
print('numeros calientes.png  OK')


# ══════════════════════════════════════════════════════════════════
# 2 – numeros frios.png   (ice: dark-navy → blue → light-blue)
# ══════════════════════════════════════════════════════════════════
img  = Image.new('RGB', (W, H))
draw = ImageDraw.Draw(img, 'RGBA')

gradient_bg(draw, W, H, (235, 245, 255), (210, 230, 255))

# deco blobs
draw.ellipse([-55, -55, 140, 140], fill=(30, 58, 95, 45))
draw.ellipse([W-130, H-130, W+60, H+60], fill=(29, 78, 216, 35))
draw.ellipse([W-70, -45, W+40, 85], fill=(147, 197, 253, 35))

# top badge
rrect(draw, 28, 20, W-28, 78, 16, (30, 58, 95))
centered_text(draw, '❄ NÚMEROS FRÍOS', F_BADGE, 35, W, 'white')

# titles
centered_text(draw, 'TOP 30', F_T1, 93, W, (15, 35, 75))
centered_text(draw, 'FRÍOS', F_T2, 142, W, (29, 78, 216))

# sub strip
rrect(draw, 65, 204, W-65, 238, 10, (29, 78, 216, 185))
centered_text(draw, '17 CRITERIOS · TARDE Y NOCHE', F_SUB, 212, W, 'white')

# ── 3 rows of 6 balls ─────────────────────────────────────────────
BALL_COLORS_F = [
    # row 1: top-10 → dark navy
    [(20, 40, 90), (25, 50, 100), (18, 45, 95),
     (22, 48, 98), (17, 38, 88), (24, 52, 102)],
    # row 2: 11-20 → medium blue
    [(29, 78, 216), (35, 85, 220), (28, 75, 210),
     (32, 82, 218), (26, 70, 205), (38, 90, 225)],
    # row 3: 21-30 → light blue (dark text handled separately)
    [(70, 130, 220), (80, 140, 225), (75, 135, 222),
     (65, 125, 218), (85, 145, 228), (72, 132, 221)],
]
BALL_NUMS_F = [
    ['11', '45', '23', '67', '89', '02'],
    ['56', '34', '78', '12', '90', '43'],
    ['66', '19', '52', '87', '31', '74'],
]

for ri, (row_colors, row_nums, cy) in enumerate(zip(BALL_COLORS_F, BALL_NUMS_F, row_y)):
    for ci, (color, num) in enumerate(zip(row_colors, row_nums)):
        cx = start_x + ci * spacing - spacing // 2 + 10
        r  = 24 if ri == 0 else 21 if ri == 1 else 18
        ball(draw, cx, cy, r, color, num, F_BALL if ri == 0 else F_BALL_S)

# scattered accent balls
for cx, cy, r, c, lbl in [(35, 175, 14, (20,40,90),  '08'),
                            (466, 170, 14, (29,78,216), '63'),
                            (30,  450, 13, (70,130,220),'91')]:
    ball(draw, cx, cy, r, c, lbl, F_BALL_S)

# snowflake dots accent
for i in range(6):
    angle = i * 60 * math.pi / 180
    cx = int(W//2 + 195 * math.cos(angle))
    cy = int(265 + 10 * math.sin(angle))
    if 0 < cx < W and 0 < cy < H:
        draw.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(147, 197, 253, 120))

# bottom strip
rrect(draw, 0, H-50, W, H, 0, (30, 58, 95))
centered_text(draw, 'Pick 3 Florida · Análisis Predictivo', F_BOT, H-38, W, 'white')

img.save(os.path.join(OUT, 'numeros frios.png'), 'PNG')
print('numeros frios.png  OK')
