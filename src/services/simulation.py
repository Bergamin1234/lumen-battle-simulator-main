# src/services/simulation.py
from dataclasses import dataclass
from src.core.battle import BattleEngine
from src.models.lumen import Lumen
from src.models.enums import AIStrategyType

@dataclass
class SimulationMetrics:
    total_battles: int
    wins_a: int
    wins_b: int
    avg_turns: float
    win_rate_a: float

class MassSimulator:
    def __init__(self, lumen_a_factory, lumen_b_factory):
        self.lumen_a_factory = lumen_a_factory
        self.lumen_b_factory = lumen_b_factory

    def run_benchmark(self, rounds: int, strat_a: AIStrategyType, strat_b: AIStrategyType) -> SimulationMetrics:
        wins_a = 0
        wins_b = 0
        total_turns = 0

        for _ in range(rounds):
            lumen_a: Lumen = self.lumen_a_factory()
            lumen_b: Lumen = self.lumen_b_factory()
            
            engine = BattleEngine(lumen_a, lumen_b, strat_a, strat_b)
            result = engine.run()

            total_turns += result.turns
            if result.winner.name == lumen_a.name:
                wins_a += 1
            else:
                wins_b += 1

        return SimulationMetrics(
            total_battles=rounds,
            wins_a=wins_a,
            wins_b=wins_b,
            avg_turns=total_turns / rounds,
            win_rate_a=(wins_a / rounds) * 100
        )