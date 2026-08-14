import time
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Set, Dict, Any, Tuple
import numpy as np

from src.models.lumen import StateSnapshot, TeamStatus, BattleTelemetry
from src.models.combat_vision import CombatSnapshot, CombatDecision, SkillSlot
from src.combat.decision_engine import CombatDecisionEngine, ActionDecision
from src.combat.action_executor import ActionExecutor
from src.combat.skill_executor import SkillExecutor
from src.memory.memory_manager import MemoryManager
from src.core.event_bus import EventBus, EventType
from src.telemetry.telemetry_manager import TelemetryManager

logger = logging.getLogger("LumenaCombat")


class CombatAgentState(str, Enum):
    IDLE = "IDLE"
    WAITING_FOR_BATTLE = "WAITING_FOR_BATTLE"
    ANALYZING = "ANALYZING"
    SELECTING_ACTION = "SELECTING_ACTION"
    POSITIONING = "POSITIONING"
    EXECUTING_ACTION = "EXECUTING_ACTION"
    VERIFYING_ACTION = "VERIFYING_ACTION"
    WAITING_RESULT = "WAITING_RESULT"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"


@dataclass
class CombatTurnResult:
    """Resultado detalhado do turno processado pelo CombatAgent."""
    agent_state: CombatAgentState
    decision: Optional[Any]
    executed_successfully: bool
    turn_count: int
    message: str


