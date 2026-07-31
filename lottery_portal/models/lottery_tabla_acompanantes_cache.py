# -*- coding: utf-8 -*-
"""Cache persistente de la Tabla LotoAnálisis: para un (sorteo, fecha de
corte) el resultado nunca cambia — la historia hasta esa fecha ya pasó y
no se altera con salidas futuras — así que una vez calculada se reutiliza
en vez de recalcularla cada vez que se vuelve a pedir la misma combinación.
"""
import json

from odoo import api, fields, models

from .tabla_acompanantes_grid import build_grid


class LotteryTablaAcompanantesCache(models.Model):
    _name = 'lottery.tabla.acompanantes.cache'
    _description = 'Cache de Tabla LotoAnálisis por sorteo y fecha de corte'

    sorteo_id = fields.Many2one('lottery.sorteo', required=True, index=True)
    fecha_corte = fields.Date(required=True, index=True)
    # required + default 'general' (nunca False/NULL): un unique() de
    # Postgres no considera iguales dos NULL, así que si "General" se
    # guardara como NULL la restricción de abajo no evitaría duplicados.
    turno = fields.Selection([
        ('general', 'General'), ('afternoon', 'Tarde'), ('evening', 'Noche'),
    ], string='Turno', required=True, default='general')
    # required, nunca False/NULL, por la misma razón que turno (ver nota
    # de más abajo sobre la unique constraint).
    grid_size = fields.Selection([
        ('11', '11 × 11'), ('12', '12 × 12'),
    ], string='Tamaño de grilla', required=True, default='12')
    grid_json = fields.Text(required=True)
    png_attachment_id = fields.Many2one('ir.attachment')

    # OJO: mantener siempre el mismo nombre 'unique_sorteo_fecha' aunque se
    # le agreguen columnas — Odoo solo detecta y reemplaza una constraint
    # existente si el nombre coincide; si se le pone un nombre nuevo, la
    # vieja queda huérfana en la base y sigue bloqueando (pasó justo eso
    # al agregar turno).
    _sql_constraints = [
        ('unique_sorteo_fecha',
         'unique(sorteo_id, fecha_corte, turno, grid_size)',
         'Ya existe una Tabla LotoAnálisis calculada para ese sorteo, esa '
         'fecha de corte, ese turno y ese tamaño de grilla.'),
    ]

    @api.model
    def get_grid(self, sorteo_id, fecha_corte, turno='general', grid_size='12'):
        """Grilla {(fila, col): numero} para la combinación pedida, usando la
        caché o calculándola y guardándola. Reutilizable por el wizard y por
        el endpoint REST de la app (misma lógica que
        lottery.tabla.acompanantes.action_generar)."""
        rec = self.sudo().search([
            ('sorteo_id', '=', sorteo_id),
            ('fecha_corte', '=', fecha_corte),
            ('turno', '=', turno),
            ('grid_size', '=', grid_size),
        ], limit=1)
        if rec:
            grid_json = rec.grid_json
        else:
            turno_arg = turno if turno != 'general' else False
            affinity = self.env['lottery.stats.service'].sudo() \
                .get_companion_affinity(
                    sorteo_id, fecha_corte=str(fecha_corte), turno=turno_arg)
            grid, _empty = build_grid(affinity, size=int(grid_size))
            grid_json = json.dumps(
                {f'{r},{c}': n for (r, c), n in grid.items()})
            self.sudo().create({
                'sorteo_id': sorteo_id,
                'fecha_corte': fecha_corte,
                'turno': turno,
                'grid_size': grid_size,
                'grid_json': grid_json,
            })
        return {
            tuple(int(x) for x in key.split(',')): n
            for key, n in json.loads(grid_json).items()
        }
