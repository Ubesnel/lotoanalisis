# -*- coding: utf-8 -*-
"""Heurística de armado de la "Tabla LotoAnálisis": ubica los 100 números
(00-99) en una grilla intentando que los números "acompañantes" (según la
afinidad calculada en lottery.stats.service.get_companion_affinity) queden
en una celda adyacente (horizontal, vertical o diagonal).

Es un problema de tipo asignación cuadrática (NP-difícil para 100 nodos);
esto es una heurística de crecimiento tipo Prim: arranca del par con más
afinidad y va agregando, de a uno, el número no ubicado con mayor afinidad
a algún número ya ubicado, en la celda vacía adyacente que más afinidad
adicional sume con el resto de los ya colocados. No garantiza el óptimo,
pero da un buen resultado visual.

Las celdas decorativas (donde van las caritas) se reservan ANTES de ubicar
los números, no son simplemente lo que sobra: así se puede garantizar que
nunca queden dos consecutivas (ver decorative_cells) y quedan repartidas
por toda la grilla en vez de amontonarse en un borde.
"""
from .charada_data import charada_shared

NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1),
               (0, -1),           (0, 1),
               (1, -1),  (1, 0),  (1, 1)]
NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _subsample(cells, count):
    """`count` elementos de `cells`, lo más parejo posible según el orden
    en que vienen (no agrupados en un tramo) — sub-muestreo tipo Bresenham."""
    if count >= len(cells):
        return list(cells)
    step = len(cells) / count
    selected = []
    acc = 0.0
    for cell in cells:
        acc += 1
        if acc >= step and len(selected) < count:
            selected.append(cell)
            acc -= step
    # Redondeo de punto flotante: puede faltar 1 para llegar a `count`.
    if len(selected) < count:
        rest = [c for c in cells if c not in selected]
        selected.extend(rest[:count - len(selected)])
    return selected


def decorative_cells(size, count):
    """`count` celdas repartidas por toda la grilla para el relleno
    decorativo (las "caritas"), nunca dos consecutivas entre sí.

    Primero intenta que no se toquen ni siquiera en diagonal: celdas en
    fila Y columna par, separadas de a 2 (máximo ceil(size/2)**2 — para
    11x11 con 21 decorativas entra perfecto, ahí no se tocan ni en
    diagonal). Si no entran así (12x12 con 44 decorativas: el máximo sin
    tocarse en diagonal ahí es 36, no alcanza), cae a la garantía más
    débil pero que siempre entra: nunca dos pegadas en horizontal/vertical,
    apoyándose en que dos celdas de la misma paridad de (fila+columna)
    nunca son ortogonalmente adyacentes (patrón de tablero de ajedrez,
    hasta la mitad de las celdas de la grilla)."""
    diagonal_safe = [(r, c) for r in range(0, size, 2) for c in range(0, size, 2)]
    if count <= len(diagonal_safe):
        return set(_subsample(diagonal_safe, count))

    even_parity = [(r, c) for r in range(size) for c in range(size)
                   if (r + c) % 2 == 0]
    return set(_subsample(even_parity, count))


def _weight(affinity, a, b):
    key = (a, b) if a < b else (b, a)
    return affinity.get(key, 0)


def _nearest_available_cell(grid, reserved, placed, size):
    """Celda disponible (no ocupada, no reservada) más cercana al centroide
    de lo ya ubicado — fallback para números sin afinidad positiva con nada
    de lo colocado (raro, pero posible con fechas de corte muy tempranas),
    y para elegir la celda semilla inicial."""
    if placed:
        rs = [p[0] for p in placed.values()]
        cs = [p[1] for p in placed.values()]
        cr, cc = sum(rs) // len(rs), sum(cs) // len(cs)
    else:
        cr, cc = size // 2, size // 2
    best = None
    for r in range(size):
        for c in range(size):
            if (r, c) in grid or (r, c) in reserved:
                continue
            d = max(abs(r - cr), abs(c - cc))
            if best is None or d < best[0]:
                best = (d, (r, c))
    return best[1]


def build_grid(affinity, size=12, numbers=range(100)):
    """Devuelve (grid, empty_cells).

    grid: dict {(row, col): numero} — exactamente len(numbers) entradas.
    empty_cells: lista de (row, col) decorativas (nunca dos ortogonalmente
    consecutivas), para el relleno con las caritas.
    """
    numbers = list(numbers)
    reserved = decorative_cells(size, size * size - len(numbers))
    grid = {}
    placed = {}

    def cell_ok(r, c):
        return (0 <= r < size and 0 <= c < size
                and (r, c) not in grid and (r, c) not in reserved)

    def place(n, cell):
        grid[cell] = n
        placed[n] = cell

    if affinity:
        (a, b), _ = max(affinity.items(), key=lambda kv: kv[1])
    else:
        a, b = numbers[0], numbers[1] if len(numbers) > 1 else numbers[0]

    seed = _nearest_available_cell(grid, reserved, {}, size)
    place(a, seed)
    if b != a:
        for dr, dc in NEIGHBORS_8:
            cell = (seed[0] + dr, seed[1] + dc)
            if cell_ok(*cell):
                place(b, cell)
                break

    remaining = [n for n in numbers if n not in placed]

    while remaining:
        best = None  # (local_score, charada_bonus, weight) , unplaced, cell
        for u in remaining:
            for p, (pr, pc) in placed.items():
                w = _weight(affinity, u, p)
                if w <= 0:
                    continue
                for dr, dc in NEIGHBORS_8:
                    cell = (pr + dr, pc + dc)
                    if not cell_ok(*cell):
                        continue
                    r, c = cell
                    local_score = sum(
                        _weight(affinity, u, grid[(r + ddr, c + ddc)])
                        for ddr, ddc in NEIGHBORS_8
                        if (r + ddr, c + ddc) in grid
                    )
                    charada_bonus = charada_shared(u, p)
                    candidate = (local_score, charada_bonus, w)
                    if best is None or candidate > best[0]:
                        best = (candidate, u, cell)
        if best is None:
            # Nadie ubicado tiene afinidad positiva con lo que queda —
            # no hay celda "correcta", se pone en la más cercana al grupo.
            u = remaining[0]
            cell = _nearest_available_cell(grid, reserved, placed, size)
            place(u, cell)
            remaining.remove(u)
            continue
        _, u, cell = best
        place(u, cell)
        remaining.remove(u)

    return grid, sorted(reserved)
