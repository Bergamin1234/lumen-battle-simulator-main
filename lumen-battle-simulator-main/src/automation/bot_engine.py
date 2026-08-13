import time
import os
import json
import logging
import threading
import cv2
from typing import Optional, Dict, Any, Callable, Tuple
import numpy as np

from config.settings import BotConfig, KeyBindings, MonitorConfig, BattleConfig
from src.models import StateSnapshot, BattleTelemetry, TeamStatus, AgentState
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture
from src.perception.state_classifier import StateClassifier
from src.memory.memory_manager import MemoryManager
from src.combat.combat_agent import CombatAgent
from src.combat.action_executor import ActionExecutor
from src.automation.navigation import NavigationController
from src.automation.state_machine import BotState, BotStateMachine
from src.telemetry.telemetry_manager import TelemetryManager

logger = logging.getLogger("LumenaMacro")


class LumenaBotEngine:
    """Motor unificado de ciclo contínuo em malha fechada (Closed Loop) para o Lumena Bot."""

    def __init__(self, config: Optional[BotConfig] = None) -> None:
        self.logger = logging.getLogger("LumenaMacro")
        self.config = config or BotConfig(
            keys=KeyBindings(),
            monitor_cfg=MonitorConfig(),
            battle_cfg=BattleConfig(),
        )
        self.fsm = BotStateMachine(initial_state=BotState.IDLE)
        self.telemetry = TelemetryManager()

        # Componentes do Pipeline
        self.input_ctrl = InputController()
        monitor_idx = getattr(getattr(self.config, "monitor_cfg", None), "monitor_index", getattr(self.config, "monitor", 1))
        self.screen_capture = ScreenCapture(monitor_index=monitor_idx)
        self.state_classifier = StateClassifier()
        self.memory_manager = MemoryManager()
        self.action_executor = ActionExecutor(
            input_controller=self.input_ctrl,
            memory_manager=self.memory_manager,
        )
        self.combat_agent = CombatAgent(
            action_executor=self.action_executor,
            memory_manager=self.memory_manager,
        )
        self.navigation = NavigationController(
            config=self.config,
            input_ctrl=self.input_ctrl,
        )

        # Modos de Execução: 'AUTONOMOUS', 'ASSISTED', 'MANUAL'
        self.mode = "AUTONOMOUS"
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
        self._last_state_snapshot: Optional[StateSnapshot] = None
        self._latest_annotated_frame = None

        # Anti-Stuck & Recovery Tracker
        self._last_movement_time = time.time()
        self._consecutive_no_movement = 0
        self._stuck_threshold_seconds = 10.0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_state(self) -> BotState:
        return self.fsm.current_state

    def get_latest_frame(self):
        """Retorna o frame anotado mais recente para a página Vision da interface."""
        return self._latest_annotated_frame

    def start(self, mode: str = "AUTONOMOUS") -> bool:
        """Inicia a execução do loop fechado do bot."""
        if self._running:
            self.logger.warning("BotEngine já está em execução.")
            return True

        self.mode = mode.upper()
        self._running = True
        self._paused = False
        self._stop_event.clear()
        self._consecutive_errors = 0
        self._consecutive_no_movement = 0

        self.fsm.transition_to(BotState.STARTING, reason="Iniciando BotEngine")
        self.telemetry.update_agent_status(state="STARTING", objective="Validando Ambiente e Janela")

        # Procura e ativa a janela alvo
        self.fsm.transition_to(BotState.INITIALIZING, reason="Procurando janela do Lumena.gg / Chrome")
        target_info = self.input_ctrl.window_manager.find_target_window()

        if target_info:
            self.fsm.transition_to(BotState.FOCUSING, reason="Focando janela do jogo e canvas WebGL")
            self.input_ctrl.focus_game_window()
            self.fsm.transition_to(BotState.OBSERVING, reason="Janela conectada e pronta para observação")
            self.logger.info(f"✓ Conectado à janela: {target_info.title} (HWND: {target_info.hwnd})")
        else:
            self.logger.warning("⚠️ Nenhuma janela do jogo detectada. O bot aguardará a abertura do navegador.")
            self.fsm.transition_to(BotState.OBSERVING, reason="Aguardando janela alvo")

        self.logger.info(f"🚀 LumenaBotEngine iniciado no modo: {self.mode}")
        return True

    def stop(self) -> None:
        """Para a execução do motor de forma segura."""
        self.logger.info("🛑 Parando LumenaBotEngine...")
        self.fsm.transition_to(BotState.STOPPING, reason="Comando de Parada")
        self._running = False
        self._paused = False
        self._stop_event.set()
        self.input_ctrl.release_all_keys()
        self.fsm.transition_to(BotState.IDLE, reason="Motor Parado")
        self.telemetry.update_agent_status(state="IDLE", objective="Parado", decision="Nenhuma", reason="Bot Desativado")
        self.logger.info("✓ LumenaBotEngine parado com segurança.")

    def emergency_stop(self) -> None:
        """Parada imediata de emergência (ESC / Botão Vermelho)."""
        self.logger.critical("🛑 [EMERGENCY STOP] Interrupção Imediata de Emergência!")
        self.input_ctrl.emergency_stop()
        self.fsm.transition_to(BotState.EMERGENCY_STOP, reason="Parada de Emergência Solicitada")
        self._running = False
        self._stop_event.set()
        self.telemetry.update_agent_status(
            state="EMERGENCY_STOP",
            objective="Parada de Emergência",
            decision="BLOQUEIO_TOTAL",
            reason="Intervenção do Usuário (ESC)",
            error="EMERGENCY STOP ACIONADO",
        )

    def pause(self) -> None:
        self._paused = True
        self.logger.info("⏸️ LumenaBotEngine pausado.")

    def resume(self) -> None:
        self._paused = False
        self.input_ctrl.reset_emergency()
        if self.fsm.current_state == BotState.EMERGENCY_STOP:
            self.fsm.transition_to(BotState.OBSERVING, reason="Retomada após emergência")
        self.logger.info("▶️ LumenaBotEngine retomado.")

    def run_loop(self) -> None:
        """Loop principal em malha fechada executado na thread do agente."""
        self.logger.info("⚡ Iniciando loop contínuo de percepção e decisão...")

        while self._running and not self._stop_event.is_set():
            if self._paused:
                time.sleep(0.1)
                continue

            try:
                self.telemetry.record_tick()
                self._execute_single_cycle()
            except Exception as e:
                self.logger.error(f"Erro no ciclo do BotEngine: {e}", exc_info=True)
                self._handle_cycle_error(str(e))

            time.sleep(0.05)

        self.stop()

    def _execute_single_cycle(self) -> None:
        """Executa um passo fechado: Captura ➔ Percepção ➔ Memória ➔ Decisão ➔ Ação ➔ Observação."""
        # 1. OBSERVE: Captura de Tela
        frame, timestamp = self.screen_capture.capture_frame()

        if frame is None:
            self.telemetry.update_agent_status(error="Falha na Captura de Tela (Monitor Inativo)")
            time.sleep(0.2)
            return

        # 2. INTERPRET: Classificação de Estado e Detecção Multimodal
        snapshot = self.state_classifier.classify_frame(frame, timestamp=timestamp)
        self._last_state_snapshot = snapshot
        confidence = 0.9 if snapshot.screen_state != AgentState.UNKNOWN_STATE else 0.2
        self.telemetry.update_perception_confidence(confidence)

        # Gera frame anotado para a página Vision da GUI
        self._latest_annotated_frame = self._generate_annotated_frame(frame, snapshot)

        # 3. MEMORY: Atualização da Memória Operacional
        self.memory_manager.update_from_snapshot(snapshot)

        # 4. DECIDE & ACT: Máquina de Estados e Despacho
        bt = snapshot.battle_telemetry

        if bt and bt.victory_detected:
            self.fsm.transition_to(BotState.VICTORY, reason="Tela de Vitória Detectada")
            self.telemetry.record_battle_result(is_victory=True)
            self._handle_battle_cycle(snapshot, frame)

        elif bt and bt.defeat_detected:
            self.fsm.transition_to(BotState.DEFEAT, reason="Tela de Derrota Detectada")
            self.telemetry.record_battle_result(is_victory=False)
            self._handle_battle_cycle(snapshot, frame)

        elif snapshot.screen_state in (AgentState.BATTLE, AgentState.BATTLE_DETECTED) or (bt and bt.in_battle):
            self.fsm.transition_to(BotState.BATTLE, reason="Interface de Batalha Ativa")
            self._handle_battle_cycle(snapshot, frame)

        elif snapshot.screen_state in (AgentState.HEALING, AgentState.SEARCHING_CRYSTAL) or snapshot.crystal_detected:
            self.fsm.transition_to(BotState.HEALING, reason="Ponto de Cura / Cristal Ativo")
            self._handle_healing_cycle(snapshot)

        elif bt and bt.dialog_active:
            self.fsm.transition_to(BotState.DIALOG, reason="Caixa de Diálogo Detectada")
            self._handle_dialog_cycle(snapshot)

        elif snapshot.screen_state in (AgentState.EXPLORING, AgentState.SEARCHING_FARM):
            self.fsm.transition_to(BotState.EXPLORING, reason="Mundo Aberto Ativo")
            self._handle_overworld_cycle(snapshot, frame)

        else:
            self.fsm.transition_to(BotState.OBSERVING, reason="Observando Estado Desconhecido")
            self.telemetry.update_agent_status(
                state="OBSERVING",
                objective="Identificando Tela do Jogo",
                decision="Observando",
                reason=f"Estado: {snapshot.screen_state.name}",
            )

        self._consecutive_errors = 0

    def _handle_battle_cycle(self, snapshot: StateSnapshot, frame_before: np.ndarray) -> None:
        """Processa turno de combate inteligente via CombatAgent com verificação fechada."""
        if self.mode == "MANUAL":
            self.telemetry.update_agent_status(
                state="BATTLE (MANUAL)",
                objective="Combate Controlado pelo Jogador",
                decision="Aguardando Input Manual",
                reason="Modo Manual Ativo",
            )
            return

        t0 = time.time()
        turn_res = self.combat_agent.process_turn(snapshot)
        t1 = time.time()

        if turn_res.decision:
            d = turn_res.decision
            self.telemetry.update_agent_status(
                state="BATTLE",
                objective="Lutando contra Inimigo",
                decision=f"{d.action_type} -> {d.target_name}",
                reason=d.reason,
            )

        self.telemetry.record_action(
            turn_res.executed_successfully,
            latency=t1 - t0,
            action_type="BATTLE_ACTION",
        )

    def _handle_overworld_cycle(self, snapshot: StateSnapshot, frame_before: np.ndarray) -> None:
        """Processa navegação e exploração no mundo aberto com validação de delta visual e anti-stuck."""
        if self.mode == "MANUAL":
            self.telemetry.update_agent_status(
                state="EXPLORING (MANUAL)",
                objective="Exploração Manual",
                decision="Aguardando WASD",
                reason="Modo Manual Ativo",
            )
            return

        self.telemetry.update_agent_status(
            state="EXPLORING",
            objective="Patrulhando Área de Farm",
            decision="Navegação WASD",
            reason="Buscando Encontros de Lumens",
        )

        dir_key = "w"
        t0 = time.time()
        diag = self.input_ctrl.press_key_with_diagnostic(dir_key, duration=0.25)
        t1 = time.time()

        # Observa novo frame para confirmação real
        frame_after, _ = self.screen_capture.capture_frame()
        confirmed, delta = self.input_ctrl.compute_visual_delta(frame_before, frame_after)

        if confirmed:
            self._last_movement_time = time.time()
            self._consecutive_no_movement = 0
            self.telemetry.record_action(True, latency=t1 - t0, action_type="OVERWORLD_MOVE")
        else:
            self._consecutive_no_movement += 1
            self.telemetry.record_action(False, latency=t1 - t0, action_type="OVERWORLD_MOVE_NO_DELTA")
            # Anti-Stuck Trigger
            if self._consecutive_no_movement >= 4:
                self._handle_anti_stuck()

    def _handle_anti_stuck(self) -> None:
        """Rotina inteligente de desengate e recuperação anti-stuck."""
        self.logger.warning(f"⚠️ [ANTI-STUCK] Personagem parado por {self._consecutive_no_movement} tentativas. Tentando desengate...")
        self.telemetry.update_agent_status(
            state="RECOVERING",
            objective="Desengate Anti-Stuck",
            decision="WASD Jiggle",
            reason="Posição inalterada",
        )
        self.input_ctrl.press_key("s", duration=0.2)
        self.input_ctrl.press_key("d", duration=0.2)
        self.input_ctrl.press_key("w", duration=0.2)
        self._consecutive_no_movement = 0

    def _handle_healing_cycle(self, snapshot: StateSnapshot) -> None:
        """Processa recuperação de vida e PP no ponto de cura."""
        self.telemetry.update_agent_status(
            state="HEALING",
            objective="Recuperando Equipe no Cristal",
            decision="Interagir com Cristal",
            reason="HP Baixo ou Ponto de Cura Próximo",
        )
        self.input_ctrl.press_key("space", duration=0.15)
        time.sleep(0.5)

    def _handle_dialog_cycle(self, snapshot: StateSnapshot) -> None:
        """Avança caixas de diálogo e mensagens na tela."""
        self.telemetry.update_agent_status(
            state="DIALOG",
            objective="Avançando Diálogo",
            decision="Pressionar Espaço / Enter",
            reason="Caixa de Diálogo Detectada",
        )
        self.input_ctrl.press_key("space", duration=0.1)

    def _handle_cycle_error(self, error_msg: str) -> None:
        """Mecanismo de recuperação autônoma com exportação de diagnóstico completo."""
        self._consecutive_errors += 1
        self.telemetry.record_recovery()
        self.telemetry.update_agent_status(error=f"Erro ({self._consecutive_errors}/{self._max_consecutive_errors}): {error_msg}")

        self._save_comprehensive_debug(f"cycle_error_{int(time.time())}", error_msg)

        if self._consecutive_errors >= self._max_consecutive_errors:
            self.fsm.transition_to(BotState.ERROR, reason=f"Limite de {self._max_consecutive_errors} erros atingido")
            self.logger.error("🛑 Limite de erros consecutivos atingido. Acionando recuperação do sistema...")
            self.fsm.transition_to(BotState.RECOVERING, reason="Tentativa de Reaquisição de Janela e Foco")
            self.input_ctrl.release_all_keys()
            self.input_ctrl.focus_game_window()
            time.sleep(1.0)
            self._consecutive_errors = 0
            self.fsm.transition_to(BotState.OBSERVING, reason="Recuperação Concluída")

    def _save_comprehensive_debug(self, tag: str, error_msg: str) -> None:
        """Salva diagnóstico completo (screenshot, state.json, telemetry.json, error.log) em debug/."""
        try:
            os.makedirs("debug", exist_ok=True)
            ts = time.strftime("%Y-%m-%d_%H-%M-%S")
            prefix = f"debug/{ts}_{tag}"

            frame, _ = self.screen_capture.capture_frame()
            if frame is not None:
                cv2.imwrite(f"{prefix}_screenshot.png", frame)

            with open(f"{prefix}_error.log", "w", encoding="utf-8") as f:
                f.write(f"Timestamp: {ts}\nError: {error_msg}\nState: {self.fsm.current_state.name}\nMode: {self.mode}\n")

            with open(f"{prefix}_telemetry.json", "w", encoding="utf-8") as f:
                json.dump(self.telemetry.get_snapshot(), f, indent=2)

            self.logger.info(f"📸 Diagnóstico completo salvo em: {prefix}_*")
        except Exception as e:
            self.logger.debug(f"Não foi possível salvar diagnóstico de debug: {e}")

    def _generate_annotated_frame(self, frame, snapshot: StateSnapshot):
        """Desenha bounding boxes e rótulos semânticos ([PLAYER], [ENEMY], [HP], [FIGHT], [CRYSTAL], [DIALOG]) para a GUI."""
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        state_text = f"STATE: {snapshot.screen_state.name}"
        cv2.rectangle(annotated, (10, 10), (360, 45), (20, 20, 20), -1)
        cv2.putText(annotated, state_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2)

        for name, ui in getattr(snapshot, "ui_elements", {}).items():
            score = getattr(ui, "confidence", 1.0)
            bounds = getattr(ui, "bounding_box", None)
            if bounds:
                bx, by, bw, bh = bounds
                tag = f"[{name.upper()}] ({score:.2f})"
                cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), (0, 165, 255), 2)
                cv2.putText(annotated, tag, (bx, max(15, by - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

        return annotated