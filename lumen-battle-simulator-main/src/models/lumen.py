from dataclasses import dataclass, field
from typing import List, Optional
from src.models.enums import Element, Rarity, MoveCategory, CodeTraitGrade
from dataclasses import dataclass, field
from typing import List, Optional
from src.models.enums import Element, CodeTraitGrade, MoveCategory

@dataclass
class LumenSpecies:
    codex_number: int  # ID sequencial no Códice (1, 2, 3...)
    species_name: str
    primary_type: Element
    secondary_type: Optional[Element] = None
    base_hp: int = 45
    base_attack: int = 49
    base_defense: int = 49
    base_sp_attack: int = 65
    base_sp_defense: int = 65
    base_speed: int = 45
    evolution_level: Optional[int] = None  # Nível para evoluir para ID + 1 (None = forma final)
@dataclass
class Skill:
    name: str
    element: Element
    category: MoveCategory
    power: int
    accuracy: float
    max_pp: int
    current_pp: int

@dataclass
class LumenSpecies:
    codex_number: int
    species_name: str
    primary_type: Element
    secondary_type: Optional[Element] = None
    base_hp: int = 45
    base_attack: int = 49
    base_defense: int = 49
    base_sp_attack: int = 65
    base_sp_defense: int = 65
    base_speed: int = 45

@dataclass
class Lumen:
    id: Optional[int]
    nickname: str
    species: LumenSpecies
    level: int = 1
    experience: int = 0
    is_shiny: bool = False
    resonance_rank: int = 1
    code_trait: CodeTraitGrade = CodeTraitGrade.C
    skills: List[Skill] = field(default_factory=list)
    current_hp: int = field(init=False)

    def __post_init__(self):
        self.current_hp = self.total_hp

    @property
    def total_hp(self) -> int:
        return int((self.species.base_hp * 2 * self.code_trait.value * self.level / 100) + self.level + 10)

    @property
    def total_attack(self) -> int:
        return int((self.species.base_attack * 2 * self.code_trait.value * self.level / 100) + 5)

    @property
    def total_defense(self) -> int:
        return int((self.species.base_defense * 2 * self.code_trait.value * self.level / 100) + 5)

    @property
    def total_sp_attack(self) -> int:
        return int((self.species.base_sp_attack * 2 * self.code_trait.value * self.level / 100) + 5)

    @property
    def total_sp_defense(self) -> int:
        return int((self.species.base_sp_defense * 2 * self.code_trait.value * self.level / 100) + 5)

    @property
    def total_speed(self) -> int:
        return int((self.species.base_speed * 2 * self.code_trait.value * self.level / 100) + 5)

    def is_alive(self) -> bool:
        return self.current_hp > 0