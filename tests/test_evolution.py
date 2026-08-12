import unittest
from src.models.lumen import Lumen, LumenSpecies
from src.models.enums import Element, CodeTraitGrade
from src.services.evolution import EvolutionService


class TestEvolutionService(unittest.TestCase):
    def test_lumen_level_up(self):
        species = LumenSpecies(
            codex_number=1,
            species_name="Charm",
            primary_type=Element.FIRE,
        )
        lumen = Lumen(
            id=1,
            nickname="Spark",
            species=species,
            level=1,
            code_trait=CodeTraitGrade.C,
        )

        # Adiciona XP suficiente para subir de nível
        result = EvolutionService.add_experience(lumen, 150)

        self.assertTrue(result["leveled_up"])
        self.assertGreater(lumen.level, 1)

    def test_stat_recalculation_on_level_up(self):
        species = LumenSpecies(
            codex_number=2,
            species_name="Leaf",
            primary_type=Element.GRASS,
            base_hp=50,
        )
        lumen = Lumen(
            id=2,
            nickname="Sprout",
            species=species,
            level=1,
            code_trait=CodeTraitGrade.C,
        )

        old_hp = lumen.total_hp
        EvolutionService.add_experience(lumen, 200)

        # Valida se os atributos reagem e sobem com o novo nível
        self.assertGreater(lumen.total_hp, old_hp)


if __name__ == "__main__":
    unittest.main()