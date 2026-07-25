# -*- coding: utf-8 -*-
"""Charada Cubana: nombre principal + alias por número (00-99).

Copia server-side del dataset canónico de la app Flutter
(E:\\Trabajo\\Flutter\\lottery_app\\lib\\data\\charada.dart) — se usa solo
como criterio de desempate en la Tabla LotoAnálisis (lottery_tabla_
acompanantes.py), no se expone por API. Si se actualiza uno, actualizar
el otro.
"""

CHARADA = {
    0: ('Inodoro', ['Dios', 'Escoba', 'Automóvil']),
    1: ('Caballo', ['Sol', 'Tintero', 'Camello', 'Pescado chico']),
    2: ('Mariposa', ['Hombre', 'Cafetera', 'Caracol']),
    3: ('Marinero', ['Luna', 'Taza', 'Ciempiés', 'Muerto']),
    4: ('Gato', ['Soldado', 'Llave', 'Vela', 'Militar', 'Pavo Real']),
    5: ('Monja', ['Mar', 'Candado', 'Periódico', 'Fruta', 'Lombriz']),
    6: ('Jicotea', ['Carta', 'Reverbero', 'Botella', 'Luna']),
    7: ('Caracol', ['Sueño', 'Heces Fecales', 'Medias', 'Caballero', 'Cochino']),
    8: ('Muerto', ['León', 'Calabaza', 'Mesa', 'Tigre']),
    9: ('Elefante', ['Entierro', 'Lira', 'Cubo', 'Esqueleto', 'Buey']),
    10: ('Pescado Grande', ['Paseo', 'Malla', 'Cazuela', 'Dinero', 'Lancha']),
    11: ('Gallo', ['Lluvia', 'Fósforo', 'Taller', 'Fábrica', 'Caballo']),
    12: ('Mujer Santa', ['Viaje', 'Toallas', 'Cometa', 'Dama', 'Perro Grande']),
    13: ('Pavo Real', ['Niño', 'Anafe', 'Souteneur', 'Elefante']),
    14: ('Gato Tigre', ['Matrimonio', 'Arreste', 'Sartén', 'Cementerio']),
    15: ('Perro', ['Visita', 'Cuchara', 'Gallo', 'Ratón']),
    16: ('Toro', ['Plancha', 'Vestido', 'Incendio pequeño', 'Funerales', 'Avispa']),
    17: ('Luna', ['Mujer buena', 'Hule', 'Camisón', 'Armas', 'Fumar opio']),
    18: ('Pescado Chiquito', ['Iglesia', 'Sirena', 'Palma', 'Pescado', 'Gato amarillo']),
    19: ('Lombriz', ['Campesino', 'Tropa', 'Mesa Grande', 'Armadura', 'Jutía']),
    20: ('Gato Fino', ['Cañón', 'Camiseta', 'Orinal', 'Libro', 'Mujer']),
    21: ('Maja', ['Reloj de bolsillo', 'Chaleco', 'Cotorra', 'Cigarro', 'Gallo']),
    22: ('Sapo', ['Estrella', 'Lirio', 'Chimenea', 'Sol', 'Jicotea']),
    23: ('Vapor', ['Submarino', 'Monte', 'Escalera', 'Barco', 'Águila']),
    24: ('Paloma', ['Música', 'Carpintero', 'Cocina', 'Pescado Grande']),
    25: ('Piedra Fina', ['Casa', 'Sol', 'Monja', 'Rana']),
    26: ('Anguila', ['Calle', 'Médico', 'Brillante', 'Nube de Oro']),
    27: ('Avispa', ['Campana', 'Cuchara Grande', 'Canario', 'Baúl', 'Mono']),
    28: ('Chivo', ['Bandera', 'Político', 'Uvas', 'Perro Chico']),
    29: ('Ratón', ['Nube', 'Venado', 'Águila']),
    30: ('Camarón', ['Arco Iris', 'Almanaque', 'Buey', 'Cangrejo', 'Chivo']),
    31: ('Venado', ['Escuela', 'Zapatos', 'Pato']),
    32: ('Cochino', ['Enemigo', 'Mulo', 'Demonio', 'Maja']),
    33: ('Tiñosa', ['Baraja', 'Santa', 'Jesucristo', 'Bofetón', 'Camarón']),
    34: ('Mono', ['Familia', 'Negro', 'Capataz', 'Paloma']),
    35: ('Araña', ['Novia', 'Bombillos', 'Mosquito', 'Mariposa']),
    36: ('Cachimba', ['Teatro', 'Bodega', 'Opio', 'Coloso', 'Pajarito']),
    37: ('Gallina Prieta', ['Gitana', 'Hormiga', 'Carretera', 'Piedra Fina']),
    38: ('Dinero', ['Macao', 'Carro', 'Goleta', 'Guantes', 'Barril']),
    39: ('Conejo', ['Culebra', 'Rayo', 'Baile', 'Tintorero']),
    40: ('Cura', ['Sangre', 'Bombero', 'Muchacho Maldita', 'Cantina', 'Estatua']),
    41: ('Lagartija', ['Prisión', 'Pato Chico', 'Jubo', 'Capuchino', 'Clarín']),
    42: ('Pato', ['País Lejano', 'Carnero', 'España', 'Abismo', 'Liga']),
    43: ('Alacrán', ['Amigo', 'Vaca', 'Puerta', 'Presidiario', 'Jorobado']),
    44: ('Tormenta', ['Año del Cuero', 'Infierno', 'Año Malo', 'Temporal', 'Plancha']),
    45: ('Tiburón', ['Presidente', 'Traje', 'Tranvía', 'Escuela', 'Estrella']),
    46: ('Guagua', ['Humo', 'Hambre', 'Hurón', 'Baile', 'Chino']),
    47: ('Pájaro', ['Mala Noticia', 'Mucha Sangre', 'Escolta', 'Gallo', 'Rosa']),
    48: ('Cucaracha', ['Abanico', 'Barbería', 'Cubo']),
    49: ('Borracho', ['Riqueza', 'Figurín', 'Percha', 'Tesoro', 'Fantasma']),
    50: ('Policía', ['Alegría', 'Florero', 'Alcalde', 'Pícaro', 'Árbol']),
    51: ('Soldado', ['Sed', 'Oro', 'Sereno', 'Anteojos', 'Presillas']),
    52: ('Bicicleta', ['Coche', 'Borracho', 'Abogado', 'Riña', 'Libreta']),
    53: ('Luz Eléctrica', ['Prenda', 'Tragedia', 'Diamante', 'Beso', 'Alguacil']),
    54: ('Flores', ['Gallina Blanca', 'Sueño', 'Timbre', 'Cañón', 'Rosas']),
    55: ('Cangrejo', ['Baile', 'Iglesia Grande', 'Los Isleños', 'Caerse', 'Sellos']),
    56: ('Reina Escorpión', ['Pato Grande', 'Merengue', 'Piedra', 'Cara']),
    57: ('Cama', ['Ángeles', 'Telegrama', 'Puerta']),
    58: ('Adulterio', ['Retrato', 'Cuchillo', 'Cangrejo', 'Ferretero', 'Batea']),
    59: ('Loco', ['Fonógrafo', 'Langosta', 'Anillo', 'Araña Grande']),
    60: ('Payaso', ['Sol Oscuro', 'Cómico', 'Tempestad', 'Avecillas']),
    61: ('Cañonazo', ['Piedra Grande', 'Revolver', 'Boticario', 'Pintor', 'Saco']),
    62: ('Matrimonio', ['Nieve', 'Lámpara', 'Visión', 'Academia', 'Carretilla']),
    63: ('Asesino', ['Cuernos', 'Espada', 'Bandidos', 'Caracol', 'Escalera']),
    64: ('Muerto Grande', ['Tiro de Rifle', 'Maromero', 'Relajo', 'Vahos', 'Fiera']),
    65: ('Cárcel', ['Comida', 'Bruja', 'Ventana', 'Trueno']),
    66: ('Carnaval', ['Divorcio', 'Tarros', 'Máscara', 'Estrella', 'Mudada']),
    67: ('Puñalada', ['Reloj', 'Autoridad', 'Fonda', 'Aborto', 'Zapato']),
    68: ('Cementerio Grande', ['Globo', 'Cuchillo Grande', 'Templo', 'Bolos', 'Dinero']),
    69: ('Polvorín', ['Pozo', 'Fiera', 'Loma', 'Vagos']),
    70: ('Teléfono', ['Coco', 'Tiro', 'Barril', 'Arco Iris', 'Bala']),
    71: ('Sombrero', ['Riñó', 'Perro Mediano', 'Pantera', 'Fusil']),
    72: ('Ferrocarril', ['Buey Viejo', 'Serrucho', 'Collar', 'Cetro', 'Relámpago']),
    73: ('Parque', ['Navaja', 'Manzanas', 'Maleta', 'Ajedrez', 'Cigarrillo']),
    74: ('Papalote', ['Coronel', 'Serpiente', 'Cólera', 'Tarima']),
    75: ('Cine', ['Corbata', 'Viento', 'Guitarra', 'Flores', 'Quiosco']),
    76: ('Bailarina', ['Humo en Cantidad', 'Caja de Hierro', 'Violín', 'Iluminaciones', 'Represa']),
    77: ('Banderas', ['Guerra', 'Colegio', 'Billetes de Banco', 'Ánfora']),
    78: ('Rey', ['Obispo', 'Tigre', 'Sarcófago', 'Apetito', 'Lunares']),
    79: ('Coche', ['Lagarto', 'Abogado', 'Tren de Viajeros', 'Dulces']),
    80: ('Médico', ['Buena Noticia', 'Luna Llena', 'Paraguas', 'Barba', 'Trompo']),
    81: ('Teatro', ['Barco', 'Navaja Grande', 'Ingeniero', 'Cuerda', 'Actriz']),
    82: ('Madre', ['León', 'Batea', 'Pleito', 'Estrella', 'Muelle']),
    83: ('Tragedia', ['Procesión', 'Limosnero', 'Bastón', 'Madera']),
    84: ('Ciego', ['Sastre', 'Bohío', 'Banquero', 'Cofre', 'Marcha Atrás']),
    85: ('Avión', ['Reloj', 'Madrid', 'Águila', 'Espejo', 'Guano']),
    86: ('Convento', ['Marino', 'Ardilla', 'Tijera', 'Desnudar', 'Palma']),
    87: ('Nueva York', ['Baúl', 'Paloma', 'Fuego', 'Plátanos']),
    88: ('Espejuelos', ['Gusano', 'Vaso', 'Hojas', 'Aduanero']),
    89: ('Lotería', ['Agua', 'Mona Vieja', 'Cometa', 'Melón', 'Tesorero']),
    90: ('Viejo', ['Espejo Grande', 'Caramelo', 'Temporal', 'Asesino']),
    91: ('Tranvía', ['Pájaro Negro', 'Limosnero', 'Alpargatas', 'Bolsas', 'Bolchevique']),
    92: ('Cuba', ['Globo muy Alto', 'Suicidio', 'Anarquista', 'Gato', 'León Grande']),
    93: ('Revolución', ['Sortija de Valor', 'General', 'Andarín', 'Joyas', 'Libertad']),
    94: ('Machete', ['Mariposa Grande', 'Leontina', 'Habana', 'Flores']),
    95: ('Guerra', ['Perro Grande', 'Alacrán Grande', 'Espada', 'Matanzas', 'Revolución']),
    96: ('Periódico', ['Desafió', 'Pícaro', 'Zapatos Nuevos', 'Roca', 'Mujer Santa']),
    97: ('Mosquito Grande', ['Mono Grande', 'Sinsonte', 'Grillo Grande', 'Correr', 'Limosnero']),
    98: ('Piano', ['Entierro Grande', 'Traición', 'Visita Regia', 'Fonógrafo', 'Ortofónica']),
    99: ('Lluvia', ['Serrucho', 'Gallo Grande', 'Temporal muy Grande', 'Carbonero']),
}

# Colores por decena (00-09, 10-19, ...), copiados de charadaDecadeColors en
# la app — se usan para las bolitas de la Tabla LotoAnálisis.
DECADE_COLORS = [
    (0x7B, 0x2F, 0xF7),  # 00-09
    (0x15, 0x65, 0xC0),  # 10-19
    (0x00, 0x89, 0x7B),  # 20-29
    (0xE9, 0x1E, 0x63),  # 30-39
    (0x6A, 0x1B, 0x9A),  # 40-49
    (0x00, 0x97, 0xA7),  # 50-59
    (0xC6, 0x28, 0x28),  # 60-69
    (0x38, 0x8E, 0x3C),  # 70-79
    (0xE6, 0x51, 0x00),  # 80-89
    (0x28, 0x35, 0x93),  # 90-99
]


def charada_terms(number):
    """Set de términos (nombre + alias, normalizados) de un número 00-99."""
    entry = CHARADA.get(number)
    if not entry:
        return set()
    name, aliases = entry
    return {t.strip().lower() for t in [name, *aliases]}


def charada_shared(a, b):
    """Cantidad de términos en común entre dos números (0 si ninguno)."""
    return len(charada_terms(a) & charada_terms(b))