class CombatAgent:
    """Sub-Agente autônomo de combate inteligente com suporte a visão dinâmica de habilidades,

    posicionamento tático, verificação pós-ação e execução em malha fechada.
    """

    def __init__(
        self,
        decision_engine: Optional[CombatDecisionEngine] = None,
        action_executor: Optional[ActionExecutor] = None,
        skill_executor: Optional[SkillExecutor] = None,
        memory_manager: Optional[MemoryManager] = None,
        max_turn_retries: int = 3,
        max_battle_turns: int = 40,
    ) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        self.event_bus = EventBus()
        self.telemetry = TelemetryManager()
        self.decision_engine = decision_engine or CombatDecisionEngine()
        self.action_executor = action_executor or ActionExecutor(memory_manager=memory_manager)
        self.skill_executor = skill_executor or SkillExecutor()
        self.memory_manager = memory_manager

        self.max_turn_retries = max_turn_retries
        self.max_battle_turns = max_battle_turns

        # Máquina de estados interna do combate
        self.current_state: CombatAgentState = CombatAgentState.IDLE
        self.turn_count: int = 0
        self.consecutive_turn_failures: int = 0
        self._failed_targets_this_battle: Set[str] = set()

    def reset_battle(self) -> None:
        """Reinicia os contadores para um novo confronto."""
        self.current_state = CombatAgentState.IDLE
        self.turn_count = 0
        self.consecutive_turn_failures = 0
        self._failed_targets_this_battle.clear()

    def process_combat_snapshot(
        self,
        snapshot: CombatSnapshot,
        screen_capture_func: Optional[Any] = None,
        frame_before: Optional[np.ndarray] = None,
    ) -> CombatTurnResult:
        """Executa um ciclo completo de combate baseado em CombatSnapshot dinâmico da visão com verificação pós-ação."""
        if hasattr(self, "telemetry") and self.telemetry:
            self.telemetry.record_observation()

        if not snapshot.in_battle and not snapshot.target_enemy:
            self.current_state = CombatAgentState.WAITING_FOR_BATTLE
            return CombatTurnResult(
                agent_state=self.current_state,
                decision=None,
                executed_successfully=True,
                turn_count=self.turn_count,
                message="Nenhuma batalha ativa detectada no frame.",
            )

        self.current_state = CombatAgentState.ANALYZING
        self.current_state = CombatAgentState.SELECTING_ACTION

        decision: CombatDecision = self.decision_engine.evaluate_combat_snapshot(
            snapshot, recent_failed_skills=self._failed_targets_this_battle
        )
        if hasattr(self, "telemetry") and self.telemetry:
            self.telemetry.record_decision()

        self.logger.info(
            f"🎯 [Combate Dinâmico | Turno {self.turn_count + 1}] Decisão: {decision.action_type} "
            f"(Score: {decision.score:.1f} | Razão: {decision.reason})"
        )

        executed_ok = False

        if decision.action_type in ("APPROACH_TARGET", "MAINTAIN_DISTANCE"):
            self.current_state = CombatAgentState.POSITIONING
            move_key = decision.move_direction or "w"
            self.event_bus.publish(
                EventType.POSITIONING_STARTED,
                data={"direction": move_key, "action": decision.action_type},
                category="COMBAT",
                level="DEBUG",
                message=f"Posicionamento de combate: {decision.action_type} via '{move_key}'",
            )
            if hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_request()
            executed_ok = self.skill_executor.input_ctrl.press_key(move_key, duration=0.15)
            if executed_ok and hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_dispatched()

            self.event_bus.publish(
                EventType.POSITIONING_COMPLETED,
                data={"direction": move_key, "success": executed_ok},
                category="COMBAT",
                level="DEBUG",
                message=f"Posicionamento concluído: {executed_ok}",
            )

        elif decision.action_type == "USE_SKILL" and decision.selected_skill:
            self.current_state = CombatAgentState.EXECUTING_ACTION
            if hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_request()

            skill = decision.selected_skill
            now = time.time()
            action_id = f"act_{int(now * 1000)}_{skill.slot_index}"
            target_info = self.skill_executor.input_ctrl.window_manager._current_target
            target_hwnd = target_info.hwnd if target_info else 0
            target_pid = getattr(target_info, "pid", 0) if target_info else 0

            try:
                executed_ok, _ = self.skill_executor.execute_skill(skill, frame_before=frame_before)
            except TypeError:
                executed_ok, _ = self.skill_executor.execute_skill(skill)

            if executed_ok and hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_dispatched()

            # Verificação pós-ação em malha fechada (Action Verification)
            self.current_state = CombatAgentState.VERIFYING_ACTION
            self.event_bus.publish(
                EventType.ACTION_VERIFICATION_STARTED,
                data={
                    "timestamp": time.time(),
                    "action_id": action_id,
                    "target_hwnd": target_hwnd,
                    "target_pid": target_pid,
                    "state": "BATTLE",
                    "skill_id": skill.id,
                    "skill_position": (skill.center_x, skill.center_y),
                    "input_type": "HOTKEY" if skill.hotkey else "CLICK",
                },
                category="COMBAT",
                level="DEBUG",
                message=f"ACTION_VERIFICATION_STARTED: Verificando resultado de '{skill.skill_name}'",
            )

            visual_delta = 0.0
            confirmed = False
            if screen_capture_func:
                try:
                    time.sleep(0.15)
                    after_frame, _ = screen_capture_func()
                    if after_frame is not None and frame_before is not None:
                        confirmed, visual_delta = self.skill_executor.input_ctrl.compute_visual_delta(frame_before, after_frame)
                        self.logger.debug(f"[Combate] Verificando resultado visual do ataque: delta={visual_delta:.4f}")
                except Exception as e:
                    self.logger.error(f"Erro na verificação visual pós-ação: {e}")

            # Se a ação foi despachada mas não houve alteração visual ou falhou
            if not executed_ok:
                skill_id = skill.id or f"skill_slot_{skill.slot_index}"
                self._failed_targets_this_battle.add(skill_id)
                if hasattr(self, "telemetry") and self.telemetry:
                    self.telemetry.record_action_unconfirmed()
                self.event_bus.publish(
                    EventType.ACTION_UNCONFIRMED,
                    data={
                        "timestamp": time.time(),
                        "action_id": action_id,
                        "target_hwnd": target_hwnd,
                        "target_pid": target_pid,
                        "state": "BATTLE",
                        "skill_id": skill_id,
                        "skill_position": (skill.center_x, skill.center_y),
                        "input_type": "HOTKEY" if skill.hotkey else "CLICK",
                        "visual_delta": visual_delta,
                    },
                    category="COMBAT",
                    level="WARNING",
                    message=f"ACTION_UNCONFIRMED: Ataque '{skill.skill_name}' falhou ou não despachado.",
                )
            elif frame_before is not None and not confirmed and visual_delta <= 0.005:
                # Input despachado mas jogo não alterou nada visualmente
                skill_id = skill.id or f"skill_slot_{skill.slot_index}"
                if hasattr(self, "telemetry") and self.telemetry:
                    self.telemetry.record_action_unconfirmed()
                self.event_bus.publish(
                    EventType.ACTION_UNCONFIRMED,
                    data={
                        "timestamp": time.time(),
                        "action_id": action_id,
                        "target_hwnd": target_hwnd,
                        "target_pid": target_pid,
                        "state": "BATTLE",
                        "skill_id": skill_id,
                        "skill_position": (skill.center_x, skill.center_y),
                        "input_type": "HOTKEY" if skill.hotkey else "CLICK",
                        "visual_delta": visual_delta,
                    },
                    category="COMBAT",
                    level="WARNING",
                    message=f"ACTION_UNCONFIRMED: Ataque '{skill.skill_name}' despachado sem resposta visual (delta={visual_delta:.4f}).",
                )
            else:
                if hasattr(self, "telemetry") and self.telemetry:
                    self.telemetry.record_action_verified()
                self.event_bus.publish(
                    EventType.ACTION_VERIFIED,
                    data={
                        "timestamp": time.time(),
                        "action_id": action_id,
                        "target_hwnd": target_hwnd,
                        "target_pid": target_pid,
                        "state": "BATTLE",
                        "skill_id": skill.id,
                        "skill_position": (skill.center_x, skill.center_y),
                        "input_type": "HOTKEY" if skill.hotkey else "CLICK",
                        "visual_delta": visual_delta,
                    },
                    category="COMBAT",
                    level="INFO",
                    message=f"ACTION_VERIFIED: Ataque '{skill.skill_name}' confirmado com sucesso (delta={visual_delta:.4f}).",
                )

        elif decision.action_type == "OPEN_FIGHT_MENU" and snapshot.fight_button_pos:
            self.current_state = CombatAgentState.EXECUTING_ACTION
            if hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_request()
            executed_ok = self.skill_executor.input_ctrl.click(snapshot.fight_button_pos[0], snapshot.fight_button_pos[1])
            if executed_ok and hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_dispatched()

        elif decision.action_type in ("CONFIRM_VICTORY", "CLEAR_DEFEAT", "ADVANCE_DIALOG"):
            self.current_state = CombatAgentState.EXECUTING_ACTION
            if hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_request()
            executed_ok = self.skill_executor.input_ctrl.click(960, 540)
            if executed_ok and hasattr(self, "telemetry") and self.telemetry:
                self.telemetry.record_input_dispatched()

        else:
            # WAIT, REASSESS, PERCEPTION_FAILURE
            if decision.reason.startswith("PERCEPTION_FAILURE"):
                self.event_bus.publish(
                    EventType.PERCEPTION_FAILURE,
                    data={"reason": decision.reason},
                    category="PERCEPTION",
                    level="WARNING",
                    message=decision.reason,
                )
            executed_ok = False

        if executed_ok:
            self.consecutive_turn_failures = 0
            self.turn_count += 1
            if decision.action_type == "CONFIRM_VICTORY":
                self.current_state = CombatAgentState.VICTORY
            elif decision.action_type == "CLEAR_DEFEAT":
                self.current_state = CombatAgentState.DEFEAT
            else:
                self.current_state = CombatAgentState.WAITING_RESULT
            msg = f"Ação de combate '{decision.action_type}' executada com sucesso."

            if self.memory_manager:
                try:
                    self.memory_manager.world_memory.recent_actions.append(decision.action_type)
                except Exception:
                    pass
        else:
            self.consecutive_turn_failures += 1
            self.current_state = CombatAgentState.ERROR
            msg = f"Falha na ação de combate '{decision.action_type}'."

        return CombatTurnResult(
            agent_state=self.current_state,
            decision=decision,
            executed_successfully=executed_ok,
            turn_count=self.turn_count,
            message=msg,
        )

    def process_turn(
        self,
        snapshot: Optional[StateSnapshot],
        team: Optional[TeamStatus] = None,
    ) -> CombatTurnResult:
        """Executa um ciclo completo de turno legado em malha fechada via StateSnapshot."""
        if snapshot is None or snapshot.battle_telemetry is None:
            self.current_state = CombatAgentState.ERROR
            return CombatTurnResult(
                agent_state=self.current_state,
                decision=None,
                executed_successfully=False,
                turn_count=self.turn_count,
                message="Snapshot ou telemetria de combate inexistente.",
            )

        telemetry: BattleTelemetry = snapshot.battle_telemetry

        if not telemetry.in_battle:
            self.current_state = CombatAgentState.WAITING_FOR_BATTLE
            return CombatTurnResult(
                agent_state=self.current_state,
                decision=None,
                executed_successfully=True,
                turn_count=self.turn_count,
                message="Nenhuma batalha ativa detectada no momento.",
            )

        if self.turn_count >= self.max_battle_turns:
            self.logger.warning(f"⚠️ Limite máximo de {self.max_battle_turns} turnos atingido na batalha!")
            self.current_state = CombatAgentState.RECOVERING
            return CombatTurnResult(
                agent_state=self.current_state,
                decision=None,
                executed_successfully=False,
                turn_count=self.turn_count,
                message=f"Limite de {self.max_battle_turns} turnos excedido. Entrando em recuperação.",
            )

        self.current_state = CombatAgentState.ANALYZING
        self.current_state = CombatAgentState.SELECTING_ACTION

        decision = self.decision_engine.evaluate_turn(
            telemetry=telemetry,
            team=team,
            recent_failed_targets=self._failed_targets_this_battle,
        )

        self.logger.info(
            f"🎯 [Turno {self.turn_count + 1}] Decisão: {decision.action_type} -> {decision.target_name} "
            f"(Score: {decision.score:.1f} | Razão: {decision.reason})"
        )

        self.current_state = CombatAgentState.EXECUTING_ACTION
        executed_ok = self.action_executor.execute_plan(
            plan=decision.action_plan,
            telemetry=telemetry,
            timeout=4.0,
            max_retries=2,
        )

        if executed_ok:
            self.consecutive_turn_failures = 0
            self.turn_count += 1

            if decision.action_type == "CONFIRM_VICTORY":
                self.current_state = CombatAgentState.VICTORY
                msg = "Vitória confirmada e concluída."
            elif decision.action_type == "CLEAR_DEFEAT":
                self.current_state = CombatAgentState.DEFEAT
                msg = "Derrota processada."
            else:
                self.current_state = CombatAgentState.WAITING_RESULT
                msg = f"Ação '{decision.target_name}' executada com sucesso."
        else:
            self.consecutive_turn_failures += 1
            target_id = f"{decision.action_type.lower()}_slot_{decision.target_slot}"
            self._failed_targets_this_battle.add(target_id)
            self.logger.warning(
                f"❌ Falha na execução da ação '{decision.target_name}' ({self.consecutive_turn_failures}/{self.max_turn_retries})."
            )

            if self.consecutive_turn_failures >= self.max_turn_retries:
                self.current_state = CombatAgentState.RECOVERING
                msg = f"Falhas consecutivas ({self.consecutive_turn_failures}). Entrando em modo de recuperação de combate."
            else:
                self.current_state = CombatAgentState.ERROR
                msg = f"Falha na ação '{decision.target_name}'."

        return CombatTurnResult(
            agent_state=self.current_state,
            decision=decision,
            executed_successfully=executed_ok,
            turn_count=self.turn_count,
            message=msg,
        )
