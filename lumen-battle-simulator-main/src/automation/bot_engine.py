import time
import logging
from typing import Optional, Dict

from config.settings import BotConfig
from src.models.enums import AgentState
from src.models.lumen import StateSnapshot, TeamStatus, LumenMemberState, Element
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture
from src.perception.state_classifier import StateClassifier
from src.memory.memory_manager import MemoryManager
from src.memory.world_memory import WorldMemory
from src.memory.experience_store import ExperienceStore
from src.combat.combat_agent import CombatAgent, CombatAgentState
from src.combat.action_executor import ActionExecutor
from src.automation.navigation import NavigationController
from src.automation.healing import HealingController
from src.automation.movement import MovementController


class LumenaBotEngine:
    """Motor unificado e autônomo em malha fechada (Closed-Loop) integrando Percepção, Memória, Decisão e Execução Física."""

    def __init__(self, config: Optional[BotConfig] = None) -> None:
        self.config = config or BotConfig.load_from_json()
        self.logger = logging.getLogger("LumenaMacro")
        self.is_running = False

        # 1. Camada de Entrada e Janela
        self.input_ctrl = InputController()

        # 2. Camada de Percepção
        monitor_idx = getattr(self.config, "monitor", 1)
        self.screen_capture = ScreenCapture(monitor_index=monitor_idx)
        self.state_classifier = StateClassifier()

        # 3. Camada de Memória
        self.world_memory = WorldMemory()
        self.experience_store = ExperienceStore(db_path="config/experience.db")
        self.memory_manager = MemoryManager(
            world_memory=self.world_memory,
            experience_store=self.experience_store,
        )

        # 4. Camada de Decisão e Combate
        self.action_executor = ActionExecutor(
            input_controller=self.input_ctrl,
            memory_manager=self.memory_manager,
        )
        self.combat_agent = CombatAgent(
            action_executor=self.action_executor,
            memory_manager=self.memory_manager,
        )

        # 5. Navegação e Movimento
        self.nav_ctrl = NavigationController(self.config, self.input_ctrl)
        self.movement_ctrl = MovementController(self.config, self.input_ctrl)

        # 6. Telemetria e Contadores
        self.tick_count = 0
        self.battle_count = 0
        self.consecutive_errors = 0

    def start(self) -> None:
        """Inicia o loop autônomo contínuo."""
        self.is_running = True
        self.tick_count = 0
        self.consecutive_errors = 0

        self.logger.info("🚀 [MAIN] Bot Autônomo Iniciado!")
        self.logger.info("🔍 [WINDOW] Procurando e ativando janela do jogo...")

        # Traz a janela do jogo para frente e garante foco
        if self.input_ctrl.focus_game_window():
            self.logger.info("✓ [WINDOW] Janela alvo ativada com sucesso!")
        else:
            self.logger.warning("⚠️ [WINDOW] Janela do jogo não encontrada. Por favor, mantenha o Chrome/Lumena visível.")

        self.logger.info("⚡ [AGENT] Loop principal em malha fechada ativo.")

        while self.is_running:
            self.tick_count += 1
            loop_start = time.time()

            try:
                # 1. OBSERVE (Captura de tela real)
                frame, timestamp = self.screen_capture.capture_frame()
                if frame is None:
                    self.logger.debug(f"[LOOP #{self.tick_count}] Sem frame capturado nesta iteração.")
                    time.sleep(0.2)
                    continue

                # 2. INTERPRET (Classificação do estado da cena)
                motion_energy = self.screen_capture.get_motion_energy()
                snapshot: StateSnapshot = self.state_classifier.classify_frame(
                    frame=frame,
                    timestamp=timestamp,
                    motion_energy=motion_energy,
                )

                # 3. UPDATE MEMORY (Ingestão no modelo de mundo)
                self.memory_manager.ingest_snapshot(snapshot)

                # 4. DECIDE & ACT (Comportamento de acordo com o estado do jogo)
                state = snapshot.screen_state
                self.logger.info(f"[TICK #{self.tick_count}] Estado: {state.name} | Grama: {snapshot.grass_density:.1%} | Cristal: {snapshot.crystal_detected}")

                # Cenário A: Batalha Ativa ou Tela de Resultado de Combate
                if state in (AgentState.BATTLE, AgentState.BATTLE_RESULT) or (snapshot.battle_telemetry and snapshot.battle_telemetry.in_battle):
                    turn_result = self.combat_agent.process_turn(snapshot)
                    self.logger.info(f"⚔️ [COMBATE] Turno {turn_result.turn_count}: {turn_result.message}")

                    if turn_result.agent_state == CombatAgentState.VICTORY:
                        self.battle_count += 1
                        self.logger.info(f"🏆 [COMBATE] Batalha vencida! Total: {self.battle_count}/{self.config.battles_before_heal_check}")
                        self.combat_agent.reset_battle()

                        # Se atingiu o limite de batalhas, executa a rota de cura
                        if self.battle_count >= self.config.battles_before_heal_check:
                            self.logger.info("🔋 [CURA] Limite de batalhas atingido! Executando rota até o Cristal...")
                            self.nav_ctrl.walk_to_heal_point()
                            self._execute_crystal_heal()
                            self.nav_ctrl.return_to_farm_area()
                            self.battle_count = 0

                    elif turn_result.agent_state == CombatAgentState.DEFEAT:
                        self.logger.warning("💀 [COMBATE] Derrota registrada. Retornando ao ponto seguro...")
                        self.combat_agent.reset_battle()
                        self.nav_ctrl.return_to_farm_area()

                # Cenário B: Diálogo ou Menu Aberto
                elif state == AgentState.DIALOG:
                    self.logger.info("💬 [DIALOG] Avançando caixa de diálogo com Espaço...")
                    self.input_ctrl.press_key("space", duration=0.15)
                    time.sleep(0.3)

                # Cenário C: Mundo Aberto / Exploração / Farm no Mato
                elif state in (AgentState.OVERWORLD, AgentState.EXPLORING, AgentState.HEALING):
                    if snapshot.crystal_detected:
                        self.logger.info("💎 [CRISTAL] Cristal de cura visível na tela.")
                    
                    # Movimento de farm em zig-zag
                    self.movement_ctrl.execute_step()

                # Reseta erros consecutivos após ciclo bem-sucedido
                self.consecutive_errors = 0

            except Exception as e:
                self.consecutive_errors += 1
                self.logger.error(f"❌ [ERRO] Exceção no ciclo #{self.tick_count}: {e}", exc_info=True)
                if self.consecutive_errors >= 5:
                    self.logger.warning("⚠️ [RECOVERY] Múltiplos erros consecutivos. Pausando por 1.0s para recuperação.")
                    time.sleep(1.0)
                    self.input_ctrl.release_all_keys()

            # Controle de taxa do loop (5 a 10 ticks por segundo para responsividade sem sobrecarga)
            elapsed = time.time() - loop_start
            sleep_time = max(0.05, 0.20 - elapsed)
            time.sleep(sleep_time)

    def _execute_crystal_heal(self) -> None:
        """Executa a sequência de interação com o Cristal de Cura."""
        self.logger.info("💎 [CURA] Interagindo com o Cristal Azul...")
        for step_idx in range(3):
            self.input_ctrl.press_key("space", duration=0.2)
            time.sleep(1.2)
        self.logger.info("✓ [CURA] Lumens restaurados!")

    def stop(self) -> None:
        """Interrompe imediatamente o loop e libera todas as entradas físicas."""
        self.is_running = False
        self.input_ctrl.release_all_keys()
        self.screen_capture.close()
        self.logger.info("⏹ [MAIN] Bot Autônomo Parado.")

    def test_vision_system(self) -> Dict[str, bool]:
        """Realiza teste de percepção no frame atual da tela."""
        frame, _ = self.screen_capture.capture_frame()
        if frame is None:
            return {"Captura de Tela": False}

        snapshot = self.state_classifier.classify_frame(frame)
        return {
            "Captura de Tela": True,
            "Estado Semântico": snapshot.screen_state.name,
            "Botão FIGHT Detectado": snapshot.battle_telemetry.fight_button_pos is not None if snapshot.battle_telemetry else False,
            "Cristal Azul Detectado": snapshot.crystal_detected,
            "Vegetação/Grama Presente": snapshot.grass_density > 0.05,
        }