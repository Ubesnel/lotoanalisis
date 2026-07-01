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

    @api.model
    def create(self, vals):
        # ① Capturar predicción ANTES de guardar el sorteo.
        #    El caché refleja el estado previo al sorteo, que es exactamente lo que se necesita.
        validation = self._snapshot_validation(vals)

        # ② Guardar el sorteo.
        record = super().create(vals)

        # ③ Limpiar caché para que la próxima lectura refleje el nuevo sorteo.
        self._after_change()

        # ④ Persistir la validación capturada en ①.
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
        Evalúa los rankings actuales (antes del sorteo) contra los valores
        que está a punto de guardarse.  Retorna el dict de campos o {} si
        faltan datos.
        """
        turn        = vals.get('turn_day')
        number_id   = vals.get('number_id')
        hundreds_id = vals.get('hundreds_id')
        fireball_id = vals.get('fireball_id')
        draw_date   = vals.get('date')
        sorteo_id   = vals.get('sorteo_id')

        sorteo = self.env['lottery.sorteo'].browse(sorteo_id)
        uses_fireball = bool(sorteo.uses_fireball)

        if not all([turn, number_id, hundreds_id, draw_date]) or (uses_fireball and not fireball_id):
            return {}

        LottoNum = self.env['lottery.number']
        num_rec = LottoNum.browse(number_id)
        cen_rec = LottoNum.browse(hundreds_id)
        be_rec  = LottoNum.browse(fireball_id) if uses_fireball else LottoNum

        if not (num_rec.exists() and cen_rec.exists() and (not uses_fireball or be_rec.exists())):
            return {}

        # Contexto = "próximo sorteo" guardado en el sorteo (lo que el portal
        # mostró ANTES de guardar). Con secuencialidad estricta coincide con la
        # salida que se registra. Si no está seteado, get_next_draw lo deriva.
        try:
            ctx_date, ctx_turn = sorteo.get_next_draw()
            service  = self.env['lottery.stats.service']
            turn_data = service.get_validation_sets(ctx_turn, ctx_date, sorteo_id=sorteo_id)
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
