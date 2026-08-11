# src/ai/strategy.py
import random
from abc import ABC, abstractmethod
from typing import Optional
from src.models.lumen import Lumen, Skill
from src.models.enums import AIStrategyType

class BaseStrategy(ABC):
    @abstractmethod
    def choose_action(self, self_lumen: Lumen, target: Lumen) -> Optional[Skill]:
        pass

class AggressiveStrategy(BaseStrategy):
    def choose_action(self, self_lumen: Lumen, target: Lumen) -> Optional[Skill]:
        affordable = [s for s in self_lumen.skills if s.energy_cost <= self_lumen.current_energy]
        return max(affordable, key=lambda s: s.power) if affordable else None

class DefensiveStrategy(BaseStrategy):
    def choose_action(self, self_lumen: Lumen, target: Lumen) -> Optional[Skill]:
        affordable = [s for s in self_lumen.skills if s.energy_cost <= self_lumen.current_energy]
        # Prioriza skills de baixo custo de energia para preservar sustentabilidade
        return min(affordable, key=lambda s: s.energy_cost) if affordable else None

class BalancedStrategy(BaseStrategy):
    def choose_action(self, self_lumen: Lumen, target: Lumen) -> Optional[Skill]:
        affordable = [s for s in self_lumen.skills if s.energy_cost <= self_lumen.current_energy]
        if not affordable:
            return None
        return sorted(affordable, key=lambda s: (s.power / max(1, s.energy_cost)), reverse=True)[0]

class RandomStrategy(BaseStrategy):
    def choose_action(self, self_lumen: Lumen, target: Lumen) -> Optional[Skill]:
        affordable = [s for s in self_lumen.skills if s.energy_cost <= self_lumen.current_energy]
        return random.choice(affordable) if affordable else None

class AIStrategyFactory:
    @staticmethod
    def get_strategy(strategy_type: AIStrategyType) -> BaseStrategy:
        strategies = {
            AIStrategyType.AGGRESSIVE: AggressiveStrategy(),
            AIStrategyType.DEFENSIVE: DefensiveStrategy(),
            AIStrategyType.BALANCED: BalancedStrategy(),
            AIStrategyType.RANDOM: RandomStrategy()
        }
        return strategies.get(strategy_type, BalancedStrategy())