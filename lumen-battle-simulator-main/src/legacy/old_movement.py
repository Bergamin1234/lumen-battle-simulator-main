import time
import logging
from config.settings import BotConfig
from src.input.input_controller import InputController


class LegacyMovementController:
    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")
        self.step_toggle = 0

    def execute_step(self) -> None:
        """Executa o movimento de Zig-Zag visível alternando entre Esquerda (A) e Direita (D)."""
        duration = getattr(self.config, "step_duration", 0.4)

        if self.step_toggle == 0:
            self.logger.info("👣 Andando para a ESQUERDA (A)...")
            self.input_ctrl.press_key("a", duration=duration)
            self.step_toggle = 1
        else:
            self.logger.info("👣 Andando para a DIREITA (D)...")
            self.input_ctrl.press_key("d", duration=duration)
            self.step_toggle = 0

        time.sleep(0.1)
