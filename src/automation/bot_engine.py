import time
import logging
from config.settings import BotConfig
from src.automation.input_controller import InputController
from src.automation.vision import VisionSystem
from src.automation.movement import MovementController
from src.automation.healing import HealingController
from src.automation.navigation import NavigationController
from src.automation.battle_macro import BattleMacro


class LumenaBotEngine:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("LumenaMacro")
        self.is_running = False

        self.input_ctrl = InputController()
        self.vision = VisionSystem(
            templates_dir=getattr(config, "templates_dir", "templates"),
            confidence=getattr(config, "confidence", 0.8),
            monitor_index=getattr(config, "monitor", 1),
        )
        self.movement_ctrl = MovementController(config, self.input_ctrl)
        self.healing_ctrl = HealingController(config, self.vision, self.input_ctrl)
        self.nav_ctrl = NavigationController(config, self.input_ctrl)
        self.battle_macro = BattleMacro(config, self.vision, self.input_ctrl)

        self.battle_count = 0

    def start(self) -> None:
        self.is_running = True
        self.logger.info("🚀 === BOT INICIADO (DANDO FOCO NO NAVEGADOR) ===")
        
        # Garante que a janela do jogo recebe o foco do Windows
        if not self.input_ctrl.focus_game_window():
            self.logger.warning("⚠️ Janela 'Lumena' ou 'Chrome' não encontrada. Clique na janela do jogo para dar foco!")

        while self.is_running:
            # 1. Checa se entrou em Batalha
            if self.battle_macro.in_battle():
                self.logger.info("⚔️ Batalha Detectada!")
                self.battle_macro.run_battle_sequence()
                self.battle_count += 1
                self.logger.info(f"Batalhas concluídas: {self.battle_count}/{self.config.battles_before_heal_check}")

                # Se bateu o limite de batalhas, executa a Rota
                if self.battle_count >= self.config.battles_before_heal_check:
                    self.logger.info("🔋 Limite de batalhas atingido! Executando Rota de Cura...")
                    self.nav_ctrl.walk_to_heal_point()
                    self.healing_ctrl.perform_heal()
                    self.nav_ctrl.return_to_farm_area()
                    self.battle_count = 0
                continue

            # 2. Se não está em batalha, ANDA em Zig-Zag no Mato
            self.movement_ctrl.execute_step()
            time.sleep(0.2)

    def stop(self) -> None:
        self.is_running = False
        self.logger.info("⏹ === BOT PARADO ===")

    def test_vision_system(self) -> dict[str, bool]:
        return {
            "fight_button.png": self.vision.template_exists("fight_button.png"),
        }