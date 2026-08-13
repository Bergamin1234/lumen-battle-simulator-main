import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from src.models.enums import Element


@dataclass
class TargetWindowInfo:
    """Modelo completo para representação e auditoria de janelas candidatas a alvo."""
    hwnd: int
    pid: int
    process_name: str
    executable_path: str = ""
    window_title: str = ""
    class_name: str = ""
    left: int = 0
    top: int = 0
    width: int = 1920
    height: int = 1080
    is_visible: bool = True
    is_minimized: bool = False
    is_foreground: bool = False
    is_browser: bool = False
    browser_type: str = "UNKNOWN"  # CHROME, EDGE, FIREFOX, OTHER, UNKNOWN
    is_self_process: bool = False
    is_valid_candidate: bool = True
    rejection_reason: Optional[str] = None
    canvas_detected: bool = False
    confidence: float = 1.0

    @property
    def title(self) -> str:
        """Alias de compatibilidade com WindowInfo."""
        return self.window_title

    @property
    def is_active(self) -> bool:
        """Alias de compatibilidade com WindowInfo."""
        return self.is_foreground


@dataclass
class SkillSlot:
    """Representa um slot de habilidade/ataque detectado dinamicamente na interface."""
    slot_index: int = 0
    id: str = ""
    index: int = 0
    hotkey: Optional[str] = None
    screen_x: int = 0
    screen_y: int = 0
    width: int = 60
    height: int = 60
    center_x: int = 0
    center_y: int = 0
    icon_region: Optional[Tuple[int, int, int, int]] = None
    icon_detected: bool = True
    cooldown: float = 0.0
    cooldown_ratio: float = 0.0
    cooldown_remaining: float = 0.0
    available: bool = True
    disabled: bool = False
    confidence: float = 1.0
    skill_name: Optional[str] = None
    element: Optional[Element] = None
    power: int = 40
    energy_cost: int = 5
    range_type: str = "MELEE"  # MELEE, RANGED, HEAL, BUFF, UTILITY
    target_type: str = "ENEMY"
    priority: float = 1.0
    last_seen: float = 0.0
    last_used: float = 0.0
    visual_signature: Optional[str] = None
    current_pp: int = 15
    max_pp: int = 15

    def __post_init__(self):
        if not self.id:
            self.id = f"skill_{self.slot_index or self.index}"
        if not self.index and self.slot_index:
            self.index = self.slot_index
        elif not self.slot_index and self.index:
            self.slot_index = self.index
        if not self.center_x:
            self.center_x = self.screen_x + self.width // 2
        if not self.center_y:
            self.center_y = self.screen_y + self.height // 2
        if not self.skill_name:
            self.skill_name = f"Skill_{self.slot_index}"
        if self.cooldown > 0 and not self.cooldown_remaining:
            self.cooldown_remaining = self.cooldown


@dataclass
class EnemyTarget:
    """Representa um alvo inimigo detectado na tela ou arena de combate."""
    target_id: int = 1
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, w, h)
    center: Tuple[int, int] = (0, 0)
    confidence: float = 1.0
    hp_estimate: float = 1.0  # 0.0 a 1.0
    distance: float = 0.0  # pixels ou unidades relativas
    state: str = "IDLE"  # IDLE, ATTACKING, CASTING, DEFEATED, UNKNOWN
    element: Optional[Element] = None
    weakness: Optional[Element] = None
    priority: float = 1.0
    name: Optional[str] = None


@dataclass
class PositionInfo:
    """Informações estruturadas de posicionamento tático e distância de combate."""
    player_pos: Tuple[int, int] = (960, 540)
    target_pos: Optional[Tuple[int, int]] = None
    distance: float = 0.0
    required_range: float = 150.0
    positioning_state: str = "ATTACK_POSITION_READY"  # APPROACH_TARGET, MAINTAIN_DISTANCE, RETREAT, REPOSITION, ATTACK_POSITION_READY
    last_movement_direction: Optional[str] = None
    movement_confirmed: bool = True


@dataclass
class CombatSnapshot:
    """Snapshot completo e dinâmico da visão de combate."""
    timestamp: float = field(default_factory=time.time)
    player_hp: float = 1.0
    player_resource: float = 100.0
    player_position: Tuple[int, int] = (960, 540)
    target_enemy: Optional[EnemyTarget] = None
    detected_enemies: List[EnemyTarget] = field(default_factory=list)
    available_skills: List[SkillSlot] = field(default_factory=list)
    combat_state: str = "IDLE"
    position_info: Optional[PositionInfo] = None
    dialog_active: bool = False
    in_battle: bool = False
    victory_detected: bool = False
    defeat_detected: bool = False
    fight_button_pos: Optional[Tuple[int, int]] = None


@dataclass
class CombatDecision:
    """Decisão estruturada gerada pelo CombatDecisionEngine dinâmico."""
    action_type: str  # "USE_SKILL", "MOVE_TO_TARGET", "APPROACH_TARGET", "MAINTAIN_DISTANCE", "RETREAT", "DODGE", "HEAL", "OPEN_FIGHT_MENU", "CONFIRM_VICTORY", "CLEAR_DEFEAT", "WAIT", "REASSESS"
    selected_skill: Optional[SkillSlot] = None
    target_pos: Optional[Tuple[int, int]] = None
    hotkey: Optional[str] = None
    reason: str = ""
    score: float = 0.0
    confidence: float = 1.0
    move_direction: Optional[str] = None
