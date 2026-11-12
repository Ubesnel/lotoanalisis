# -*- coding: utf-8 -*-
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import sql

# Antes de esta hora (Uruguay) la jornada sigue siendo la de ayer: los sorteos
# de la noche se publican pasada la medianoche.
JORNADA_CORTE_H = 6
# Días para "próximos a vencer" (códigos sin canjear y Premium de regalo).
DIAS_VENCER = 7
# Días que guarda lottery.api.log (cron de limpieza de lottery_api).
DIAS_LOG = 3

ESTADO_TAREA = {'pending': 'Pendiente', 'late': 'Atrasada', 'done': 'Hecha'}


class LotteryDashboard(models.AbstractModel):
    _name = 'lottery.dashboard'
    _description = 'Tablero de control de loterías'

    # ── Utilidades ─────────────────────────────────────────────────────────

    @api.model
    def _tz(self):
        return pytz.timezone(self.env.company.partner_id.tz or 'America/Montevideo')

    @api.model
    def _ahora_local(self):
        return pytz.utc.localize(fields.Datetime.now()).astimezone(self._tz())

    @api.model
    def _jornada_actual(self):
        ahora = self._ahora_local()
        dia = ahora.date()
        return dia - timedelta(days=1) if ahora.hour < JORNADA_CORTE_H else dia

    @api.model
    def _rango_utc(self, desde, hasta):
        """Fechas locales [desde, hasta] → datetimes UTC sin zona [ini, fin)."""
        tz = self._tz()
        ini = tz.localize(datetime(desde.year, desde.month, desde.day))
        fin = tz.localize(datetime(hasta.year, hasta.month, hasta.day)) + timedelta(days=1)
        return (ini.astimezone(pytz.utc).replace(tzinfo=None),
                fin.astimezone(pytz.utc).replace(tzinfo=None))

    @api.model
    def _hora_local(self, dt):
        if not dt:
            return ''
        loc = pytz.utc.localize(dt).astimezone(self._tz())
        h12 = loc.hour % 12 or 12
        return '%d:%02d %s' % (h12, loc.minute, 'AM' if loc.hour < 12 else 'PM')

    # ── Entrada ────────────────────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self, date=None, periodo='day', corridos=False):
        if not self.env.user.has_group('lottery_base.group_lottery_manager'):
            raise AccessError('Solo los administradores de lotería ven el tablero.')
        jornada = fields.Date.to_date(date) if date else self._jornada_actual()
        hoy = self._ahora_local().date()
        return {
            'date': fields.Date.to_string(jornada),
            'jornada_actual': fields.Date.to_string(self._jornada_actual()),
            'es_hoy': jornada == self._jornada_actual(),
            'generado': self._hora_local(fields.Datetime.now()),
            'tareas': self._data_tareas(jornada),
            'predicciones': self._data_predicciones(jornada),
            'numeros': self._data_numeros(jornada, periodo, corridos),
            'regalos': self._data_regalos(),
            'premium': self._data_premium(),
            'consultas': self._data_consultas(jornada, hoy),
            'accesos': self._data_accesos_premium(jornada, hoy),
            'alertas': self._data_alertas(jornada),
        }

    # ── Tareas (agenda) ────────────────────────────────────────────────────

    @api.model
    def _data_tareas(self, jornada):
        eventos = self.env['calendar.event'].sudo().search([
            ('lottery_sorteo_id', '!=', False),
            ('lottery_date', '=', jornada),
        ], order='start')
        ahora = fields.Datetime.now()
        conteo = Counter(eventos.mapped('lottery_state'))
        lista = []
        for ev in eventos:
            lista.append({
                'id': ev.id,
                'sorteo': ev.lottery_sorteo_id.name,
                'turno': ev.lottery_turno_id.name,
                'hora': self._hora_local(ev.start),
                'cruza': (pytz.utc.localize(ev.start).astimezone(self._tz()).date() > jornada
                          if ev.start else False),
                'state': ev.lottery_state or 'pending',
                'state_label': ESTADO_TAREA.get(ev.lottery_state or 'pending'),
                'minutos': int((ev.start - ahora).total_seconds() // 60) if ev.start else 0,
            })
        proxima = next((t for t in lista if t['state'] == 'pending'), None)
        return {
            'total': len(eventos),
            'pending': conteo.get('pending', 0),
            'late': conteo.get('late', 0),
            'done': conteo.get('done', 0),
            'lista': lista,
            'proxima': proxima,
        }

    # ── Predicciones normales y Premium ────────────────────────────────────

    @api.model
    def _estado_pred(self, rec):
        if not rec:
            return 'missing'
        return 'published' if rec.published else 'draft'

    @api.model
    def _data_predicciones(self, jornada):
        sorteos = self.env['lottery.sorteo'].sudo().search([
            ('show_in_app', '=', True),
            ('exclude_from_predictions', '=', False),
        ], order='sequence, name')
        dow = str(jornada.weekday())
        Pred = self.env['lottery.prediction'].sudo()
        Prem = self.env['lottery.prediction.premium'].sudo()
        Output = self.env['lottery.output'].sudo()

        dominio = [('sorteo_id', 'in', sorteos.ids), ('date', '=', jornada)]
        normales = {(p.sorteo_id.id, p.turno_id.id): p for p in Pred.search(dominio)}
        premiums = {(p.sorteo_id.id, p.turno_id.id): p for p in Prem.search(dominio)}
        salidas = {(o.sorteo_id.id, o.turno_id.id): o for o in Output.search(dominio)}

        filas = []
        resumen = Counter()
        for sorteo in sorteos:
            slots = sorteo.slot_ids.filtered(lambda s: s.dow == dow).sorted(
                lambda s: (s.turno_id.sequence, s.turno_id.id))
            if not slots:
                continue
            try:
                prox_fecha, prox_turno = sorteo.get_next_draw()
            except Exception:  # noqa: BLE001 - el tablero no debe caerse por un sorteo
                prox_fecha, prox_turno = False, self.env['lottery.turno']
            celdas = []
            for slot in slots:
                clave = (sorteo.id, slot.turno_id.id)
                normal = self._estado_pred(normales.get(clave))
                premium = self._estado_pred(premiums.get(clave))
                if normal == 'published' and premium == 'published':
                    combinado = 'ok'
                elif normal == 'missing' and premium == 'missing':
                    combinado = 'none'
                else:
                    combinado = 'partial'
                salida = salidas.get(clave)
                resumen[combinado] += 1
                resumen['normal_' + normal] += 1
                resumen['premium_' + premium] += 1
                if normal == 'published' and salida:
                    resumen['neval_pendiente' if not normales[clave].verification_date else 'neval_ok'] += 1
                if premium == 'published' and salida:
                    resumen['eval_pendiente' if not premiums[clave].evaluada else 'eval_ok'] += 1
                celdas.append({
                    'turno': slot.turno_id.name,
                    'turno_color': slot.turno_id.color or '',
                    'hora': '%s:%02d %s' % (slot.hora_h, slot.hora_min or 0,
                                            (slot.hora_ampm or 'pm').upper()) if slot.hora_h else '',
                    'normal': normal,
                    'normal_id': normales[clave].id if clave in normales else False,
                    'normal_eval': ('si' if clave in normales and normales[clave].verification_date
                                    else 'pendiente' if normal == 'published' and salida
                                    else ''),
                    'premium': premium,
                    'premium_id': premiums[clave].id if clave in premiums else False,
                    'premium_eval': ('si' if clave in premiums and premiums[clave].evaluada
                                     else 'pendiente' if premium == 'published' and salida
                                     else ''),
                    'estado': combinado,
                    'salida': salida.complete_number if salida else '',
                    'proximo': (prox_fecha == fields.Date.to_string(jornada)
                                and prox_turno == slot.turno_id),
                })
            filas.append({
                'id': sorteo.id,
                'name': sorteo.name,
                'pais': sorteo.country_id.name or '',
                'pais_code': (sorteo.country_id.code or '').upper(),
                'celdas': celdas,
                'completo': all(c['estado'] == 'ok' for c in celdas),
                'estado': ('ok' if all(c['estado'] == 'ok' for c in celdas)
                           else 'none' if all(c['estado'] == 'none' for c in celdas)
                           else 'partial'),
            })
        total = sum(len(f['celdas']) for f in filas)
        return {
            'filas': filas,
            'total': total,
            'ok': resumen['ok'],
            'partial': resumen['partial'],
            'none': resumen['none'],
            'normal': {k: resumen['normal_' + k] for k in ('published', 'draft', 'missing')},
            'premium': {k: resumen['premium_' + k] for k in ('published', 'draft', 'missing')},
            'neval_ok': resumen['neval_ok'],
            'neval_pendiente': resumen['neval_pendiente'],
            'eval_ok': resumen['eval_ok'],
            'eval_pendiente': resumen['eval_pendiente'],
        }

    # ── Números del día: líneas, terminales, pintas ────────────────────────

    @api.model
    def _data_numeros(self, jornada, periodo, corridos):
        dias = {'week': 7, 'month': 30}.get(periodo, 1)
        desde = jornada - timedelta(days=dias - 1)
        columnas = ['n1.name']
        joins = ['JOIN lottery_number n1 ON n1.id = o.number_id']
        if corridos:
            columnas += ['n2.name', 'n3.name']
            joins += ['LEFT JOIN lottery_number n2 ON n2.id = o.premio_2_id',
                      'LEFT JOIN lottery_number n3 ON n3.id = o.premio_3_id']
        self.env.cr.execute("""
            SELECT s.name, coalesce(t.name->>'es_ES', t.name->>'en_US'), o.date, %s
              FROM lottery_output o
              JOIN lottery_sorteo s ON s.id = o.sorteo_id
              LEFT JOIN lottery_turno t ON t.id = o.turno_id
              %s
             WHERE o.date BETWEEN %%s AND %%s AND s.active
               AND s.show_in_app AND NOT coalesce(s.exclude_from_predictions, false)
        """ % (', '.join(columnas), ' '.join(joins)), (desde, jornada))
        filas = self.env.cr.fetchall()

        lineas, terminales, pintas, numeros = Counter(), Counter(), Counter(), Counter()
        donde = defaultdict(list)
        sorteos_con_salida = set()
        cantidad = 0
        for fila in filas:
            sorteos_con_salida.add(fila[0])
            for premio, n in enumerate(fila[3:], 1):
                if n is None:
                    continue
                n = int(n) % 100
                cantidad += 1
                dec, uni = divmod(n, 10)
                lineas[dec] += 1
                terminales[uni] += 1
                for d in {dec, uni}:
                    pintas[d] += 1
                numeros[n] += 1
                donde[n].append({'sorteo': fila[0], 'turno': fila[1] or '',
                                 'fecha': fields.Date.to_string(fila[2]), 'premio': premio})

        def serie(counter):
            valores = [counter.get(d, 0) for d in range(10)]
            maximo = max(valores) if any(valores) else 0
            minimo = min(valores) if any(valores) else 0
            return {
                'valores': valores,
                'mas': [d for d, v in enumerate(valores) if maximo and v == maximo],
                'menos': [d for d, v in enumerate(valores) if any(valores) and v == minimo],
                'ceros': [d for d, v in enumerate(valores) if v == 0],
            }

        repetidos = [{'numero': '%02d' % n, 'veces': v, 'donde': donde[n]}
                     for n, v in numeros.most_common() if v > 1][:15]
        return {
            'periodo': periodo,
            'desde': fields.Date.to_string(desde),
            'corridos': bool(corridos),
            'cantidad': cantidad,
            'sorteos': len(filas),
            'loterias': len(sorteos_con_salida),
            'lineas': serie(lineas),
            'terminales': serie(terminales),
            'pintas': serie(pintas),
            'repetidos': repetidos,
            'distintos': len(numeros),
        }

    # ── Códigos de regalo ──────────────────────────────────────────────────

    @api.model
    def _data_regalos(self):
        Gift = self.env['lottery.premium.gift'].sudo()
        ahora = fields.Datetime.now()
        limite = ahora + timedelta(days=DIAS_VENCER)
        base = [('google_robot', '=', False)]

        estados = Counter()
        origenes = Counter()
        por_pais = defaultdict(Counter)
        for grupo in Gift.read_group(base, ['state', 'origin', 'country_id'],
                                     ['country_id', 'state', 'origin'], lazy=False):
            n = grupo['__count']
            estados[grupo['state']] += n
            origenes[grupo['origin']] += n
            pais = grupo['country_id'][1] if grupo['country_id'] else 'Sin país'
            por_pais[pais][grupo['state']] += n
            por_pais[pais]['total'] += n
        paises = sorted(por_pais.items(), key=lambda kv: -kv[1]['total'])
        top = paises[:10]
        resto = paises[10:]
        if resto:
            otros = Counter()
            for _, c in resto:
                otros.update(c)
            top.append(('Otros (%d)' % len(resto), otros))

        por_vencer = Gift.search(base + [
            ('state', '=', 'available'),
            ('valid_until', '!=', False),
            ('valid_until', '>=', ahora),
            ('valid_until', '<=', limite),
        ], order='valid_until')
        premium_vence = Gift.search(base + [
            ('state', '=', 'redeemed'),
            ('pass_id.expiry_date', '>=', ahora),
            ('pass_id.expiry_date', '<=', limite),
        ]).sorted(lambda g: g.pass_expiry)

        desde = ahora - timedelta(days=30)
        recientes = Counter()
        for g in Gift.search_read(base + [('create_date', '>=', desde)], ['create_date', 'origin']):
            dia = pytz.utc.localize(g['create_date']).astimezone(self._tz()).date()
            recientes[(fields.Date.to_string(dia), g['origin'])] += 1
        hoy = self._ahora_local().date()
        dias30 = [fields.Date.to_string(hoy - timedelta(days=i)) for i in range(29, -1, -1)]

        def fila_codigo(g, fecha):
            return {
                'id': g.id,
                'name': g.name,
                'pais': g.country_id.name or g.redeem_country_id.name or '',
                'origin': dict(g._fields['origin'].selection).get(g.origin),
                'vence': fields.Datetime.to_string(fecha),
                'dias': max(0, (fecha - ahora).days),
                'note': g.note or '',
            }

        return {
            'total': sum(estados.values()),
            'estados': {k: estados.get(k, 0) for k in ('available', 'redeemed', 'expired', 'revoked')},
            'origenes': {k: origenes.get(k, 0) for k in ('purchase', 'courtesy', 'trial')},
            'robots': Gift.search_count([('google_robot', '=', True)]),
            'paises': [{
                'pais': pais,
                'available': c.get('available', 0),
                'redeemed': c.get('redeemed', 0),
                'expired': c.get('expired', 0) + c.get('revoked', 0),
                'total': c['total'],
            } for pais, c in top],
            'por_vencer': [fila_codigo(g, g.valid_until) for g in por_vencer[:20]],
            'por_vencer_total': len(por_vencer),
            'premium_vence': [fila_codigo(g, g.pass_expiry) for g in premium_vence[:20]],
            'premium_vence_total': len(premium_vence),
            'dias_vencer': DIAS_VENCER,
            'recientes': {
                'dias': dias30,
                'purchase': [recientes.get((d, 'purchase'), 0) for d in dias30],
                'courtesy': [recientes.get((d, 'courtesy'), 0) for d in dias30],
                'trial': [recientes.get((d, 'trial'), 0) for d in dias30],
            },
        }

    # ── Premium (pases) ────────────────────────────────────────────────────

    @api.model
    def _data_premium(self):
        Pass = self.env['lottery.premium.pass'].sudo()
        ahora = fields.Datetime.now()
        vigentes = [('state', 'in', ('active', 'grace', 'canceled')),
                    ('is_test', '=', False),
                    '|', ('expiry_date', '=', False), ('expiry_date', '>', ahora)]
        por_origen = Counter()
        for g in Pass.read_group(vigentes, ['origin'], ['origin'], lazy=False):
            por_origen[g['origin']] += g['__count']
        inicio_hoy, _ = self._rango_utc(self._ahora_local().date(), self._ahora_local().date())
        return {
            'activos': sum(por_origen.values()),
            'suscripcion': por_origen.get('subscription', 0),
            'regalo': por_origen.get('gift', 0),
            'nuevos_hoy': Pass.search_count([('create_date', '>=', inicio_hoy), ('is_test', '=', False)]),
            'vencen_7': Pass.search_count(vigentes + [
                ('expiry_date', '<=', ahora + timedelta(days=DIAS_VENCER))]),
            'en_riesgo': Pass.search_count([('state', 'in', ('grace', 'on_hold')), ('is_test', '=', False)]),
        }

    # ── Consultas a la API (log de 3 días) ─────────────────────────────────

    @api.model
    def _data_consultas(self, jornada, hoy):
        disponible = (hoy - jornada).days < DIAS_LOG
        if not disponible:
            return {'disponible': False, 'dias_log': DIAS_LOG}
        ini, fin = self._rango_utc(jornada, jornada)
        cr = self.env.cr
        tz = self._tz().zone
        cr.execute("""
            SELECT count(*), count(DISTINCT ip),
                   count(*) FILTER (WHERE status >= 500),
                   count(*) FILTER (WHERE status >= 400 AND status < 500)
              FROM lottery_api_log WHERE create_date >= %s AND create_date < %s
        """, (ini, fin))
        total, ips, err5, err4 = cr.fetchone()
        cr.execute("""
            SELECT s.name, count(*), count(DISTINCT l.ip)
              FROM lottery_api_log l JOIN lottery_sorteo s ON s.id = l.sorteo_id
             WHERE l.create_date >= %s AND l.create_date < %s
             GROUP BY s.name ORDER BY 2 DESC LIMIT 12
        """, (ini, fin))
        sorteos = [{'name': r[0], 'count': r[1], 'ips': r[2]} for r in cr.fetchall()]
        cr.execute("""
            SELECT coalesce(nullif(country_name, ''), 'Desconocido'), count(*), count(DISTINCT ip)
              FROM lottery_api_log WHERE create_date >= %s AND create_date < %s
             GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """, (ini, fin))
        paises = [{'name': r[0], 'count': r[1], 'ips': r[2]} for r in cr.fetchall()]
        cr.execute("""
            SELECT regexp_replace(endpoint, '^/api/lottery/v1', ''), count(*)
              FROM lottery_api_log WHERE create_date >= %s AND create_date < %s
             GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """, (ini, fin))
        endpoints = [{'name': r[0] or '/', 'count': r[1]} for r in cr.fetchall()]
        cr.execute("""
            SELECT extract(hour FROM (create_date AT TIME ZONE 'UTC') AT TIME ZONE %s)::int, count(*)
              FROM lottery_api_log WHERE create_date >= %s AND create_date < %s
             GROUP BY 1
        """, (tz, ini, fin))
        por_hora = dict(cr.fetchall())
        return {
            'disponible': True,
            'dias_log': DIAS_LOG,
            'total': total,
            'ips': ips,
            'errores_5xx': err5,
            'errores_4xx': err4,
            'sorteos': sorteos,
            'paises': paises,
            'endpoints': endpoints,
            'por_hora': [por_hora.get(h, 0) for h in range(24)],
        }

    # ── Accesos a contenido Premium ────────────────────────────────────────

    @api.model
    def _data_accesos_premium(self, jornada, hoy):
        if (hoy - jornada).days >= DIAS_LOG:
            return {'disponible': False}
        cr = self.env.cr
        if not sql.column_exists(cr, 'lottery_api_log', 'premium_access'):
            return {'disponible': False, 'falta_update': True}
        ini, fin = self._rango_utc(jornada, jornada)
        rango = "create_date >= %s AND create_date < %s AND premium_access IS NOT NULL"
        cr.execute("""
            SELECT count(*) FILTER (WHERE premium_access = 'granted'),
                   count(DISTINCT pass_id) FILTER (WHERE premium_access = 'granted'),
                   count(*) FILTER (WHERE premium_access = 'locked' AND NOT coalesce(pass_sent, false)),
                   count(DISTINCT ip) FILTER (WHERE premium_access = 'locked' AND NOT coalesce(pass_sent, false)),
                   count(*) FILTER (WHERE premium_access = 'locked' AND pass_sent),
                   count(DISTINCT coalesce(device_id, ip)) FILTER (WHERE premium_access = 'locked' AND pass_sent)
              FROM lottery_api_log WHERE """ + rango, (ini, fin))
        con_pase, pases, curiosos, curiosos_ips, rechazados, rechazados_disp = cr.fetchone()

        cr.execute("""
            SELECT regexp_replace(endpoint, '^/api/lottery/v1', ''),
                   count(*) FILTER (WHERE premium_access = 'granted'),
                   count(*) FILTER (WHERE premium_access = 'locked')
              FROM lottery_api_log WHERE """ + rango + """
             GROUP BY 1 ORDER BY 3 DESC, 2 DESC LIMIT 8
        """, (ini, fin))
        endpoints = [{'name': r[0], 'granted': r[1], 'locked': r[2]} for r in cr.fetchall()]

        # Pase vigente rechazado: vencido, reembolsado, otro teléfono o token falso.
        cr.execute("""
            SELECT coalesce(device_id, ''), ip, coalesce(nullif(country_name, ''), '—'),
                   count(*), max(create_date)
              FROM lottery_api_log
             WHERE """ + rango + """ AND premium_access = 'locked' AND pass_sent
             GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 15
        """, (ini, fin))
        sospechosos = [{'device': r[0], 'ip': r[1], 'pais': r[2], 'veces': r[3],
                        'ultima': self._hora_local(r[4])} for r in cr.fetchall()]

        # Un mismo pase usado desde más de un teléfono o desde muchas IPs.
        cr.execute("""
            SELECT pass_id, count(DISTINCT device_id), count(DISTINCT ip), count(*),
                   string_agg(DISTINCT coalesce(nullif(country_name, ''), '—'), ', ')
              FROM lottery_api_log
             WHERE """ + rango + """ AND premium_access = 'granted' AND pass_id IS NOT NULL
             GROUP BY pass_id
            HAVING count(DISTINCT device_id) > 1 OR count(DISTINCT ip) > 4
             ORDER BY 2 DESC, 3 DESC LIMIT 15
        """, (ini, fin))
        Pass = self.env['lottery.premium.pass'].sudo()
        compartidos = [{'pass_id': r[0], 'name': Pass.browse(r[0]).display_name,
                        'dispositivos': r[1], 'ips': r[2], 'veces': r[3], 'paises': r[4],
                        'copia': r[1] > 1}
                       for r in cr.fetchall()]

        # Gratis que más insisten: posibles interesados en suscribirse.
        cr.execute("""
            SELECT ip, coalesce(nullif(country_name, ''), '—'), count(*),
                   count(DISTINCT endpoint)
              FROM lottery_api_log
             WHERE """ + rango + """ AND premium_access = 'locked' AND NOT coalesce(pass_sent, false)
             GROUP BY 1, 2 HAVING count(*) >= 5 ORDER BY 3 DESC LIMIT 10
        """, (ini, fin))
        insistentes = [{'ip': r[0], 'pais': r[1], 'veces': r[2], 'endpoints': r[3]}
                       for r in cr.fetchall()]
        return {
            'disponible': True,
            'con_pase': con_pase,
            'pases': pases,
            'curiosos': curiosos,
            'curiosos_ips': curiosos_ips,
            'rechazados': rechazados,
            'rechazados_disp': rechazados_disp,
            'endpoints': endpoints,
            'sospechosos': sospechosos,
            'compartidos': compartidos,
            'copias': sum(1 for c in compartidos if c['copia']),
            'muchas_ips': sum(1 for c in compartidos if not c['copia']),
            'insistentes': insistentes,
        }

    # ── Alertas ────────────────────────────────────────────────────────────

    @api.model
    def _data_alertas(self, jornada):
        alertas = []
        Sorteo = self.env['lottery.sorteo'].sudo()
        for s in Sorteo.search([('auto_prediction_error', '!=', False)]):
            alertas.append({
                'nivel': 'critical', 'titulo': 'Error en predicción automática',
                'detalle': '%s: %s' % (s.name, (s.auto_prediction_error or '').splitlines()[0][:160]),
                'model': 'lottery.sorteo', 'res_id': s.id,
            })
        sin_push = self.env['lottery.output'].sudo().search([
            ('date', '=', jornada), ('push_sent', '=', False),
            ('sorteo_id.show_in_app', '=', True)])
        if sin_push:
            alertas.append({
                'nivel': 'warning', 'titulo': 'Salidas sin notificación push',
                'detalle': ', '.join('%s %s' % (o.sorteo_id.name, o.turno_id.name) for o in sin_push[:8])
                           + (' …' if len(sin_push) > 8 else ''),
                'model': 'lottery.output', 'ids': sin_push.ids,
            })
        sin_evaluar = self.env['lottery.prediction.premium'].sudo().search([
            ('date', '<', jornada), ('evaluada', '=', False), ('published', '=', True),
            ('output_id', '!=', False)])
        if sin_evaluar:
            alertas.append({
                'nivel': 'warning', 'titulo': 'Premium con resultado sin evaluar',
                'detalle': '%d predicciones Premium de días anteriores' % len(sin_evaluar),
                'model': 'lottery.prediction.premium', 'ids': sin_evaluar.ids,
            })
        return alertas
