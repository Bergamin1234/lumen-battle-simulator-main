import enum
import logging
from typing import List, Callable, Dict, Set, Optional

from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaSystem")


class BotState(enum.Enum):
    IDLE = "IDLE"
    STOPPED = "IDLE"
    STARTING = "STARTING"
    INITIALIZING = "INITIALIZING"
    CONNECTING = "INITIALIZING"
    FOCUSING = "FOCUSING"
    READY = "OBSERVING"
    OBSERVING = "OBSERVING"
    EXPLORING = "EXPLORING"
    BATTLE_DETECTED = "BATTLE_DETECTED"
    ENGAGING_BATTLE = "BATTLE"
    BATTLE = "BATTLE"
    BATTLE_ACTION_REQUIRED = "BATTLE"
    BATTLE_SKILL_SELECTION = "BATTLE"
    BATTLE_WAITING_TURN = "BATTLE_WAITING_TURN_RESOLUTION"
    BATTLE_WAITING_TURN_RESOLUTION = "BATTLE_WAITING_TURN_RESOLUTION"
    BATTLE_MODAL_DISMISSAL = "BATTLE_MODAL_DISMISSAL"
    POST_BATTLE_EVALUATION = "POST_BATTLE_EVALUATION"
    DIALOG = "DIALOG"
    SEARCHING_CRYSTAL = "HEALING"
    HEALING = "HEALING"
    HEALING_ROUTINE = "HEALING"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    RECOVERING = "RECOVERING"
    LOADING_SCREEN = "LOADING_SCREEN"
    NETWORK_RECONNECTING = "NETWORK_RECONNECTING"
    UNRESPONSIVE_RECOVERY = "UNRESPONSIVE_RECOVERY"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SAFE_STOP = "SAFE_STOP"
    MANUAL = "MANUAL"


class BotStateMachine:
    """Máquina de estados finitos formal para o ciclo de vida, observação e execução do agente."""

    def __init__(self, initial_state: BotState = BotState.IDLE) -> None:
        self.logger = logging.getLogger("LumenaSystem")
        self._current_state = initial_state
        self._listeners: List[Callable[[BotState, BotState], None]] = []
        self._event_bus = EventBus()

        # Tabela de transições permitidas
        self._allowed_transitions: Dict[BotState, Set[BotState]] = {
            BotState.IDLE: {BotState.STARTING, BotState.INITIALIZING, BotState.MANUAL, BotState.EMERGENCY_STOP, BotState.SAFE_STOP, BotState.OBSERVING, BotState.EXPLORING, BotState.BATTLE, BotState.HEALING, BotState.DIALOG, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING},
            BotState.STARTING: {BotState.INITIALIZING, BotState.FOCUSING, BotState.OBSERVING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP, BotState.LOADING_SCREEN},
            BotState.INITIALIZING: {BotState.FOCUSING, BotState.OBSERVING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP, BotState.LOADING_SCREEN},
            BotState.FOCUSING: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP, BotState.LOADING_SCREEN},
            BotState.OBSERVING: {BotState.EXPLORING, BotState.BATTLE_DETECTED, BotState.BATTLE, BotState.DIALOG, BotState.HEALING, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING, BotState.UNRESPONSIVE_RECOVERY, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP, BotState.MANUAL},
            BotState.EXPLORING: {BotState.OBSERVING, BotState.BATTLE_DETECTED, BotState.BATTLE, BotState.DIALOG, BotState.HEALING, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING, BotState.UNRESPONSIVE_RECOVERY, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.BATTLE_DETECTED: {BotState.BATTLE, BotState.OBSERVING, BotState.RECOVERING, BotState.LOADING_SCREEN, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.BATTLE: {BotState.BATTLE_WAITING_TURN_RESOLUTION, BotState.BATTLE_MODAL_DISMISSAL, BotState.POST_BATTLE_EVALUATION, BotState.VICTORY, BotState.DEFEAT, BotState.EXPLORING, BotState.OBSERVING, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.BATTLE_WAITING_TURN_RESOLUTION: {BotState.BATTLE, BotState.BATTLE_MODAL_DISMISSAL, BotState.POST_BATTLE_EVALUATION, BotState.VICTORY, BotState.DEFEAT, BotState.EXPLORING, BotState.OBSERVING, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.BATTLE_MODAL_DISMISSAL: {BotState.POST_BATTLE_EVALUATION, BotState.EXPLORING, BotState.HEALING, BotState.BATTLE, BotState.OBSERVING, BotState.LOADING_SCREEN, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.POST_BATTLE_EVALUATION: {BotState.EXPLORING, BotState.HEALING, BotState.OBSERVING, BotState.LOADING_SCREEN, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.DIALOG: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.HEALING: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.LOADING_SCREEN, BotState.NETWORK_RECONNECTING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.VICTORY: {BotState.OBSERVING, BotState.EXPLORING, BotState.HEALING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.DEFEAT: {BotState.OBSERVING, BotState.EXPLORING, BotState.HEALING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.LOADING_SCREEN: {BotState.OBSERVING, BotState.EXPLORING, BotState.BATTLE, BotState.UNRESPONSIVE_RECOVERY, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.NETWORK_RECONNECTING: {BotState.OBSERVING, BotState.EXPLORING, BotState.UNRESPONSIVE_RECOVERY, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.UNRESPONSIVE_RECOVERY: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.NETWORK_RECONNECTING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.RECOVERING: {BotState.OBSERVING, BotState.FOCUSING, BotState.EXPLORING, BotState.LOADING_SCREEN, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.ERROR: {BotState.RECOVERING, BotState.IDLE, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.STOPPING: {BotState.IDLE, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
            BotState.EMERGENCY_STOP: {BotState.IDLE, BotState.OBSERVING, BotState.RECOVERING},
            BotState.SAFE_STOP: {BotState.IDLE, BotState.OBSERVING, BotState.RECOVERING},
            BotState.MANUAL: {BotState.OBSERVING, BotState.IDLE, BotState.EMERGENCY_STOP, BotState.SAFE_STOP},
        }

    @property
    def current_state(self) -> BotState:
        return self._current_state

    def add_listener(self, listener: Callable[[BotState, BotState], None]) -> None:
        self._listeners.append(listener)

    def transition_to(self, new_state: BotState, reason: str = "") -> bool:
        """Executa a transição de estado validando a máquina de estados e notificando ouvintes."""
        if self._current_state == new_state:
            return True

        allowed = self._allowed_transitions.get(self._current_state, set())
        # Permite transição para EMERGENCY_STOP, IDLE ou ERROR de qualquer estado
        if new_state in (BotState.EMERGENCY_STOP, BotState.IDLE, BotState.STOPPING, BotState.ERROR) or new_state in allowed:
            old_state = self._current_state
            self._current_state = new_state
            msg = f"Transição: {old_state.name} -> {new_state.name} ({reason or 'Ciclo de Controle'})"
            self.logger.info(f"🔄 [FSM] {msg}")

            # Publica no EventBus
            self._event_bus.publish(
                EventType.STATE_CHANGED,
                data={"old_state": old_state.name, "new_state": new_state.name, "reason": reason},
                category="SYSTEM",
                level="INFO",
                message=msg,
            )

            for listener in self._listeners:
                try:
                    listener(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"Erro no listener da FSM: {e}")
            return True
        else:
            self.logger.warning(f"⚠️ [FSM] Transição rejeitada: {self._current_state.name} ➔ {new_state.name} (Motivo: {reason})")
            return False
