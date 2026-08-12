import time
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Set, Dict, Any

from src.models.lumen import StateSnapshot, TeamStatus, BattleTelemetry
from src.combat.decision_engine import CombatDecisionEngine, ActionDecision
from src.combat.action_executor import ActionExecutor
from src.memory.memory_manager import MemoryManager


class CombatAgentState(str, Enum):
    IDLE = "IDLE"
    WAITING_FOR_BATTLE = "WAITING_FOR_BATTLE"
    ANALYZING = "ANALYZING"
    SELECTING_ACTION = "SELECTING_ACTION"
    EXECUTING_ACTION = "EXECUTING_ACTION"
    WAITING_RESULT = "WAITING_RESULT"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"


@dataclass
class CombatTurnResult:
    """Resultado detalhado do turno processado pelo CombatAgent."""
    agent_state: CombatAgentState
    decision: Optional[ActionDecision]
    executed_successfully: bool
    turn_count: int
    message: str


class CombatAgent:
    """Sub-Agente autônomo de combate inteligente, desacoplado de captura de tela direta e acoplado via StateSnapshot."""

    def __init__(
        self,
        decision_engine: Optional[CombatDecisionEngine] = None,
        action_executor: Optional[ActionExecutor] = None,
        memory_manager: Optional[MemoryManager] = None,
        max_turn_retries: int = 3,
        max_battle_turns: int = 40,
    ) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        self.decision_engine = decision_engine or CombatDecisionEngine()
        self.action_executor = action_executor or ActionExecutor(memory_manager=memory_manager)
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

    def process_turn(
        self,
        snapshot: Optional[StateSnapshot],
        team: Optional[TeamStatus] = None,
    ) -> CombatTurnResult:
        """
        Executa um ciclo completo de turno em malha fechada:
        Observação (StateSnapshot) -> Análise e Decisão (CombatDecisionEngine) -> Execução (ActionExecutor) -> Atualização de Memória.
        """
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

        # 1. Se não estiver em batalha
        if not telemetry.in_battle:
            self.current_state = CombatAgentState.WAITING_FOR_BATTLE
            return CombatTurnResult(
                agent_state=self.current_state,
                decision=None,
                executed_successfully=True,
                turn_count=self.turn_count,
                message="Nenhuma batalha ativa detectada no momento.",
            )

        # 2. Prevenção de loop infinito / limite de turnos
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

        # 3. Transição para ANALYZING e tomada de decisão
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

        # 4. Transição para EXECUTING_ACTION
        self.current_state = CombatAgentState.EXECUTING_ACTION
        executed_ok = self.action_executor.execute_plan(
            plan=decision.action_plan,
            telemetry=telemetry,
            timeout=4.0,
            max_retries=2,
        )

        # 5. Avaliação do Resultado da Execução
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
