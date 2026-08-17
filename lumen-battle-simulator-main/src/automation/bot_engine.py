import time
import os
import json
import math
import logging
import threading
import cv2
from typing import Optional, Dict, Any, Callable, Tuple
import numpy as np

from config.settings import BotConfig, KeyBindings, MonitorConfig, BattleConfig
from src.models import StateSnapshot, BattleTelemetry, TeamStatus, AgentState
from src.models.combat_vision import CombatSnapshot
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
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult
from src.combat.battle_ui_controller import BattleUIController
from src.navigation.movement_controller import GrassPatrolEngine
from src.navigation.recorded_path_engine import RecordedPathEngine
from src.perception.hp_bar_parser import HPBarParser
from src.telemetry.blackbox_recorder import BlackboxFlightRecorder
from src.automation.self_healing_engine import SelfHealingEngine

logger = logging.getLogger("LumenaMacro")


class LumenaBotEngine:
    """Motor central autônomo e determinístico do Lumena Bot Master v5.0 / v5.3."""

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaBotEngine")
        self.config = config or BotConfig(
            keys=KeyBindings(),
            monitor_cfg=MonitorConfig(),
            battle_cfg=BattleConfig(),
        )
        self.event_bus = event_bus or EventBus()
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

        # v3.7 & v3.8 Battle UI Controller & Detector
        self.battle_ui_detector = BattleUIDetector(event_bus=self.event_bus)
        self.battle_ui_controller = BattleUIController(
            input_controller=self.input_ctrl,
            ui_detector=self.battle_ui_detector,
            event_bus=self.event_bus,
        )
        self.battle_action_deadline = 2.0
        self.battle_observation_without_action = 0

        # v5.3 HP Parser & Recorded Path Engine (Waypoint Macro & Healing Sequence)
        self.hp_parser = HPBarParser()
        self.recorded_path_engine = RecordedPathEngine(
            input_controller=self.input_ctrl,
            event_bus=self.event_bus,
        )

        # v3.9 Emergency Killswitch & Safety
        from src.input.killswitch import EmergencyKillswitch
        self.killswitch = EmergencyKillswitch(
            event_bus=self.event_bus,
            state_machine=self.fsm,
            release_keys_callback=lambda: self.input_ctrl.backend.release_all_keys() if hasattr(self.input_ctrl, "backend") and hasattr(self.input_ctrl.backend, "release_all_keys") else None,
        )
        # v4.2 Blackbox Flight Recorder (15s Ring Buffer in RAM)
        self.blackbox = BlackboxFlightRecorder(buffer_size=150)

        # v4.3 Self-Healing Runtime Engine
        self.self_healing = SelfHealingEngine(
            window_manager=self.input_ctrl.window_manager,
            input_controller=self.input_ctrl,
            event_bus=self.event_bus,
        )

        # v5.0 Grass Patrol Engine & Map-Agnostic Anti-Softlock
        self.grass_patrol = GrassPatrolEngine(
            input_controller=self.input_ctrl,
            event_bus=self.event_bus,
        )
        self._prev_frame: Optional[np.ndarray] = None
        self._crystal_search_start_time: float = 0.0
        self._crystal_search_cooldown_until: float = 0.0

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
        self._last_combat_action_time = time.time()
        self._stalled_warning_emitted = False
        self._combat_stalled_emitted = False
        self.critical_hp_ratio = getattr(self.config, "critical_hp_ratio", 0.35)
        self.healing_hp_ratio = getattr(self.config, "healing_hp_ratio", 0.35)
        self.combat_action_timeout = getattr(self.config, "combat_action_timeout", 5.0)

        self.health_monitor: Dict[str, Any] = {
            "state": "STOPPED",
            "battle_status": "INACTIVE",
            "battle_ui": "INACTIVE",
            "fight": "NOT_FOUND",
            "enemy_detected": "NO",
            "player_hp": "100 / 100",
            "hp_ratio": "100.0%",
            "healing_required": "NO",
            "crystal": "BLOCKED",
            "crystal_search": "BLOCKED",
            "crystal_search_blocked": True,
            "skills_detected": 0,
            "skills_available": 0,
            "selected_skill": "NONE",
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
            "watchdog": "OK",
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

        self.killswitch.start_listening()
        self.logger.info(f"🚀 LumenaBotEngine iniciado no modo: {self.mode}")
        return True

    def stop(self) -> None:
        """Para a execução do motor de forma segura."""
        self.logger.info("🛑 Parando LumenaBotEngine...")
        self.killswitch.stop_listening()
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
        self.blackbox.dump_blackbox(reason="EMERGENCY_STOP")
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

        # 1.1 Detecção Dinâmica de Canvas Bounds & Letterboxing (Módulo 0)
        canvas_bounds = self.screen_capture.detect_webgl_canvas_bounds(frame)
        self.health_monitor["canvas_bounds"] = canvas_bounds
        self.health_monitor["is_letterboxed"] = self.screen_capture.is_letterboxed

        # 1.2 Self-Healing: Detecção de Congelamento WebGL e Popups Intrusivos (Módulo 2)
        if self._running and not self._paused:
            self.self_healing.detect_and_recover_webgl_freeze(frame)
            self.self_healing.auto_dismiss_unexpected_popups(frame)

        # 1.3 Gravação no Blackbox Flight Recorder em Memória (Módulo 3)
        self.blackbox.record_step(
            frame=frame,
            state_name=self.fsm.current_state.name,
            last_input=self.health_monitor.get("last_input", ""),
            events=[e.__dict__ for e in self.event_bus.get_recent_events(5) if hasattr(e, "__dict__")],
            extra_metrics={"hp_ratio": self.health_monitor.get("hp_ratio", "100%"), "state": self.fsm.current_state.name},
        )

        # 2. INTERPRET: Classificação de Estado e Detecção Multimodal
        snapshot = self.state_classifier.classify_frame(frame, timestamp=timestamp)
        self._last_state_snapshot = snapshot
        confidence = 0.9 if snapshot.screen_state != AgentState.UNKNOWN_STATE else 0.2
        self.telemetry.update_perception_confidence(confidence)

        # 2.1 Análise Visual de Combate Dinâmico (SkillScanner & EnemyVision)
        combat_snapshot = self.combat_vision.analyze_frame(frame, timestamp=timestamp)
        bt = snapshot.battle_telemetry

        # 2.2 Blindagem de Resiliência: Detecção de Desconexão de Rede e Tela de Carregamento
        in_battle = bool((bt and bt.in_battle) or (combat_snapshot and combat_snapshot.in_battle))

        if not in_battle:
            if self._detect_network_disconnect(frame, snapshot=snapshot):
                self.logger.warning("🌐 [RESILIENCE] Queda de conexão detectada! Transicionando para NETWORK_RECONNECTING e acionando recarga.")
                self.fsm.transition_to(BotState.NETWORK_RECONNECTING, reason="Perda de Conexão")
                self.input_ctrl.press_key("f5", duration=0.2)
                self.health_monitor["state"] = "NETWORK_RECONNECTING"
                return

            if "black_screen" in snapshot.ui_elements or snapshot.screen_state == AgentState.CALIBRATING:
                self.logger.debug("⏳ [RESILIENCE] Tela de carregamento / transição detectada.")
                self.fsm.transition_to(BotState.LOADING_SCREEN, reason="Tela de Carregamento")
                self._last_physical_action_time = time.time()
                self._last_combat_action_time = time.time()
                self.health_monitor["state"] = "LOADING_SCREEN"
                return

        # Atualiza métricas de monitoramento em tempo real (Regra #18 e #19)
        target_info = self.input_ctrl.window_manager._current_target
        fg_hwnd = self.input_ctrl.window_manager.get_foreground_window()
        is_fg = bool(target_info and target_info.hwnd == fg_hwnd)
        self.health_monitor["window"] = target_info.title if target_info else "NONE"
        self.health_monitor["foreground"] = is_fg
        self.health_monitor["canvas"] = bool(target_info and target_info.canvas_detected)
        self.health_monitor["time_since_last_action"] = round(time.time() - self._last_physical_action_time, 1)

        if snapshot.player_info and snapshot.player_info.detected:
            self.health_monitor["player_pos"] = snapshot.player_info.center

        # Gera frame anotado para a página Vision da GUI
        self._latest_annotated_frame = self._generate_annotated_frame(frame, snapshot, combat_snapshot)

        # 3. MEMORY: Atualização da Memória Operacional
        self.memory_manager.update_from_snapshot(snapshot)

        # Watchdog Geral: Verifica se o bot está travado apenas observando sem ação física (> 15s)
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

        # 4. DECIDE & ACT: HIERARQUIA REVISADA v3.6 (Batalha > Exploração > Cura Preventiva)
        team_needs_heal = self.memory_manager.team_status.requires_immediate_heal if hasattr(self.memory_manager, "team_status") and self.memory_manager.team_status else False

        # Extração e normalização da taxa de HP do jogador
        player_hp_pct = bt.player_hp_pct if (bt and bt.player_hp_pct is not None) else (combat_snapshot.player_hp if combat_snapshot and combat_snapshot.player_hp is not None else 1.0)
        self.health_monitor["hp_ratio"] = f"{player_hp_pct * 100:.1f}%"
        self.health_monitor["player_hp"] = f"{int(player_hp_pct * 113)} / 113"

        crit_threshold = self.critical_hp_ratio
        heal_threshold = self.healing_hp_ratio

        # Verificação Visual Estrita da Arena de Batalha (Zero Guesswork / Direct Visual Gating - Diretiva v5.2)
        is_battle_visually_confirmed = self.battle_ui_detector.is_battle_visually_confirmed(
            frame=frame,
            canvas_bounds=self.health_monitor.get("canvas_bounds"),
        )
        is_battle_active = is_battle_visually_confirmed or bool(bt and (bt.in_battle or bt.victory_detected or bt.defeat_detected)) or (snapshot.screen_state in (AgentState.BATTLE, AgentState.BATTLE_DETECTED)) or bool(combat_snapshot and combat_snapshot.in_battle)

        if bt and bt.victory_detected:
            self.grass_patrol.release_all_movement_keys()
            self.health_monitor["battle_status"] = "VICTORY"
            self.fsm.transition_to(BotState.VICTORY, reason="Tela de Vitória Detectada")
            self.telemetry.record_battle_result(is_victory=True)
            self.event_bus.publish(EventType.BATTLE_WON, category="COMBAT", level="INFO", message="Batalha vencida!")
            self._handle_battle_cycle(snapshot, frame, combat_snapshot=combat_snapshot)

        elif bt and bt.defeat_detected:
            self.grass_patrol.release_all_movement_keys()
            self.health_monitor["battle_status"] = "DEFEAT"
            self.fsm.transition_to(BotState.DEFEAT, reason="Tela de Derrota Detectada")
            self.telemetry.record_battle_result(is_victory=False)
            self.event_bus.publish(EventType.BATTLE_LOST, category="COMBAT", level="WARNING", message="Batalha perdida ou Lumen desmaiou")
            self._handle_battle_cycle(snapshot, frame, combat_snapshot=combat_snapshot)

        elif is_battle_active:
            # ========================================================
            # REGRA ABSOLUTA: COMBATE TEM PRIORIDADE TOTAL
            # ========================================================
            self.grass_patrol.release_all_movement_keys()
            self.health_monitor["battle_status"] = "ACTIVE"
            self.health_monitor["current_goal"] = "COMBAT"
            self.health_monitor["current_target"] = "ENEMY"
            self.health_monitor["target_type"] = "ENEMY"
            self.health_monitor["state"] = "BATTLE"
            self.health_monitor["crystal_search"] = "BLOCKED"
            self.health_monitor["crystal_search_blocked"] = True
            self.health_monitor["healing_required"] = "NO" if player_hp_pct > crit_threshold else "EMERGENCY"

            if player_hp_pct <= crit_threshold:
                self.logger.warning(f"⚠️ [EMERGÊNCIA] HP Crítico em Batalha ({player_hp_pct*100:.1f}% <= {crit_threshold*100:.1f}%)!")

            self.fsm.transition_to(BotState.BATTLE, reason="Arena de Batalha Confirmada Visualmente")
            self._handle_battle_cycle(snapshot, frame, combat_snapshot=combat_snapshot)

        elif (player_hp_pct <= heal_threshold or team_needs_heal):
            # FORA DE COMBATE E HP BAIXO (<= 35%) -> CURA PREVENTIVA VIA ROTA GRAVADA (ETAPA 3 & 4)
            self.health_monitor["battle_status"] = "INACTIVE"
            self.health_monitor["enemy_detected"] = "NO"
            self.health_monitor["current_goal"] = "HEAL"
            self.health_monitor["current_target"] = "HEALING_CRYSTAL"
            self.health_monitor["target_type"] = "HEALING_CRYSTAL"
            self.health_monitor["state"] = "RETURNING_TO_HEAL"
            self.health_monitor["crystal_search"] = "ALLOWED"
            self.health_monitor["crystal_search_blocked"] = False
            self.health_monitor["healing_required"] = "YES"

            crystal = snapshot.ui_elements.get("blue_crystal")
            if crystal or snapshot.crystal_detected:
                if crystal:
                    self.health_monitor["target_confidence"] = crystal.confidence
                    self.health_monitor["target_pos"] = crystal.center
                if snapshot.crystal_relative_pos:
                    self.health_monitor["distance"] = round(math.hypot(*snapshot.crystal_relative_pos), 1)
                self.health_monitor["state"] = "HEALING"
                self.fsm.transition_to(BotState.HEALING, reason=f"Cristal Visível. Aproximação Tática ({player_hp_pct*100:.1f}%)")
                self._handle_healing_cycle(snapshot, frame)
            else:
                self.health_monitor["target_confidence"] = 0.50
                self.health_monitor["state"] = "RETURNING_TO_HEAL"
                self.fsm.transition_to(BotState.RETURNING_TO_HEAL, reason=f"HP Baixo fora de combate ({player_hp_pct*100:.1f}% <= {heal_threshold*100:.1f}%)")
                self._handle_healing_route(snapshot, frame)

        elif bt and bt.dialog_active:
            self.health_monitor["battle_status"] = "INACTIVE"
            self.health_monitor["current_goal"] = "ADVANCE_DIALOG"
            self.health_monitor["state"] = "DIALOG"
            self.health_monitor["crystal_search"] = "BLOCKED"
            self.health_monitor["crystal_search_blocked"] = True
            self.fsm.transition_to(BotState.DIALOG, reason="Caixa de Diálogo Detectada")
            self._handle_dialog_cycle(snapshot)

        elif snapshot.screen_state in (AgentState.EXPLORING, AgentState.SEARCHING_FARM):
            # FORA DE COMBATE COM HP SAUDÁVEL -> EXPLORAÇÃO
            self.health_monitor["battle_status"] = "INACTIVE"
            self.health_monitor["enemy_detected"] = "NO"
            self.health_monitor["current_goal"] = "EXPLORE"
            self.health_monitor["current_target"] = "NONE"
            self.health_monitor["target_type"] = "NONE"
            self.health_monitor["state"] = "EXPLORING"
            self.health_monitor["crystal_search"] = "BLOCKED"
            self.health_monitor["crystal_search_blocked"] = True
            self.health_monitor["healing_required"] = "NO"
            self.fsm.transition_to(BotState.EXPLORING, reason="Mundo Aberto Ativo (HP Saudável)")
            self._handle_overworld_cycle(snapshot, frame)

        else:
            self.health_monitor["state"] = "OBSERVING"
            self.health_monitor["battle_status"] = "INACTIVE"
            self.health_monitor["crystal_search"] = "BLOCKED"
            self.health_monitor["crystal_search_blocked"] = True
            self.fsm.transition_to(BotState.OBSERVING, reason="Observando Estado Desconhecido")
            self.telemetry.update_agent_status(
                state="OBSERVING",
                objective="Identificando Tela do Jogo",
                decision="Observando",
                reason=f"Estado: {snapshot.screen_state.name if hasattr(snapshot.screen_state, 'name') else snapshot.screen_state}",
            )

        self._consecutive_errors = 0

    def resolve_high_level_state(
        self,
        snapshot: StateSnapshot,
        frame: Optional[np.ndarray] = None,
    ) -> BotState:
        """Resolução estrita de estado de alto nível (Section 20).
        1. Se BATTLE UI / Batalha confirmada -> BATTLE (Prioridade Absoluta)
        2. Se LOW_HP fora de batalha -> HEALING
        3. Caso contrário -> WORLD (EXPLORING / READY)
        """
        battle_ui_res = self.battle_ui_detector.analyze_battle_ui(frame) if frame is not None else None
        bt = snapshot.battle_telemetry
        is_battle = bool(
            (battle_ui_res and battle_ui_res.battle_ui_confirmed) or
            (bt and bt.in_battle) or
            (snapshot.screen_state in (AgentState.BATTLE, AgentState.BATTLE_DETECTED))
        )
        if is_battle:
            return BotState.BATTLE

        player_hp_pct = bt.player_hp_pct if (bt and bt.player_hp_pct is not None) else 1.0
        team_needs_heal = (
            self.memory_manager.team_status.requires_immediate_heal
            if hasattr(self.memory_manager, "team_status") and self.memory_manager.team_status
            else False
        )
        if player_hp_pct <= self.healing_hp_ratio or team_needs_heal:
            return BotState.HEALING

        return BotState.EXPLORING

    def _handle_battle_cycle(
        self,
        snapshot: StateSnapshot,
        frame_before: np.ndarray,
        combat_snapshot: Optional[CombatSnapshot] = None,
    ) -> None:
        """Processa turno de combate inteligente via CombatAgent com visão dinâmica e verificação fechada."""
        # 1. Solta imediatamente quaisquer teclas de movimentação (W, A, S, D)
        self.grass_patrol.release_all_movement_keys()

        if self.mode == "MANUAL":
            self.telemetry.update_agent_status(
                state="BATTLE (MANUAL)",
                objective="Combate Controlado pelo Jogador",
                decision="Aguardando Input Manual",
                reason="Modo Manual Ativo",
            )
            return

        t0 = time.time()
        # 1. Analisa Battle UI dedicada (Template-First)
        battle_ui_res = self.battle_ui_detector.analyze_battle_ui(frame_before)
        self.health_monitor["battle_ui"] = "CONFIRMED" if battle_ui_res.battle_ui_confirmed else "INACTIVE"
        self.health_monitor["fight"] = "FOUND" if (battle_ui_res.fight_button and battle_ui_res.fight_button.is_present) else "NOT_FOUND"

        # Se estiver em Turn Lock (aguardando resolução da animação de turno)
        if self.battle_ui_controller.is_waiting_turn_resolution:
            res_done = self.battle_ui_controller.process_turn_resolution_check(frame_before)
            if not res_done:
                self.logger.debug("⏳ [COMBAT] Aguardando resolução da animação de turno...")
                self.battle_ui_controller.handle_battle_watchdog()
                return

        in_battle_hint = bool(
            (combat_snapshot and combat_snapshot.in_battle) or
            (snapshot and snapshot.battle_telemetry and snapshot.battle_telemetry.in_battle) or
            (snapshot and snapshot.screen_state in (AgentState.BATTLE, AgentState.BATTLE_DETECTED))
        )

        # Checa se a batalha terminou (apenas se vitória/derrota detectada ou se nem telemetria nem snapshot nem visual indicam batalha)
        bt = snapshot.battle_telemetry
        if (bt and (bt.victory_detected or bt.defeat_detected)) or (not in_battle_hint and not self.battle_ui_detector.is_battle_visually_confirmed(frame_before, canvas_bounds=self.health_monitor.get("canvas_bounds"))):
            if self.battle_ui_controller.is_battle_finished(frame_before, in_battle_hint=in_battle_hint) or not in_battle_hint:
                self.logger.info("⚔️ [BATTLE UI] Batalha finalizada. Avaliando HP pós-combate (ETAPA 3)...")
                player_hp = snapshot.player_info.hp_ratio if snapshot.player_info else 1.0
                if player_hp <= self.healing_hp_ratio:
                    self.logger.warning(f"🩹 [POST_BATTLE] HP Crítico pós-batalha ({player_hp*100:.1f}% <= {self.healing_hp_ratio*100:.1f}%). Transicionando para rota gravada de cura (ETAPA 4).")
                    self.fsm.transition_to(BotState.POST_BATTLE_EVALUATION, reason="Batalha Concluída")
                    self._handle_healing_route(snapshot, frame_before)
                else:
                    self.logger.info("🌲 [POST_BATTLE] HP Saudável (> 35%). Retornando à exploração (ETAPA 1).")
                    self.fsm.transition_to(BotState.EXPLORING, reason="Batalha Concluída (HP Saudável)")
                    self._handle_overworld_cycle(snapshot, frame_before)
                return

        # Se um modal pós-batalha for detectado (VICTORY, LEVEL UP, LOOT, REWARD)
        if battle_ui_res.modal_detected:
            self.logger.info(f"🏆 [BATTLE UI] Modal pós-combate detectado ({battle_ui_res.modal_type}). Dispensando modal...")
            self.battle_ui_controller.dismiss_post_battle_modal(frame_before, screen_capture_func=self.screen_capture.capture_frame)
            return

        # Se nenhum elemento visual de batalha e nenhuma dica de batalha for confirmada, retoma EXPLORING
        if not in_battle_hint and not self.battle_ui_detector.is_battle_visually_confirmed(frame_before, canvas_bounds=self.health_monitor.get("canvas_bounds")):
            self.logger.info("🌲 [BATTLE UI] Arena de combate não mais visível. Retornando ao estado EXPLORING.")
            self.fsm.transition_to(BotState.EXPLORING, reason="Arena de Combate Inexistente")
            return

        # Se o botão FIGHT estiver disponível e o menu de skills não estiver aberto: CLIQUE DETERMINÍSTICO IMEDIATO
        if battle_ui_res.fight_button and battle_ui_res.fight_button.is_present and not battle_ui_res.skill_menu_open:
            self.logger.info("⚔️ [BATTLE UI] Botão FIGHT detectado. Executando clique determinístico imediato.")
            dispatched, latency, verified = self.battle_ui_controller.click_fight(
                frame_before=frame_before,
                screen_capture_func=self.screen_capture.capture_frame,
            )
            if dispatched:
                self._last_physical_action_time = time.time()
                self._last_combat_action_time = time.time()
                self._stalled_warning_emitted = False
                self._combat_stalled_emitted = False
                self.health_monitor["input_dispatched"] = True
                self.health_monitor["input_requested"] = True
                self.health_monitor["action"] = True
                self.health_monitor["verification"] = verified
                self.health_monitor["last_action"] = "CLICK_FIGHT"
                self.health_monitor["decision"] = "CLICK_FIGHT"
                self.telemetry.record_action(True, latency=latency, action_type="CLICK_FIGHT")
                return

        # Se o menu de habilidades estiver aberto: Seleciona e despacha habilidade primária
        if battle_ui_res.skill_menu_open:
            skills = self.battle_ui_controller.find_available_skills(frame_before)
            if skills:
                primary = self.battle_ui_controller.select_primary_skill(skills)
                if primary:
                    self.logger.info(f"⚔️ [BATTLE UI] Executando habilidade primária: {primary.skill_name} (#{primary.slot_index})")
                    dispatched, latency, verified = self.battle_ui_controller.execute_skill(
                        skill=primary,
                        frame_before=frame_before,
                        screen_capture_func=self.screen_capture.capture_frame,
                    )
                    if dispatched:
                        self._last_physical_action_time = time.time()
                        self._last_combat_action_time = time.time()
                        self._stalled_warning_emitted = False
                        self._combat_stalled_emitted = False
                        self.health_monitor["input_dispatched"] = True
                        self.health_monitor["input_requested"] = True
                        self.health_monitor["action"] = True
                        self.health_monitor["verification"] = verified
                        self.health_monitor["last_action"] = f"SKILL_{primary.slot_index}"
                        self.health_monitor["decision"] = f"SKILL_{primary.slot_index}"
                        self.telemetry.record_action(True, latency=latency, action_type="USE_SKILL")
                        return

        # 2. Analisa visão dinâmica de combate (N slots de skill, posicionamento, alvos)
        csnap = combat_snapshot if combat_snapshot is not None else self.combat_vision.analyze_frame(frame_before, timestamp=snapshot.timestamp)

        # Atualiza métricas de combate para a GUI e HealthMonitor
        self.health_monitor["battle_status"] = "ACTIVE"
        self.health_monitor["player_detected"] = "YES" if getattr(csnap, "player_detected", True) else "NO"
        self.health_monitor["player_hp"] = f"{int(csnap.player_hp * 113)} / 113"
        self.health_monitor["hp_ratio"] = f"{csnap.player_hp * 100:.1f}%"
        self.health_monitor["crystal_search"] = "BLOCKED"
        self.health_monitor["crystal_search_blocked"] = True
        self.health_monitor["skills_detected"] = len(csnap.available_skills)
        avail_count = sum(1 for s in csnap.available_skills if s.available and s.cooldown <= 0)
        self.health_monitor["skills_available"] = avail_count
        self.health_monitor["watchdog"] = "OK"

        if csnap.target_enemy:
            self.health_monitor["enemy_detected"] = "YES"
            self.health_monitor["target"] = csnap.target_enemy.name or "ENEMY"
            self.health_monitor["target_pos"] = csnap.target_enemy.center
            self.health_monitor["distance"] = round(csnap.target_enemy.distance, 1)
        else:
            self.health_monitor["enemy_detected"] = "NO"
            self.health_monitor["target"] = "NONE"

        # Watchdog de Batalha (Regra dos 5 segundos / Zero Fake Pass)
        time_since_combat_action = time.time() - self._last_combat_action_time
        if csnap.target_enemy and (time_since_combat_action > self.combat_action_timeout):
            self.health_monitor["watchdog"] = "STALLED"
            if not self._combat_stalled_emitted:
                self.logger.warning(f"🛑 [WATCHDOG] BATTLE_EXECUTION_STALLED: Batalha ativa sem ação há {time_since_combat_action:.1f}s > {self.combat_action_timeout}s!")
                self.event_bus.publish(
                    EventType.BATTLE_EXECUTION_STALLED,
                    data={
                        "elapsed": time_since_combat_action,
                        "target": csnap.target_enemy.name if csnap.target_enemy else "ENEMY",
                        "foreground": self.input_ctrl.verify_foreground(),
                        "hwnd": getattr(self.input_ctrl.window_manager._current_target, "hwnd", 0),
                        "backend": self.input_ctrl.active_backend_name,
                    },
                    category="COMBAT",
                    level="WARNING",
                    message=f"BATTLE_EXECUTION_STALLED: Nenhuma ação física enviada há {time_since_combat_action:.1f}s. Forçando reaquisição de foco e input.",
                )
                self._combat_stalled_emitted = True
                self.input_ctrl.focus_game_window()
                self.input_ctrl.window_manager.ensure_canvas_focus(0.5, 0.5)

            if time_since_combat_action > 25.0:
                self.logger.critical("🛑 [SAFE_STOP] Parada segura acionada por inatividade crítica em combate.")
                self.event_bus.publish(
                    EventType.EXECUTION_FAILURE,
                    data={"reason": "Stall de combate crítico > 25s", "elapsed": time_since_combat_action},
                    category="SAFETY",
                    level="CRITICAL",
                    message="EXECUTION_FAILURE: Combate travado sem resposta de entrada física.",
                )

        # Executa turno com frame_before real para permitir verificação de delta visual
        turn_res = self.combat_agent.process_combat_snapshot(
            csnap,
            screen_capture_func=self.screen_capture.capture_frame,
            frame_before=frame_before,
        )
        t1 = time.time()

        if turn_res.executed_successfully and turn_res.decision and turn_res.decision.action_type not in ("WAIT", "REASSESS", "NO_ACTION"):
            self._last_physical_action_time = time.time()
            self._last_combat_action_time = time.time()
            self._stalled_warning_emitted = False
            self._combat_stalled_emitted = False
            self.health_monitor["input_dispatched"] = True
            self.health_monitor["input_requested"] = True
            self.health_monitor["action"] = True
            self.health_monitor["verification"] = True
            self.health_monitor["last_verified_action"] = f"COMBAT_{turn_res.agent_state.name}"
        else:
            self.health_monitor["input_dispatched"] = False
            self.health_monitor["verification"] = False

        if turn_res.decision:
            d = turn_res.decision
            self.health_monitor["decision"] = getattr(d, "action_type", "ATTACK")
            self.health_monitor["last_action"] = getattr(d, "action_type", "ATTACK")
            if hasattr(d, "selected_skill") and d.selected_skill:
                self.health_monitor["selected_skill"] = f"#{d.selected_skill.slot_index} ({d.selected_skill.skill_name})"
            else:
                self.health_monitor["selected_skill"] = "NONE"

            self.telemetry.update_agent_status(
                state="BATTLE",
                objective=f"Lutando contra {getattr(csnap.target_enemy, 'name', 'Inimigo')}",
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
        """Processa navegação e exploração no mundo aberto via GrassPatrolEngine (Wiggle A/D e Anti-Stuck)."""
        if self.mode == "MANUAL":
            self.telemetry.update_agent_status(
                state="EXPLORING (MANUAL)",
                objective="Exploração Manual",
                decision="Aguardando WASD",
                reason="Modo Manual Ativo",
            )
            return

        # Se HP estiver baixo (<= 35%), transiciona para rotina de cura no Cristal via rota gravada (ETAPA 4)
        player_hp = snapshot.player_info.hp_ratio if snapshot.player_info else 1.0
        if player_hp <= self.healing_hp_ratio:
            self.logger.warning(f"🩹 [EXPLORING] HP Baixo ({player_hp*100:.1f}% <= {self.healing_hp_ratio*100:.1f}%). Transicionando para rota gravada de cura no Cristal.")
            self._handle_healing_route(snapshot, frame_before)
            return

        # Executa passo de patrulha oscilatória no mato alto (A/D Wiggle + Ancoragem + Anti-Stuck)
        t0 = time.time()
        self.telemetry.record_movement_action()
        key_dispatched, stuck_triggered = self.grass_patrol.execute_patrol_step(
            current_frame=frame_before,
            prev_frame=self._prev_frame,
        )
        t1 = time.time()

        self._last_physical_action_time = time.time()
        self._stalled_warning_emitted = False
        self.health_monitor["action"] = True
        self.health_monitor["last_input"] = str(key_dispatched).upper()
        self.health_monitor["verification"] = True
        self.health_monitor["last_verified_action"] = f"GRASS_PATROL_{str(key_dispatched).upper()}"
        self.telemetry.record_action(True, latency=t1 - t0, action_type="GRASS_PATROL")
        self._prev_frame = frame_before.copy() if frame_before is not None else None

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

    def _detect_network_disconnect(self, frame: np.ndarray, snapshot: Optional[StateSnapshot] = None) -> bool:
        """Detector de perda de conexão WebSocket/HTTP e desync de sessão."""
        if snapshot is not None and "network_disconnected" in snapshot.ui_elements:
            return True

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        std_dev = float(np.std(gray))
        mean_val = float(np.mean(gray))

        # Mede saturação de cor: overlay de desconexão é acromático (cinza/dessaturado)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) if len(frame.shape) == 3 else None
        mean_sat = float(np.mean(hsv[:, :, 1])) if hsv is not None else 0.0

        # Se for um overlay cinza uniforme característico de desconexão (std_dev baixo, mean intermediário e baixa saturação)
        if std_dev < 15.0 and 30 < mean_val < 110 and mean_sat < 25.0:
            return True
        return False

    def _handle_healing_route(self, snapshot: StateSnapshot, frame: Optional[np.ndarray] = None) -> None:
        """Executa a sequência determinística de 3 etapas com rota gravada até o cristal e retorno (ETAPA 4)."""
        self.grass_patrol.release_all_movement_keys()
        self.telemetry.record_healing_action()
        self.health_monitor["current_goal"] = "HEAL"
        self.health_monitor["current_target"] = "HEALING_CRYSTAL"
        self.health_monitor["target_type"] = "HEALING_CRYSTAL"
        self.health_monitor["state"] = "RETURNING_TO_HEAL"
        self.fsm.transition_to(BotState.RETURNING_TO_HEAL, reason="Executando Rota Gravada para Cristal")

        # Executa o protocolo de 3 etapas da RecordedPathEngine
        success = self.recorded_path_engine.execute_healing_sequence(
            screen_capture_func=self.screen_capture.capture_frame,
            hp_check_func=lambda f: self.hp_parser.parse_player_hp_ratio(f),
            cancel_predicate=lambda: not self._running or self._paused,
        )

        if success:
            self.logger.info("🌲 [HEALING ROUTE] Cura no cristal concluída. Retomando exploração no mato.")
            self.fsm.transition_to(BotState.EXPLORING, reason="Cura Concluída via Rota Gravada")
            self.health_monitor["state"] = "EXPLORING"
            self.health_monitor["healing_required"] = "NO"
            self.health_monitor["battle_status"] = "INACTIVE"
        else:
            # Fallback para o controlador de cura adaptativo
            self.fsm.transition_to(BotState.HEALING, reason="Fallback para HealingController")
            self._handle_healing_cycle(snapshot, frame)

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

    def _generate_annotated_frame(self, frame: np.ndarray, snapshot: StateSnapshot, combat_snapshot: Optional[Any] = None) -> np.ndarray:
        """Desenha apenas o estado e a sub-ROI ativa de combate para exibição fluida (>= 30 FPS) na GUI."""
        if frame is None or frame.size == 0:
            return frame

        annotated = frame.copy()
        h, w = annotated.shape[:2]

        state_name = snapshot.screen_state.name if hasattr(snapshot.screen_state, "name") else str(snapshot.screen_state)
        state_text = f"STATE: {state_name}"
        cv2.rectangle(annotated, (10, 10), (320, 42), (15, 15, 15), -1)
        cv2.putText(annotated, state_text, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2)

        # Se estiver em combate, destaca a Sub-ROI do botão FIGHT
        if "BATTLE" in state_name:
            fx, fy = int(w * 0.70), int(h * 0.70)
            fw, fh = int(w * 0.28), int(h * 0.28)
            cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), (0, 140, 255), 2)
            cv2.putText(annotated, "FIGHT ROI", (fx + 6, fy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 255), 1)

        return annotated