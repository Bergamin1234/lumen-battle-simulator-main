"""
LUMENA BOT v3.6.1 — PHYSICAL EXECUTION PROOF & ZERO FAKE PASS UNIT TESTS
========================================================================
Testes de Não-Regressão para validação física:
TEST 1: HP alto + batalha -> BATTLE -> ENEMY -> ATTACK -> crystal blocked
TEST 2: HP baixo + batalha -> modo de emergência
TEST 3: Fora de batalha + HP baixo + cristal visível -> HEALING
TEST 4: Batalha + nenhuma skill disponível -> NÃO executar ataque cego (WAIT / NO_SKILL)
TEST 5: Batalha + skill detectada -> ACTION_REQUESTED e INPUT_REQUESTED
TEST 6: INPUT_REQUESTED sem INPUT_DISPATCHED -> INPUT_BLOCKED / EXECUTION_FAILURE
TEST 7: INPUT_DISPATCHED sem alteração visual -> ACTION_UNCONFIRMED
TEST 8: > 5 segundos sem ação durante batalha -> BATTLE_EXECUTION_STALLED
"""

import unittest
import time
import numpy as np
from unittest.mock import MagicMock, patch

from config.settings import BotConfig, CRITICAL_HP_RATIO, HEALING_HP_RATIO, COMBAT_ACTION_TIMEOUT
from src.models.enums import AgentState, Element
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement
from src.models.combat_vision import (
    CombatSnapshot,
    EnemyTarget,
    SkillSlot,
    CombatDecision,
)
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.combat.combat_agent import CombatAgent
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.skill_executor import SkillExecutor
from src.core.event_bus import EventBus, EventType


