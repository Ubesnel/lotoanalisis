# -*- coding: utf-8 -*-
"""Informe de resultados de la Quiniela Uruguay: los 20 premios de un
sorteo (fecha + turno), con la identidad de LotoAnálisis.

Los datos ya existen: el importador `lottery.scraper.quiniela.uy` guarda cada
premio como una salida de su propio `lottery.sorteo` (`quiniela_uy_1` …
`quiniela_uy_20`, todos con `source_code = 'quiniela_uy'`), con la centena en
`hundreds_id` y las dos últimas cifras en `number_id`. Acá sólo se leen y se
arman los 3 dígitos de vuelta.

Diseño: cabezal de color sobre cuerpo claro, igual que el wizard Tabla
LotoAnálisis; verde y dorado de la marca Quiniela en el cabezal; y las bolas
pintadas por turno con la misma receta que la app usa en Últimas salidas
(`Ball` de lib/widgets/result_card.dart): naranja la Vespertina, azul noche
la Nocturna. Todo eso vive en `quiniela_uy_ui`, compartido con la Tómbola.
"""

from odoo import api, fields, models

from .quiniela_uy_ui import (
    COLOR_TURNO, FUENTE, TEXTO, TEXTO_SUAVE, TURN_LABEL,
    badge, bola, cabezal, hueco, tarjeta,
)

SOURCE_CODE = 'quiniela_uy'
TOTAL_PREMIOS = 20
# Los 20 premios se muestran en 4 columnas de 5 y no en 2 de 10: así la
# tarjeta entra entera en el diálogo de Odoo y se le puede sacar la captura
# de pantalla de una sola vez. Cada columna sigue siendo un tramo
# correlativo (1-5, 6-10, 11-15, 16-20).
FILAS = 5


class LotteryQuinielaUyResultados(models.TransientModel):
    """Wizard: elegí fecha y turno y mostrá los 20 premios de esa quiniela."""
    _name = 'lottery.quiniela.uy.resultados'
    _description = 'Resultados Quiniela Uruguay'

    date = fields.Date(
        string='Fecha', required=True,
        default=lambda self: self._default_date(),
        help='Fecha del sorteo. Arranca en el último día con resultados '
             'importados.')
    turn_day = fields.Selection([
        ('afternoon', 'Vespertina'),
        ('evening', 'Nocturna'),
    ], string='Turno', required=True,
        default=lambda self: self._default_turn())
    result_html = fields.Html(string='Resultado', readonly=True,
                              sanitize=False)

    # ── Defaults: el último sorteo que haya entrado ───────────────────────

    @api.model
    def _last_output(self):
        return self.env['lottery.output'].sudo().search(
            [('sorteo_id.source_code', '=', SOURCE_CODE)],
            order='date desc, turn_day desc, id desc', limit=1)

    @api.model
    def _default_date(self):
        last = self._last_output()
        return last.date if last else fields.Date.context_today(self)

    @api.model
    def _default_turn(self):
        last = self._last_output()
        return last.turn_day if last else 'evening'

    # ── Lectura de los 20 premios ─────────────────────────────────────────

    def _premios(self):
        """[(premio, '410'), …] ordenado por premio, sólo los que existen.

        El número de premio sale del sufijo del código del sorteo
        (`quiniela_uy_7` → 7), igual que hace el importador: es más robusto
        que confiar en el `sequence`, que es un dato de presentación y se
        puede reordenar desde la interfaz.
        """
        self.ensure_one()
        outputs = self.env['lottery.output'].sudo().search([
            ('sorteo_id.source_code', '=', SOURCE_CODE),
            ('date', '=', self.date),
            ('turn_day', '=', self.turn_day),
        ])
        premios = []
        for out in outputs:
            try:
                premio = int(out.sorteo_id.code.rsplit('_', 1)[-1])
            except (ValueError, AttributeError):
                continue
            centena = out.hundreds_id.name if out.hundreds_id else 0
            premios.append((premio, '%d%02d' % (centena, out.number_id.name)))
        return sorted(premios)

    # ── Acción ────────────────────────────────────────────────────────────

    def action_consultar(self):
        self.ensure_one()
        self.result_html = self._render_html(self._premios())
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    # ── Render ────────────────────────────────────────────────────────────

    def _render_html(self, premios):
        self.ensure_one()
        cuerpo = (self._render_premios(premios) if premios
                  else self._render_vacio())
        return tarjeta(cabezal(self.turn_day, self.date), cuerpo)

    def _render_premios(self, premios):
        por_premio = dict(premios)
        faltan = TOTAL_PREMIOS - len(premios)
        color = COLOR_TURNO[self.turn_day]

        filas = []
        for i in range(1, FILAS + 1):
            celdas = []
            for premio in range(i, TOTAL_PREMIOS + 1, FILAS):
                numero = por_premio.get(premio)
                celdas.append(
                    '<td style="padding:5px 4px;">'
                    '<div style="display:flex;align-items:center;gap:8px;">'
                    '%s%s</div></td>'
                    % (badge(premio),
                       bola(numero, color) if numero else hueco()))
            filas.append('<tr>%s</tr>' % ''.join(celdas))

        aviso = ''
        if faltan:
            aviso = (
                '<div style="margin:10px 16px 0;padding:8px 10px;'
                'border-radius:9px;background:#FFF7E3;border:1px solid #F5E3B3;'
                'font:600 11.5px/1.45 %s;color:#8A6416;text-align:center;">'
                'Faltan %d de los %d premios: el sorteo se importó incompleto.'
                '</div>' % (FUENTE, faltan, TOTAL_PREMIOS))

        return (
            '<div style="padding:14px 10px 14px;">'
            '<table style="border-collapse:collapse;margin:0 auto;">'
            '<tbody>%s</tbody></table>%s</div>'
            % (''.join(filas), aviso)
        )

    def _render_vacio(self):
        return (
            '<div style="padding:22px 18px 22px;text-align:center;">'
            '<div style="padding:16px;border-radius:14px;background:#FFFFFF;'
            'border:1px solid %s;font:700 13.5px/1.5 %s;color:%s;">'
            'No hay resultados cargados para esta fecha y turno.<br/>'
            '<span style="font-weight:500;color:%s;">Puede que el sorteo '
            'todavía no se haya jugado, que ese día no hubiera %s, o que '
            'falte correr el importador.</span></div></div>'
            % ('#C6E4CF', FUENTE, TEXTO, TEXTO_SUAVE,
               TURN_LABEL[self.turn_day].lower())
        )
