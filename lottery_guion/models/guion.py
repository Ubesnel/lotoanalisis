# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api

from .guion_comentario import TIPO_GUION, PERSONAJE


class LotteryGuion(models.Model):
    _name = 'lottery.guion'
    _description = 'Guión de lotería'
    _order = 'fecha desc, id desc'
    _rec_name = 'fecha'

    tipo_guion = fields.Selection(
        TIPO_GUION, string='Tipo de Guión', required=True)
    fecha = fields.Date(string='Fecha', required=True, default=fields.Date.today)
    intro_line_ids = fields.One2many(
        'lottery.guion.intro.line', 'guion_id', string='Líneas de Introducción',
        default=lambda self: self._default_intro_lines())
    line_ids = fields.One2many(
        'lottery.guion.line', 'guion_id', string='Líneas de Desarrollo')
    final_line_ids = fields.One2many(
        'lottery.guion.final.line', 'guion_id', string='Líneas de Final',
        default=lambda self: self._default_final_lines())

    def _default_intro_lines(self):
        commands = [(5, 0, 0)]
        comentarios = self.env['lottery.guion.comentario.intro'].search([], order='sequence')
        for comentario in comentarios:
            commands.append((0, 0, {
                'sequence': comentario.sequence,
                'personaje': comentario.personaje,
                'comentario_id': comentario.id,
                'texto_final': comentario.comentario,
            }))
        return commands

    def _default_final_lines(self):
        commands = [(5, 0, 0)]
        comentarios = self.env['lottery.guion.comentario.final'].search([], order='sequence')
        for comentario in comentarios:
            commands.append((0, 0, {
                'sequence': comentario.sequence,
                'personaje': comentario.personaje,
                'comentario_id': comentario.id,
                'texto_final': comentario.comentario,
            }))
        return commands

    @api.onchange('tipo_guion')
    def _onchange_tipo_guion(self):
        for guion in self:
            lines = [(5, 0, 0)]
            comentarios = self.env['lottery.guion.comentario'].search(
                [('tipo_guion', '=', guion.tipo_guion)], order='sequence')
            for comentario in comentarios:
                lines.append((0, 0, {
                    'sequence': comentario.sequence,
                    'personaje': comentario.personaje,
                    'comentario_id': comentario.id,
                    'texto_final': comentario.comentario,
                }))
            guion.line_ids = lines

    def action_download_guion(self):
        self.ensure_one()
        personaje_labels = dict(PERSONAJE)

        def _line_text(line):
            return '%s|%s' % (
                personaje_labels.get(line.personaje, ''),
                line.texto_final or '',
            )

        lines = []
        lines.extend(_line_text(l) for l in self.intro_line_ids.sorted('sequence'))
        lines.extend(_line_text(l) for l in self.line_ids.sorted('sequence'))
        lines.extend(_line_text(l) for l in self.final_line_ids.sorted('sequence'))
        content = '\n'.join(lines)

        attachment = self.env['ir.attachment'].create({
            'name': 'guion_%s.txt' % (self.fecha or fields.Date.today()),
            'type': 'binary',
            'datas': base64.b64encode(content.encode('cp1252')),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
