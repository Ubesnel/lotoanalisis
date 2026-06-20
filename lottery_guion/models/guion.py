# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api

from .guion_comentario import TIPO_GUION


class LotteryGuion(models.Model):
    _name = 'lottery.guion'
    _description = 'Guión de lotería'
    _order = 'fecha desc, id desc'

    tipo_guion = fields.Selection(
        TIPO_GUION, string='Tipo de Guión', required=True)
    fecha = fields.Date(string='Fecha', required=True, default=fields.Date.today)
    line_ids = fields.One2many(
        'lottery.guion.line', 'guion_id', string='Líneas de Guión')

    @api.onchange('tipo_guion')
    def _onchange_tipo_guion(self):
        for guion in self:
            lines = []
            comentarios = self.env['lottery.guion.comentario'].search(
                [('tipo_guion', '=', guion.tipo_guion)], order='sequence')
            for comentario in comentarios:
                lines.append((0, 0, {
                    'sequence': comentario.sequence,
                    'comentario_id': comentario.id,
                    'texto_final': comentario.comentario,
                }))
            guion.line_ids = lines

    def action_download_guion(self):
        self.ensure_one()
        content = '\n'.join(
            '%s|%s' % (dict(line._fields['personaje'].selection).get(line.personaje, ''),
                        line.texto_final or '')
            for line in self.line_ids.sorted('sequence')
        )
        attachment = self.env['ir.attachment'].create({
            'name': 'guion_%s.txt' % (self.fecha or fields.Date.today()),
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
