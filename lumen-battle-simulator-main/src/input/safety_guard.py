import os
import time
import logging
import ctypes
from typing import Set, Optional, Callable, Any
from src.input.input_backend import InputBackend
from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaInput")
user32 = ctypes.windll.user32


class SafetyGuard:
    """Guardião de segurança crítico para validação de foco, prevenção de inputs em janelas erradas,

    rejeição formal de target inválido, liberação garantida de teclas em blocos finally e parada imediata de emergência (ESC).
    """

    def __init__(self, max_actions_per_second: int = 20) -> None:
        self.logger = logging.getLogger("LumenaInput")
        self.event_bus = EventBus()
        self._emergency_stop = False
        self._held_keys: Set[str] = set()
        self._max_rate = max_actions_per_second
        self._action_timestamps = []
        self._emergency_callbacks = []
        self._own_pid = os.getpid()

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop

    def register_emergency_callback(self, callback: Callable[[], None]) -> None:
        self._emergency_callbacks.append(callback)

    def trigger_emergency_stop(self, backend: Optional[InputBackend] = None) -> None:
        """Aciona a parada de emergência imediata e libera todas as teclas físicas."""
        self._emergency_stop = True
        self.logger.critical("🛑 [EMERGENCY STOP] Parada de emergência acionada! Bloqueando novos inputs.")
        self.event_bus.publish(
            EventType.EMERGENCY_STOP,
            category="SAFETY",
            level="CRITICAL",
            message="EMERGENCY STOP acionado pelo usuário ou sistema.",
        )

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

    def validate_can_dispatch(
        self,
        is_window_confirmed: bool = True,
        target_hwnd: Optional[int] = None,
        target_pid: Optional[int] = None,
        target_title: Optional[str] = None,
        target_process: Optional[str] = None,
        foreground_hwnd: Optional[int] = None,
    ) -> bool:
        """Verifica rigorosamente se o sistema está autorizado a despachar ações físicas.

        Nenhum input é enviado para a própria janela do Lumena Bot ou para janelas fora de foco.
        """
        # 1. Checa Parada de Emergência
        if self._emergency_stop:
            self.logger.warning("[SAFETY] Input bloqueado: Parada de emergência ativa.")
            self.event_bus.publish(
                EventType.INPUT_BLOCKED,
                data={"reason": "emergency_stop"},
                category="SAFETY",
                level="WARNING",
                message="Input bloqueado: Parada de emergência ativa.",
            )
            return False

        # 2. Checa se o PID alvo é o próprio processo do LumenaBot
        if target_pid and target_pid == self._own_pid and self._own_pid > 0:
            self.logger.critical(f"[SAFETY] Input BLOQUEADO: Tentativa de despachar entrada para o próprio PID do Lumena Bot ({target_pid}).")
            self.event_bus.publish(
                EventType.TARGET_WINDOW_REJECTED,
                data={"hwnd": target_hwnd, "pid": target_pid, "reason": "self_process"},
                category="SAFETY",
                level="CRITICAL",
                message=f"TARGET_WINDOW_REJECTED: reason=self_process hwnd={target_hwnd} pid={target_pid}",
            )
            self.event_bus.publish(
                EventType.INPUT_BLOCKED,
                data={"reason": "self_process", "pid": target_pid},
                category="SAFETY",
                level="CRITICAL",
                message="Input bloqueado: Alvo é o próprio processo do bot.",
            )
            return False

        # 3. Checa títulos proibidos do LumenaBot
        if target_title:
            t_lower = target_title.lower()
            if any(rej in t_lower for rej in ["lumenabot", "autonomous agent suite", "lumena bot control center"]):
                self.logger.critical(f"[SAFETY] Input BLOQUEADO: Tentativa de despachar entrada para a interface do Lumena Bot ('{target_title}').")
                self.event_bus.publish(
                    EventType.TARGET_WINDOW_REJECTED,
                    data={"hwnd": target_hwnd, "title": target_title, "reason": "self_title"},
                    category="SAFETY",
                    level="CRITICAL",
                    message=f"TARGET_WINDOW_REJECTED: reason=self_title title='{target_title}'",
                )
                self.event_bus.publish(
                    EventType.INPUT_BLOCKED,
                    data={"reason": "self_title", "title": target_title},
                    category="SAFETY",
                    level="CRITICAL",
                    message=f"Input bloqueado: Alvo é a própria interface do bot ('{target_title}').",
                )
                return False

        # 4. Checa processo do navegador
        if target_process:
            p_lower = target_process.lower()
            valid_procs = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe")
            if not any(vp in p_lower for vp in valid_procs) and target_hwnd != 1001:
                self.logger.warning(f"[SAFETY] Input BLOQUEADO: Processo alvo '{target_process}' não é um navegador suportado.")
                self.event_bus.publish(
                    EventType.TARGET_WINDOW_REJECTED,
                    data={"hwnd": target_hwnd, "process": target_process, "reason": "non_chrome_process"},
                    category="SAFETY",
                    level="WARNING",
                    message=f"TARGET_WINDOW_REJECTED: reason=non_chrome_process process='{target_process}'",
                )
                self.event_bus.publish(
                    EventType.INPUT_BLOCKED,
                    data={"reason": "non_chrome_process", "process": target_process},
                    category="SAFETY",
                    level="WARNING",
                    message=f"Input bloqueado: Processo '{target_process}' não é um navegador suportado.",
                )
                return False

        # 5. Checa foreground match explícito se fornecido
        if foreground_hwnd is not None and target_hwnd is not None and target_hwnd != 1001:
            if foreground_hwnd != target_hwnd:
                self.logger.warning(f"[SAFETY] Input BLOQUEADO: Foreground HWND ({foreground_hwnd}) != Target HWND ({target_hwnd}).")
                self.event_bus.publish(
                    EventType.TARGET_WINDOW_REJECTED,
                    data={"target_hwnd": target_hwnd, "foreground_hwnd": foreground_hwnd, "reason": "foreground_mismatch"},
                    category="SAFETY",
                    level="WARNING",
                    message=f"TARGET_WINDOW_REJECTED: reason=foreground_mismatch target={target_hwnd} fg={foreground_hwnd}",
                )
                self.event_bus.publish(
                    EventType.INPUT_BLOCKED,
                    data={"reason": "foreground_mismatch", "target_hwnd": target_hwnd, "foreground_hwnd": foreground_hwnd},
                    category="SAFETY",
                    level="WARNING",
                    message="Input bloqueado: Janela não está no primeiro plano ativo.",
                )
                return False

        # 6. Checa confirmação geral de janela
        if not is_window_confirmed:
            self.logger.warning("[SAFETY] Input bloqueado: Janela alvo não está confirmada em primeiro plano.")
            self.event_bus.publish(
                EventType.INPUT_BLOCKED,
                data={"reason": "window_not_confirmed"},
                category="SAFETY",
                level="WARNING",
                message="Input bloqueado: Janela alvo não está confirmada em primeiro plano.",
            )
            return False

        # 7. Rate limiting
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
            self.event_bus.publish(
                EventType.INPUT_RELEASED,
                category="SAFETY",
                level="DEBUG",
                message="Todas as teclas pressionadas foram liberadas via release_all_keys().",
            )
