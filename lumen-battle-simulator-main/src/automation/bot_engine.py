import os
import time
import logging
import threading
from config.settings import BotConfig
from src.automation.vision import VisionSystem
from src.automation.input_controller import InputController
from src.automation.movement import MovementController
from src.automation.navigation import NavigationController
from src.automation.healing import HealingController
from src.automation.battle_macro import BattleController


def setup_logging(logs_dir: str) -> None:
    os.makedirs(logs_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, "macro.log"), encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


class LumenaBotEngine:
    def __init__(self) -> None:
        self.config = BotConfig.load_from_json()
        setup_logging(self.config.logs_dir)
        self.logger = logging.getLogger("LumenaMacro")

        self.vision = VisionSystem(
            templates_dir=self.config.templates_dir,
            confidence=self.config.confidence,
            monitor_index=self.config.monitor
        )
        self.input_ctrl = InputController()
        self.movement = MovementController(self.config, self.input_ctrl)
        self.battle = BattleController(self.config, self.vision, self.input_ctrl)
        self.navigation = NavigationController(self.config, self.input_ctrl)
        self.healing = HealingController(self.config, self.vision, self.input_ctrl)

        self.is_running = False
        self.macro_thread: threading.Thread | None = None

    def full_heal_routine(self) -> None:
        self.logger.info("=== CICLO DE REPOSIÇÃO E CURA NA ESTRUTURA AZUL ===")
        self.navigation.walk_to_healer()
        self.healing.perform_heal()
        self.navigation.walk_to_farm()
        self.battle.reset_battle_counter()
        self.logger.info("=== RETORNANDO AO FARM ===")

    def _macro_loop(self) -> None:
        self.logger.info("Loop do Bot Autônomo iniciado.")
        while self.is_running:
            try:
                if self.battle.in_battle():
                    self.battle.handle_battle()

                    if self.battle.needs_healing():
                        self.full_heal_routine()
                else:
                    self.movement.execute_step()

                time.sleep(0.02)
            except Exception as e:
                self.logger.error(f"Erro na FSM do Bot: {e}")
                time.sleep(1.0)

    def start(self) -> None:
        if not self.is_running:
            self.is_running = True
            self.macro_thread = threading.Thread(target=self._macro_loop, daemon=True)
            self.macro_thread.start()
            print("\n[+] Bot Autônomo INICIADO.")

    def stop(self) -> None:
        if self.is_running:
            self.is_running = False
            if self.macro_thread and self.macro_thread.is_alive():
                self.macro_thread.join(timeout=2.0)
            print("\n[-] Bot PARADO.")