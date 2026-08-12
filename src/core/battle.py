# src/core/battle.py
import random
import logging
from dataclasses import dataclass
from src.models.lumen import Lumen, Skill
from src.core.elements import get_elemental_multiplier
from src.ai.strategy import AIStrategyFactory
from src.models.enums import AIStrategyType, StatusEffect

logging.basicConfig(level=logging.INFO)

@dataclass
class BattleResult:
    winner: Lumen
    loser: Lumen
    turns: int
    total_damage_dealt: dict[str, int]

class BattleEngine:
    def __init__(self, lumen_a: Lumen, lumen_b: Lumen, strat_a: AIStrategyType, strat_b: AIStrategyType):
        self.lumen_a = lumen_a
        self.lumen_b = lumen_b
        self.ai_a = AIStrategyFactory.get_strategy(strat_a)
        self.ai_b = AIStrategyFactory.get_strategy(strat_b)
        self.turns = 0
        self.damage_tracker = {lumen_a.name: 0, lumen_b.name: 0}

    def execute_turn(self) -> bool:
        self.turns += 1
        # Determina ordem por velocidade
        if self.lumen_a.total_speed >= self.lumen_b.total_speed:
            first, second = (self.lumen_a, self.ai_a), (self.lumen_b, self.ai_b)
        else:
            first, second = (self.lumen_b, self.ai_b), (self.lumen_a, self.ai_a)

        if self._perform_action(first[0], second[0], first[1]):
            return True
        if self._perform_action(second[0], first[0], second[1]):
            return True

        self._apply_end_turn_effects(self.lumen_a)
        self._apply_end_turn_effects(self.lumen_b)
        return not (self.lumen_a.is_alive() and self.lumen_b.is_alive())

    def _perform_action(self, attacker: Lumen, defender: Lumen, ai) -> bool:
        if not attacker.is_alive():
            return True
            
        # Regeneração passiva de energia
        attacker.current_energy = min(attacker.max_energy, attacker.current_energy + 5)
        
        skill = ai.choose_action(attacker, defender)
        if skill and attacker.current_energy >= skill.energy_cost:
            attacker.current_energy -= skill.energy_cost
            damage = self._calculate_damage(attacker, defender, skill)
            defender.current_hp = max(0, defender.current_hp - damage)
            self.damage_tracker[attacker.name] += damage

            if random.random() < skill.status_chance and defender.active_status == StatusEffect.NONE:
                defender.active_status = skill.status_effect
                defender.status_turns = 3

        return not defender.is_alive()

    def _calculate_damage(self, attacker: Lumen, defender: Lumen, skill: Skill) -> int:
        if random.random() > skill.accuracy:
            return 0  # Esquiva

        base_damage = (attacker.total_attack / defender.total_defense) * skill.power
        elem_mult = get_elemental_multiplier(skill.element, defender.element)
        crit_mult = 1.5 if random.random() < 0.1 else 1.0  # 10% crítico

        return max(1, int(base_damage * elem_mult * crit_mult))

    def _apply_end_turn_effects(self, lumen: Lumen) -> None:
        if lumen.status_turns > 0:
            if lumen.active_status == StatusEffect.BURN:
                lumen.current_hp = max(0, lumen.current_hp - 5)
            elif lumen.active_status == StatusEffect.POISON:
                lumen.current_hp = max(0, lumen.current_hp - 8)
            lumen.status_turns -= 1
            if lumen.status_turns == 0:
                lumen.active_status = StatusEffect.NONE

    def run(self) -> BattleResult:
        while not self.execute_turn() and self.turns < 100:
            pass
        
        winner = self.lumen_a if self.lumen_a.is_alive() else self.lumen_b
        loser = self.lumen_b if winner == self.lumen_a else self.lumen_a
        return BattleResult(winner, loser, self.turns, self.damage_tracker)