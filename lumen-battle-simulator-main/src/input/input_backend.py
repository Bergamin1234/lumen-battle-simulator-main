import abc
import ctypes
import time
import random
import logging
from typing import List, Tuple, Dict, Optional
import pyautogui

logger = logging.getLogger("LumenaInput")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
PUL = ctypes.POINTER(ctypes.c_ulong)

# Constantes Win32
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Estruturas Win32 SendInput 64-bit
class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
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
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(Input), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint

# Mapeamentos de Teclas
VK_MAP: Dict[str, int] = {
    "w": 0x57,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    "e": 0x45,
    "space": 0x20,
    "esc": 0x1B,
    "enter": 0x0D,
}

SCANCODES: Dict[str, int] = {
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "e": 0x12,
    "space": 0x39,
    "esc": 0x01,
    "enter": 0x1C,
}


class InputBackend(abc.ABC):
    """Interface abstrata para backends de entrada física."""

    @abc.abstractmethod
    def press_key(self, key: str, duration: float = 0.15) -> bool:
        pass

    @abc.abstractmethod
    def key_down(self, key: str) -> bool:
        pass

    @abc.abstractmethod
    def key_up(self, key: str) -> bool:
        pass

    @abc.abstractmethod
    def click(self, x: int, y: int) -> bool:
        pass

    @abc.abstractmethod
    def release_all(self, active_keys: List[str]) -> None:
        pass


class Win32InputBackend(InputBackend):
    """Backend nativo de alta performance para Windows (SendInput + DirectInput + PostMessage)."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaInput")

    def _get_vk_and_scancode(self, key: str) -> Tuple[int, int]:
        k = key.lower().strip()
        vk = VK_MAP.get(k, ord(k.upper()) if len(k) == 1 else 0)
        sc = SCANCODES.get(k, user32.MapVirtualKeyW(vk, 0))
        return vk, sc

    def key_down(self, key: str, target_hwnd: Optional[int] = None, child_hwnds: Optional[List[int]] = None) -> bool:
        vk, sc = self._get_vk_and_scancode(key)
        # 1. SendInput com scancode
        try:
            ii_ = Input_I()
            ii_.ki = KeyBdInput(vk, sc, KEYEVENTF_SCANCODE, 0, None)
            x = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)
            inserted = user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(Input))
            if inserted == 0:
                err = kernel32.GetLastError()
                self.logger.warning(f"⚠️ [INPUT] SendInput key_down({key}) retornou 0 eventos inseridos (GetLastError={err}).")
        except Exception as e:
            self.logger.debug(f"SendInput key_down exception: {e}")

        # 2. DirectInput keybd_event
        try:
            user32.keybd_event(vk, sc, 0, 0)
        except Exception:
            pass

        # 3. PostMessageW para o HWND e widgets filhos do Chrome
        if target_hwnd:
            lparam = 1 | (sc << 16)
            try:
                user32.PostMessageW(target_hwnd, WM_KEYDOWN, vk, lparam)
            except Exception:
                pass
            for child in (child_hwnds or []):
                try:
                    user32.PostMessageW(child, WM_KEYDOWN, vk, lparam)
                except Exception:
                    pass
        return True

    def key_up(self, key: str, target_hwnd: Optional[int] = None, child_hwnds: Optional[List[int]] = None) -> bool:
        vk, sc = self._get_vk_and_scancode(key)
        # 1. SendInput keyup
        try:
            ii_ = Input_I()
            ii_.ki = KeyBdInput(vk, sc, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, None)
            x = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)
            inserted = user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(Input))
            if inserted == 0:
                err = kernel32.GetLastError()
                self.logger.warning(f"⚠️ [INPUT] SendInput key_up({key}) retornou 0 eventos inseridos (GetLastError={err}).")
        except Exception as e:
            self.logger.debug(f"SendInput key_up exception: {e}")

        # 2. DirectInput keybd_event keyup
        try:
            user32.keybd_event(vk, sc, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

        # 3. PostMessageW keyup
        if target_hwnd:
            lparam = 1 | (sc << 16) | (1 << 30) | (1 << 31)
            try:
                user32.PostMessageW(target_hwnd, WM_KEYUP, vk, lparam)
            except Exception:
                pass
            for child in (child_hwnds or []):
                try:
                    user32.PostMessageW(child, WM_KEYUP, vk, lparam)
                except Exception:
                    pass
        return True

    def press_key(self, key: str, duration: float = 0.15) -> bool:
        self.key_down(key)
        time.sleep(max(0.02, duration))
        self.key_up(key)
        return True

    def click(self, x: int, y: int) -> bool:
        try:
            user32.SetCursorPos(x, y)
            time.sleep(0.01)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception as e:
            self.logger.error(f"Erro no Win32 click ({x}, {y}): {e}")
            return False

    def release_all(self, active_keys: List[str]) -> None:
        for k in list(active_keys):
            self.key_up(k)


class PyAutoGUIInputBackend(InputBackend):
    """Backend baseado em PyAutoGUI (Fallback de alto nível)."""

    def __init__(self) -> None:
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.02

    def key_down(self, key: str) -> bool:
        try:
            pyautogui.keyDown(key.lower().strip())
            return True
        except Exception:
            return False

    def key_up(self, key: str) -> bool:
        try:
            pyautogui.keyUp(key.lower().strip())
            return True
        except Exception:
            return False

    def press_key(self, key: str, duration: float = 0.15) -> bool:
        k = key.lower().strip()
        try:
            pyautogui.keyDown(k)
            time.sleep(max(0.02, duration))
            pyautogui.keyUp(k)
            return True
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        try:
            pyautogui.click(x, y)
            return True
        except Exception:
            return False

    def release_all(self, active_keys: List[str]) -> None:
        for k in list(active_keys):
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
