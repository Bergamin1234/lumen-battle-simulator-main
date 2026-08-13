import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class TelemetryData:
    fps: float = 0.0
    ticks_total: int = 0
    actions_total: int = 0
    actions_successful: int = 0
    actions_failed: int = 0
    actions_per_minute: float = 0.0
    battles_total: int = 0
    victories_total: int = 0
    defeats_total: int = 0
    recoveries_total: int = 0
    inputs_total: int = 0
    last_perception_confidence: float = 0.0
    average_action_latency: float = 0.0
    current_state: str = "STOPPED"
    current_objective: str = "Aguardando Início"
    current_decision: str = "Nenhuma"
    current_reason: str = "Sistema Parado"
    last_error: str = ""
    start_time: float = field(default_factory=time.time)


class TelemetryManager:
    """Gerenciador central de métricas, telemetria em tempo real e histórico de eventos."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TelemetryManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._data = TelemetryData()
        self._action_latencies = deque(maxlen=50)
        self._action_timestamps = deque(maxlen=100)
        self._frame_timestamps = deque(maxlen=30)
        self._recent_events = deque(maxlen=200)
        self._initialized = True

    def record_tick(self) -> None:
        """Registra um ciclo do loop principal e calcula FPS."""
        now = time.time()
        with self._lock:
            self._data.ticks_total += 1
            self._frame_timestamps.append(now)
            if len(self._frame_timestamps) > 1:
                dt = self._frame_timestamps[-1] - self._frame_timestamps[0]
                if dt > 0:
                    self._data.fps = round((len(self._frame_timestamps) - 1) / dt, 1)

    def record_action(self, success: bool, latency: float = 0.0, action_type: str = "") -> None:
        """Registra uma ação executada pelo agente."""
        now = time.time()
        with self._lock:
            self._data.actions_total += 1
            if success:
                self._data.actions_successful += 1
            else:
                self._data.actions_failed += 1

            if latency > 0:
                self._action_latencies.append(latency)
                self._data.average_action_latency = round(
                    sum(self._action_latencies) / len(self._action_latencies), 3
                )

            self._action_timestamps.append(now)
            # Calcula ações por minuto na janela de 60s
            recent_actions = [t for t in self._action_timestamps if now - t <= 60.0]
            self._data.actions_per_minute = round(len(recent_actions) * (60.0 / max(1.0, now - self._data.start_time if (now - self._data.start_time) < 60.0 else 60.0)), 1)

    def record_input(self) -> None:
        with self._lock:
            self._data.inputs_total += 1

    def record_battle_result(self, is_victory: bool) -> None:
        with self._lock:
            self._data.battles_total += 1
            if is_victory:
                self._data.victories_total += 1
            else:
                self._data.defeats_total += 1

    def record_recovery(self) -> None:
        with self._lock:
            self._data.recoveries_total += 1

    def update_perception_confidence(self, confidence: float) -> None:
        with self._lock:
            self._data.last_perception_confidence = round(confidence * 100.0, 1)

    def update_agent_status(
        self,
        state: Optional[str] = None,
        objective: Optional[str] = None,
        decision: Optional[str] = None,
        reason: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if state is not None:
                self._data.current_state = state
            if objective is not None:
                self._data.current_objective = objective
            if decision is not None:
                self._data.current_decision = decision
            if reason is not None:
                self._data.current_reason = reason
            if error is not None:
                self._data.last_error = error

    def add_event(self, category: str, message: str) -> None:
        timestamp_str = time.strftime("%H:%M:%S")
        entry = f"{timestamp_str} [{category.upper()}] {message}"
        with self._lock:
            self._recent_events.append(entry)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "fps": self._data.fps,
                "ticks": self._data.ticks_total,
                "actions_total": self._data.actions_total,
                "actions_successful": self._data.actions_successful,
                "actions_failed": self._data.actions_failed,
                "actions_per_minute": self._data.actions_per_minute,
                "battles_total": self._data.battles_total,
                "victories_total": self._data.victories_total,
                "defeats_total": self._data.defeats_total,
                "recoveries_total": self._data.recoveries_total,
                "inputs_total": self._data.inputs_total,
                "confidence": self._data.last_perception_confidence,
                "avg_latency": self._data.average_action_latency,
                "state": self._data.current_state,
                "objective": self._data.current_objective,
                "decision": self._data.current_decision,
                "reason": self._data.current_reason,
                "last_error": self._data.last_error,
                "uptime": round(time.time() - self._data.start_time, 1),
            }

    def get_recent_events(self, max_count: int = 50) -> List[str]:
        with self._lock:
            return list(self._recent_events)[-max_count:]

    def reset(self) -> None:
        with self._lock:
            self._data = TelemetryData()
            self._action_latencies.clear()
            self._action_timestamps.clear()
            self._frame_timestamps.clear()
            self._recent_events.clear()
