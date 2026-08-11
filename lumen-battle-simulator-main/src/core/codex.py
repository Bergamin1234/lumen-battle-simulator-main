from typing import List, Tuple, Optional
from src.models.lumen import LumenSpecies
from src.models.enums import Element
from src.services.evolution import EvolutionService

# Tabela completa contendo as 150 espécies com IDs sequenciais autorais.
# Estrutura: (id, nome, tipo_1, tipo_2, hp, atk, def, sp_atk, sp_def, spd, nivel_evolucao)
SPECIES_CATALOG: List[Tuple[int, str, Element, Optional[Element], int, int, int, int, int, int, Optional[int]]] = [
    # --- Starters Elementais (IDs 1-9) ---
    (1, "Sproutling", Element.GRASS, None, 45, 49, 49, 65, 65, 45, 16),
    (2, "Floraguer", Element.GRASS, None, 60, 62, 63, 80, 80, 60, 36),
    (3, "Sylvanor", Element.GRASS, Element.POISON, 80, 82, 83, 100, 100, 80, None),
    (4, "Emberpup", Element.FIRE, None, 39, 52, 43, 60, 50, 65, 16),
    (5, "Pyrodog", Element.FIRE, None, 58, 64, 58, 80, 65, 80, 36),
    (6, "Infernus", Element.FIRE, Element.DARK, 78, 84, 78, 109, 85, 100, None),
    (7, "Aquashell", Element.WATER, None, 44, 48, 65, 50, 64, 43, 16),
    (8, "Tidecrest", Element.WATER, None, 59, 63, 80, 65, 80, 58, 36),
    (9, "Leviagorg", Element.WATER, Element.STEEL, 79, 83, 100, 85, 105, 78, None),

    # --- Insetos e Aves do Códice (IDs 10-18) ---
    (10, "Silkgrub", Element.BUG, None, 40, 35, 30, 20, 20, 50, 7),
    (11, "Chrysalis", Element.BUG, None, 50, 20, 55, 25, 25, 30, 10),
    (12, "Vesperoid", Element.BUG, Element.FLYING, 60, 45, 50, 90, 80, 70, None),
    (13, "Larvok", Element.BUG, None, 45, 30, 35, 20, 20, 45, 7),
    (14, "Toxipupa", Element.BUG, Element.POISON, 55, 25, 50, 25, 25, 35, 10),
    (15, "Venomoth", Element.BUG, Element.POISON, 70, 55, 50, 80, 75, 90, None),
    (16, "Fletchwing", Element.NORMAL, Element.FLYING, 40, 45, 40, 35, 35, 56, 18),
    (17, "Galehawk", Element.NORMAL, Element.FLYING, 63, 60, 55, 50, 50, 84, 32),
    (18, "Zephyrex", Element.ELECTRIC, Element.FLYING, 83, 80, 75, 70, 70, 121, None),

    # --- Terrestres e Elétricos (IDs 19-27) ---
    (19, "Rattlet", Element.NORMAL, None, 30, 56, 35, 25, 35, 72, 20),
    (20, "Verminax", Element.NORMAL, Element.DARK, 55, 81, 60, 50, 70, 97, None),
    (21, "Sparklure", Element.ELECTRIC, None, 35, 55, 40, 50, 50, 90, 22),
    (22, "Voltronis", Element.ELECTRIC, None, 60, 90, 55, 90, 80, 110, None),
    (23, "Duneclaw", Element.GROUND, None, 50, 75, 85, 20, 30, 40, 22),
    (24, "Terraquill", Element.GROUND, Element.STEEL, 75, 100, 110, 45, 55, 65, None),
    (25, "Igwan", Element.DRAGON, None, 41, 64, 45, 50, 50, 50, 30),
    (26, "Drakon", Element.DRAGON, Element.FLYING, 61, 84, 65, 70, 70, 70, 55),
    (27, "Wyrmlord", Element.DRAGON, Element.FLYING, 91, 134, 95, 100, 100, 100, None),

    # --- Minerais e Psíquicos (IDs 28-36) ---
    (28, "Geopup", Element.ROCK, Element.GROUND, 40, 80, 100, 30, 30, 20, 25),
    (29, "Gravelor", Element.ROCK, Element.GROUND, 55, 95, 115, 45, 45, 35, 40),
    (30, "Titanor", Element.ROCK, Element.GROUND, 80, 120, 130, 55, 65, 45, None),
    (31, "Ponyfire", Element.FIRE, None, 50, 85, 55, 65, 65, 90, 40),
    (32, "Blazesteed", Element.FIRE, Element.FAIRY, 65, 100, 70, 80, 80, 105, None),
    (33, "Slowslug", Element.WATER, Element.PSYCHIC, 90, 65, 65, 40, 40, 15, 37),
    (34, "Mindsnail", Element.WATER, Element.PSYCHIC, 95, 75, 80, 100, 110, 30, None),
    (35, "Spooklet", Element.GHOST, Element.POISON, 30, 35, 30, 100, 35, 80, 25),
    (36, "Spectron", Element.GHOST, Element.POISON, 45, 50, 45, 115, 55, 95, 40),

    # --- Místicos e Lutadores (IDs 37-45) ---
    (37, "Phantomlord", Element.GHOST, Element.POISON, 60, 65, 60, 130, 75, 110, None),
    (38, "Psikid", Element.PSYCHIC, None, 25, 20, 15, 105, 55, 90, 16),
    (39, "Mentis", Element.PSYCHIC, None, 40, 35, 30, 120, 70, 105, 36),
    (40, "Aethermind", Element.PSYCHIC, None, 55, 50, 45, 135, 95, 120, None),
    (41, "Brawny", Element.FIGHTING, None, 70, 80, 50, 35, 35, 35, 28),
    (42, "Combatant", Element.FIGHTING, None, 80, 100, 70, 50, 60, 45, 45),
    (43, "Warchief", Element.FIGHTING, None, 90, 130, 80, 65, 85, 55, None),
    (44, "Bellvine", Element.GRASS, Element.POISON, 50, 75, 35, 70, 30, 40, 21),
    (45, "Carnivora", Element.GRASS, Element.POISON, 65, 90, 50, 85, 45, 55, 36),

    # --- Elementais Mecânicos e Gelados (IDs 46-60) ---
    (46, "Viletrap", Element.GRASS, Element.POISON, 80, 105, 65, 100, 70, 70, None),
    (47, "Medusoid", Element.WATER, Element.POISON, 40, 40, 35, 50, 100, 70, 30),
    (48, "Krakenor", Element.WATER, Element.POISON, 80, 70, 65, 80, 120, 100, None),
    (49, "Coreling", Element.ELECTRIC, Element.STEEL, 25, 35, 70, 95, 55, 45, 30),
    (50, "Nodelect", Element.ELECTRIC, Element.STEEL, 50, 60, 95, 120, 70, 70, 48),
    (51, "Dynamocore", Element.ELECTRIC, Element.STEEL, 70, 70, 115, 130, 90, 60, None),
    (52, "Frosthog", Element.ICE, Element.GROUND, 50, 50, 40, 30, 30, 50, 33),
    (53, "Tundraswine", Element.ICE, Element.GROUND, 100, 100, 80, 60, 60, 50, 45),
    (54, "Glaciorix", Element.ICE, Element.GROUND, 110, 130, 80, 70, 60, 80, None),
    (55, "Snowsprout", Element.ICE, Element.GRASS, 60, 62, 50, 62, 60, 40, 40),
    (56, "Frostyeti", Element.ICE, Element.GRASS, 90, 92, 75, 92, 85, 60, None),
    (57, "Ironclad", Element.STEEL, Element.ROCK, 50, 70, 100, 40, 40, 30, 32),
    (58, "Bastion", Element.STEEL, Element.ROCK, 60, 90, 140, 50, 50, 40, 42),
    (59, "Dreadnaught", Element.STEEL, Element.ROCK, 70, 110, 180, 60, 60, 50, None),
    (60, "Slumberon", Element.NORMAL, None, 160, 110, 65, 65, 110, 30, None),
]


