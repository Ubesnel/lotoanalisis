# -*- coding: utf-8 -*-
from odoo import models, fields, api


def _default_sorteo(self):
    return self.env.ref('lottery_base.sorteo_florida', raise_if_not_found=False)


class LotteryCuriosity(models.Model):
    _name = 'lottery.curiosity'
    _description = 'Curiosidad (LotoAnálisis informa)'
    _order = 'date desc, id desc'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True, index=True,
        default=_default_sorteo,
        help='Sorteo/juego al que corresponde esta curiosidad.')
    date = fields.Date(
        string='Fecha publicación', required=True, index=True,
        default=lambda self: fields.Date.today(),
        help='Fecha de la curiosidad; la app la muestra como fecha de la noticia.')
    text = fields.Text(
        string='Noticia', required=True,
        help='Texto de la curiosidad/información que se muestra en la app.')
    text_en = fields.Text(
        string='Noticia (inglés)',
        help='Traducción al inglés de la noticia. Opcional: si se deja vacío, '
             'la app muestra el texto en español también a los usuarios en '
             'inglés (no queda ninguna noticia en blanco).')
    published = fields.Boolean(
        string='Publicado', default=False, index=True,
        help='Solo las curiosidades publicadas se envían a la app móvil '
             '(sección "LotoAnálisis informa"). Permite prepararlas con '
             'anticipación y publicarlas cuando estén listas.')

    @api.depends('date', 'text', 'sorteo_id.name')
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date.strftime('%d-%m-%Y') if rec.date else ''
            snippet = (rec.text or '').strip().replace('\n', ' ')
            if len(snippet) > 40:
                snippet = snippet[:40] + '…'
            rec.display_name = f"{date_str} / {snippet}"
