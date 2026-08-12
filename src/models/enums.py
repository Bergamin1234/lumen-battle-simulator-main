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


class AgentState(Enum):
    BOOT = auto()
    INACTIVE = auto()
    CALIBRATING = auto()
    SEARCHING_FARM = auto()
    EXPLORING = auto()
    BATTLE_DETECTED = auto()
    BATTLE = auto()
    SWITCHING_LUMEN = auto()
    BATTLE_RESULT = auto()
    EVALUATING_TEAM = auto()
    NAVIGATING_TO_HEAL = auto()
    SEARCHING_CRYSTAL = auto()
    HEALING = auto()
    VERIFYING_HEAL = auto()
    RETURNING_TO_FARM = auto()
    STUCK_RECOVERY = auto()
    UNKNOWN_STATE = auto()
    SAFE_STOP = auto()
    ERROR_RECOVERY = auto()


class MoveDirection(Enum):
    UP = "w"
    DOWN = "s"
    LEFT = "a"
    RIGHT = "d"
    UP_LEFT = "w+a"
    UP_RIGHT = "w+d"
    DOWN_LEFT = "s+a"
    DOWN_RIGHT = "s+d"
    INTERACT = "e"
    CANCEL = "esc"