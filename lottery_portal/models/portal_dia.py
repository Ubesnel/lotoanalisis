# -*- coding: utf-8 -*-
"""Resultados del día de la portada web (`/salidas/dia`), con caché.

La portada pide el día completo de todas las loterías públicas; son varias
búsquedas y, con muchas visitas a la misma fecha, siempre dan lo mismo hasta
que se registra una salida. Por eso el resultado se guarda en la caché del ORM
(compartida por los workers) y se borra solo cuando cambia algo que lo afecta:
una salida (o de la Tómbola), un sorteo, su calendario o un turno. Como red de
seguridad, la clave lleva un tramo de 10 minutos: si alguna invalidación se
perdiera, el dato viejo vive como mucho ese tiempo.
"""
import time
from datetime import datetime

import pytz

from odoo import api, models, tools

# Código del sorteo-origen de la Quiniela Uruguaya (20 sorteos, uno por premio).
QUINIELA_UY = 'quiniela_uy'

DIAS = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

# Orden de los países en la portada; los que no estén van después.
PAISES_ORDEN = ['US', 'DO', 'SX', 'NI', 'HN', 'SV', 'CR', 'UY']
PAISES_NOMBRE = {
    'US': 'Estados Unidos', 'DO': 'República Dominicana', 'SX': 'San Martín',
    'NI': 'Nicaragua', 'HN': 'Honduras', 'SV': 'El Salvador', 'CR': 'Costa Rica',
    'UY': 'Uruguay',
}


def _flag(codigo):
    """Bandera emoji a partir del ISO de dos letras ('' si no hay)."""
    if len(codigo or '') != 2:
        return ''
    return ''.join(chr(0x1F1E6 + ord(c) - 65) for c in codigo.upper())


def _iniciales(nombre):
    return ''.join(p[0] for p in (nombre or '').split()[:2]).upper()


def _logo_url(sorteo):
    """URL del logo del sorteo, o None si no tiene (no se lee la imagen)."""
    if not sorteo.with_context(bin_size=True).image_128:
        return None
    version = int(sorteo.write_date.timestamp()) if sorteo.write_date else 0
    return '/lottery/logo/%d?v=%d' % (sorteo.id, version)


def _hora_slot(slot):
    """Hora del sorteo de una línea del calendario ('10:45 PM'), o None."""
    if not slot or not slot.hora_h:
        return None
    return '%s:%02d %s' % (slot.hora_h, slot.hora_min or 0, (slot.hora_ampm or 'pm').upper())


def _turnos_dia(sorteo, dia, por_turno, pendiente_ok):
    """Turnos de un sorteo para esa fecha, en orden del día. Solo los que el
    calendario del sorteo habilita ese día de la semana (o los que ya tienen
    salida)."""
    habilitados = sorteo._enabled_slots()
    slots = {sl.turno_id.id: sl for sl in sorteo.slot_ids if sl.dow == str(dia.weekday())}
    turnos = []
    for turno in sorteo._ordered_turnos():
        salida = por_turno.get(turno.id)
        if not salida and (dia.weekday(), turno.id) not in habilitados:
            continue
        item = {'code': turno.code, 'label': turno.name or '',
                'color': turno.color or '', 'hora': _hora_slot(slots.get(turno.id))}
        if salida:
            item.update(
                estado='salio',
                centena=str(salida.hundreds_id.name) if sorteo.uses_hundreds and salida.hundreds_id else None,
                numero=str(salida.number_id.name).zfill(2),
                extra=str(salida.fireball_id.name) if salida.fireball_id else None,
                premio_2=str(salida.premio_2_id.name).zfill(2) if salida.premio_2_id else None,
                premio_3=str(salida.premio_3_id.name).zfill(2) if salida.premio_3_id else None)
        else:
            item['estado'] = 'pendiente' if pendiente_ok else 'sin_resultado'
        turnos.append(item)
    return turnos


def _quiniela_uy(env, quiniela, dia, por_sorteo, pendiente_ok):
    """Quiniela Uruguaya como una sola lotería: por turno, los 20 premios
    (3 cifras) y los 20 números de la Tómbola de esa fecha y turno."""
    primero = quiniela[0]
    tombola = env['lottery.tombola.output'].sudo().search([('date', '=', dia)])
    slots = {sl.turno_id.id: sl for sl in primero.slot_ids if sl.dow == str(dia.weekday())}
    habilitados = primero._enabled_slots()
    turnos = []
    for turno in primero._ordered_turnos():
        premios = []
        for sorteo in quiniela:
            salida = por_sorteo.get(sorteo.id, {}).get(turno.id)
            if not salida:
                continue
            try:
                n = int(sorteo.code.rsplit('_', 1)[-1])
            except ValueError:
                continue
            centena = salida.hundreds_id.name if salida.hundreds_id else 0
            premios.append({'n': n, 'num': '%d%02d' % (centena, salida.number_id.name)})
        premios.sort(key=lambda p: p['n'])
        if not premios and (dia.weekday(), turno.id) not in habilitados:
            continue
        item = {'code': turno.code, 'label': turno.name or '', 'color': turno.color or '',
                'hora': _hora_slot(slots.get(turno.id))}
        if premios:
            item.update(
                estado='salio', premios=premios,
                tombola=sorted(str(t.number_id.name).zfill(2)
                               for t in tombola if t.turno_id == turno))
        else:
            item['estado'] = 'pendiente' if pendiente_ok else 'sin_resultado'
        turnos.append(item)
    if not turnos:
        return None
    con_logo = next((s for s in quiniela if s.image_128), primero)
    return {'tipo': 'quiniela', 'id': con_logo.id, 'nombre': 'Quiniela Uruguaya',
            'logo': _logo_url(con_logo), 'iniciales': 'QU', 'turnos': turnos}


