from enum import Enum, auto

class Element(Enum):
    NORMAL = "normal"
    FIRE = "fogo"
    WATER = "água"
    GRASS = "planta"
    ELECTRIC = "elétrico"
    ICE = "gelo"
    FIGHTING = "lutador"
    POISON = "venenoso"
    GROUND = "terrestre"
    FLYING = "voador"
    PSYCHIC = "psíquico"
    BUG = "inseto"
    ROCK = "pedra"
    GHOST = "fantasma"
    DRAGON = "dragão"
    DARK = "sombrio"
    STEEL = "aço"
    FAIRY = "fada"

class CodeTraitGrade(Enum):
    E = 0.8
    D = 0.9
    C = 1.0
    B = 1.1
    A = 1.2
    S = 1.3

class MoveCategory(Enum):
    PHYSICAL = "físico"
    SPECIAL = "especial"
    STATUS = "status"

class Rarity(Enum):
    COMMON = 1.0
    UNCOMMON = 1.2
    RARE = 1.5
    EPIC = 1.8
    LEGENDARY = 2.2

class StatusEffect(Enum):
    NONE = auto()
    BURN = auto()
    FREEZE = auto()
    PARALYSIS = auto()
    POISON = auto()

class AIStrategyType(Enum):
    AGGRESSIVE = "agressiva"
    DEFENSIVE = "defensiva"
    BALANCED = "equilibrada"
    RANDOM = "aleatória"
    RL_AGENT = "aprendizado_reforco"