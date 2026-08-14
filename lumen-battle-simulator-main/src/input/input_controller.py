import time
import random
import logging
import ctypes
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any, Set
import numpy as np
import pyautogui

from src.input.target_window import TargetWindowManager, WindowInfo
from src.input.input_backend import InputBackend, Win32InputBackend, PyAutoGUIInputBackend
from src.input.safety_guard import SafetyGuard
from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaInput")
user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


@dataclass
class KeyDiagnosticResult:
    key: str
    vk_code: int
    scancode: int
    sendinput_down_ret: int
    sendinput_up_ret: int
    keybd_event_dispatched: bool
    postmessage_count: int
    pyautogui_dispatched: bool
    total_events: int
    duration: float
    window_focused: bool
    visual_delta: float
    movement_confirmed: bool
    success: bool

    @property
    def latency(self) -> float:
        return self.duration

    @property
    def scan_code(self) -> int:
        return self.scancode


class InputController:
    """Controlador de entrada unificado, thread-safe, com proteção de Safety Guard e validação de feedback visual real."""

    def __init__(
        self,
        target_window_titles: Optional[List[str]] = None,
        preferred_backend: str = "win32",
    ) -> None:
        self.logger = logging.getLogger("LumenaInput")
        self.target_window_titles = target_window_titles or [
            "Lumena.gg",
            "Lumena",
            "IA Autônoma para Jogo - Google Chrome",
            "Google Chrome",
            "Chrome",
            "Brave",
            "Edge",
            "Firefox",
        ]
        self.window_manager = TargetWindowManager(self.target_window_titles)
        self.safety_guard = SafetyGuard()
        self.event_bus = EventBus()

        self.win32_backend = Win32InputBackend()
        self.pyautogui_backend = PyAutoGUIInputBackend()
        self.active_backend_name = preferred_backend.lower()

        self._last_focus_check = 0.0
        self._is_window_focused = False

    @property
    def backend(self) -> InputBackend:
        if self.active_backend_name == "pyautogui":
            return self.pyautogui_backend
        return self.win32_backend

    def set_backend(self, name: str) -> None:
        """Altera dinamicamente o backend de entrada ('win32' ou 'pyautogui')."""
        if name.lower() in ("win32", "pyautogui"):
            self.active_backend_name = name.lower()
            self.logger.info(f"[INPUT] Backend de entrada alterado para: {self.active_backend_name.upper()}")

    def emergency_stop(self) -> None:
        """Aciona parada de emergência e libera teclas."""
        self.safety_guard.trigger_emergency_stop(self.backend)
        self.event_bus.publish(
            EventType.SAFETY_TRIGGERED,
            data={"reason": "Emergency Stop Acionado"},
            category="SAFETY",
            level="CRITICAL",
            message="PARADA DE EMERGÊNCIA ATIVADA — Todas as teclas liberadas",
        )

    def reset_emergency(self) -> None:
        """Reseta a trava de segurança."""
        self.safety_guard.reset_emergency_stop()

    def focus_game_window(self) -> bool:
        """Encontra e ativa a janela alvo do jogo, garantindo foco no canvas."""
        now = time.time()
        if self._is_window_focused and (now - self._last_focus_check < 0.3):
            return True

        self._last_focus_check = now
        success = self.window_manager.bring_to_foreground()
        self._is_window_focused = success

        info = self.window_manager._current_target
        if success and info:
            self.event_bus.publish(
                EventType.TARGET_FOUND,
                data={"hwnd": info.hwnd, "title": info.title},
                category="WINDOW",
                level="INFO",
                message=f"Janela alvo focada: '{info.title}' (HWND: {info.hwnd})",
            )
        elif not success:
            self.event_bus.publish(
                EventType.TARGET_LOST,
                data={"hwnd": info.hwnd if info else 0},
                category="WINDOW",
                level="WARNING",
                message="Janela alvo não confirmada em primeiro plano",
            )

        return success

    def is_target_focused(self) -> bool:
        return self._is_window_focused

    def verify_foreground(self, hwnd: Optional[int] = None) -> bool:
        """Verifica se a janela alvo do jogo está estritamente em primeiro plano no Windows."""
        return self.window_manager.verify_foreground(hwnd)

    def compute_visual_delta(self, frame_before: Optional[np.ndarray], frame_after: Optional[np.ndarray]) -> Tuple[bool, float]:
        """Calcula a variação de pixels entre dois frames para confirmar se houve resposta física real."""
        if frame_before is None or frame_after is None:
            return False, 0.0
        try:
            diff = np.abs(frame_before.astype(np.float32) - frame_after.astype(np.float32))
            delta = float(np.mean(diff) / 255.0)
            confirmed = delta > 0.005
            return confirmed, round(delta, 4)
        except Exception:
            return False, 0.0

    def press_key_with_diagnostic(
        self,
        key: str,
        duration: float = 0.15,
        jitter: bool = True,
        frame_before: Optional[np.ndarray] = None,
        frame_after: Optional[np.ndarray] = None,
    ) -> KeyDiagnosticResult:
        """Pressiona tecla com rastreamento formal dos estados de entrada."""
        k = key.lower().strip()
        self.logger.info(f"⚡ [INPUT] INPUT_REQUESTED: key='{k.upper()}', duration={duration:.2f}s")
        self.event_bus.publish(
            EventType.INPUT_REQUESTED,
            data={"key": k, "duration": duration},
            category="INPUT",
            level="DEBUG",
            message=f"Input solicitado: {k.upper()} ({duration:.2f}s)",
        )

        focused = self.focus_game_window()
        info = self.window_manager._current_target
        hwnd = info.hwnd if info else 0
        title = info.title if info else "Nenhuma"
        fg_hwnd = user32.GetForegroundWindow() if user32 and hasattr(user32, "GetForegroundWindow") else 0
        can_dispatch = self.safety_guard.validate_can_dispatch(
            is_window_confirmed=focused,
            target_hwnd=hwnd,
            target_pid=getattr(info, "pid", None),
            target_title=title,
            target_process=getattr(info, "process_name", None),
            foreground_hwnd=fg_hwnd,
        )

        if not can_dispatch:
            self.logger.warning(f"🛑 [SAFETY] INPUT_BLOCKED: Janela não confirmada, própria aplicação detectada ou parada de emergência ativa.")
            self.event_bus.publish(
                EventType.INPUT_BLOCKED,
                data={"key": k, "reason": "Janela não confirmada, própria aplicação ou Parada de Emergência"},
                category="SAFETY",
                level="WARNING",
                message=f"Input bloqueado por segurança: {k.upper()}",
            )
            return KeyDiagnosticResult(
                key=k,
                vk_code=0,
                scancode=0,
                sendinput_down_ret=0,
                sendinput_up_ret=0,
                keybd_event_dispatched=False,
                postmessage_count=0,
                pyautogui_dispatched=False,
                total_events=0,
                duration=duration,
                window_focused=False,
                visual_delta=0.0,
                movement_confirmed=False,
                success=False,
            )

        vk, scancode = self.win32_backend._get_vk_and_scancode(k)
        actual_duration = max(0.02, duration)
        if jitter and duration > 0.05:
            actual_duration += random.uniform(-0.01, 0.01)
            actual_duration = max(0.02, actual_duration)

        child_hwnds = getattr(info, "child_hwnds", []) if info else []

        try:
            self.safety_guard.track_key_down(k)

            # Executa KeyDown
            self.win32_backend.key_down(k, hwnd, child_hwnds)
            self.pyautogui_backend.key_down(k)
            self.logger.info(f"🎮 [INPUT] INPUT_DISPATCHED: Win32 SendInput (VK=0x{vk:02X}, Scan=0x{scancode:02X}) [KEY_DOWN]")
            self.event_bus.publish(
                EventType.INPUT_SENT,
                data={"key": k, "vk": vk, "scancode": scancode, "duration": actual_duration},
                category="INPUT",
                level="INFO",
                message=f"Tecla {k.upper()} despachada ({actual_duration:.2f}s)",
            )

            time.sleep(actual_duration)

            # Executa KeyUp
            self.win32_backend.key_up(k, hwnd, child_hwnds)
            self.pyautogui_backend.key_up(k)
            self.safety_guard.track_key_up(k)
            self.logger.info(f"🎮 [INPUT] INPUT_DISPATCHED: [KEY_UP] '{k.upper()}' liberada após {actual_duration:.2f}s")

            # Validação de Feedback Visual
            confirmed, delta = self.compute_visual_delta(frame_before, frame_after)
            if frame_before is not None and frame_after is not None:
                self.event_bus.publish(
                    EventType.INPUT_FEEDBACK,
                    data={"key": k, "delta": delta, "confirmed": confirmed},
                    category="PERCEPTION",
                    level="INFO" if confirmed else "WARNING",
                    message=f"Feedback visual tecla {k.upper()}: delta={delta:.4f} ({'CONFIRMADO' if confirmed else 'SEM ALTERAÇÃO'})",
                )

            return KeyDiagnosticResult(
                key=k,
                vk_code=vk,
                scancode=scancode,
                sendinput_down_ret=1,
                sendinput_up_ret=1,
                keybd_event_dispatched=True,
                postmessage_count=len(child_hwnds) + (1 if hwnd else 0),
                pyautogui_dispatched=True,
                total_events=4 + len(child_hwnds),
                duration=actual_duration,
                window_focused=True,
                visual_delta=delta,
                movement_confirmed=confirmed,
                success=True,
            )
        except Exception as e:
            self.logger.error(f"Erro no press_key '{k}': {e}", exc_info=True)
            return KeyDiagnosticResult(
                key=k,
                vk_code=vk,
                scancode=scancode,
                sendinput_down_ret=0,
                sendinput_up_ret=0,
                keybd_event_dispatched=False,
                postmessage_count=0,
                pyautogui_dispatched=False,
                total_events=0,
                duration=actual_duration,
                window_focused=focused,
                visual_delta=0.0,
                movement_confirmed=False,
                success=False,
            )
        finally:
            self.release_all_keys()

    def press_key(self, key: str, duration: float = 0.15, jitter: bool = True) -> bool:
        """Pressiona uma tecla com proteção e liberação garantida."""
        diag = self.press_key_with_diagnostic(key, duration=duration, jitter=jitter)
        return diag.success

    def hold_keys(self, keys: List[str], duration: float = 0.2) -> bool:
        """Pressiona múltiplas teclas simultaneamente (ex: diagonais W+A)."""
        focused = self.focus_game_window()
        info = self.window_manager._current_target
        target_hwnd = info.hwnd if info else None
        target_pid = getattr(info, "pid", None) if info else None
        target_title = getattr(info, "title", None) if info else None
        target_process = getattr(info, "process_name", None) if info else None
        fg_hwnd = user32.GetForegroundWindow() if user32 and hasattr(user32, "GetForegroundWindow") else 0

        if not self.safety_guard.validate_can_dispatch(
            is_window_confirmed=focused,
            target_hwnd=target_hwnd,
            target_pid=target_pid,
            target_title=target_title,
            target_process=target_process,
            foreground_hwnd=fg_hwnd,
        ):
            return False

        child_hwnds = getattr(info, "child_hwnds", []) if info else []

        pressed = []
        try:
            for k in keys:
                clean_k = k.lower().strip()
                self.safety_guard.track_key_down(clean_k)
                self.win32_backend.key_down(clean_k, target_hwnd, child_hwnds)
                self.pyautogui_backend.key_down(clean_k)
                pressed.append(clean_k)

            time.sleep(max(0.02, duration))
            return True
        except Exception as e:
            self.logger.error(f"Erro no hold_keys {keys}: {e}")
            return False
        finally:
            for clean_k in reversed(pressed):
                self.win32_backend.key_up(clean_k, target_hwnd, child_hwnds)
                self.pyautogui_backend.key_up(clean_k)
                self.safety_guard.track_key_up(clean_k)
            self.release_all_keys()

    def release_all_keys(self) -> None:
        """Garante a liberação de qualquer tecla física ativa."""
        self.safety_guard.release_all_keys(self.backend)

    def click(self, x: int, y: int, jitter: bool = True) -> bool:
        """Clica na coordenada validando limites e foco."""
        focused = self.focus_game_window()
        info = self.window_manager._current_target
        target_hwnd = info.hwnd if info else None
        target_pid = getattr(info, "pid", None) if info else None
        target_title = getattr(info, "title", None) if info else None
        target_process = getattr(info, "process_name", None) if info else None
        fg_hwnd = user32.GetForegroundWindow() if user32 and hasattr(user32, "GetForegroundWindow") else 0

        if not self.safety_guard.validate_can_dispatch(
            is_window_confirmed=focused,
            target_hwnd=target_hwnd,
            target_pid=target_pid,
            target_title=target_title,
            target_process=target_process,
            foreground_hwnd=fg_hwnd,
        ):
            return False

        screen_w, screen_h = pyautogui.size()
        target_x = max(0, min(screen_w - 1, x))
        target_y = max(0, min(screen_h - 1, y))

        if jitter:
            target_x += random.randint(-1, 1)
            target_y += random.randint(-1, 1)
            target_x = max(0, min(screen_w - 1, target_x))
            target_y = max(0, min(screen_h - 1, target_y))

        ok_win32 = self.win32_backend.click(target_x, target_y)
        ok_pyautogui = self.pyautogui_backend.click(target_x, target_y)
        return ok_win32 or ok_pyautogui

    def click_normalized(
        self,
        nx: float,
        ny: float,
        frame_width: int,
        frame_height: int,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> bool:
        actual_x = int(nx * frame_width) + offset_x
        actual_y = int(ny * frame_height) + offset_y
        return self.click(actual_x, actual_y)

    def get_screen_center(self) -> Tuple[int, int]:
        bounds = self.window_manager.get_window_bounds()
        if bounds:
            left, top, w, h = bounds
            return left + w // 2, top + h // 2
        w, h = pyautogui.size()
        return w // 2, h // 2
