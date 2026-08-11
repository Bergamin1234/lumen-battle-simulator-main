import random
from config.settings import BotConfig
from src.automation.input_controller import InputController


class MovementController:
    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.pattern_step = 0

    def _move(self, direction: str, duration: float) -> None:
        key = getattr(self.config.keys, direction, "w")
        self.input_ctrl.press_key(key, duration)

    def execute_step(self) -> None:
        pattern = self.config.movement_pattern.lower()
        duration = self.config.step_duration

        if pattern == "zigzag":
            directions = ["up", "right", "down", "right"]
            self._move(directions[self.pattern_step % len(directions)], duration)
            self.pattern_step += 1

        elif pattern == "square":
            directions = ["up", "right", "down", "left"]
            self._move(directions[self.pattern_step % len(directions)], duration)
            self.pattern_step += 1

        elif pattern == "left_right":
            directions = ["left", "right"]
            self._move(directions[self.pattern_step % len(directions)], duration)
            self.pattern_step += 1

        elif pattern == "random":
            chosen = random.choice(["up", "down", "left", "right"])
            self._move(chosen, duration)

        else:
            self._move("left", duration)
            self._move("right", duration)