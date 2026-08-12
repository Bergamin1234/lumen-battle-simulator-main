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
        self.vision = VisionSystem(config)
        self.movement_ctrl = MovementController(config, self.input_ctrl)
        self.healing_ctrl = HealingController(config, self.vision, self.input_ctrl)
        self.nav_ctrl = NavigationController(config, self.input_ctrl)
        self.battle_macro = BattleMacro(config, self.vision, self.input_ctrl)

        self.battle_count = 0

    def start(self) -> None:
        """Loop Infinito 100% Autônomo e Auto-Sustentável."""
        self.is_running = True
        self.logger.info("🚀 === LUMENA BOT AUTÔNOMO INICIADO (CICLO INFINITO) ===")

        while self.is_running:
            # 1. MONITORAMENTO DE BATALHA: Checa se entrou em combate
            if self.battle_macro.in_battle():
                self.logger.info("⚔️ Lumena selvagem encontrado! Entrando em combate...")
                self.battle_macro.run_battle_sequence()
                self.battle_count += 1
                self.logger.info(f"Progresso do Ciclo: {self.battle_count}/{self.config.battles_before_heal_check} batalhas realizadas.")

                # 2. ROTA AUTÔNOMA DE CURA: Ao atingir o número limite de lutas
                if self.battle_count >= self.config.battles_before_heal_check:
                    self.logger.info("🔋 Time precisa de restauração! Iniciando ciclo de cura na cidade...")
                    
                    # Passo A: Volta para a cidade
                    self.nav_ctrl.walk_to_heal_point()
                    
                    # Passo B: Restaura Lumens no Cristal Azul (Sequência de Espaço)
                    self.healing_ctrl.perform_heal()
                    
                    # Passo C: Atravessa o Portal Amarelo de volta para o mato
                    self.nav_ctrl.return_to_farm_area()
                    
                    # Zera o contador para o próximo ciclo infinito
                    self.battle_count = 0
                continue

            # 3. FARM NO MATO: Se não está em batalha, realiza movimento Zig-Zag com WASD
            self.movement_ctrl.execute_step()
            time.sleep(0.1)

    def stop(self) -> None:
        self.is_running = False
        self.logger.info("⏹ === BOT PARADO ===")

    def test_vision_system(self) -> dict[str, bool]:
        return {
            "fight_button.png": self.vision.template_exists("fight_button.png"),
        }