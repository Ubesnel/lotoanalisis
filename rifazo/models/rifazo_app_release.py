# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RifazoAppRelease(models.Model):
    """Versión de la APK de Rifazo que se descarga desde la web (/rifazo).
    La que se ofrece es la publicada con el número de build más alto."""
    _name = 'rifazo.app.release'
    _description = 'Versión de la app Rifazo'
    _order = 'version_code desc, id desc'

    name = fields.Char('Versión', required=True, help='Como la ve la gente. Ej: 1.0.0')
    version_code = fields.Integer(
        'Número de build', required=True,
        help='El versionCode de Android (el número después del "+" en pubspec.yaml). '
             'Tiene que crecer en cada versión.')
    apk_file = fields.Binary('Archivo APK', attachment=True, required=True)
    apk_filename = fields.Char('Nombre del archivo')
    release_notes = fields.Text('Novedades', help='Se muestran en la página de descarga.')
    published = fields.Boolean(
        'Publicada', default=True,
        help='Solo las versiones publicadas se ofrecen para descargar.')
    release_date = fields.Datetime('Fecha', default=fields.Datetime.now, required=True)
    download_count = fields.Integer('Descargas', readonly=True, copy=False)
    file_size = fields.Integer('Tamaño (bytes)', compute='_compute_file_size')
    file_size_label = fields.Char('Tamaño', compute='_compute_file_size')

    _sql_constraints = [
        ('version_code_uniq', 'unique(version_code)', 'Ya existe una versión con ese número de build.'),
    ]

    @api.depends('apk_file')
    def _compute_file_size(self):
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name),
            ('res_field', '=', 'apk_file'),
            ('res_id', 'in', self.ids),
        ])
        sizes = {a.res_id: a.file_size for a in attachments}
        for rec in self:
            size = sizes.get(rec.id, 0)
            rec.file_size = size
            rec.file_size_label = ('%.1f MB' % (size / 1024 / 1024)) if size else ''

    @api.constrains('apk_filename')
    def _check_apk_filename(self):
        for rec in self:
            if rec.apk_filename and not rec.apk_filename.lower().endswith('.apk'):
                raise ValidationError(_('El archivo tiene que ser un .apk.'))

    @api.model
    def _get_current(self):
        """Versión que se ofrece para descargar."""
        return self.sudo().search([('published', '=', True)], limit=1)

    def _download_filename(self):
        self.ensure_one()
        return 'Rifazo-%s.apk' % self.name.strip().replace(' ', '-')
