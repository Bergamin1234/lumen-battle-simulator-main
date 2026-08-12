import time
import random
import logging
import ctypes
from typing import Optional, List, Tuple
import pyautogui

from src.input.target_window import TargetWindowManager

# Configurações de segurança do PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02

user32 = ctypes.windll.user32
PUL = ctypes.POINTER(ctypes.c_ulong)

# Estruturas Win32 SendInput para despacho de baixo nível (garantia de recepção no Chrome/Canvas)
class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short), ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

# Scancodes de hardware do teclado (DirectInput / Win32)
SCANCODES = {
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "e": 0x12,
    "space": 0x39,
    "esc": 0x01,
    "enter": 0x1C,
}

KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class InputController:
    """Controlador de entrada seguro com suporte duplo (Win32 SendInput direto + PyAutoGUI fallback)."""

    def __init__(self, target_window_titles: Optional[List[str]] = None) -> None:
        self.logger = logging.getLogger("LumenaInput")
        self.target_window_titles = target_window_titles or [
            "Lumena",
            "Lumena.gg",
            "IA Autônoma para Jogo - Google Chrome",
            "Google Chrome",
            "Chrome",
            "Brave",
            "Edge",
            "Firefox",
        ]
        self.window_manager = TargetWindowManager(self.target_window_titles)
        self._active_held_keys = set()
        self._is_window_focused = False
        self._last_focus_check = 0.0

    def focus_game_window(self) -> bool:
        """Encontra e ativa a janela alvo do jogo, garantindo foco no canvas."""
        now = time.time()
        if self._is_window_focused and (now - self._last_focus_check < 0.3):
            return True

        self._last_focus_check = now
        success = self.window_manager.bring_to_foreground()
        self._is_window_focused = success
        return success

    def _win32_key_down(self, scancode: int) -> None:
        try:
            extra = ctypes.c_ulong(0)
            ii_ = Input_I()
            ii_.ki = KeyBdInput(0, scancode, KEYEVENTF_SCANCODE, 0, ctypes.pointer(extra))
            x = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)
            user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
        except Exception:
            pass

    def _win32_key_up(self, scancode: int) -> None:
        try:
            extra = ctypes.c_ulong(0)
            ii_ = Input_I()
            ii_.ki = KeyBdInput(0, scancode, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
            x = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)
            user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
        except Exception:
            pass

    def press_key(self, key: str, duration: float = 0.15, jitter: bool = True) -> bool:
        """Pressiona uma tecla de forma atômica com garantia de liberação e timing preciso."""
        self.focus_game_window()
        k = key.lower().strip()
        scancode = SCANCODES.get(k)

        actual_duration = max(0.02, duration)
        if jitter and duration > 0.05:
            actual_duration += random.uniform(-0.01, 0.01)
            actual_duration = max(0.02, actual_duration)

        try:
            self._active_held_keys.add(k)
            # Envia via Win32 hardware scancode (para Chrome/Canvas)
            if scancode is not None:
                self._win32_key_down(scancode)
            # Envia via PyAutoGUI
            pyautogui.keyDown(k)

            time.sleep(actual_duration)

            if scancode is not None:
                self._win32_key_up(scancode)
            pyautogui.keyUp(k)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao pressionar tecla '{k}': {e}")
            return False
        finally:
            self.release_all_keys()

    def hold_keys(self, keys: List[str], duration: float = 0.2) -> bool:
        """Pressiona simultaneamente múltiplas teclas (ex: diagonais W+A) com liberação segura."""
        self.focus_game_window()
        pressed = []
        try:
            for key in keys:
                k = key.lower().strip()
                scancode = SCANCODES.get(k)
                if scancode is not None:
                    self._win32_key_down(scancode)
                pyautogui.keyDown(k)
                pressed.append(k)
                self._active_held_keys.add(k)

            time.sleep(max(0.02, duration))
            return True
        except Exception as e:
            self.logger.error(f"Erro ao segurar teclas {keys}: {e}")
            return False
        finally:
            for k in reversed(pressed):
                sc = SCANCODES.get(k)
                try:
                    if sc is not None:
                        self._win32_key_up(sc)
                    pyautogui.keyUp(k)
                except Exception:
                    pass
                self._active_held_keys.discard(k)

    def release_all_keys(self) -> None:
        """Garante que nenhuma tecla permaneça presa no sistema operacional."""
        for k in list(self._active_held_keys):
            sc = SCANCODES.get(k)
            try:
                if sc is not None:
                    self._win32_key_up(sc)
                pyautogui.keyUp(k)
            except Exception:
                pass
        self._active_held_keys.clear()

    def click(self, x: int, y: int, jitter: bool = True) -> bool:
        """Clica na coordenada especificada validando limites de tela e bounds."""
        self.focus_game_window()
        screen_w, screen_h = pyautogui.size()

        target_x = max(0, min(screen_w - 1, x))
        target_y = max(0, min(screen_h - 1, y))

        if jitter:
            target_x += random.randint(-1, 1)
            target_y += random.randint(-1, 1)
            target_x = max(0, min(screen_w - 1, target_x))
            target_y = max(0, min(screen_h - 1, target_y))

        try:
            pyautogui.click(target_x, target_y)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao clicar em ({target_x}, {target_y}): {e}")
            return False

    def click_normalized(
        self,
        nx: float,
        ny: float,
        frame_width: int,
        frame_height: int,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> bool:
        """Executa clique a partir de coordenadas normalizadas (0.0 a 1.0)."""
        actual_x = int(nx * frame_width) + offset_x
        actual_y = int(ny * frame_height) + offset_y
        return self.click(actual_x, actual_y)

    def get_screen_center(self) -> Tuple[int, int]:
        """Retorna o centro da janela do jogo ou da tela principal."""
        bounds = self.window_manager.get_window_bounds()
        if bounds:
            left, top, w, h = bounds
            return left + w // 2, top + h // 2
        w, h = pyautogui.size()
        return w // 2, h // 2
