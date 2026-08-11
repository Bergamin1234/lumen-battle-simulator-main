import time
import logging
from config.settings import BotConfig
from src.automation.vision import VisionSystem
from src.automation.input_controller import InputController


class HealingController:
    def __init__(self, config: BotConfig, vision: VisionSystem, input_ctrl: InputController) -> None:
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")

    def perform_heal(self) -> bool:
        self.logger.info("Interagindo com a Estrutura Azul de Cura...")
        interact_key = self.config.keys.interact

        self.input_ctrl.press_key(interact_key, duration=0.2)
        time.sleep(0.8)

        start_time = time.time()
        max_dialogue_timeout = 12.0

        while time.time() - start_time < max_dialogue_timeout:
            heal_yes = self.vision.find_template("heal_yes_btn.png")
            if heal_yes:
                cx, cy = self.vision.get_center_coords(heal_yes)
                self.input_ctrl.click(cx, cy)
                self.logger.info("Confirmado clique no menu de cura.")
                time.sleep(1.0)
                continue

            if self.vision.template_exists("dialog_box.png") or self.vision.template_exists("dialog_arrow.png"):
                self.logger.info("Avançando diálogo da Estrutura Azul...")
                self.input_ctrl.press_key(interact_key, duration=0.15)
                time.sleep(0.6)
                continue

            close_btn = self.vision.find_template("close_dialog.png")
            if close_btn:
                cx, cy = self.vision.get_center_coords(close_btn)
                self.input_ctrl.click(cx, cy)
                self.logger.info("Diálogo concluído via botão fechar.")
                break

            if not self.vision.template_exists("dialog_box.png") and not self.vision.template_exists("dialog_arrow.png"):
                self.input_ctrl.press_key(interact_key, duration=0.15)
                time.sleep(0.5)
                break

        self.logger.info("Equipe totalmente restaurada!")
        return True