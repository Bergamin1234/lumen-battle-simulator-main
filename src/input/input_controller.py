import time
import random
import logging
from typing import Optional, List, Tuple
import pyautogui
import pygetwindow as gw

# Habilita a trava de segurança obrigatória do PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


class InputController:
    """Controlador de entrada seguro com suporte a micro-ações em malha fechada."""

    def __init__(self, target_window_titles: Optional[List[str]] = None) -> None:
        self.logger = logging.getLogger("LumenaMacro")
        self.target_window_titles = target_window_titles or [
            "Lumena",
            "Lumena.gg",
            "Chrome",
            "Brave",
            "Edge",
            "Firefox",
        ]
        self._last_focus_check = 0.0
        self._is_window_focused = False

    def focus_game_window(self) -> bool:
        """Encontra e foca a janela do jogo caso não esteja ativa."""
        now = time.time()
        # Otimização: evita checagem pesada do SO em intervalos < 0.3s se já estiver focado
        if self._is_window_focused and (now - self._last_focus_check < 0.3):
            return True

        self._last_focus_check = now
        try:
            for title in self.target_window_titles:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    win = windows[0]
                    if not win.isActive:
                        win.activate()
                        time.sleep(0.05)
                    self._is_window_focused = True
                    return True
        except Exception as e:
            self.logger.debug(f"Aviso ao verificar foco da janela: {e}")

        self._is_window_focused = False
        return False

    def press_key(self, key: str, duration: float = 0.15, jitter: bool = True) -> bool:
        """Executa um pressionamento atômico de tecla com duração controlada e micro-jitter."""
        if not self.focus_game_window():
            self.logger.warning("Janela do jogo não pôde ser focada antes do envio de tecla.")

        key_map = {
            "w": "w",
            "a": "a",
            "s": "s",
            "d": "d",
            "e": "e",
            "esc": "esc",
            "space": "space",
            "enter": "enter",
        }
        clean_key = key.lower().strip()
        k = key_map.get(clean_key, clean_key)

        actual_duration = duration
        if jitter and duration > 0.05:
            actual_duration += random.uniform(-0.015, 0.015)
            actual_duration = max(0.02, actual_duration)

        try:
            pyautogui.keyDown(k)
            time.sleep(actual_duration)
            pyautogui.keyUp(k)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao pressionar tecla '{k}': {e}")
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
            return False

    def hold_keys(self, keys: List[str], duration: float = 0.2) -> bool:
        """Pressiona múltiplas teclas simultaneamente (ex: diagonais W+A)."""
        self.focus_game_window()
        pressed = []
        try:
            for key in keys:
                k = key.lower().strip()
                pyautogui.keyDown(k)
                pressed.append(k)

            time.sleep(max(0.02, duration))
            return True
        except Exception as e:
            self.logger.error(f"Erro ao segurar teclas {keys}: {e}")
            return False
        finally:
            for k in reversed(pressed):
                try:
                    pyautogui.keyUp(k)
                except Exception:
                    pass

    def click(self, x: int, y: int, jitter: bool = True) -> bool:
        """Clica na coordenada absoluta após validar limites de tela."""
        self.focus_game_window()
        screen_w, screen_h = pyautogui.size()

        target_x = max(0, min(screen_w - 1, x))
        target_y = max(0, min(screen_h - 1, y))

        if jitter:
            target_x += random.randint(-2, 2)
            target_y += random.randint(-2, 2)
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
        """Retorna o centro da tela principal."""
        w, h = pyautogui.size()
        return w // 2, h // 2
