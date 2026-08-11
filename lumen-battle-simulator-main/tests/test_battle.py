# tests/test_battle.py
import pytest
from src.models.lumen import Lumen, Skill
from src.models.enums import Element, Rarity, AIStrategyType
from src.core.battle import BattleEngine
from src.core.elements import get_elemental_multiplier

def test_elemental_multiplier():
    assert get_elemental_multiplier(Element.WATER, Element.FIRE) == 2.0
    assert get_elemental_multiplier(Element.FIRE, Element.WATER) == 0.5

def test_battle_execution():
    skill = Skill("Ataque", Element.FIRE, power=30, energy_cost=5, accuracy=1.0)
    l1 = Lumen(1, "FireLumen", Element.FIRE, Rarity.COMMON, skills=[skill])
    l2 = Lumen(2, "WaterLumen", Element.WATER, Rarity.COMMON, skills=[skill])

    engine = BattleEngine(l1, l2, AIStrategyType.AGGRESSIVE, AIStrategyType.AGGRESSIVE)
    result = engine.run()

    assert result.winner in [l1, l2]
    assert result.turns > 0