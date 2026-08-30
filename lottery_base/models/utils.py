# -*- coding: utf-8 -*-
from odoo import fields

MAPPING_WEEK_DATE = {0: 'lu', 1: 'ma', 2: 'mi', 3: 'ju', 4: 'vi', 5: 'sa', 6: 'do'}


def default_today_local(self):
    """Fecha de hoy en la zona horaria del usuario, no la del servidor.
    fields.Date.today() usa hora del servidor (UTC): pasadas las 21:00 en
    Uruguay (UTC-3) el servidor ya está en el día siguiente y proponía esa
    fecha por default en Salidas/Curiosidades/Predicciones."""
    return fields.Datetime.context_timestamp(self, fields.Datetime.now()).date()

MONTHS = [
    ('1', 'Enero'),
    ('2', 'Febrero'),
    ('3', 'Marzo'),
    ('4', 'Abril'),
    ('5', 'Mayo'),
    ('6', 'Junio'),
    ('7', 'Julio'),
    ('8', 'Agosto'),
    ('9', 'Septiembre'),
    ('10', 'Octubre'),
    ('11', 'Noviembre'),
    ('12', 'Diciembre'),
]

MONTHS_DICT = {
    '1': 'Enero',
    '2': 'Febrero',
    '3': 'Marzo',
    '4': 'Abril',
    '5': 'Mayo',
    '6': 'Junio',
    '7': 'Julio',
    '8': 'Agosto',
    '9': 'Septiembre',
    '10': 'Octubre',
    '11': 'Noviembre',
    '12': 'Diciembre'
}

MONTHS_ABREV = {
    '1': 'ENE',
    '2': 'FEB',
    '3': 'MAR',
    '4': 'ABR',
    '5': 'MAY',
    '6': 'JUN',
    '7': 'JUL',
    '8': 'AGO',
    '9': 'SEP',
    '10': 'OCT',
    '11': 'NOV',
    '12': 'DIC'
}