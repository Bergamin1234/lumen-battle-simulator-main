import math

def xp_required_for_level(level: int) -> int:
    """Calcula a quantidade de XP necessária para alcançar o próximo nível."""
    return int(100 * math.pow(level, 1.5))

def calculate_stat_growth(base_stat: int, level: int, growth_factor: float = 1.1) -> int:
    """Calcula a evolução de um atributo base com base no nível."""
    return int(base_stat * math.pow(growth_factor, level - 1))