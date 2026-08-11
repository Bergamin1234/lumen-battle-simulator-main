import time
import logging
from config.settings import BotConfig
from src.automation.input_controller import InputController


class NavigationController:
    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")

    def walk_to_healer(self) -> None:
        self.logger.info("Navegando da área de farm até a Estrutura Azul...")
        for step in self.config.route_to_heal:
            key = getattr(self.config.keys, step.direction, "w")
            self.logger.info(f"Andando '{step.direction}' por {step.duration}s")
            self.input_ctrl.press_key(key, duration=step.duration)
            time.sleep(0.1)

    def walk_to_farm(self) -> None:
        self.logger.info("Navegando da Estrutura Azul de volta para o mato...")
        for step in self.config.route_to_farm:
            key = getattr(self.config.keys, step.direction, "w")
            self.logger.info(f"Andando '{step.direction}' por {step.duration}s")
            self.input_ctrl.press_key(key, duration=step.duration)
            time.sleep(0.1)
            