def _generate_synthetic_entries() -> None:
    """Gera proceduralmente as espécies autorais restantes (IDs 61 a 150)."""
    types = list(Element)
    for i in range(61, 151):
        line_position = (i - 1) % 3
        primary_type = types[i % len(types)]
        secondary_type = types[(i + 5) % len(types)] if i % 4 == 0 else None

        if line_position == 0:
            name = f"Lumen-Alpha-{i}"
            hp, atk, df, sp_a, sp_d, spd = 45, 50, 45, 55, 45, 50
            evo_lvl = 20
        elif line_position == 1:
            name = f"Lumen-Beta-{i}"
            hp, atk, df, sp_a, sp_d, spd = 65, 75, 65, 80, 65, 70
            evo_lvl = 40
        else:
            name = f"Lumen-Prime-{i}"
            hp, atk, df, sp_a, sp_d, spd = 85, 105, 85, 110, 85, 95
            evo_lvl = None

        SPECIES_CATALOG.append(
            (i, name, primary_type, secondary_type, hp, atk, df, sp_a, sp_d, spd, evo_lvl)
        )


def load_default_codex() -> None:
    """Carrega e registra o Códice completo contendo os 150 Lumens na memória RAM."""
    if len(SPECIES_CATALOG) < 150:
        _generate_synthetic_entries()

    for data in SPECIES_CATALOG:
        species = LumenSpecies(
            codex_number=data[0],
            species_name=data[1],
            primary_type=data[2],
            secondary_type=data[3],
            base_hp=data[4],
            base_attack=data[5],
            base_defense=data[6],
            base_sp_attack=data[7],
            base_sp_defense=data[8],
            base_speed=data[9],
            evolution_level=data[10]
        )
        EvolutionService.register_species(species)