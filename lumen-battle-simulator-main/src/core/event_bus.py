import time
import queue
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional

logger = logging.getLogger("LumenaEventBus")


class EventType(str, Enum):
    # Ciclo de Vida do Agente
    BOT_STARTED = "BOT_STARTED"
    BOT_STOPPED = "BOT_STOPPED"
    BOT_PAUSED = "BOT_PAUSED"
    BOT_RESUMED = "BOT_RESUMED"
    BOT_ERROR = "BOT_ERROR"
    STATE_CHANGED = "STATE_CHANGED"

    # Ações & Decisões
    ACTION_STARTED = "ACTION_STARTED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"

    # Percepção & Combate
    ENEMY_DETECTED = "ENEMY_DETECTED"
    BATTLE_STARTED = "BATTLE_STARTED"
    BATTLE_WON = "BATTLE_WON"
    BATTLE_LOST = "BATTLE_LOST"

    # Navegação & Rotas
    ROUTE_STARTED = "ROUTE_STARTED"
    ROUTE_STEP_COMPLETED = "ROUTE_STEP_COMPLETED"
    ROUTE_COMPLETED = "ROUTE_COMPLETED"

    # Entrada Física & Segurança
    INPUT_REQUESTED = "INPUT_REQUESTED"
    INPUT_SENT = "INPUT_SENT"
    INPUT_BLOCKED = "INPUT_BLOCKED"
    INPUT_FEEDBACK = "INPUT_FEEDBACK"
    TARGET_FOUND = "TARGET_FOUND"
    TARGET_LOST = "TARGET_LOST"
    SAFETY_TRIGGERED = "SAFETY_TRIGGERED"

    # Diagnóstico & Sistema
    DIAGNOSTIC_COMPLETED = "DIAGNOSTIC_COMPLETED"
    STUCK_DETECTED = "STUCK_DETECTED"
    NOTIFICATION_EMITTED = "NOTIFICATION_EMITTED"
    TELEMETRY_UPDATED = "TELEMETRY_UPDATED"


@dataclass
class BotEvent:
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    category: str = "SYSTEM"
    level: str = "INFO"
    message: str = ""

    def formatted_time(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))


class EventBus:
    """Barramento central thread-safe de publicação e assinatura de eventos do Lumena Bot."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._subscribers: Dict[EventType, List[Callable[[BotEvent], None]]] = {et: [] for et in EventType}
        self._queues: Dict[str, queue.Queue] = {}
        self._event_history: List[BotEvent] = []
        self._max_history = 500
        self._initialized = True

    def subscribe(self, event_type: EventType, callback: Callable[[BotEvent], None]) -> None:
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].append(callback)

    def get_or_create_queue(self, subscriber_id: str, maxsize: int = 1000) -> queue.Queue:
        with self._lock:
            if subscriber_id not in self._queues:
                self._queues[subscriber_id] = queue.Queue(maxsize=maxsize)
            return self._queues[subscriber_id]

    def publish(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        category: str = "SYSTEM",
        level: str = "INFO",
        message: str = "",
    ) -> BotEvent:
        event = BotEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data or {},
            category=category.upper(),
            level=level.upper(),
            message=message,
        )

        with self._lock:
            # Armazena no histórico limitado
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

            # Envia para filas de assinantes assíncronos (como a GUI)
            for q in self._queues.values():
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

            # Notifica callbacks diretos
            callbacks = list(self._subscribers.get(event_type, []))

        for cb in callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Erro ao executar callback de evento {event_type}: {e}")

        return event

    def get_recent_events(self, max_count: int = 50, category: Optional[str] = None) -> List[BotEvent]:
        with self._lock:
            if category:
                filtered = [e for e in self._event_history if e.category == category.upper()]
                return filtered[-max_count:]
            return self._event_history[-max_count:]

    def clear(self) -> None:
        with self._lock:
            self._event_history.clear()
            for q in self._queues.values():
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
