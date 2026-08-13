import logging
import threading
from typing import Optional, Dict, Any, List
from config.settings import BotConfig
from src.automation.bot_engine import LumenaBotEngine
from src.automation.state_machine import BotState

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
        self.config = config
        self.engine = LumenaBotEngine(config=self.config)
        self._worker_thread: Optional[threading.Thread] = None
        self._initialized = True

    def start(self, mode: str = "AUTONOMOUS") -> bool:
        """Inicia o motor autônomo em uma thread dedicada de background."""
        if self.engine.is_running:
            self.logger.warning("BotController: O bot já está em execução.")
            return True

        success = self.engine.start(mode=mode)
        if not success:
            return False

        self._worker_thread = threading.Thread(
            target=self.engine.run_loop,
            name="LumenaBotWorkerThread",
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.info("✓ BotController: Worker thread iniciada com sucesso.")
        return True

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