def construir_dia(env, dia, hoy):
    """Todo lo que salió (y lo que falta) en `dia`, de todas las loterías
    habilitadas para la web, agrupado por país."""
    Sorteo = env['lottery.sorteo'].sudo()
    publicos = Sorteo.search([('show_in_public', '=', True)], order='sequence, id')
    quiniela = Sorteo
    if any(s.source_code == QUINIELA_UY for s in publicos):
        quiniela = Sorteo.search([('source_code', '=', QUINIELA_UY)], order='sequence, id')
    normales = publicos.filtered(lambda s: s.source_code != QUINIELA_UY)

    salidas = env['lottery.output'].sudo().search(
        [('date', '=', dia), ('sorteo_id', 'in', (normales | quiniela).ids)])
    por_sorteo = {}
    for s in salidas:
        por_sorteo.setdefault(s.sorteo_id.id, {})[s.turno_id.id] = s

    # Un turno sin salida está "pendiente" hoy y en fechas futuras; en un día
    # pasado simplemente no hay resultado.
    pendiente_ok = dia >= hoy
    por_pais = {}
    for sorteo in normales:
        turnos = _turnos_dia(sorteo, dia, por_sorteo.get(sorteo.id, {}), pendiente_ok)
        if not turnos:
            continue
        por_pais.setdefault(sorteo.country_id.code or '', []).append({
            'tipo': 'sorteo',
            'id': sorteo.id,
            'nombre': sorteo.name,
            'logo': _logo_url(sorteo),
            'iniciales': _iniciales(sorteo.name),
            # Solo un número de 2 cifras (sin centena, bola extra ni corridos):
            # la portada junta sus turnos de a dos para que no queden en una
            # columna larguísima (La Diaria tiene 3 o 4 por día).
            'simple': not (sorteo.uses_hundreds or sorteo.uses_fireball or sorteo.is_pick3),
            'turnos': turnos,
        })
    if quiniela:
        item = _quiniela_uy(env, quiniela, dia, por_sorteo, pendiente_ok)
        if item:
            por_pais.setdefault(quiniela[0].country_id.code or 'UY', []).append(item)

    orden = [c for c in PAISES_ORDEN if c in por_pais]
    orden += [c for c in por_pais if c not in PAISES_ORDEN]
    paises = []
    for codigo in orden:
        nombre = PAISES_NOMBRE.get(codigo)
        if not nombre:
            pais = env['res.country'].sudo().search([('code', '=', codigo)], limit=1)
            nombre = pais.name if pais else 'Otras loterías'
        paises.append({'codigo': codigo, 'nombre': nombre, 'flag': _flag(codigo),
                       'loterias': por_pais[codigo]})
    return {
        'fecha': dia.isoformat(),
        'fecha_larga': '%s %d de %s' % (DIAS[dia.weekday()], dia.day, MESES[dia.month - 1]),
        'es_hoy': dia == hoy,
        'paises': paises,
    }


class LotteryPortalDia(models.AbstractModel):
    _name = 'lottery.portal.dia'
    _description = 'Resultados del día de la portada (con caché)'

    @api.model
    def get_dia(self, fecha=None):
        """Día pedido (ISO 'YYYY-MM-DD'; vacío o inválido = hoy) listo para
        devolver por JSON. El resultado viene de la caché: no se modifica."""
        tz = pytz.timezone(self.env.company.sudo().partner_id.tz or 'America/Montevideo')
        hoy = datetime.now(pytz.utc).astimezone(tz).date()
        try:
            dia = datetime.strptime(fecha, '%Y-%m-%d').date() if fecha else hoy
        except (TypeError, ValueError):
            dia = hoy
        return self._dia_cacheado(dia.isoformat(), hoy.isoformat(), int(time.time() // 600))

    @api.model
    @tools.ormcache('self.env.company.id', 'dia_iso', 'hoy_iso', 'tramo')
    def _dia_cacheado(self, dia_iso, hoy_iso, tramo):
        return construir_dia(
            self.env, datetime.strptime(dia_iso, '%Y-%m-%d').date(),
            datetime.strptime(hoy_iso, '%Y-%m-%d').date())

    @api.model
    def invalidar(self):
        # Odoo solo admite sus cachés con nombre fijo: se usa la general (la
        # misma que ya borra el recálculo de estadísticas al registrar una salida).
        self.env.registry.clear_cache()


class _InvalidaPortalDia(models.AbstractModel):
    """Mixin: cualquier alta, cambio o baja borra la caché del día."""
    _name = 'lottery.portal.dia.invalida'
    _description = 'Invalida la caché de resultados del día'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.env['lottery.portal.dia'].invalidar()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.env['lottery.portal.dia'].invalidar()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['lottery.portal.dia'].invalidar()
        return res


class LotteryOutput(models.Model):
    _name = 'lottery.output'
    _inherit = ['lottery.output', 'lottery.portal.dia.invalida']


class LotteryTombolaOutput(models.Model):
    _name = 'lottery.tombola.output'
    _inherit = ['lottery.tombola.output', 'lottery.portal.dia.invalida']


class LotterySorteo(models.Model):
    _name = 'lottery.sorteo'
    _inherit = ['lottery.sorteo', 'lottery.portal.dia.invalida']


class LotterySorteoSlot(models.Model):
    _name = 'lottery.sorteo.slot'
    _inherit = ['lottery.sorteo.slot', 'lottery.portal.dia.invalida']


class LotteryTurno(models.Model):
    _name = 'lottery.turno'
    _inherit = ['lottery.turno', 'lottery.portal.dia.invalida']
