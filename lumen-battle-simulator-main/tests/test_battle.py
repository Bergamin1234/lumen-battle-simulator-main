import unittest
from src.models.lumen import Lumen, Skill, LumenSpecies
from src.models.enums import Element, Rarity, AIStrategyType
from src.core.battle import BattleEngine
from src.core.elements import get_elemental_multiplier


class TestBattleCore(unittest.TestCase):
    def test_elemental_multiplier(self):
        self.assertEqual(get_elemental_multiplier(Element.WATER, Element.FIRE), 2.0)
        self.assertEqual(get_elemental_multiplier(Element.FIRE, Element.WATER), 0.5)

    def test_battle_execution(self):
        species_fire = LumenSpecies(codex_number=4, species_name="Emberpup", primary_type=Element.FIRE)
        species_water = LumenSpecies(codex_number=7, species_name="Aquashell", primary_type=Element.WATER)

        skill = Skill(name="Ataque", element=Element.FIRE, power=30, energy_cost=5, accuracy=1.0)
        l1 = Lumen(id=1, nickname="FireLumen", species=species_fire, skills=[skill])
        l2 = Lumen(id=2, nickname="WaterLumen", species=species_water, skills=[skill])

        engine = BattleEngine(l1, l2, AIStrategyType.AGGRESSIVE, AIStrategyType.AGGRESSIVE)
        result = engine.run()

        self.assertIn(result.winner, [l1, l2])
        self.assertGreater(result.turns, 0)


if __name__ == "__main__":
    unittest.main()