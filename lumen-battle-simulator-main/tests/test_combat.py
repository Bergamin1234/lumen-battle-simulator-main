import unittest
from unittest.mock import MagicMock, patch

from src.models.enums import Element, AgentState
from src.models.lumen import (
    BattleTelemetry,
    MoveSlotInfo,
    TeamStatus,
    LumenMemberState,
    StateSnapshot,
    ActionPlan,
    AtomicAction,
)
from src.combat.decision_engine import CombatDecisionEngine, ActionDecision
from src.combat.action_executor import ActionExecutor
from src.combat.combat_agent import CombatAgent, CombatAgentState
from src.memory.world_memory import WorldMemory
from src.memory.experience_store import ExperienceStore
from src.memory.memory_manager import MemoryManager


class TestCombatSubsystem(unittest.TestCase):
    def setUp(self):
        self.engine = CombatDecisionEngine()
        self.mock_input = MagicMock()
        self.mock_input.get_screen_center.return_value = (960, 540)
        self.mock_input.click.return_value = True
        self.mock_input.press_key.return_value = True

        self.world_memory = WorldMemory()
        self.experience_store = ExperienceStore(db_path=":memory:")
        self.memory_manager = MemoryManager(
            world_memory=self.world_memory,
            experience_store=self.experience_store,
        )

        self.executor = ActionExecutor(
            input_controller=self.mock_input,
            memory_manager=self.memory_manager,
        )
        self.agent = CombatAgent(
            decision_engine=self.engine,
            action_executor=self.executor,
            memory_manager=self.memory_manager,
            max_turn_retries=3,
            max_battle_turns=10,
        )

    # 1. Seleção do Maior Dano Esperado
    def test_highest_base_power_selection(self):
        m1 = MoveSlotInfo(slot_index=0, name="Tackle", power=35, current_pp=10, max_pp=10, element=Element.NORMAL)
        m2 = MoveSlotInfo(slot_index=1, name="Hyper Beam", power=120, current_pp=5, max_pp=5, element=Element.NORMAL)

        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=1.0,
            enemy_hp_pct=1.0,
            available_moves=[m1, m2],
            fight_button_pos=(500, 400),
        )

        decision = self.engine.evaluate_turn(telemetry)
        self.assertEqual(decision.target_slot, 1)
        self.assertEqual(decision.target_name, "Hyper Beam")
        self.assertGreater(decision.score, 100.0)

    # 2. Prioridade de Golpe Super Efetivo
    def test_super_effective_multiplier_priority(self):
        # Inimigo do tipo FOGO ("Emberpup")
        # Move 1: Fogo (0.5x contra Fogo, power 90) -> score ~ 90 - 30 = 60
        # Move 2: Água (2.0x contra Fogo, power 60) -> score ~ 60 + 45 = 105
        m_fire = MoveSlotInfo(slot_index=0, name="Flamethrower", power=90, current_pp=10, max_pp=10, element=Element.FIRE)
        m_water = MoveSlotInfo(slot_index=1, name="Water Gun", power=60, current_pp=10, max_pp=10, element=Element.WATER)

        telemetry = BattleTelemetry(
            in_battle=True,
            enemy_lumen_name="Emberpup",
            player_hp_pct=1.0,
            enemy_hp_pct=1.0,
            available_moves=[m_fire, m_water],
            fight_button_pos=(500, 400),
        )

        decision = self.engine.evaluate_turn(telemetry)
        self.assertEqual(decision.target_slot, 1)
        self.assertEqual(decision.target_name, "Water Gun")
        self.assertIn("Super Efetivo", decision.reason)

    # 3. Prioridade de Finalização do Inimigo (Kill Shot Opportunity)
    def test_kill_shot_opportunity(self):
        m1 = MoveSlotInfo(slot_index=0, name="Quick Attack", power=40, current_pp=10, max_pp=10, element=Element.NORMAL)
        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=1.0,
            enemy_hp_pct=0.15,  # Inimigo com HP crítico
            available_moves=[m1],
            fight_button_pos=(500, 400),
        )

        decision = self.engine.evaluate_turn(telemetry)
        self.assertEqual(decision.target_slot, 0)
        self.assertIn("Oportunidade de nocaute", decision.reason)

    # 4. Evitar Golpe sem PP
    def test_avoids_move_with_zero_pp(self):
        m_strong_empty = MoveSlotInfo(slot_index=0, name="Mega Blast", power=150, current_pp=0, max_pp=5, element=Element.NORMAL)
        m_weak_available = MoveSlotInfo(slot_index=1, name="Poke", power=20, current_pp=15, max_pp=15, element=Element.NORMAL)

        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=1.0,
            enemy_hp_pct=1.0,
            available_moves=[m_strong_empty, m_weak_available],
            fight_button_pos=(500, 400),
        )

        decision = self.engine.evaluate_turn(telemetry)
        self.assertEqual(decision.target_slot, 1)
        self.assertEqual(decision.target_name, "Poke")

    # 5 & 6. Decisão Defensiva e Seleção de Parceiro da Equipe (SWITCH)
    def test_switch_lumen_when_hp_critical(self):
        m1 = MoveSlotInfo(slot_index=0, name="Weak Move", power=30, current_pp=10, max_pp=10, element=Element.NORMAL)
        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=0.12,  # HP crítico < 25%
            enemy_hp_pct=0.90,
            available_moves=[m1],
            fight_button_pos=(500, 400),
            switch_button_pos=(500, 470),
        )

        member1 = LumenMemberState(slot=0, nickname="ActiveDying", species_name="Sprout", primary_element=Element.GRASS, hp_percentage=0.12, is_active=True)
        member2 = LumenMemberState(slot=1, nickname="HealthyTank", species_name="Leviagorg", primary_element=Element.WATER, hp_percentage=0.95, is_active=False)
        team = TeamStatus(members=[member1, member2], active_slot=0, team_alive_count=2)

        decision = self.engine.evaluate_turn(telemetry, team=team)
        self.assertEqual(decision.action_type, "SWITCH")
        self.assertEqual(decision.target_slot, 1)
        self.assertEqual(decision.target_name, "HealthyTank")

    # 7. Tratamento de Estado de Batalha Incompleto
    def test_incomplete_battle_telemetry_fallback(self):
        telemetry = BattleTelemetry(
            in_battle=True,
            available_moves=[],  # Nenhum slot detectado
            fight_button_pos=(450, 350),
        )

        decision = self.engine.evaluate_turn(telemetry)
        self.assertIsNotNone(decision)
        self.assertGreater(len(decision.action_plan.actions), 0)

    # 8. Tratamento de Decisão Inválida e Snapshot Vazio
    def test_process_turn_with_empty_snapshot(self):
        result = self.agent.process_turn(None)
        self.assertEqual(result.agent_state, CombatAgentState.ERROR)
        self.assertFalse(result.executed_successfully)

    # 9, 10 & 17. Execução com ActionExecutor e Auditoria de Memória
    def test_action_executor_dispatch_and_memory_logging(self):
        plan = ActionPlan(
            actions=[
                AtomicAction(action_type="CLICK_FIGHT", target="fight_button", duration=0.1),
                AtomicAction(action_type="WAIT", target="wait", duration=0.01),
                AtomicAction(action_type="CLICK_MOVE", target="slot_0", duration=0.1),
            ]
        )
        telemetry = BattleTelemetry(in_battle=True, fight_button_pos=(500, 400))

        success = self.executor.execute_plan(plan, telemetry=telemetry)
        self.assertTrue(success)
        self.assertGreaterEqual(self.mock_input.click.call_count, 2)
        # Memória deve registrar as ações
        self.assertGreater(len(self.world_memory.recent_actions), 0)

    # 11. Prevenção de Ações Repetidas após Falhas
    def test_anti_loop_penalty_on_failed_moves(self):
        m1 = MoveSlotInfo(slot_index=0, name="GlitchAttack", power=60, current_pp=10, max_pp=10, element=Element.NORMAL)
        m2 = MoveSlotInfo(slot_index=1, name="AlternativeAttack", power=55, current_pp=10, max_pp=10, element=Element.NORMAL)

        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=1.0,
            enemy_hp_pct=1.0,
            available_moves=[m1, m2],
            fight_button_pos=(500, 400),
        )

        # Sem falhas, m1 vence por ter 60 vs 55
        dec1 = self.engine.evaluate_turn(telemetry, recent_failed_targets=set())
        self.assertEqual(dec1.target_slot, 0)

        # Com falha registrada no slot_0, m2 deve ser escolhido
        dec2 = self.engine.evaluate_turn(telemetry, recent_failed_targets={"move_slot_0"})
        self.assertEqual(dec2.target_slot, 1)

    # 12 & 13. Vitória e Derrota
    def test_victory_and_defeat_handling(self):
        v_telemetry = BattleTelemetry(in_battle=True, victory_detected=True)
        v_snap = StateSnapshot(timestamp=1.0, screen_state=AgentState.BATTLE_RESULT, battle_telemetry=v_telemetry)
        v_res = self.agent.process_turn(v_snap)
        self.assertEqual(v_res.agent_state, CombatAgentState.VICTORY)

        d_telemetry = BattleTelemetry(in_battle=True, defeat_detected=True)
        d_snap = StateSnapshot(timestamp=2.0, screen_state=AgentState.BATTLE_RESULT, battle_telemetry=d_telemetry)
        d_res = self.agent.process_turn(d_snap)
        self.assertEqual(d_res.agent_state, CombatAgentState.DEFEAT)

    # 14. Timeout de Execução
    def test_action_executor_timeout(self):
        long_plan = ActionPlan(
            actions=[
                AtomicAction(action_type="WAIT", target="wait", duration=0.2),
                AtomicAction(action_type="WAIT", target="wait", duration=0.2),
            ]
        )
        # Timeout curto de 0.05s
        res = self.executor.execute_plan(long_plan, timeout=0.05)
        self.assertFalse(res)

    # 15. Limite de Tentativas (Turn Failures e Max Battle Turns)
    def test_max_battle_turns_and_retry_limits(self):
        # Simula agente falhando repetidamente no dispatch
        self.mock_input.click.return_value = False
        m1 = MoveSlotInfo(slot_index=0, name="Tackle", power=40, current_pp=10, max_pp=10, element=Element.NORMAL)
        telemetry = BattleTelemetry(in_battle=True, available_moves=[m1], fight_button_pos=(500, 400))
        snap = StateSnapshot(timestamp=1.0, screen_state=AgentState.BATTLE, battle_telemetry=telemetry)

        # Executa até atingir limite de 3 falhas
        self.agent.process_turn(snap)
        self.agent.process_turn(snap)
        res = self.agent.process_turn(snap)

        self.assertEqual(res.agent_state, CombatAgentState.RECOVERING)

    # 16. Integração Completa CombatAgent -> ActionDecision -> ActionPlan
    def test_combat_agent_full_turn_integration(self):
        self.mock_input.click.return_value = True
        m1 = MoveSlotInfo(slot_index=0, name="Spark", power=50, current_pp=10, max_pp=10, element=Element.ELECTRIC)
        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=0.80,
            enemy_hp_pct=0.70,
            available_moves=[m1],
            fight_button_pos=(500, 400),
        )
        snap = StateSnapshot(timestamp=10.0, screen_state=AgentState.BATTLE, battle_telemetry=telemetry)

        res = self.agent.process_turn(snap)
        self.assertTrue(res.executed_successfully)
        self.assertEqual(res.turn_count, 1)
        self.assertEqual(res.agent_state, CombatAgentState.WAITING_RESULT)
        self.assertEqual(res.decision.action_type, "MOVE")


if __name__ == "__main__":
    unittest.main()
