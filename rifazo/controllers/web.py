# -*- coding: utf-8 -*-
"""Página pública de descarga de la APK (/rifazo) y descarga directa.

La APK se distribuye fuera de Google Play, así que la página además explica
cómo instalar una app de "origen desconocido" en Android."""

from odoo import http
from odoo.http import request

APK_MIMETYPE = 'application/vnd.android.package-archive'


class RifazoWeb(http.Controller):

    @http.route('/rifazo', type='http', auth='public', methods=['GET'])
    def download_page(self, **kwargs):
        release = request.env['rifazo.app.release']._get_current()
        open_count = request.env['rifazo.raffle'].sudo().search_count([('state', '=', 'open')])
        return request.render('rifazo.download_page', {
            'release': release,
            'open_count': open_count,
        })

    @http.route('/rifazo/descargar', type='http', auth='public', methods=['GET'])
    def download_apk(self, **kwargs):
        release = request.env['rifazo.app.release']._get_current()
        if not release:
            return request.redirect('/rifazo')
        # Contador por SQL: no toca write_date ni compite con otras descargas.
        request.env.cr.execute(
            'UPDATE rifazo_app_release SET download_count = download_count + 1 WHERE id = %s',
            (release.id,))
        stream = request.env['ir.binary']._get_stream_from(
            release, 'apk_file', filename=release._download_filename(), mimetype=APK_MIMETYPE)
        return stream.get_response(as_attachment=True)

    @http.route('/api/rifazo/v1/app/latest', type='http', auth='public',
                methods=['GET'], csrf=False, cors='*')
    def latest_release(self, **kwargs):
        """Para que la app avise "hay una versión nueva" (compara version_code)."""
        release = request.env['rifazo.app.release']._get_current()
        payload = None
        if release:
            payload = {
                'version': release.name,
                'version_code': release.version_code,
                'release_notes': release.release_notes or '',
                'download_url': '/rifazo/descargar',
            }
        return request.make_json_response({'latest': payload})
