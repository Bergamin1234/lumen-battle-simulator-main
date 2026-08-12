import ctypes
import logging
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple
import pygetwindow as gw

logger = logging.getLogger("LumenaWindow")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SW_SHOW = 5


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    pid: int
    is_active: bool
    is_minimized: bool


class TargetWindowManager:
    """Gerenciador robusto de janela alvo com suporte direto a Win32 API para foco e coordenadas."""

    def __init__(self, target_titles: Optional[List[str]] = None) -> None:
        self.logger = logging.getLogger("LumenaWindow")
        self.target_titles = target_titles or [
            "Lumena",
            "Lumena.gg",
            "IA Autônoma para Jogo - Google Chrome",
            "Google Chrome",
            "Chrome",
            "Brave",
            "Edge",
            "Firefox",
        ]
        self._current_target: Optional[WindowInfo] = None
        self._last_focus_time = 0.0

    def find_target_window(self) -> Optional[WindowInfo]:
        """Localiza a janela do jogo e retorna informações estruturadas de HWND e dimensões."""
        all_windows = gw.getAllWindows()
        
        # 1. Procura match exato/prioritário
        for target in self.target_titles:
            for win in all_windows:
                if win.title and target.lower() in win.title.lower():
                    hwnd = win._hWnd
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    is_min = bool(user32.IsIconic(hwnd))
                    is_active = (user32.GetForegroundWindow() == hwnd)
                    
                    info = WindowInfo(
                        hwnd=hwnd,
                        title=win.title,
                        left=win.left,
                        top=win.top,
                        width=win.width,
                        height=win.height,
                        pid=pid.value,
                        is_active=is_active,
                        is_minimized=is_min,
                    )
                    self._current_target = info
                    self.logger.info(f"🪟 Janela alvo identificada: '{info.title}' (HWND: {info.hwnd}, Bounds: {info.width}x{info.height} em {info.left},{info.top})")
                    return info

        self._current_target = None
        return None

    def bring_to_foreground(self, hwnd: Optional[int] = None) -> bool:
        """Traz confiavelmente a janela alvo para o primeiro plano no Windows."""
        target_hwnd = hwnd or (self._current_target.hwnd if self._current_target else None)
        if not target_hwnd:
            info = self.find_target_window()
            if not info:
                return False
            target_hwnd = info.hwnd

        try:
            # 1. Restaura caso minimizada
            if user32.IsIconic(target_hwnd):
                user32.ShowWindow(target_hwnd, SW_RESTORE)
                time.sleep(0.05)
            else:
                user32.ShowWindow(target_hwnd, SW_SHOW)

            # 2. Conecta threads de entrada para contornar restrições de SetForegroundWindow do Windows
            current_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(target_hwnd, None)

            if current_thread != target_thread:
                user32.AttachThreadInput(current_thread, target_thread, True)
                user32.BringWindowToTop(target_hwnd)
                user32.SetForegroundWindow(target_hwnd)
                user32.AttachThreadInput(current_thread, target_thread, False)
            else:
                user32.BringWindowToTop(target_hwnd)
                user32.SetForegroundWindow(target_hwnd)

            time.sleep(0.05)
            is_active = (user32.GetForegroundWindow() == target_hwnd)
            self._last_focus_time = time.time()
            return is_active
        except Exception as e:
            self.logger.error(f"Erro ao focar janela HWND {target_hwnd}: {e}")
            return False

    def ensure_canvas_focus(self, relative_x: float = 0.5, relative_y: float = 0.5) -> bool:
        """Garante foco de teclado no canvas clicando dentro da área útil da janela alvo."""
        if not self.bring_to_foreground():
            return False

        if not self._current_target:
            self.find_target_window()
            if not self._current_target:
                return False

        # Evita re-clicar no canvas se já foi focado há menos de 1 segundo
        if time.time() - self._last_focus_time < 1.0:
            return True

        # Calcula o ponto central do canvas do jogo
        cx = self._current_target.left + int(self._current_target.width * relative_x)
        cy = self._current_target.top + int(self._current_target.height * relative_y)

        # Envia clique direto para garantir foco de teclado no DOM/Canvas do Chrome
        try:
            import pyautogui
            pyautogui.click(cx, cy)
            self._last_focus_time = time.time()
            return True
        except Exception as e:
            self.logger.debug(f"Aviso ao dar foco inicial no canvas: {e}")
            return False

    def get_window_bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """Retorna (left, top, width, height) da janela alvo atual."""
        if self._current_target:
            return (
                self._current_target.left,
                self._current_target.top,
                self._current_target.width,
                self._current_target.height,
            )
        info = self.find_target_window()
        if info:
            return (info.left, info.top, info.width, info.height)
        return None
