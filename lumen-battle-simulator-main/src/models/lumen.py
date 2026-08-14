from dataclasses import dataclass, field
from typing import List, Optional
from src.models.enums import Element, Rarity, MoveCategory, CodeTraitGrade, StatusEffect, AgentState



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
    category: MoveCategory = MoveCategory.PHYSICAL
    power: int = 40
    accuracy: float = 1.0
    max_pp: int = 15
    current_pp: int = 15
    energy_cost: int = 5
    status_effect: StatusEffect = StatusEffect.NONE
    status_chance: float = 0.0

    def use(self) -> bool:
        if self.current_pp > 0:
            self.current_pp -= 1
            return True
        return False

    def restore_pp(self) -> None:
        self.current_pp = self.max_pp


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
    current_energy: int = 100
    max_energy: int = 100
    active_status: StatusEffect = StatusEffect.NONE
    status_turns: int = 0
    is_active: bool = False
    is_fainted: bool = False

    def __post_init__(self) -> None:
        self.current_hp = self.total_hp
        self.is_fainted = self.current_hp <= 0

    @property
    def name(self) -> str:
        return self.nickname or self.species.species_name

    @property
    def element(self) -> Element:
        return self.species.primary_type

    @property
    def base_hp(self) -> int:
        return self.species.base_hp

    @property
    def base_attack(self) -> int:
        return self.species.base_attack

    @property
    def base_defense(self) -> int:
        return self.species.base_defense

    @property
    def base_speed(self) -> int:
        return self.species.base_speed

    @property
    def rarity(self) -> Rarity:
        return Rarity.COMMON

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

    @property
    def hp_percentage(self) -> float:
        if self.total_hp <= 0:
            return 0.0
        return max(0.0, min(1.0, self.current_hp / self.total_hp))

    def is_alive(self) -> bool:
        return self.current_hp > 0 and not self.is_fainted

    def take_damage(self, amount: int) -> int:
        actual_damage = min(self.current_hp, max(0, amount))
        self.current_hp = max(0, self.current_hp - actual_damage)
        if self.current_hp == 0:
            self.is_fainted = True
        return actual_damage

    def heal(self, amount: Optional[int] = None) -> None:
        if amount is None:
            self.current_hp = self.total_hp
        else:
            self.current_hp = min(self.total_hp, self.current_hp + max(0, amount))
        if self.current_hp > 0:
            self.is_fainted = False

    def restore_all(self) -> None:
        self.heal()
        self.current_energy = self.max_energy
        self.active_status = StatusEffect.NONE
        self.status_turns = 0
        for skill in self.skills:
            skill.restore_pp()


@dataclass(frozen=True)
class AtomicAction:
    action_type: str  # "KEY_HOLD", "KEY_PRESS", "CLICK", "WAIT"
    target: str       # "w", "a", "s", "d", "e", "(x,y)"
    duration: float = 0.15  # em segundos
    expected_feedback: str = "SCENE_SHIFT"


@dataclass
class ActionPlan:
    actions: List[AtomicAction] = field(default_factory=list)
    description: str = ""


@dataclass
class UIElement:
    name: str
    bounding_box: tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float = 1.0
    center: tuple[int, int] = (0, 0)
    semantic_type: str = "UNKNOWN"


@dataclass
class MoveSlotInfo:
    slot_index: int
    name: str
    current_pp: int
    max_pp: int
    element: Element
    is_available: bool = True
    power: int = 40
    button_rect: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class BattleTelemetry:
    in_battle: bool = False
    player_hp_pct: float = 1.0
    enemy_hp_pct: float = 1.0
    player_lumen_name: Optional[str] = None
    enemy_lumen_name: Optional[str] = None
    available_moves: List[MoveSlotInfo] = field(default_factory=list)
    fight_button_pos: Optional[tuple[int, int]] = None
    switch_button_pos: Optional[tuple[int, int]] = None
    dialog_active: bool = False
    victory_detected: bool = False
    defeat_detected: bool = False


@dataclass
class PlayerInfo:
    x: int = 0
    y: int = 0
    center: tuple[int, int] = (0, 0)
    bounding_box: tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: float = 1.0
    detected: bool = False
    detection_method: str = "HEURISTIC"

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return self.bounding_box

    @property
    def center_x(self) -> int:
        return self.center[0] if self.center else self.x

    @property
    def center_y(self) -> int:
        return self.center[1] if self.center else self.y


@dataclass
class PlayerDetection:
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    center_x: int = 0
    center_y: int = 0
    confidence: float = 1.0
    detection_method: str = "HEURISTIC"
    detected: bool = True

    @property
    def center(self) -> tuple[int, int]:
        return (self.center_x, self.center_y)


@dataclass
class CrystalDetection:
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    center_x: int = 0
    center_y: int = 0
    confidence: float = 1.0
    semantic_type: str = "HEALING_CRYSTAL"
    distance_to_player: float = 0.0
    detected: bool = True

    @property
    def center(self) -> tuple[int, int]:
        return (self.center_x, self.center_y)


@dataclass
class TargetLockInfo:
    target_id: str
    semantic_type: str = "HEALING_CRYSTAL"
    confidence: float = 0.0
    bounding_box: tuple[int, int, int, int] = (0, 0, 0, 0)
    center_x: int = 0
    center_y: int = 0
    distance: float = 0.0
    timestamp: float = 0.0
    locked: bool = True


@dataclass
class StateSnapshot:
    timestamp: float
    screen_state: AgentState
    ui_elements: dict[str, UIElement] = field(default_factory=dict)
    battle_telemetry: Optional[BattleTelemetry] = None
    crystal_detected: bool = False
    crystal_relative_pos: Optional[tuple[int, int]] = None  # Vector (dx, dy)
    grass_density: float = 0.0
    motion_energy: float = 0.0  # Delta do frame anterior
    player_info: Optional[PlayerInfo] = None
    target_lock: Optional[TargetLockInfo] = None


@dataclass
class LumenMemberState:
    slot: int
    nickname: str
    species_name: str
    primary_element: Element
    secondary_element: Optional[Element] = None
    current_hp: int = 100
    max_hp: int = 100
    hp_percentage: float = 1.0
    is_fainted: bool = False
    skills: List[MoveSlotInfo] = field(default_factory=list)
    is_active: bool = False


@dataclass
class TeamStatus:
    members: List[LumenMemberState] = field(default_factory=list)
    active_slot: int = 0
    total_usable_pp: int = 0
    team_alive_count: int = 0
    requires_immediate_heal: bool = False


@dataclass
class ActionVerificationResult:
    input_dispatched: bool = False
    visual_delta: float = 0.0
    player_changed: bool = False
    enemy_changed: bool = False
    cooldown_changed: bool = False
    state_changed: bool = False
    verified: bool = False
    confidence: float = 0.0
    reason: str = ""