class TestLumenaBotV361PhysicalExecution(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: HP ALTO + BATALHA -> BATTLE -> ENEMY -> ATTACK -> CRYSTAL BLOCKED
    # -------------------------------------------------------------------------
    def test_test_1_hp_high_battle_override(self) -> None:
        """HP 80.5% em batalha obriga foco no inimigo e bloqueia estritamente busca de cristal."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.95, name="Wild Lumen")
        skill = SkillSlot(
            id="skill_1", index=1, slot_index=1,
            screen_x=400, screen_y=600, width=60, height=60,
            available=True, cooldown=0.0, hotkey="1", skill_name="AquaJet",
            element=Element.WATER, power=50,
        )
        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            player_hp=0.805,
            target_enemy=enemy,
            detected_enemies=[enemy],
            available_skills=[skill],
        )
        bt = BattleTelemetry(in_battle=True, player_hp_pct=0.805)
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.BATTLE,
            battle_telemetry=bt,
            crystal_detected=True,
        )
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:

            mock_combat.return_value = MagicMock(
                executed_successfully=True,
                agent_state=MagicMock(name="VERIFIED"),
                decision=CombatDecision(action_type="USE_SKILL", selected_skill=skill),
            )

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)
            self.assertEqual(engine.health_monitor["current_goal"], "COMBAT")
            self.assertEqual(engine.health_monitor["current_target"], "ENEMY")
            self.assertEqual(engine.health_monitor["crystal_search"], "BLOCKED")
            self.assertTrue(engine.health_monitor["crystal_search_blocked"])
            self.assertEqual(engine.health_monitor["healing_required"], "NO")

    # -------------------------------------------------------------------------
    # TEST 2: HP BAIXO + BATALHA -> EMERGÊNCIA DETERMINÍSTICA
    # -------------------------------------------------------------------------
    def test_test_2_hp_low_battle_emergency(self) -> None:
        """HP <= 20% em batalha aciona sinalização de emergência sem quebrar o estado de combate."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90)
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=True, player_hp=0.18, target_enemy=enemy)
        bt = BattleTelemetry(in_battle=True, player_hp_pct=0.18)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=bt)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:

            mock_combat.return_value = MagicMock(executed_successfully=True, agent_state=MagicMock(name="VERIFIED"), decision=None)

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)
            self.assertEqual(engine.health_monitor["healing_required"], "EMERGENCY")

    # -------------------------------------------------------------------------
    # TEST 3: FORA DE BATALHA + HP BAIXO + CRISTAL -> HEALING
    # -------------------------------------------------------------------------
    def test_test_3_overworld_low_hp_crystal(self) -> None:
        """Fora de combate com HP <= 40% e cristal visível transiciona para HEALING."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        csnap = CombatSnapshot(timestamp=time.time(), in_battle=False, player_hp=0.30, target_enemy=None)
        bt = BattleTelemetry(in_battle=False, player_hp_pct=0.30)
        elem = UIElement(name="blue_crystal", bounding_box=(200, 200, 50, 50), confidence=0.95, center=(225, 225))
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            battle_telemetry=bt,
            crystal_detected=True,
            crystal_relative_pos=(50, 50),
            ui_elements={"blue_crystal": elem},
        )
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.healing_controller, "step", return_value=("APPROACH_TARGET", False, "Aproximando")):

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.HEALING)
            self.assertEqual(engine.health_monitor["crystal_search"], "ALLOWED")
            self.assertFalse(engine.health_monitor["crystal_search_blocked"])

    # -------------------------------------------------------------------------
    # TEST 4: BATALHA + NENHUMA SKILL DISPONÍVEL -> NÃO EXECUTAR ATAQUE CEGO
    # -------------------------------------------------------------------------
    def test_test_4_no_skill_available_no_blind_attack(self) -> None:
        """Se todas as habilidades estiverem em cooldown ou ausentes, evita ataque cego."""
        decision_engine = CombatDecisionEngine()
        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90)
        # Skills em cooldown
        skill_cd = SkillSlot(id="s1", index=1, slot_index=1, cooldown=3.5, available=False)
        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            target_enemy=enemy,
            available_skills=[skill_cd],
        )

        decision = decision_engine.evaluate_combat_snapshot(csnap)
        self.assertEqual(decision.action_type, "WAIT")
        self.assertIn("NO_SKILL_AVAILABLE", decision.reason)

    # -------------------------------------------------------------------------
    # TEST 5: BATALHA + SKILL DETECTADA -> ACTION_REQUESTED
    # -------------------------------------------------------------------------
    def test_test_5_battle_skill_detected_action_requested(self) -> None:
        """Ao escolher uma habilidade, publica ACTION_REQUESTED estruturado."""
        executor = SkillExecutor()
        skill = SkillSlot(id="s1", index=1, slot_index=1, hotkey="1", screen_x=500, screen_y=700, skill_name="FirePunch")

        with patch.object(executor.input_ctrl, "press_key", return_value=True):
            success, _ = executor.execute_skill(skill)
            self.assertTrue(success)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.ACTION_REQUESTED]
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0].data["hotkey"], "1")
            self.assertEqual(events[0].data["state"], "BATTLE")
            self.assertIn("act_", events[0].data["action_id"])

    # -------------------------------------------------------------------------
    # TEST 6: INPUT_REQUESTED SEM INPUT_DISPATCHED -> INPUT_BLOCKED
    # -------------------------------------------------------------------------
    def test_test_6_input_blocked_event(self) -> None:
        """Se o input for bloqueado por segurança ou falha de foco, emite INPUT_BLOCKED."""
        executor = SkillExecutor()
        skill = SkillSlot(id="s1", index=1, slot_index=1, hotkey="1", screen_x=500, screen_y=700, skill_name="FirePunch")

        with patch.object(executor.input_ctrl, "press_key", return_value=False):
            success, _ = executor.execute_skill(skill)
            self.assertFalse(success)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.INPUT_BLOCKED]
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0].category, "SAFETY")

    # -------------------------------------------------------------------------
    # TEST 7: INPUT_DISPATCHED SEM ALTERAÇÃO VISUAL -> ACTION_UNCONFIRMED
    # -------------------------------------------------------------------------
    def test_test_7_input_dispatched_no_visual_change(self) -> None:
        """Input despachado com visual_delta <= 0.005 gera ACTION_UNCONFIRMED."""
        agent = CombatAgent()
        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90)
        skill = SkillSlot(id="s1", index=1, slot_index=1, hotkey="1", screen_x=500, screen_y=700, skill_name="Tackle")
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=True, target_enemy=enemy, available_skills=[skill])

        # Frames idênticos -> visual_delta = 0.0
        frame_before = np.full((720, 1280, 3), 100, dtype=np.uint8)
        frame_after = np.full((720, 1280, 3), 100, dtype=np.uint8)

        with patch.object(agent.skill_executor, "execute_skill", return_value=(True, 0.15)), \
             patch.object(agent.skill_executor.input_ctrl, "compute_visual_delta", return_value=(False, 0.0)):

            turn_res = agent.process_combat_snapshot(
                csnap,
                screen_capture_func=lambda: (frame_after, time.time()),
                frame_before=frame_before,
            )

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.ACTION_UNCONFIRMED]
            self.assertGreaterEqual(len(events), 1)
            self.assertLessEqual(events[0].data["visual_delta"], 0.005)

    # -------------------------------------------------------------------------
    # TEST 8: > 5 SEGUNDOS SEM AÇÃO EM COMBATE -> BATTLE_EXECUTION_STALLED
    # -------------------------------------------------------------------------
    def test_test_8_combat_watchdog_timeout(self) -> None:
        """Inatividade >= 5.0s durante combate ativo dispara BATTLE_EXECUTION_STALLED."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False
        engine._last_combat_action_time = time.time() - 6.0  # 6s atrás

        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90)
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=True, target_enemy=enemy)
        bt = BattleTelemetry(in_battle=True)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=bt)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:

            mock_combat.return_value = MagicMock(executed_successfully=False, decision=None)

            engine._execute_single_cycle()

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.BATTLE_EXECUTION_STALLED]
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0].category, "COMBAT")


if __name__ == "__main__":
    unittest.main()
