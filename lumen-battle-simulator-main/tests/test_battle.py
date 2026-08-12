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
    species_fire = LumenSpecies(codex_number=4, species_name="Emberpup", primary_type=Element.FIRE)
    species_water = LumenSpecies(codex_number=7, species_name="Aquashell", primary_type=Element.WATER)

    skill = Skill(name="Ataque", element=Element.FIRE, power=30, energy_cost=5, accuracy=1.0)
    l1 = Lumen(id=1, nickname="FireLumen", species=species_fire, skills=[skill])
    l2 = Lumen(id=2, nickname="WaterLumen", species=species_water, skills=[skill])

    engine = BattleEngine(l1, l2, AIStrategyType.AGGRESSIVE, AIStrategyType.AGGRESSIVE)
    result = engine.run()

    assert result.winner in [l1, l2]
    assert result.turns > 0