import time
import logging
from config.settings import BotConfig
from src.input.input_controller import InputController
from src.legacy.old_vision import LegacyVisionSystem
from src.legacy.old_movement import LegacyMovementController
from src.legacy.old_healing import LegacyHealingController
from src.legacy.old_navigation import LegacyNavigationController
from src.legacy.old_battle_macro import LegacyBattleMacro


class LegacyLumenaBotEngine:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("LumenaMacro")
        self.is_running = False

        self.input_ctrl = InputController()
        self.vision = LegacyVisionSystem(
            templates_dir=getattr(config, "templates_dir", "templates"),
            confidence=getattr(config, "confidence", 0.8),
            monitor_index=getattr(config, "monitor", 1),
        )
        self.movement_ctrl = LegacyMovementController(config, self.input_ctrl)
        self.healing_ctrl = LegacyHealingController(config, self.vision, self.input_ctrl)
        self.nav_ctrl = LegacyNavigationController(config, self.input_ctrl)
        self.battle_macro = LegacyBattleMacro(config, self.vision, self.input_ctrl)

        self.battle_count = 0

    def start(self) -> None:
        self.is_running = True
        self.logger.info("🚀 === BOT INICIADO (LEGACY) ===")
        
        if not self.input_ctrl.focus_game_window():
            self.logger.warning("⚠️ Janela 'Lumena' ou 'Chrome' não encontrada. Clique na janela do jogo para dar foco!")

        while self.is_running:
            if self.battle_macro.in_battle():
                self.logger.info("⚔️ Batalha Detectada!")
                self.battle_macro.run_battle_sequence()
                self.battle_count += 1
                self.logger.info(f"Batalhas concluídas: {self.battle_count}/{self.config.battles_before_heal_check}")

                if self.battle_count >= self.config.battles_before_heal_check:
                    self.logger.info("🔋 Limite de batalhas atingido! Executando Rota de Cura...")
                    self.nav_ctrl.walk_to_heal_point()
                    self.healing_ctrl.perform_heal()
                    self.nav_ctrl.return_to_farm_area()
                    self.battle_count = 0
                continue

            self.movement_ctrl.execute_step()
            time.sleep(0.2)

    def stop(self) -> None:
        self.is_running = False
        self.logger.info("⏹ === BOT PARADO ===")
