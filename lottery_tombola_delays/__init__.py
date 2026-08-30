# -*- coding: utf-8 -*-
from . import models


def _initial_recompute(env):
    """Al instalar, calcula las estadísticas sobre el histórico de Tómbola
    ya cargado (el pipeline dirty solo recalcula hacia adelante, a partir
    del próximo create/write/unlink)."""
    env['lottery.tombola.number.stat'].cron_recompute_all()
