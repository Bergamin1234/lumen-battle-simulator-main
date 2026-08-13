import os
import json
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple
from config.settings import BotConfig
from src.automation.bot_engine import LumenaBotEngine
from src.automation.state_machine import BotState
from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaMacro")


class BotController:
    """Controlador de alto nível para gerenciamento de lifecycle do BotEngine em background thread."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BotController, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, config: Optional[BotConfig] = None) -> None:
        if self._initialized:
            return
        self.logger = logging.getLogger("LumenaMacro")
        self.event_bus = EventBus()
        self.config = config
        self.engine = LumenaBotEngine(config=self.config)
        self._worker_thread: Optional[threading.Thread] = None
        self._level_6_override: bool = False
        self._initialized = True

    def set_level_6_validated_override(self, validated: bool = True) -> None:
        """Permite habilitar manualmente a validação do Level 6 na sessão ativa."""
        self._level_6_override = validated

    def is_level_6_validated(self) -> bool:
        """Verifica se o Level 6 foi formalmente comprovado via teste físico ou evidência."""
        if self._level_6_override:
            return True
        if os.path.exists("physical_test_report.json"):
            try:
                with open("physical_test_report.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("step_17_movement_confirmed") or "PASS" in str(data.get("status", "")).upper():
                        return True
            except Exception:
                pass
        return False

    def start(self, mode: str = "AUTONOMOUS", bypass_gate: bool = False) -> Tuple[bool, str]:
        """Inicia o motor autônomo em uma thread dedicada de background, aplicando o gate do Level 7."""
        if self.engine.is_running:
            self.logger.warning("BotController: O bot já está em execução.")
            return True, "Bot já em execução."

        mode_upper = mode.upper()
        # Portão do Level 7: Modo AUTONOMOUS exige Level 6 validado
        if mode_upper == "AUTONOMOUS" and not bypass_gate and not self.is_level_6_validated():
            msg = "LEVEL 7 BLOCKED: Physical input validation (Level 6) required."
            self.logger.warning(f"🛑 [GATE] {msg}")
            self.event_bus.publish(
                EventType.SAFETY_TRIGGERED,
                data={"gate": "LEVEL_7_BLOCKED", "reason": "Level 6 not physically validated"},
                category="SAFETY",
                level="WARNING",
                message=msg,
            )
            return False, msg

        success = self.engine.start(mode=mode_upper)
        if not success:
            return False, "Falha ao inicializar o motor."

        self._worker_thread = threading.Thread(
            target=self.engine.run_loop,
            name="LumenaBotWorkerThread",
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.info("✓ BotController: Worker thread iniciada com sucesso.")
        return True, "Worker thread iniciada com sucesso."

    def stop(self) -> None:
        """Para o bot de forma limpa e aguarda finalização da thread."""
        self.engine.stop()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.5)
        self.logger.info("✓ BotController: Motor finalizado.")

    def emergency_stop(self) -> None:
        """Aciona a parada emergencial imediata de todos os módulos."""
        self.engine.emergency_stop()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)

    def pause(self) -> None:
        self.engine.pause()

    def resume(self) -> None:
        self.engine.resume()

    def set_mode(self, mode: str) -> None:
        self.engine.mode = mode.upper()
        self.logger.info(f"BotController: Modo alterado para {self.engine.mode}")

    def manual_press(self, key: str, duration: float = 0.15) -> bool:
        """Envia input manual pelo InputController."""
        return self.engine.input_ctrl.press_key(key, duration=duration)

    def get_telemetry(self) -> Dict[str, Any]:
        return self.engine.telemetry.get_snapshot()

    def get_recent_events(self, max_count: int = 50) -> List[str]:
        return self.engine.telemetry.get_recent_events(max_count=max_count)

    def get_latest_frame(self):
        return self.engine.get_latest_frame()

    def is_running(self) -> bool:
        return self.engine.is_running

    def is_paused(self) -> bool:
        return self.engine.is_paused

    def get_state(self) -> BotState:
        return self.engine.current_state
