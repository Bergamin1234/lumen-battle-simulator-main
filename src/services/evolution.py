import logging
from typing import Dict
from src.models.lumen import Lumen, LumenSpecies
from src.core.formulas import xp_required_for_level

logging.basicConfig(level=logging.INFO)

# Códice Global em Memória
CODEX_REGISTRY: Dict[int, LumenSpecies] = {}

class EvolutionService:
    @classmethod
    def register_species(cls, species: LumenSpecies) -> None:
        """Cadastra a espécie usando seu ID sequencial do Códice."""
        CODEX_REGISTRY[species.codex_number] = species

    @classmethod
    def add_experience(cls, lumen: Lumen, xp_amount: int) -> dict:
        """Processa ganho de XP, subida de nível e dispara a evolução sequencial se elegível."""
        lumen.experience += xp_amount
        leveled_up = False

        while lumen.experience >= xp_required_for_level(lumen.level):
            lumen.experience -= xp_required_for_level(lumen.level)
            lumen.level += 1
            leveled_up = True
            logging.info(f"⬆️  {lumen.nickname} subiu para o nível {lumen.level}!")

        if leveled_up:
            lumen.current_hp = lumen.total_hp

        evolved = cls.try_evolve(lumen)

        return {
            "leveled_up": leveled_up,
            "current_level": lumen.level,
            "evolved": evolved,
            "codex_id": lumen.species.codex_number,
            "species_name": lumen.species.species_name
        }

    @classmethod
    def can_evolve(cls, lumen: Lumen) -> bool:
        """Checa se a espécie atual tem nível de evolução e se a próxima ID (N+1) existe no Códice."""
        current_species = lumen.species
        
        # Forma final (não possui nível de evolução cadastrado)
        if current_species.evolution_level is None:
            return False

        # Valida nível atual e existência da próxima ID no Códice
        next_codex_id = current_species.codex_number + 1
        return lumen.level >= current_species.evolution_level and next_codex_id in CODEX_REGISTRY

    @classmethod
    def try_evolve(cls, lumen: Lumen) -> bool:
        """Aplica a transformação para a espécie do ID subsequente (N+1)."""
        if not cls.can_evolve(lumen):
            return False

        current_id = lumen.species.codex_number
        next_id = current_id + 1
        next_species = CODEX_REGISTRY[next_id]

        old_name = lumen.species.species_name
        lumen.species = next_species
        lumen.current_hp = lumen.total_hp

        logging.info(
            f"✨ EVOLUÇÃO! {lumen.nickname} ({old_name} [#{current_id}]) "
            f"evoluiu para {next_species.species_name} [#{next_id}]!"
        )
        return True