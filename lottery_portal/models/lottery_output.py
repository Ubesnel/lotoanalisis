# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

# Escribir solo estos campos no dispara _after_change ni recalcula grupos.
_VALIDATION_FIELDS = frozenset({
    'hot_numero_ok', 'hot_centena_ok', 'hot_extra_ok', 'hot_ok',
    'hot_1_ok', 'hot_2_ok', 'hot_3_ok',
    'cold_numero_ok', 'cold_centena_ok', 'cold_extra_ok', 'cold_ok',
    'cold_1_ok', 'cold_2_ok', 'cold_3_ok',
    'restante_numero_ok', 'restante_1_ok', 'restante_2_ok',
    'restante_3_ok', 'restante_4_ok', 'validation_date',
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

    # Bloque dentro de Calientes (por score descendente):
    # C1 = posiciones 1-10, C2 = 11-20, C3 = 21 en adelante (empates).
    hot_1_ok = fields.Boolean(
        'Caliente 1', default=False, index=True,
        help='El número estaba en las posiciones 1-10 de Calientes '
             '(los de mayor score) antes del sorteo.')
    hot_2_ok = fields.Boolean(
        'Caliente 2', default=False, index=True,
        help='El número estaba en las posiciones 11-20 de Calientes antes del sorteo.')
    hot_3_ok = fields.Boolean(
        'Caliente 3', default=False, index=True,
        help='El número estaba en las posiciones 21 en adelante de Calientes '
             'antes del sorteo.')

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

    # Bloque dentro de Fríos (por score frío descendente):
    # F1 = posiciones 1-10 (los más fríos), F2 = 11-20, F3 = 21 en adelante.
    cold_1_ok = fields.Boolean(
        'Frío 1', default=False, index=True,
        help='El número estaba en las posiciones 1-10 de Fríos '
             '(los más fríos) antes del sorteo.')
    cold_2_ok = fields.Boolean(
        'Frío 2', default=False, index=True,
        help='El número estaba en las posiciones 11-20 de Fríos antes del sorteo.')
    cold_3_ok = fields.Boolean(
        'Frío 3', default=False, index=True,
        help='El número estaba en las posiciones 21 en adelante de Fríos '
             'antes del sorteo.')

    validation_date = fields.Datetime('Validado el', readonly=True)

    # Restantes
    restante_numero_ok = fields.Boolean(
        'Está en Restantes?', default=False, index=True,
        help='El número salido estaba en el grupo Restantes del turno antes del sorteo.')

    # Bloque dentro de Restantes (por cercanía a Calientes según el score):
    # R1 = posiciones 1-10, R2 = 11-20, R3 = 21-30, R4 = 31 en adelante.
    restante_1_ok = fields.Boolean(
        'Restante 1', default=False, index=True,
        help='El número estaba en las posiciones 1-10 de Restantes '
             '(los más pegados a Calientes) antes del sorteo.')
    restante_2_ok = fields.Boolean(
        'Restante 2', default=False, index=True,
        help='El número estaba en las posiciones 11-20 de Restantes antes del sorteo.')
    restante_3_ok = fields.Boolean(
        'Restante 3', default=False, index=True,
        help='El número estaba en las posiciones 21-30 de Restantes antes del sorteo.')
    restante_4_ok = fields.Boolean(
        'Restante 4', default=False, index=True,
        help='El número estaba en las posiciones 31 en adelante de Restantes '
             '(los más pegados a Fríos) antes del sorteo.')

    # ── CRUD ──────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        # skip_prediction_validation: lo usan los backfills históricos. La
        # validación compara el número contra el ranking_snapshot VIGENTE, así
        # que evaluar una salida de 2020 la marcaría como acierto o fallo de una
        # predicción de hoy: banderas sin sentido que ensucian el análisis de
        # aciertos del backend. Y _check_predictions sería una búsqueda por
        # registro que nunca va a encontrar nada para fechas viejas.
        historico = self.env.context.get('skip_prediction_validation')

        # Validar contra el ranking PRE-CALCULADO (lectura instantánea de JSON)
        # y persistirlo en el mismo INSERT: evita el write() posterior con su
        # ciclo completo de overrides.
        if not historico:
            vals_list = [dict(vals, **self._snapshot_validation(vals)) for vals in vals_list]

        # El cron disparado por lottery_delays_number se encarga de:
        #   - recomputar stats incrementales
        #   - recalcular ranking_snapshot para el próximo sorteo
        #   - limpiar cachés
        records = super().create(vals_list)
        if not historico:
            records._check_predictions()
        return records

    def _check_predictions(self):
        """Verifica la predicción (lottery.prediction) de cada salida: marca
        cumplida si el número salido estaba entre los predichos."""
        Prediction = self.env['lottery.prediction'].sudo()
        for out in self:
            prediction = Prediction.search([
                ('sorteo_id', '=', out.sorteo_id.id),
                ('date', '=', out.date),
                ('turn_day', '=', out.turn_day),
            ], limit=1)
            if prediction:
                num_id = out.number_id.id
                prediction.write({
                    'cumplida':    num_id in prediction.number_ids.ids,
                    'cumplida_20': num_id in prediction.number_ids_20.ids,
                    'cumplida_10': num_id in prediction.number_ids_10.ids,
                    'cumplida_5':  num_id in prediction.number_ids_5.ids,
                    'verification_date': fields.Datetime.now(),
                })

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

    def action_clear_prediction_validation(self):
        """Borra las banderas de validación de las salidas seleccionadas.

        Sirve para limpiar lo que dejaron los backfills históricos antes de
        que existiera skip_prediction_validation: salidas viejas evaluadas
        contra el ranking_snapshot del día de la importación, que figuran como
        aciertos o fallos de predicciones que nunca existieron.
        """
        if not self:
            return
        vacios = dict.fromkeys(_VALIDATION_FIELDS, False)
        vacios['validation_date'] = False
        # El write de este modelo ya evita _after_change cuando solo se tocan
        # campos de validación, así que no dispara recálculos innecesarios.
        self.write(vacios)
        _logger.info('Validaciones borradas en %d salidas.', len(self))

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
        uses_hundreds = bool(sorteo.uses_hundreds)

        if uses_fireball and not fireball_id:
            return {}
        if uses_hundreds and not hundreds_id:
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

        def _ordered(items):
            # Lista ordenada por score descendente, tal como viene del snapshot.
            return [int(i['name'] if isinstance(i, dict) else i) for i in items]

        hot_list  = _ordered(turn_data.get('numbers', []))
        cold_list = _ordered(turn_data.get('numbers_cold', []))
        rest_list = _ordered(turn_data.get('numbers_remaining', []))
        hot_nums  = set(hot_list)
        cold_nums = set(cold_list)
        hot_cen   = _names(turn_data.get('centenas', []))
        cold_cen  = _names(turn_data.get('centenas_cold', []))
        hot_be    = _names(turn_data.get('bola_extra', []))
        cold_be   = _names(turn_data.get('bola_extra_cold', []))

        num = int(num_rec.name)
        cen = int(cen_rec.name) if cen_rec and cen_rec.exists() else -1

        h_num = num in hot_nums
        c_num = num in cold_nums
        rest_num = num not in hot_nums and num not in cold_nums

        # Sin centena (sorteos de 2 dígitos) la centena no puede fallar ni
        # acertar: se neutraliza igual que la bola extra, para que hot_ok /
        # cold_ok dependan solo de lo que el sorteo sí juega.
        if uses_hundreds:
            h_cen = cen in hot_cen
            c_cen = cen not in cold_cen
        else:
            h_cen = c_cen = True

        # Bloque dentro de cada lista según la posición en el ranking (score
        # descendente). Los primeros bloques son fijos de 10 posiciones; el
        # último absorbe el resto (varía con los empates).
        def _block(lst, max_block):
            if num not in lst:
                return 0
            return min(lst.index(num) // 10, max_block - 1) + 1

        hot_block  = _block(hot_list, 3)
        cold_block = _block(cold_list, 3)
        rest_block = _block(rest_list, 4)

        if uses_fireball:
            be    = int(be_rec.name)
            h_be  = be in hot_be
            c_be  = be not in cold_be
        else:
            h_be = c_be = True

        return {
            'hot_numero_ok':   h_num,
            'hot_centena_ok':  h_cen if uses_hundreds else False,
            'hot_extra_ok':    h_be if uses_fireball else False,
            'hot_ok':          h_num and h_cen and h_be,
            'hot_1_ok':        hot_block == 1,
            'hot_2_ok':        hot_block == 2,
            'hot_3_ok':        hot_block == 3,
            'cold_numero_ok':  c_num,
            'cold_centena_ok': c_cen if uses_hundreds else False,
            'cold_extra_ok':   c_be if uses_fireball else False,
            'cold_ok':         c_num and c_cen and c_be,
            'cold_1_ok':       cold_block == 1,
            'cold_2_ok':       cold_block == 2,
            'cold_3_ok':       cold_block == 3,
            'validation_date': fields.Datetime.now(),
            'restante_numero_ok': rest_num,
            'restante_1_ok': rest_block == 1,
            'restante_2_ok': rest_block == 2,
            'restante_3_ok': rest_block == 3,
            'restante_4_ok': rest_block == 4,
        }
