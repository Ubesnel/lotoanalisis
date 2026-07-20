# -*- coding: utf-8 -*-
from collections import Counter

from odoo import api, fields, models


class ConsultaCombinaciones(models.TransientModel):
    """Consulta de 25 números candidatos por combinación de dígitos.

    Toma las últimas N salidas registradas hasta la fecha indicada y arma
    los números de 2 cifras combinando los dígitos del número completo
    (centena/decena/unidad) de esas salidas. El puntaje de cada candidato
    es el producto de la frecuencia de sus dos dígitos en la ventana:
    a más repetido el dígito, más arriba queda la combinación.
    """
    _name = 'lottery.consulta.combinaciones'
    _description = 'Consulta 25 números por combinaciones'

    sorteo_id = fields.Many2one(
        'lottery.sorteo', string='Sorteo', required=True,
        default=lambda self: self.env['lottery.sorteo'].search([], limit=1))
    date = fields.Date(
        string='Fecha', required=True, default=fields.Date.context_today,
        help='Se usan las últimas salidas registradas hasta esta fecha '
             '(inclusive, ambos turnos).')
    window = fields.Integer(
        string='Ventana de salidas', default=15, required=True,
        help='Cantidad de salidas hacia atrás a considerar.')
    result_html = fields.Html(string='Resultado', readonly=True, sanitize=False)

    def _get_window_outputs(self):
        """Últimas `window` salidas hasta la fecha, más reciente primero."""
        self.ensure_one()
        self.env.cr.execute("""
            SELECT date, turn_day, complete_number
            FROM lottery_output
            WHERE sorteo_id = %s
              AND date <= %s
              AND complete_number IS NOT NULL
            ORDER BY date DESC,
                     CASE turn_day WHEN 'evening' THEN 1 ELSE 0 END DESC
            LIMIT %s
        """, (self.sorteo_id.id, self.date, self.window))
        return self.env.cr.fetchall()

    def _get_same_date_numbers(self):
        """Números (2 cifras) salidos el mismo dd/mm en años anteriores."""
        self.ensure_one()
        self.env.cr.execute("""
            SELECT DISTINCT RIGHT(complete_number, 2)
            FROM lottery_output
            WHERE sorteo_id = %s
              AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM %s::date)
              AND EXTRACT(DAY FROM date) = EXTRACT(DAY FROM %s::date)
              AND EXTRACT(YEAR FROM date) < EXTRACT(YEAR FROM %s::date)
              AND complete_number IS NOT NULL
        """, (self.sorteo_id.id, self.date, self.date, self.date))
        return {r[0] for r in self.env.cr.fetchall()}

    @api.model
    def _top_candidatos(self, completos, top=25):
        """Ranking de números 00-99 por producto de frecuencia de dígitos."""
        digs = Counter(d for n in completos for d in n)
        scores = {
            f'{dd}{uu}': digs.get(dd, 0) * digs.get(uu, 0)
            for dd in '0123456789' for uu in '0123456789'
        }
        orden = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return orden[:top], digs

    def action_consultar(self):
        self.ensure_one()
        outputs = self._get_window_outputs()
        if not outputs:
            self.result_html = (
                '<div class="alert alert-warning">No hay salidas registradas '
                'para ese sorteo hasta la fecha indicada.</div>')
            return self._reopen()

        completos = [n for _, _, n in outputs]
        top, digs = self._top_candidatos(completos)
        mismos_fecha = self._get_same_date_numbers()

        turn_lbl = {'afternoon': 'Tarde', 'evening': 'Noche'}
        salidas = ' '.join(
            '<span class="badge bg-light text-dark border me-1 mb-1">'
            f'{d.strftime("%d/%m")} {turn_lbl.get(t, t)}: <b>{n}</b></span>'
            for d, t, n in outputs)

        digitos = ' '.join(
            f'<span class="badge bg-secondary me-1">{d} ×{c}</span>'
            for d, c in digs.most_common())

        def bola(i, n, s):
            color = '#7B2FF7' if i < 10 else '#FF8A00' if i < 18 else '#6c757d'
            directo = n in mismos_fecha
            virado = n[::-1] in mismos_fecha
            # anillo dorado = salió esa fecha; punteado = su virado salió
            ring = ('box-shadow:0 0 0 3px #FFC107;' if directo
                    else 'outline:2px dashed #FFC107;outline-offset:2px;'
                    if virado else '')
            marca = ' ●' if directo else (' ◐' if virado else '')
            title = f'puntaje {s}'
            if directo:
                title += ' · salió un %s' % self.date.strftime('%d/%m')
            elif virado:
                title += ' · su virado %s salió un %s' % (
                    n[::-1], self.date.strftime('%d/%m'))
            return (
                '<span class="d-inline-flex align-items-center '
                'justify-content-center rounded-circle text-white fw-bold '
                f'me-2 mb-2" style="width:44px;height:44px;font-size:15px;'
                f'background:{color};{ring}" title="{title}">{n}{marca}</span>')

        bolas = ''.join(bola(i, n, s) for i, (n, s) in enumerate(top))
        numeros_txt = ' - '.join(n for n, _ in top)

        # Cruces para copiar
        cruce_directo = [n for n, _ in top if n in mismos_fecha]
        cruce_virado = [n for n, _ in top
                        if n not in mismos_fecha and n[::-1] in mismos_fecha]
        dd_mm = self.date.strftime('%d/%m')
        cruce_html = ''
        if mismos_fecha:
            cruce_html = f"""
                <h6>Coincidencias con salidas históricas del {dd_mm}</h6>
                <p class="small mb-1">
                    Directos (salieron un {dd_mm}):
                    <code>{' - '.join(cruce_directo) or '—'}</code></p>
                <p class="small mb-3">
                    Virados (su invertido salió un {dd_mm}):
                    <code>{' - '.join(cruce_virado) or '—'}</code></p>
            """

        self.result_html = f"""
            <div>
                <h5>TOP 25 candidatos</h5>
                <div class="mb-2">{bolas}</div>
                <p class="text-muted small mb-3">
                    Para copiar: <code>{numeros_txt}</code><br/>
                    Violeta: puestos 1-10 · Naranja: 11-18 · Gris: 19-25.<br/>
                    Anillo dorado ●: salió un {dd_mm} de años anteriores ·
                    Punteado ◐: su virado salió un {dd_mm}.
                </p>
                {cruce_html}
                <h6>Ventana analizada ({len(outputs)} salidas)</h6>
                <div class="mb-3">{salidas}</div>
                <h6>Calor de dígitos en la ventana</h6>
                <div>{digitos}</div>
            </div>
        """
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
