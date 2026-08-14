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
from src.combat.skill_executor import SkillExecutor
from src.perception.combat_vision import CombatVisionAnalyzer
from src.automation.healing import HealingController
from src.automation.navigation import NavigationController
from src.automation.state_machine import BotState, BotStateMachine
from src.telemetry.telemetry_manager import TelemetryManager
from src.core.event_bus import EventBus, EventType

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
        self.event_bus = EventBus()
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
        self.healing_controller = HealingController(
            config=self.config,
            input_ctrl=self.input_ctrl,
        )
        self.combat_vision = CombatVisionAnalyzer()
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

        # Execution Health & Watchdog Tracker (Real Execution Panel - Regras #18 e #19)
        self._last_physical_action_time = time.time()
        self._stalled_warning_emitted = False
        self.health_monitor: Dict[str, Any] = {
            "state": "STOPPED",
            "target": "NONE",
            "target_type": "NONE",
            "target_confidence": 0.0,
            "player_pos": (0, 0),
            "target_pos": (0, 0),
            "distance": 0.0,
            "decision": "NONE",
            "input": "NONE",
            "window": "NONE",
            "foreground": False,
            "canvas": False,
            "input_dispatched": False,
            "visual_delta": 0.0,
            "action_result": "NONE",
            "last_action": "NONE",
            "time_since_last_action": 0.0,
            # Legacy aliases
            "perception": True,
            "action": True,
            "verification": True,
            "current_goal": "IDLE",
            "current_target": "NONE",
            "last_input": "NONE",
            "last_verified_action": "NONE",
            "last_block_reason": "NONE",
        }

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

        self.event_bus.publish(
            EventType.BOT_STARTED,
            data={"mode": self.mode},
            category="SYSTEM",
            level="INFO",
            message=f"LumenaBotEngine iniciado em modo {self.mode}",
        )

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

        self.event_bus.publish(
            EventType.BOT_STOPPED,
            category="SYSTEM",
            level="INFO",
            message="LumenaBotEngine parado com sucesso",
        )
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
        self.event_bus.publish(
            EventType.SAFETY_TRIGGERED,
            category="SAFETY",
            level="CRITICAL",
            message="EMERGENCY STOP ACIONADO (ESC / Botão Vermelho)",
        )

    def pause(self) -> None:
        self._paused = True
        self.logger.info("⏸️ LumenaBotEngine pausado.")
        self.event_bus.publish(EventType.BOT_PAUSED, category="SYSTEM", level="INFO", message="LumenaBotEngine pausado")

    def resume(self) -> None:
        self._paused = False
        self.input_ctrl.reset_emergency()
        if self.fsm.current_state == BotState.EMERGENCY_STOP:
            self.fsm.transition_to(BotState.OBSERVING, reason="Retomada após emergência")
        self.logger.info("▶️ LumenaBotEngine retomado.")
        self.event_bus.publish(EventType.BOT_RESUMED, category="SYSTEM", level="INFO", message="LumenaBotEngine retomado")

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
        self.telemetry.record_observation()
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

        # Atualiza métricas de monitoramento em tempo real (Regra #18)
        target_info = self.input_ctrl.window_manager._current_target
        fg_hwnd = self.input_ctrl.window_manager.user32.GetForegroundWindow() if hasattr(self.input_ctrl.window_manager, "user32") else 0
        is_fg = bool(target_info and target_info.hwnd == fg_hwnd)
        self.health_monitor["window"] = target_info.title if target_info else "NONE"
        self.health_monitor["foreground"] = is_fg
        self.health_monitor["canvas"] = bool(target_info and target_info.canvas_detected)
        self.health_monitor["time_since_last_action"] = round(time.time() - self._last_physical_action_time, 1)

        if snapshot.player_info and snapshot.player_info.detected:
            self.health_monitor["player_pos"] = snapshot.player_info.center

        # Gera frame anotado para a página Vision da GUI
        self._latest_annotated_frame = self._generate_annotated_frame(frame, snapshot)

        # 3. MEMORY: Atualização da Memória Operacional
        self.memory_manager.update_from_snapshot(snapshot)

        # Watchdog: Verifica se o bot está travado apenas observando sem ação física (> 15s)
        if self._running and not self._paused:
            if time.time() - self._last_physical_action_time > 15.0:
                if not self._stalled_warning_emitted:
                    self.logger.warning("🛑 [WATCHDOG] EXECUTION_STALLED: Nenhuma ação física executada nos últimos 15s!")
                    self.event_bus.publish(
                        EventType.EXECUTION_STALLED,
                        data={"elapsed": time.time() - self._last_physical_action_time, "state": self.fsm.current_state.name},
                        category="SAFETY",
                        level="WARNING",
                        message="EXECUTION_STALLED: Bot observando sem ação há mais de 15s.",
                    )
                    self.health_monitor["action"] = False
                    self._stalled_warning_emitted = True
                    self.input_ctrl.focus_game_window()

        # 4. DECIDE & ACT: Hierarquia Estrita de Objetivos e Máquina de Estados
        bt = snapshot.battle_telemetry
        team_needs_heal = self.memory_manager.team_status.requires_immediate_heal if hasattr(self.memory_manager, "team_status") and self.memory_manager.team_status else False

        if bt and bt.victory_detected:
            self.fsm.transition_to(BotState.VICTORY, reason="Tela de Vitória Detectada")
            self.telemetry.record_battle_result(is_victory=True)
            self.event_bus.publish(EventType.BATTLE_WON, category="COMBAT", level="INFO", message="Batalha vencida!")
            self._handle_battle_cycle(snapshot, frame)

        elif bt and bt.defeat_detected:
            self.fsm.transition_to(BotState.DEFEAT, reason="Tela de Derrota Detectada")
            self.telemetry.record_battle_result(is_victory=False)
            self.event_bus.publish(EventType.BATTLE_LOST, category="COMBAT", level="WARNING", message="Batalha perdida ou Lumen desmaiou")
            self._handle_battle_cycle(snapshot, frame)

        elif snapshot.screen_state in (AgentState.BATTLE, AgentState.BATTLE_DETECTED) or (bt and bt.in_battle):
            self.health_monitor["current_goal"] = "COMBAT"
            self.health_monitor["current_target"] = "ENEMY"
            self.health_monitor["target_type"] = "ENEMY"
            self.health_monitor["state"] = "BATTLE"
            self.fsm.transition_to(BotState.BATTLE, reason="Interface de Batalha Ativa")
            self.event_bus.publish(EventType.BATTLE_STARTED, category="COMBAT", level="INFO", message="Combate iniciado contra inimigo")
            self._handle_battle_cycle(snapshot, frame)

        elif team_needs_heal or snapshot.screen_state in (AgentState.HEALING, AgentState.SEARCHING_CRYSTAL) or snapshot.crystal_detected:
            # Hierarquia de Objetivos: Cristal de Cura tem prioridade máxima quando necessário
            self.health_monitor["current_goal"] = "HEAL"
            self.health_monitor["current_target"] = "HEALING_CRYSTAL"
            self.health_monitor["target_type"] = "HEALING_CRYSTAL"
            self.health_monitor["state"] = "HEALING"
            crystal = snapshot.ui_elements.get("blue_crystal")
            if crystal:
                self.health_monitor["target_confidence"] = crystal.confidence
                self.health_monitor["target_pos"] = crystal.center
                if snapshot.crystal_relative_pos:
                    self.health_monitor["distance"] = round(math.hypot(*snapshot.crystal_relative_pos), 1)
            else:
                self.health_monitor["target_confidence"] = 0.50

            self.fsm.transition_to(BotState.HEALING, reason="Ponto de Cura / Cristal Ativo")
            self._handle_healing_cycle(snapshot, frame)

        elif bt and bt.dialog_active:
            self.health_monitor["current_goal"] = "ADVANCE_DIALOG"
            self.health_monitor["state"] = "DIALOG"
            self.fsm.transition_to(BotState.DIALOG, reason="Caixa de Diálogo Detectada")
            self._handle_dialog_cycle(snapshot)

        elif snapshot.screen_state in (AgentState.EXPLORING, AgentState.SEARCHING_FARM):
            self.health_monitor["current_goal"] = "EXPLORE"
            self.health_monitor["current_target"] = "NONE"
            self.health_monitor["target_type"] = "NONE"
            self.health_monitor["state"] = "EXPLORING"
            self.fsm.transition_to(BotState.EXPLORING, reason="Mundo Aberto Ativo")
            self._handle_overworld_cycle(snapshot, frame)

        else:
            self.health_monitor["state"] = "OBSERVING"
            self.fsm.transition_to(BotState.OBSERVING, reason="Observando Estado Desconhecido")
            self.telemetry.update_agent_status(
                state="OBSERVING",
                objective="Identificando Tela do Jogo",
                decision="Observando",
                reason=f"Estado: {snapshot.screen_state.name}",
            )

        self._consecutive_errors = 0

    def _handle_battle_cycle(self, snapshot: StateSnapshot, frame_before: np.ndarray) -> None:
        """Processa turno de combate inteligente via CombatAgent com visão dinâmica e verificação fechada."""
        if self.mode == "MANUAL":
            self.telemetry.update_agent_status(
                state="BATTLE (MANUAL)",
                objective="Combate Controlado pelo Jogador",
                decision="Aguardando Input Manual",
                reason="Modo Manual Ativo",
            )
            return

        t0 = time.time()
        # Analisa visão dinâmica de combate (N slots de skill, posicionamento, alvos)
        combat_snapshot = self.combat_vision.analyze_frame(frame_before, timestamp=snapshot.timestamp)
        turn_res = self.combat_agent.process_combat_snapshot(combat_snapshot, screen_capture_func=self.screen_capture.capture_frame)
        t1 = time.time()

        if turn_res.executed_successfully:
            self._last_physical_action_time = time.time()
            self._stalled_warning_emitted = False
            self.health_monitor["action"] = True
            self.health_monitor["verification"] = True
            self.health_monitor["last_verified_action"] = f"COMBAT_{turn_res.agent_state.name}"

        if turn_res.decision:
            d = turn_res.decision
            self.health_monitor["last_action"] = getattr(d, "action_type", "ATTACK")
            self.telemetry.update_agent_status(
                state="BATTLE",
                objective="Lutando contra Inimigo",
                decision=f"{getattr(d, 'action_type', 'ACTION')} -> {getattr(d, 'target_name', 'Inimigo')}",
                reason=getattr(d, "reason", "Decisão de Combate"),
            )
            self.event_bus.publish(
                EventType.ACTION_STARTED,
                data={"action_type": getattr(d, "action_type", "ACTION"), "score": getattr(d, "score", 0.0)},
                category="COMBAT",
                level="INFO",
                message=f"Ação de combate: {getattr(d, 'action_type', 'ACTION')} (Score: {getattr(d, 'score', 0.0):.1f})",
            )

        self.telemetry.record_combat_action()
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

        self.health_monitor["current_goal"] = "EXPLORE"
        self.health_monitor["current_target"] = "NONE"
        self.telemetry.update_agent_status(
            state="EXPLORING",
            objective="Patrulhando Área de Farm",
            decision="Navegação WASD",
            reason="Buscando Encontros de Lumens",
        )

        dir_key = "w"
        t0 = time.time()
        self.telemetry.record_movement_action()
        diag = self.input_ctrl.press_key_with_diagnostic(dir_key, duration=0.25)
        t1 = time.time()

        if diag.success:
            self._last_physical_action_time = time.time()
            self._stalled_warning_emitted = False
            self.health_monitor["action"] = True
            self.health_monitor["last_input"] = dir_key.upper()

        # Observa novo frame para confirmação real
        frame_after, _ = self.screen_capture.capture_frame()
        confirmed, delta = self.input_ctrl.compute_visual_delta(frame_before, frame_after)
        self.health_monitor["visual_delta"] = float(delta)

        if confirmed:
            self._last_movement_time = time.time()
            self._consecutive_no_movement = 0
            self.health_monitor["verification"] = True
            self.health_monitor["last_verified_action"] = "OVERWORLD_MOVE"
            self.telemetry.record_action(True, latency=t1 - t0, action_type="OVERWORLD_MOVE")
        else:
            self._consecutive_no_movement += 1
            self.health_monitor["verification"] = False
            self.telemetry.record_action(False, latency=t1 - t0, action_type="OVERWORLD_MOVE_NO_DELTA")
            # Anti-Stuck Trigger
            if self._consecutive_no_movement >= 4:
                self._handle_anti_stuck()

    def _handle_anti_stuck(self) -> None:
        """Rotina inteligente de desengate e recuperação anti-stuck com limite rígido de 3 tentativas."""
        if not hasattr(self, "_recovery_attempts"):
            self._recovery_attempts = 0

        self.telemetry.record_recovery_attempt()
        self._recovery_attempts += 1
        if self._recovery_attempts > 3:
            self.logger.critical(f"🛑 [ANTI-STUCK] Limite de 3 tentativas de recuperação atingido. Acionando Safe Stop.")
            self.fsm.transition_to(BotState.ERROR, reason="Max Anti-Stuck Recovery Attempts Exceeded")
            self.event_bus.publish(
                EventType.RECOVERY_FAILED,
                data={"attempts": self._recovery_attempts},
                category="NAVIGATION",
                level="CRITICAL",
                message="Falha de desengate anti-stuck: limite de 3 tentativas atingido. Entrando em Parada Segura.",
            )
            return

        self.logger.warning(f"⚠️ [ANTI-STUCK] Personagem parado por {self._consecutive_no_movement} passos (Tentativa {self._recovery_attempts}/3). Tentando desengate...")
        self.fsm.transition_to(BotState.RECOVERING, reason=f"Anti-Stuck Jiggle ({self._recovery_attempts}/3)")
        self.event_bus.publish(
            EventType.STUCK_SUSPECTED,
            data={"consecutive_failures": self._consecutive_no_movement, "attempt": self._recovery_attempts},
            category="NAVIGATION",
            level="WARNING",
            message=f"Possível travamento detectado ({self._consecutive_no_movement} passos sem alteração). Iniciando manobra {self._recovery_attempts}/3...",
        )
        self.telemetry.update_agent_status(
            state="RECOVERING",
            objective=f"Desengate Anti-Stuck ({self._recovery_attempts}/3)",
            decision="WASD Jiggle",
            reason="Posição inalterada",
        )
        self.input_ctrl.press_key("s", duration=0.2)
        self.input_ctrl.press_key("d", duration=0.2)
        self.input_ctrl.press_key("w", duration=0.2)
        self._consecutive_no_movement = 0
        self.event_bus.publish(
            EventType.RECOVERY_SUCCESS,
            data={"attempt": self._recovery_attempts},
            category="NAVIGATION",
            level="INFO",
            message=f"Manobra de desengate {self._recovery_attempts}/3 executada.",
        )

    def _handle_healing_cycle(self, snapshot: StateSnapshot, frame: Optional[np.ndarray] = None) -> None:
        """Processa recuperação de vida e PP no ponto de cura com aproximação tática e interação em malha fechada."""
        self.telemetry.record_healing_action()
        h_state, is_done, msg = self.healing_controller.step(
            snapshot,
            frame=frame,
            screen_capture_func=self.screen_capture.capture_frame,
        )
        self.health_monitor["last_action"] = h_state
        self.health_monitor["current_goal"] = "HEAL"
        self.health_monitor["current_target"] = "HEALING_CRYSTAL"
        self.health_monitor["target_type"] = "HEALING_CRYSTAL"
        self.health_monitor["decision"] = msg
        self.health_monitor["visual_delta"] = self.healing_controller.last_delta
        self.health_monitor["action_result"] = "VERIFIED" if self.healing_controller.movement_verified or is_done else "UNCONFIRMED"

        if h_state in ("APPROACH_TARGET", "INTERACTING", "INTERACT_READY"):
            self._last_physical_action_time = time.time()
            self._stalled_warning_emitted = False
            self.health_monitor["action"] = True
            self.health_monitor["input_dispatched"] = True
            self.health_monitor["input"] = self.healing_controller.last_move_key or "SPACE"
            self.health_monitor["last_input"] = self.healing_controller.last_move_key or "SPACE"

        self.telemetry.update_agent_status(
            state=f"HEALING ({h_state})",
            objective="Recuperando Equipe no Cristal",
            decision=msg,
            reason=f"Cristal: {snapshot.crystal_relative_pos}px" if snapshot.crystal_relative_pos else "Buscando",
        )

        if is_done:
            self.health_monitor["verification"] = True
            self.health_monitor["action_result"] = "VERIFIED"
            self.health_monitor["last_verified_action"] = "HEALING_VERIFIED"
            self.fsm.transition_to(BotState.EXPLORING, reason="Cura concluída no Cristal")

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
        self.event_bus.publish(
            EventType.BOT_ERROR,
            data={"error": error_msg, "count": self._consecutive_errors},
            category="ERROR",
            level="ERROR",
            message=f"Erro no ciclo do agente: {error_msg}",
        )

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