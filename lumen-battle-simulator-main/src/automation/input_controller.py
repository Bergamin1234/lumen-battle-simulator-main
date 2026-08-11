import random
import time
import pyautogui

pyautogui.FAILSAFE = True


class InputController:
    def __init__(self, key_delay: float = 0.05) -> None:
        self.key_delay = key_delay

    def press_key(self, key: str, duration: float = 0.1) -> None:
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)
        time.sleep(self.key_delay)

    def click(self, x: int, y: int, delay: float = 0.1) -> None:
        jitter_x = x + random.randint(-2, 2)
        jitter_y = y + random.randint(-2, 2)
        pyautogui.click(x=jitter_x, y=jitter_y)
        time.sleep(delay)

    def click_relative(self, base_box: tuple[int, int, int, int], offset_x: int = 0, offset_y: int = 0) -> None:
        x, y, w, h = base_box
        center_x = x + (w // 2) + offset_x
        center_y = y + (h // 2) + offset_y
        self.click(center_x, center_y)