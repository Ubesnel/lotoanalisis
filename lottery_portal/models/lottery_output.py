# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

# Escribir solo estos campos no dispara _after_change ni recalcula grupos.
_VALIDATION_FIELDS = frozenset({
    'hot_numero_ok', 'hot_centena_ok', 'hot_extra_ok', 'hot_ok',
    'cold_numero_ok', 'cold_centena_ok', 'cold_extra_ok', 'cold_ok',
    'validation_date',
})


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    # ── Validación caliente (predicción vs resultado) ─────────────
    hot_numero_ok = fields.Boolean(
        'Número caliente', default=False, index=True,
        help='El número salido estaba en el top 30 calientes del turno antes del sorteo.')
    hot_centena_ok = fields.Boolean(
        'Centena caliente', default=False, index=True,
        help='La centena estaba en el top 4 calientes del turno antes del sorteo.')
    hot_extra_ok = fields.Boolean(
        'Extra caliente', default=False, index=True,
        help='La bola extra estaba en el top 4 calientes del turno antes del sorteo.')
    hot_ok = fields.Boolean(
        'Satisfactorio caliente', default=False, index=True,
        help='Los tres (número, centena y extra) estaban en los rangos calientes.')

    # ── Validación fría ───────────────────────────────────────────
    cold_numero_ok = fields.Boolean(
        'Número no-frío', default=False, index=True,
        help='El número salido NO estaba en el top 30 fríos del turno antes del sorteo.')
    cold_centena_ok = fields.Boolean(
        'Centena no-fría', default=False, index=True,
        help='La centena NO estaba en el top 4 frías del turno antes del sorteo.')
    cold_extra_ok = fields.Boolean(
        'Extra no-frío', default=False, index=True,
        help='La bola extra NO estaba en el top 4 frías del turno antes del sorteo.')
    cold_ok = fields.Boolean(
        'Satisfactorio frío', default=False, index=True,
        help='Ninguno de los tres estaba en las listas frías.')

    validation_date = fields.Datetime('Validado el', readonly=True)

    # ── CRUD ──────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        # ① Limpiar caché para obtener rankings frescos antes del sorteo.
        self.env['lottery.stats.service'].clear_caches()

        # ② Capturar predicción ANTES de guardar el sorteo.
        #    En este momento los rankings reflejan el estado previo al sorteo.
        validation = self._snapshot_validation(vals)

        # ③ Guardar el sorteo (altera atrasos, frecuencias, etc.)
        record = super().create(vals)

        # ④ Recomputar grupos y limpiar caché
        self._after_change()

        # ⑤ Persistir la validación capturada en ②.
        #    write() con solo campos de validación NO vuelve a disparar _after_change.
        if validation:
            record.write(validation)

        return record

    def write(self, vals):
        res = super().write(vals)
        if not _VALIDATION_FIELDS.issuperset(vals.keys()):
            self._after_change()
        return res

    def unlink(self):
        res = super().unlink()
        self._after_change()
        return res

    def _after_change(self):
        self.env['lottery.group'].cron_recompute_from_sql()
        self.env['lottery.stats.service'].clear_caches()

    # ── Lógica de validación ──────────────────────────────────────

    def _snapshot_validation(self, vals):
        """
        Evalúa los rankings actuales (antes del sorteo) contra los valores
        que está a punto de guardarse.  Retorna el dict de campos o {} si
        faltan datos.
        """
        turn        = vals.get('turn_day')
        number_id   = vals.get('number_id')
        hundreds_id = vals.get('hundreds_id')
        fireball_id = vals.get('fireball_id')
        draw_date   = vals.get('date')

        if not all([turn, number_id, hundreds_id, fireball_id, draw_date]):
            return {}

        LottoNum = self.env['lottery.number']
        num_rec = LottoNum.browse(number_id)
        cen_rec = LottoNum.browse(hundreds_id)
        be_rec  = LottoNum.browse(fireball_id)

        if not (num_rec.exists() and cen_rec.exists() and be_rec.exists()):
            return {}

        try:
            service  = self.env['lottery.stats.service']
            all_data = service.get_calientes_all(str(draw_date))
            turn_data = all_data.get(turn, {})
        except Exception as exc:
            _logger.error('Validación sorteo %s %s: %s', draw_date, turn, exc)
            return {}

        hot_nums  = {int(n['name']) for n in turn_data.get('numbers', [])}
        cold_nums = {int(n['name']) for n in turn_data.get('numbers_cold', [])}
        hot_cen   = {int(n['name']) for n in turn_data.get('centenas', [])}
        cold_cen  = {int(n['name']) for n in turn_data.get('centenas_cold', [])}
        hot_be    = {int(n['name']) for n in turn_data.get('bola_extra', [])}
        cold_be   = {int(n['name']) for n in turn_data.get('bola_extra_cold', [])}

        num = int(num_rec.name)
        cen = int(cen_rec.name)
        be  = int(be_rec.name)

        h_num = num in hot_nums
        h_cen = cen in hot_cen
        h_be  = be  in hot_be
        c_num = num not in cold_nums
        c_cen = cen not in cold_cen
        c_be  = be  not in cold_be

        return {
            'hot_numero_ok':   h_num,
            'hot_centena_ok':  h_cen,
            'hot_extra_ok':    h_be,
            'hot_ok':          h_num and h_cen and h_be,
            'cold_numero_ok':  c_num,
            'cold_centena_ok': c_cen,
            'cold_extra_ok':   c_be,
            'cold_ok':         c_num and c_cen and c_be,
            'validation_date': fields.Datetime.now(),
        }
