import time
import logging
import pyautogui
import pygetwindow as gw

# Segurança do PyAutoGUI
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05


class InputController:
    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaMacro")

    def focus_game_window(self) -> bool:
        """Encontra e foca a janela do navegador/jogo Lumena para que as teclas funcionem."""
        try:
            windows = gw.getWindowsWithTitle("Lumena")
            if not windows:
                windows = gw.getWindowsWithTitle("Chrome")

            if windows:
                win = windows[0]
                if not win.isActive:
                    win.activate()
                    time.sleep(0.2)
                return True
        except Exception as e:
            self.logger.debug(f"Aviso ao focar janela: {e}")
        return False

    def press_key(self, key: str, duration: float = 0.2) -> None:
        """Foca o jogo e pressiona a tecla desejada (WASD / Espaço) por X segundos."""
        self.focus_game_window()
        key_map = {"w": "w", "a": "a", "s": "s", "d": "d", "space": "space"}
        k = key_map.get(key.lower(), key.lower())

        pyautogui.keyDown(k)
        time.sleep(duration)
        pyautogui.keyUp(k)

    def click(self, x: int, y: int) -> None:
        """Foca a janela e clica na coordenada exata."""
        self.focus_game_window()
        pyautogui.click(x, y)

    def get_screen_center(self) -> tuple[int, int]:
        """Retorna o centro da tela principal."""
        w, h = pyautogui.size()
        return w // 2, h // 2