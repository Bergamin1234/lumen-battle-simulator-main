import time
import logging
from typing import Set, Optional, Callable
from src.input.input_backend import InputBackend

logger = logging.getLogger("LumenaInput")


class SafetyGuard:
    """Guardião de segurança para prevenção de inputs indevidos, travamento de teclas e parada de emergência."""

    def __init__(self, max_actions_per_second: int = 20) -> None:
        self.logger = logging.getLogger("LumenaInput")
        self._emergency_stop = False
        self._held_keys: Set[str] = set()
        self._max_rate = max_actions_per_second
        self._action_timestamps = []
        self._emergency_callbacks = []

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop

    def register_emergency_callback(self, callback: Callable[[], None]) -> None:
        self._emergency_callbacks.append(callback)

    def trigger_emergency_stop(self, backend: Optional[InputBackend] = None) -> None:
        """Aciona a parada de emergência imediata e libera todas as teclas físicas."""
        self._emergency_stop = True
        self.logger.critical("🛑 [EMERGENCY STOP] Parada de emergência acionada! Bloqueando novos inputs.")

        if backend is not None:
            self.release_all_keys(backend)

        for cb in self._emergency_callbacks:
            try:
                cb()
            except Exception as e:
                self.logger.error(f"Erro em callback de emergência: {e}")

    def reset_emergency_stop(self) -> None:
        """Restaura o estado normal do guardião após intervenção do usuário."""
        self._emergency_stop = False
        self._held_keys.clear()
        self.logger.info("✓ [SAFETY] Parada de emergência desativada. Sistema pronto para retomar.")

    def validate_can_dispatch(self, is_window_confirmed: bool) -> bool:
        """Verifica se o sistema está autorizado a despachar ações físicas."""
        if self._emergency_stop:
            self.logger.warning("[SAFETY] Input bloqueado: Parada de emergência ativa.")
            return False

        if not is_window_confirmed:
            self.logger.warning("[SAFETY] Input bloqueado: Janela alvo não está confirmada em primeiro plano.")
            return False

        # Rate limiting
        now = time.time()
        self._action_timestamps = [t for t in self._action_timestamps if now - t < 1.0]
        if len(self._action_timestamps) >= self._max_rate:
            self.logger.warning(f"[SAFETY] Limite de {self._max_rate} ações/segundo atingido. Atrasando micro-ação.")
            time.sleep(0.05)

        self._action_timestamps.append(now)
        return True

    def track_key_down(self, key: str) -> None:
        self._held_keys.add(key.lower().strip())

    def track_key_up(self, key: str) -> None:
        self._held_keys.discard(key.lower().strip())

    def get_held_keys(self) -> Set[str]:
        return set(self._held_keys)

    def release_all_keys(self, backend: InputBackend) -> None:
        """Garante que todas as teclas registradas como pressionadas sejam liberadas."""
        if self._held_keys:
            self.logger.info(f"[SAFETY] Liberando teclas ativas: {list(self._held_keys)}")
            backend.release_all(list(self._held_keys))
            self._held_keys.clear()
