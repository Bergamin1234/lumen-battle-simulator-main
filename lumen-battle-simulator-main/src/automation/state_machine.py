import enum
import logging
from typing import List, Callable, Dict, Set, Optional

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
    BATTLE = "BATTLE"
    DIALOG = "DIALOG"
    HEALING = "HEALING"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    MANUAL = "MANUAL"


class BotStateMachine:
    """Máquina de estados finitos formal para o ciclo de vida, observação e execução do agente."""

    def __init__(self, initial_state: BotState = BotState.IDLE) -> None:
        self.logger = logging.getLogger("LumenaSystem")
        self._current_state = initial_state
        self._listeners: List[Callable[[BotState, BotState], None]] = []

        # Tabela de transições permitidas
        self._allowed_transitions: Dict[BotState, Set[BotState]] = {
            BotState.IDLE: {BotState.STARTING, BotState.INITIALIZING, BotState.MANUAL, BotState.EMERGENCY_STOP},
            BotState.STARTING: {BotState.INITIALIZING, BotState.FOCUSING, BotState.OBSERVING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.INITIALIZING: {BotState.FOCUSING, BotState.OBSERVING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.FOCUSING: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.OBSERVING: {BotState.EXPLORING, BotState.BATTLE_DETECTED, BotState.BATTLE, BotState.DIALOG, BotState.HEALING, BotState.STOPPING, BotState.EMERGENCY_STOP, BotState.MANUAL},
            BotState.EXPLORING: {BotState.OBSERVING, BotState.BATTLE_DETECTED, BotState.BATTLE, BotState.DIALOG, BotState.HEALING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.BATTLE_DETECTED: {BotState.BATTLE, BotState.OBSERVING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.BATTLE: {BotState.VICTORY, BotState.DEFEAT, BotState.OBSERVING, BotState.RECOVERING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.DIALOG: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.HEALING: {BotState.OBSERVING, BotState.EXPLORING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.VICTORY: {BotState.OBSERVING, BotState.EXPLORING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.DEFEAT: {BotState.OBSERVING, BotState.RECOVERING, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.RECOVERING: {BotState.OBSERVING, BotState.FOCUSING, BotState.EXPLORING, BotState.ERROR, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.ERROR: {BotState.RECOVERING, BotState.IDLE, BotState.STOPPING, BotState.EMERGENCY_STOP},
            BotState.STOPPING: {BotState.IDLE, BotState.EMERGENCY_STOP},
            BotState.EMERGENCY_STOP: {BotState.IDLE, BotState.OBSERVING, BotState.RECOVERING},
            BotState.MANUAL: {BotState.OBSERVING, BotState.IDLE, BotState.EMERGENCY_STOP},
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
            self.logger.info(f"🔄 [FSM] Transição: {old_state.name} ➔ {new_state.name} ({reason or 'Ciclo de Controle'})")
            for listener in self._listeners:
                try:
                    listener(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"Erro no listener da FSM: {e}")
            return True
        else:
            self.logger.warning(f"⚠️ [FSM] Transição rejeitada: {self._current_state.name} ➔ {new_state.name} (Motivo: {reason})")
            return False
