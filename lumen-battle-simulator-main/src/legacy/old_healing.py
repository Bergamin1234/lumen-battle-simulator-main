import time
import logging
from config.settings import BotConfig
from src.automation.vision import VisionSystem
from src.input.input_controller import InputController


class LegacyHealingController:
    def __init__(self, config: BotConfig, vision: VisionSystem, input_ctrl: InputController) -> None:
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")

    def perform_heal(self) -> bool:
        """
        Executa a sequência exata de cura no Cristal Azul:
        1. Pressiona Espaço para abrir o diálogo.
        2. Pressiona Espaço para avançar do texto inicial para a confirmação.
        3. Pressiona Espaço para fechar a caixa de diálogo.
        """
        self.logger.info("Aproximando-se do Cristal Azul de Cura...")
        interact_key = getattr(self.config.keys, "interact", "space")

        # 1. Pressionar Espaço para abrir o diálogo do Cristal
        self.input_ctrl.press_key(interact_key, duration=0.2)
        time.sleep(1.2)

        # 2. Pressionar Espaço para avançar do texto inicial ('The crystuml's leught...')
        self.logger.info("Avançando mensagem do Cristal de Cura...")
        self.input_ctrl.press_key(interact_key, duration=0.2)
        time.sleep(1.2)

        # 3. Pressionar Espaço para fechar o diálogo final ('Your Lumens are fully healed...')
        self.logger.info("Concluindo cura do time ('Your Lumens are fully healed')...")
        self.input_ctrl.press_key(interact_key, duration=0.2)
        time.sleep(1.0)

        self.logger.info("✓ Todos os Lumens foram curados com sucesso!")
        return True
