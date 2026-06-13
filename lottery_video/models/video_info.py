# -*- coding: utf-8 -*-
import base64
import io
import logging
import os
import tempfile
from datetime import date

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class LotteryVideoInfo(models.Model):
    _name = 'lottery.video.info'
    _description = 'Información para video de lotería'
    _order = 'date desc, id desc'

    name = fields.Char(string='Título', required=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.today)
    turno = fields.Selection([
        ('tarde', 'Tarde'),
        ('noche', 'Noche'),
    ], string='Turno', required=True, default='tarde')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('ready', 'Info obtenida'),
        ('video_ok', 'Video generado'),
    ], default='draft', string='Estado')

    # ─── Números más salidores (top 10) ──────────────────────────────────────
    salidores_general_ids = fields.Many2many(
        'lottery.number', 'lv_salidores_general_rel', 'info_id', 'number_id',
        string='Más salidores — General')
    salidores_tarde_ids = fields.Many2many(
        'lottery.number', 'lv_salidores_tarde_rel', 'info_id', 'number_id',
        string='Más salidores — Tarde')
    salidores_noche_ids = fields.Many2many(
        'lottery.number', 'lv_salidores_noche_rel', 'info_id', 'number_id',
        string='Más salidores — Noche')

    # ─── Atrasos Terminales (texto: "00-90, 01-91, ...") ─────────────────────
    terminal_general = fields.Text(string='Terminales atrasados — General')
    terminal_tarde = fields.Text(string='Terminales atrasados — Tarde')
    terminal_noche = fields.Text(string='Terminales atrasados — Noche')

    # ─── Atrasos Líneas (texto: "00-09, 10-19, ...") ─────────────────────────
    linea_general = fields.Text(string='Líneas atrasadas — General')
    linea_tarde = fields.Text(string='Líneas atrasadas — Tarde')
    linea_noche = fields.Text(string='Líneas atrasadas — Noche')

    # ─── Números más atrasados (top 10) ───────────────────────────────────────
    atrasado_general_ids = fields.Many2many(
        'lottery.number', 'lv_atrasado_general_rel', 'info_id', 'number_id',
        string='Más atrasados — General')
    atrasado_tarde_ids = fields.Many2many(
        'lottery.number', 'lv_atrasado_tarde_rel', 'info_id', 'number_id',
        string='Más atrasados — Tarde')
    atrasado_noche_ids = fields.Many2many(
        'lottery.number', 'lv_atrasado_noche_rel', 'info_id', 'number_id',
        string='Más atrasados — Noche')

    # ─── 4 Centenas más atrasadas ─────────────────────────────────────────────
    centena_general_ids = fields.Many2many(
        'lottery.number', 'lv_centena_general_rel', 'info_id', 'number_id',
        string='Centenas atrasadas — General')
    centena_tarde_ids = fields.Many2many(
        'lottery.number', 'lv_centena_tarde_rel', 'info_id', 'number_id',
        string='Centenas atrasadas — Tarde')
    centena_noche_ids = fields.Many2many(
        'lottery.number', 'lv_centena_noche_rel', 'info_id', 'number_id',
        string='Centenas atrasadas — Noche')

    # ─── 4 Bolas Extra más atrasadas ─────────────────────────────────────────
    bola_extra_general_ids = fields.Many2many(
        'lottery.number', 'lv_bola_extra_general_rel', 'info_id', 'number_id',
        string='Bola Extra atrasada — General')
    bola_extra_tarde_ids = fields.Many2many(
        'lottery.number', 'lv_bola_extra_tarde_rel', 'info_id', 'number_id',
        string='Bola Extra atrasada — Tarde')
    bola_extra_noche_ids = fields.Many2many(
        'lottery.number', 'lv_bola_extra_noche_rel', 'info_id', 'number_id',
        string='Bola Extra atrasada — Noche')

    # ─── Top 3 Grupos más atrasados ───────────────────────────────────────────
    grupo_general_ids = fields.Many2many(
        'lottery.group', 'lv_grupo_general_rel', 'info_id', 'group_id',
        string='Grupos atrasados — General')
    grupo_tarde_ids = fields.Many2many(
        'lottery.group', 'lv_grupo_tarde_rel', 'info_id', 'group_id',
        string='Grupos atrasados — Tarde')
    grupo_noche_ids = fields.Many2many(
        'lottery.group', 'lv_grupo_noche_rel', 'info_id', 'group_id',
        string='Grupos atrasados — Noche')

    # ─── Top 3 Pintas más atrasadas ───────────────────────────────────────────
    pinta_general_ids = fields.Many2many(
        'lottery.group', 'lv_pinta_general_rel', 'info_id', 'group_id',
        string='Pintas atrasadas — General')
    pinta_tarde_ids = fields.Many2many(
        'lottery.group', 'lv_pinta_tarde_rel', 'info_id', 'group_id',
        string='Pintas atrasadas — Tarde')
    pinta_noche_ids = fields.Many2many(
        'lottery.group', 'lv_pinta_noche_rel', 'info_id', 'group_id',
        string='Pintas atrasadas — Noche')

    # ─── 30 Números calientes ─────────────────────────────────────────────────
    caliente_tarde_ids = fields.Many2many(
        'lottery.number', 'lv_caliente_tarde_rel', 'info_id', 'number_id',
        string='Calientes — Tarde')
    caliente_noche_ids = fields.Many2many(
        'lottery.number', 'lv_caliente_noche_rel', 'info_id', 'number_id',
        string='Calientes — Noche')

    # ─── Guión ────────────────────────────────────────────────────────────────
    script_line_ids = fields.One2many(
        'lottery.video.script.line', 'video_info_id', string='Guión')

    # ─── Video ────────────────────────────────────────────────────────────────
    video_file = fields.Binary(string='Video', attachment=True)
    video_filename = fields.Char(default='video_loteria.mp4')

    # ─── Acción: Obtener información ──────────────────────────────────────────

    def action_get_info(self):
        self.ensure_one()
        svc = self.env['lottery.stats.service'].sudo()
        today_str = str(self.date or date.today())

        def _num_ids_ordered(dicts):
            """Convierte lista [{name: '07', ...}] a IDs de lottery.number respetando orden."""
            result = []
            for d in dicts:
                raw = d.get('name')
                if raw is None:
                    continue
                try:
                    rec = self.env['lottery.number'].sudo().search(
                        [('name', '=', int(raw))], limit=1)
                    if rec:
                        result.append(rec.id)
                except (ValueError, TypeError):
                    pass
            return result

        def _ceb_ids_ordered(dicts, key='centena'):
            """Convierte lista [{centena: '3', ...}] a IDs de lottery.number."""
            result = []
            for d in dicts:
                raw = d.get(key)
                if raw is None:
                    continue
                try:
                    rec = self.env['lottery.number'].sudo().search(
                        [('name', '=', int(raw))], limit=1)
                    if rec:
                        result.append(rec.id)
                except (ValueError, TypeError):
                    pass
            return result

        def _group_ids_by_codes(codes):
            result = []
            for code in codes:
                g = self.env['lottery.group'].sudo().search(
                    [('code', '=', code)], limit=1)
                if g:
                    result.append(g.id)
            return result

        # Números más salidores (top 10)
        top_gen = svc.get_top_10_general()[:10]
        top_tarde = svc.get_top_10_dia()[:10]
        top_noche = svc.get_top_10_noche()[:10]

        def _names_text(groups):
            return ', '.join(g['name'] for g in groups if g.get('name'))

        # Números más atrasados (top 10)
        LN = self.env['lottery.number'].sudo()
        atrasado_gen = LN.search([], order='total_atrasadas desc', limit=10).ids
        atrasado_tarde = LN.search([], order='total_atrasadas_dia desc', limit=10).ids
        atrasado_noche = LN.search([], order='total_atrasadas_noche desc', limit=10).ids

        # Centenas más atrasadas (top 4)
        cen_gen = _ceb_ids_ordered(svc.get_top5_centenas_general()[:4])
        cen_tarde = _ceb_ids_ordered(svc.get_top5_centenas_afternoon()[:4])
        cen_noche = _ceb_ids_ordered(svc.get_top5_centenas_evening()[:4])

        # Bola extra más atrasada (top 4)
        be_gen = _ceb_ids_ordered(svc.get_top5_bola_extra_general()[:4])
        be_tarde = _ceb_ids_ordered(svc.get_top5_bola_extra_afternoon()[:4])
        be_noche = _ceb_ids_ordered(svc.get_top5_bola_extra_evening()[:4])

        # Día de semana para coincidir exactamente con los crons de artículos
        _WCODE = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}
        wcode = _WCODE[(self.date or date.today()).weekday()]

        # Terminales y líneas: top 3 por turno, igual que cron_generate_grupos_dia_semana
        lt_data = svc.get_lineas_terminales_dia_semana(wcode, top_n=3)
        term_gen   = _names_text(lt_data.get('terminales', {}).get('general',   []))
        term_tarde = _names_text(lt_data.get('terminales', {}).get('afternoon', []))
        term_noche = _names_text(lt_data.get('terminales', {}).get('evening',   []))
        linea_gen   = _names_text(lt_data.get('lineas', {}).get('general',   []))
        linea_tarde = _names_text(lt_data.get('lineas', {}).get('afternoon', []))
        linea_noche = _names_text(lt_data.get('lineas', {}).get('evening',   []))

        grupo_gen   = [g['id'] for g in svc.get_top_6_groups('general',   wcode)[:3]]
        grupo_tarde = [g['id'] for g in svc.get_top_6_groups('afternoon', wcode)[:3]]
        grupo_noche = [g['id'] for g in svc.get_top_6_groups('evening',   wcode)[:3]]
        pinta_gen   = [g['id'] for g in svc.get_top_3_pintas('general',   wcode)[:2]]
        pinta_tarde = [g['id'] for g in svc.get_top_3_pintas('afternoon', wcode)[:2]]
        pinta_noche = [g['id'] for g in svc.get_top_3_pintas('evening',   wcode)[:2]]

        # Calientes (30 números) — solo el turno seleccionado
        calientes_data = svc.get_calientes_all(today_str)
        api_turno = 'afternoon' if self.turno == 'tarde' else 'evening'
        cal_ids = _num_ids_ordered(calientes_data.get(api_turno, {}).get('numbers', [])[:30])
        cal_tarde = cal_ids if self.turno == 'tarde' else []
        cal_noche = cal_ids if self.turno == 'noche' else []

        self.write({
            'salidores_general_ids': [(6, 0, _num_ids_ordered(top_gen))],
            'salidores_tarde_ids':   [(6, 0, _num_ids_ordered(top_tarde))],
            'salidores_noche_ids':   [(6, 0, _num_ids_ordered(top_noche))],
            'terminal_general':      term_gen,
            'terminal_tarde':        term_tarde,
            'terminal_noche':        term_noche,
            'linea_general':         linea_gen,
            'linea_tarde':           linea_tarde,
            'linea_noche':           linea_noche,
            'atrasado_general_ids':  [(6, 0, atrasado_gen)],
            'atrasado_tarde_ids':    [(6, 0, atrasado_tarde)],
            'atrasado_noche_ids':    [(6, 0, atrasado_noche)],
            'centena_general_ids':   [(6, 0, cen_gen)],
            'centena_tarde_ids':     [(6, 0, cen_tarde)],
            'centena_noche_ids':     [(6, 0, cen_noche)],
            'bola_extra_general_ids': [(6, 0, be_gen)],
            'bola_extra_tarde_ids':   [(6, 0, be_tarde)],
            'bola_extra_noche_ids':   [(6, 0, be_noche)],
            'grupo_general_ids':     [(6, 0, grupo_gen)],
            'grupo_tarde_ids':       [(6, 0, grupo_tarde)],
            'grupo_noche_ids':       [(6, 0, grupo_noche)],
            'pinta_general_ids':     [(6, 0, pinta_gen)],
            'pinta_tarde_ids':       [(6, 0, pinta_tarde)],
            'pinta_noche_ids':       [(6, 0, pinta_noche)],
            'caliente_tarde_ids':    [(6, 0, cal_tarde)],
            'caliente_noche_ids':    [(6, 0, cal_noche)],
            'state': 'ready',
            'video_file': False,
            'video_filename': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ─── Acción: Generar Guión ───────────────────────────────────────────────

    def action_generate_script(self):
        self.ensure_one()
        if self.state == 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'message': 'Primero obtén la información del video.',
                           'type': 'warning', 'sticky': False},
            }

        def _num_names(records, limit=10):
            recs = records if limit is None else records[:limit]
            return ', '.join(str(r.name).zfill(2) for r in recs)

        def _group_names(records, limit=3):
            return ', '.join(r.name for r in records[:limit])

        fecha = str(self.date or date.today())

        lines = [
            # ── Intro ────────────────────────────────────────────────────────
            (10, 'valeria',
             '¡Hola a todos! Bienvenidos al análisis del Pick 3 Florida del %s.' % fecha),
            (20, 'mateo',
             '¡Hola Valeria! Hoy tenemos mucha información interesante para los jugadores.'),

            # ── Salidores ────────────────────────────────────────────────────
            (30, 'valeria',
             '¿Cuáles son los números que más han salido hoy en general?'),
            (40, 'mateo',
             'Los 10 más salidores en general son: %s.' % _num_names(self.salidores_general_ids)),
            (50, 'valeria',
             '¿Y por turno?'),
            (60, 'mateo',
             'En el turno de tarde: %s. Y en noche: %s.' % (
                 _num_names(self.salidores_tarde_ids),
                 _num_names(self.salidores_noche_ids))),

            # ── Atrasados ────────────────────────────────────────────────────
            (70, 'valeria',
             '¿Qué números llevan más tiempo sin salir?'),
            (80, 'mateo',
             'Los más atrasados en general son: %s.' % _num_names(self.atrasado_general_ids)),
            (90, 'valeria',
             '¿Hay diferencia entre tarde y noche?'),
            (100, 'mateo',
             'Sí. En tarde los más atrasados son %s, y en noche %s.' % (
                 _num_names(self.atrasado_tarde_ids),
                 _num_names(self.atrasado_noche_ids))),

            # ── Terminales y Líneas ───────────────────────────────────────────
            (110, 'valeria',
             '¿Qué terminales están más atrasados?'),
            (120, 'mateo',
             'Los terminales más atrasados en general son: %s.' % (self.terminal_general or 'N/D')),
            (130, 'valeria',
             '¿Y las líneas?'),
            (140, 'mateo',
             'Las líneas más atrasadas en general son: %s.' % (self.linea_general or 'N/D')),

            # ── Centenas y Bola Extra ─────────────────────────────────────────
            (150, 'valeria',
             '¿Cuáles son las centenas más atrasadas?'),
            (160, 'mateo',
             'Las 4 centenas más atrasadas en general son: %s.' % _num_names(self.centena_general_ids, 4)),
            (170, 'valeria',
             '¿Y la bola extra?'),
            (180, 'mateo',
             'Las bolas extra más atrasadas son: %s en general.' % _num_names(self.bola_extra_general_ids, 4)),

            # ── Grupos y Pintas ───────────────────────────────────────────────
            (190, 'valeria',
             '¿Qué grupos están más atrasados?'),
            (200, 'mateo',
             'Los top 3 grupos más atrasados en general son: %s.' % _group_names(self.grupo_general_ids)),
            (210, 'valeria',
             '¿Y las pintas?'),
            (220, 'mateo',
             'Las pintas más atrasadas son: %s.' % _group_names(self.pinta_general_ids)),

            # ── Calientes ─────────────────────────────────────────────────────
            (230, 'valeria',
             '¿Cuáles son los números más calientes para hoy?'),
            (240, 'mateo',
             'Los %d más calientes para el turno de %s son: %s.' % (
                 len(self.caliente_tarde_ids or self.caliente_noche_ids),
                 'tarde' if self.turno == 'tarde' else 'noche',
                 _num_names(self.caliente_tarde_ids or self.caliente_noche_ids,
                            limit=len(self.caliente_tarde_ids or self.caliente_noche_ids)))),

            # ── Cierre ────────────────────────────────────────────────────────
            (270, 'valeria',
             '¡Excelente análisis Mateo! Recuerden que esto es solo un análisis estadístico.'),
            (280, 'mateo',
             '¡Así es! Jueguen con responsabilidad. ¡Buena suerte a todos!'),
        ]

        # Elimina líneas anteriores y crea las nuevas
        self.script_line_ids.unlink()
        for seq, char, text in lines:
            self.env['lottery.video.script.line'].create({
                'video_info_id': self.id,
                'sequence': seq,
                'character': char,
                'text': text,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ─── Acción: Descargar Video ──────────────────────────────────────────────

    def action_download_video(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/video_file/%s?download=true' % (
                self._name, self.id, self.video_filename or 'video.mp4'),
            'target': 'self',
        }

    # ─── Acción: Generar Video ────────────────────────────────────────────────

    def action_generate_video(self):
        self.ensure_one()
        if self.state == 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Primero obtén la información del video.',
                    'type': 'warning', 'sticky': False,
                },
            }

        try:
            video_bytes = self._build_video()
        except Exception as e:
            _logger.error('action_generate_video: %s', e, exc_info=True)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error al generar el video: %s' % str(e),
                    'type': 'danger', 'sticky': True,
                },
            }

        filename = 'loteria_%s.mp4' % str(self.date or date.today()).replace('-', '')
        self.write({
            'video_file': base64.b64encode(video_bytes),
            'video_filename': filename,
            'state': 'video_ok',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ─── Construcción del video ───────────────────────────────────────────────

    def _build_video(self):
        """Genera el video como bytes MP4 usando moviepy + Pillow."""
        try:
            from moviepy.editor import ImageClip, concatenate_videoclips
        except ImportError as e:
            raise ImportError('Instala moviepy: pip install "moviepy<2.0". Detalle: %s' % e)
        try:
            from PIL import Image
        except ImportError as e:
            raise ImportError('Instala Pillow: pip install Pillow. Detalle: %s' % e)

        cfg = self.env['lottery.video.config']._get_config()
        W = cfg.video_width or 1080
        H = cfg.video_height or 1920
        FPS = cfg.video_fps or 24
        bg_color = self._hex_to_rgb(cfg.bg_color_hex or '#0d1b2a')
        accent_color = self._hex_to_rgb(cfg.accent_color_hex or '#f5c518')

        mateo_pil = self._load_character_image(cfg.mateo_image, W // 2, H // 3)
        valeria_pil = self._load_character_image(cfg.valeria_image, W // 2, H // 3)
        _logger.info('Personajes cargados — Mateo: %s, Valeria: %s',
                     mateo_pil.size if mateo_pil else 'NO CARGADO',
                     valeria_pil.size if valeria_pil else 'NO CARGADO')

        slides = self._build_slides(W, H, bg_color, accent_color, mateo_pil, valeria_pil)

        import numpy as np
        import shutil

        tmp_dir = tempfile.mkdtemp()
        try:
            clips = []
            for idx, (frame_pil, duration) in enumerate(slides):
                try:
                    frame_rgb = frame_pil.convert('RGB')
                    w, h = frame_rgb.size
                    arr = np.frombuffer(frame_rgb.tobytes(), dtype=np.uint8).reshape(h, w, 3)
                    clips.append(ImageClip(arr).set_duration(duration))
                except Exception as slide_err:
                    raise RuntimeError('Error en slide %d (tipo=%s, size=%s): %s' % (
                        idx, type(frame_pil), getattr(frame_pil, 'size', '?'), slide_err
                    )) from slide_err

            video = concatenate_videoclips(clips, method='compose')
            tmp_out = os.path.join(tmp_dir, 'output.mp4')
            video.write_videofile(
                tmp_out, fps=FPS, codec='libx264', audio=False,
                logger=None, verbose=False,
            )
            video.close()
            with open(tmp_out, 'rb') as f:
                return f.read()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _build_slides(self, W, H, bg_color, accent_color, mateo_pil, valeria_pil):
        """Genera slides de diálogo: una línea del guión por slide."""
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        fecha_str = str(self.date or date.today())

        # ── Colores por personaje ─────────────────────────────────────────────
        VALERIA_COLOR   = (255, 200, 60)    # amarillo
        MATEO_COLOR     = (80, 160, 255)    # azul
        BUBBLE_VALERIA  = (40, 30, 10)      # fondo burbuja Valeria
        BUBBLE_MATEO    = (10, 25, 50)      # fondo burbuja Mateo
        CHAR_H = int(H * 0.42)             # altura máxima del personaje
        CHAR_W = int(W * 0.46)
        BUBBLE_Y_TOP = 80                  # donde empieza la burbuja
        BUBBLE_MARGIN = 50
        CHAR_BOTTOM_MARGIN = 20

        def _font(size):
            for name in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans.ttf'):
                try:
                    return ImageFont.truetype(name, size)
                except Exception:
                    pass
            return ImageFont.load_default()

        def _gradient_bg():
            """Fondo con degradado vertical oscuro."""
            img = Image.new('RGB', (W, H), bg_color)
            draw = ImageDraw.Draw(img)
            # degradado simple: lineas horizontales de oscuro a ligeramente más claro
            r0, g0, b0 = bg_color
            r1, g1, b1 = min(r0 + 30, 255), min(g0 + 30, 255), min(b0 + 30, 255)
            for y in range(H):
                t = y / H
                r = int(r0 + (r1 - r0) * t)
                g = int(g0 + (g1 - g0) * t)
                b = int(b0 + (b1 - b0) * t)
                draw.line([(0, y), (W, y)], fill=(r, g, b))
            # banda superior acento
            draw.rectangle([(0, 0), (W, 8)], fill=accent_color)
            draw.rectangle([(0, H - 8), (W, H)], fill=accent_color)
            return img

        def _paste_character(img, char_img, side, alpha=255):
            """Pega personaje: side='left' o 'right'. alpha para atenuar."""
            if not char_img:
                return
            ch = char_img.copy()
            if alpha < 255:
                r, g, b, a = ch.split()
                a = a.point(lambda x: int(x * alpha / 255))
                ch = Image.merge('RGBA', (r, g, b, a))
            x = 0 if side == 'left' else W - ch.width
            y = H - ch.height - CHAR_BOTTOM_MARGIN
            img.paste(ch, (x, y), ch)

        def _bubble(draw, text, side, color_border, color_bg, font_size=34):
            """Dibuja burbuja de diálogo con texto envuelto."""
            fnt = _font(font_size)
            max_chars = 28
            lines = textwrap.wrap(text, width=max_chars)
            line_h = font_size + 10
            bw = W - BUBBLE_MARGIN * 2 - CHAR_W // 2
            bh = len(lines) * line_h + 40
            if side == 'left':   # Valeria habla → burbuja a la derecha
                bx = CHAR_W // 2 + 20
            else:                # Mateo habla → burbuja a la izquierda
                bx = BUBBLE_MARGIN
            by = BUBBLE_Y_TOP
            # sombra
            draw.rounded_rectangle(
                [(bx + 4, by + 4), (bx + bw + 4, by + bh + 4)],
                radius=20, fill=(0, 0, 0, 120))
            # fondo burbuja
            draw.rounded_rectangle(
                [(bx, by), (bx + bw, by + bh)],
                radius=20, fill=color_bg, outline=color_border, width=3)
            # puntero de burbuja
            tip_x = bx - 18 if side == 'right' else bx + bw + 18
            tip_y = by + bh // 2
            draw.polygon([
                (bx if side == 'right' else bx + bw, tip_y - 12),
                (tip_x, tip_y),
                (bx if side == 'right' else bx + bw, tip_y + 12),
            ], fill=color_bg)
            # texto
            ty = by + 20
            for line in lines:
                tb = draw.textbbox((0, 0), line, font=fnt)
                tx = bx + (bw - (tb[2] - tb[0])) // 2
                draw.text((tx, ty), line, font=fnt, fill=(255, 255, 255))
                ty += line_h
            return by + bh

        def _name_badge(draw, name, side, color):
            fnt = _font(28)
            tb = draw.textbbox((0, 0), name, font=fnt)
            bw = tb[2] - tb[0] + 30
            bh = 44
            if side == 'left':
                bx = 20
            else:
                bx = W - bw - 20
            by = H - CHAR_H - CHAR_BOTTOM_MARGIN - 60
            draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=12, fill=color)
            draw.text((bx + 15, by + (bh - (tb[3] - tb[1])) // 2), name, font=fnt,
                      fill=(10, 10, 10))

        def _header(draw, fecha):
            fnt = _font(26)
            tb = draw.textbbox((0, 0), 'PICK 3 FLORIDA · %s' % fecha, font=fnt)
            x = (W - (tb[2] - tb[0])) // 2
            draw.text((x, 18), 'PICK 3 FLORIDA · %s' % fecha, font=fnt,
                      fill=(200, 200, 200))

        def _make_dialogue_slide(char, text):
            img = _gradient_bg()
            draw = ImageDraw.Draw(img, 'RGBA')
            _header(draw, fecha_str)

            if char == 'valeria':
                # Valeria activa izquierda, Mateo atenuado derecha
                _paste_character(img, valeria_pil, 'left', alpha=255)
                _paste_character(img, mateo_pil,   'right', alpha=80)
                _bubble(draw, text, side='left',
                        color_border=VALERIA_COLOR, color_bg=BUBBLE_VALERIA)
                _name_badge(draw, 'Valeria', 'left', VALERIA_COLOR)
            else:
                # Mateo activo derecha, Valeria atenuada izquierda
                _paste_character(img, valeria_pil, 'left', alpha=80)
                _paste_character(img, mateo_pil,   'right', alpha=255)
                _bubble(draw, text, side='right',
                        color_border=MATEO_COLOR, color_bg=BUBBLE_MATEO)
                _name_badge(draw, 'Mateo', 'right', MATEO_COLOR)

            return img

        def _make_intro_slide():
            img = _gradient_bg()
            draw = ImageDraw.Draw(img)
            _header(draw, fecha_str)
            fnt_title = _font(64)
            fnt_sub = _font(36)
            tb = draw.textbbox((0, 0), 'PICK 3 FLORIDA', font=fnt_title)
            x = (W - (tb[2] - tb[0])) // 2
            draw.text((x, 200), 'PICK 3 FLORIDA', font=fnt_title, fill=accent_color)
            tb2 = draw.textbbox((0, 0), 'Análisis del día', font=fnt_sub)
            x2 = (W - (tb2[2] - tb2[0])) // 2
            draw.text((x2, 300), 'Análisis del día', font=fnt_sub, fill=(220, 220, 220))
            _paste_character(img, valeria_pil, 'left',  alpha=255)
            _paste_character(img, mateo_pil,   'right', alpha=255)
            return img

        slides = []

        # Portada con ambos personajes
        slides.append((_make_intro_slide(), 3))

        # Una slide por línea del guión
        script_lines = self.script_line_ids.sorted('sequence')
        if not script_lines:
            # Si no hay guión, slide de aviso
            img = _gradient_bg()
            draw = ImageDraw.Draw(img)
            fnt = _font(36)
            draw.text((80, H // 2 - 40),
                      'Sin guión. Usa "Generar Guión".', font=fnt, fill=(255, 80, 80))
            slides.append((img, 4))
        else:
            for line in script_lines:
                duration = max(3, len(line.text) // 12)  # ~12 chars/seg
                duration = min(duration, 8)
                slides.append((_make_dialogue_slide(line.character, line.text), duration))

        return slides

    # ─── Utilidades ───────────────────────────────────────────────────────────

    @staticmethod
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _load_character_image(binary_field, max_w, max_h):
        if not binary_field:
            _logger.warning('_load_character_image: campo vacío (False/None)')
            return None
        try:
            from PIL import Image
            # Odoo ORM devuelve Binary como bytes base64-encoded
            raw = binary_field
            if isinstance(raw, str):
                raw = raw.encode('ascii')
            _logger.info('_load_character_image: tipo=%s len=%d', type(raw).__name__, len(raw))
            data = base64.b64decode(raw)
            _logger.info('_load_character_image: decoded %d bytes', len(data))
            img = Image.open(io.BytesIO(data))
            img.load()
            img = img.convert('RGBA')
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            _logger.info('_load_character_image: OK size=%s', img.size)
            return img
        except Exception as e:
            _logger.warning('_load_character_image: falló — %s', e, exc_info=True)
            return None
