# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

# Escribir solo estos campos no dispara _after_change ni recalcula grupos.
_VALIDATION_FIELDS = frozenset({
    'hot_numero_ok', 'hot_centena_ok', 'hot_extra_ok', 'hot_ok',
    'cold_numero_ok', 'cold_centena_ok', 'cold_extra_ok', 'cold_ok',
    'restante_numero_ok', 'validation_date',
})


class LotteryOutput(models.Model):
    _inherit = 'lottery.output'

    # ── Validación caliente (predicción vs resultado) ─────────────
    hot_numero_ok = fields.Boolean(
        'Está en Calientes?', default=False, index=True,
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
        'Está en Fríos?', default=False, index=True,
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

    # Restantes
    restante_numero_ok = fields.Boolean(
        'Está en Restantes?', default=False, index=True,
        help='El número salido estaba en el grupo Restantes del turno antes del sorteo.')

    # ── CRUD ──────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        # Validar contra el ranking PRE-CALCULADO (lectura instantánea de JSON)
        # y persistirlo en el mismo INSERT: evita el write() posterior con su
        # ciclo completo de overrides.
        vals_list = [dict(vals, **self._snapshot_validation(vals)) for vals in vals_list]

        # El cron disparado por lottery_delays_number se encarga de:
        #   - recomputar stats incrementales
        #   - recalcular ranking_snapshot para el próximo sorteo
        #   - limpiar cachés
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if not _VALIDATION_FIELDS.issuperset(vals.keys()):
            self._after_change()
        return res

    def unlink(self):
        res = super().unlink()
        self._after_change()
        return res

    _MATERIALIZED_VIEWS = [
        'lottery_centena_week_mv',
        'lottery_centena_weekday_mv',
        'lottery_group_sequences_mv',
        'lottery_group_analysis_mv',
        'lottery_top10_afternoon_mv',
        'lottery_top10_dia_semana_mv',
        'lottery_top10_mv',
        'lottery_top10_evening_mv',
        'lottery_top_atrasos_lineas_mv',
        'lottery_number_groups_atrasos_mv',
        'lottery_top_atrasos_terminales_mv',
        'lottery_top5_bola_extra_dia_mv',
        'lottery_top5_bola_extra_general_mv',
        'lottery_top5_bola_extra_noche_mv',
        'lottery_top5_centena_dia_mv',
        'lottery_top5_centena_general_mv',
        'lottery_top5_centena_noche_mv',
        'lottery_ultima_salida_dia_semana_mv',
        'lottery_weekend_groups_mv',
    ]

    def _after_change(self):
        self.env['lottery.stats.service'].clear_caches()

    def refresh_materialized_views(self):
        for view in self._MATERIALIZED_VIEWS:
            self.env.cr.execute(f"REFRESH MATERIALIZED VIEW {view}")

    # ── Lógica de validación ──────────────────────────────────────

    def _snapshot_validation(self, vals):
        """
        Evalúa el número contra el ranking PRE-CALCULADO del sorteo (guardado
        en lottery.sorteo.ranking_snapshot).  Lectura instantánea, sin SQL.
        Retorna el dict de campos de validación o {} si no hay snapshot.
        """
        turn        = vals.get('turn_day')
        number_id   = vals.get('number_id')
        hundreds_id = vals.get('hundreds_id')
        fireball_id = vals.get('fireball_id')
        sorteo_id   = vals.get('sorteo_id')

        if not all([turn, number_id, sorteo_id]):
            return {}

        sorteo = self.env['lottery.sorteo'].browse(sorteo_id)
        uses_fireball = bool(sorteo.uses_fireball)

        if uses_fireball and not fireball_id:
            return {}

        turn_data = sorteo.get_validation_data(turn)
        if not turn_data:
            return {}

        LottoNum = self.env['lottery.number']
        num_rec = LottoNum.browse(number_id)
        cen_rec = LottoNum.browse(hundreds_id) if hundreds_id else LottoNum
        be_rec  = LottoNum.browse(fireball_id) if uses_fireball else LottoNum

        if not num_rec.exists():
            return {}

        def _names(items):
            return {int(i['name'] if isinstance(i, dict) else i) for i in items}

        hot_nums  = _names(turn_data.get('numbers', []))
        cold_nums = _names(turn_data.get('numbers_cold', []))
        hot_cen   = _names(turn_data.get('centenas', []))
        cold_cen  = _names(turn_data.get('centenas_cold', []))
        hot_be    = _names(turn_data.get('bola_extra', []))
        cold_be   = _names(turn_data.get('bola_extra_cold', []))

        num = int(num_rec.name)
        cen = int(cen_rec.name) if cen_rec and cen_rec.exists() else -1

        h_num = num in hot_nums
        h_cen = cen in hot_cen
        c_num = num in cold_nums
        c_cen = cen not in cold_cen
        rest_num = num not in hot_nums and num not in cold_nums

        if uses_fireball:
            be    = int(be_rec.name)
            h_be  = be in hot_be
            c_be  = be not in cold_be
        else:
            h_be = c_be = True

        return {
            'hot_numero_ok':   h_num,
            'hot_centena_ok':  h_cen,
            'hot_extra_ok':    h_be if uses_fireball else False,
            'hot_ok':          h_num and h_cen and h_be,
            'cold_numero_ok':  c_num,
            'cold_centena_ok': c_cen,
            'cold_extra_ok':   c_be if uses_fireball else False,
            'cold_ok':         c_num and c_cen and c_be,
            'validation_date': fields.Datetime.now(),
            'restante_numero_ok': rest_num
        }
