"""
LUMENA BOT v3.8 — COMPLETE COMBAT CYCLE UNIT TEST SUITE
========================================================
Suíte de testes para validação do ciclo completo de combate v3.8:
1. test_fight_to_skill_menu_transition
2. test_skill_selection_dispatch
3. test_waiting_turn_suppresses_inputs
4. test_battle_end_restores_world_state
5. test_crystal_remains_blocked_until_world_confirmed
6. test_battle_watchdog_timeout_recovery
"""

import unittest
import time
import numpy as np
import cv2
from unittest.mock import MagicMock, patch

from config.settings import BotConfig, KeyBindings, MonitorConfig, BattleConfig
from src.core.event_bus import EventBus, EventType
from src.models.enums import AgentState, Element
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.combat.battle_ui_controller import BattleUIController
from src.perception.landmark_detector import LandmarkDetector


class TestLumenaBotV38CombatCycle(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: FIGHT TO SKILL MENU TRANSITION
    # -------------------------------------------------------------------------
    def test_fight_to_skill_menu_transition(self) -> None:
        """FIGHT clicado -> Abre menu de skills e emite eventos correspondentes."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame_before = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Frame after com menu de habilidades simulado
        frame_after = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame_after, (350, 520), (550, 580), (200, 200, 200), -1)
        cv2.rectangle(frame_after, (350, 600), (550, 660), (200, 200, 200), -1)

        with patch.object(controller.input_ctrl, "click", return_value=True), \
             patch.object(controller.input_ctrl, "compute_visual_delta", return_value=(True, 0.035)):

            dispatched, latency, verified = controller.click_fight(
                frame_before=frame_before,
                screen_capture_func=lambda: (frame_after, time.time()),
            )

            self.assertTrue(dispatched)
            self.assertTrue(verified)

            # Verifica eventos emitidos
            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.FIGHT_CLICK_VERIFIED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 2: SKILL SELECTION DISPATCH
    # -------------------------------------------------------------------------
    def test_skill_selection_dispatch(self) -> None:
        """Skill 1 selecionada deterministicamente e despachada fisicamente."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        skills = controller.find_available_skills(frame)
        self.assertGreaterEqual(len(skills), 1)

        primary_skill = controller.select_primary_skill(skills)
        self.assertIsNotNone(primary_skill)
        self.assertEqual(primary_skill.slot_index, 1)

        with patch.object(controller.input_ctrl, "press_key", return_value=True):
            dispatched, latency, _ = controller.execute_skill(
                skill=primary_skill,
                frame_before=frame,
            )
            self.assertTrue(dispatched)
            self.assertTrue(controller.is_waiting_turn_resolution)

            disp_events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.SKILL_ACTION_DISPATCHED]
            self.assertGreaterEqual(len(disp_events), 1)

    # -------------------------------------------------------------------------
    # TEST 3: WAITING TURN SUPPRESSES INPUTS (Turn Lock)
    # -------------------------------------------------------------------------
    def test_waiting_turn_suppresses_inputs(self) -> None:
        """Enquanto em Turn Lock, cliques subsequentes são suprimidos."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Força estado de Turn Lock ativo
        controller._is_waiting_turn_resolution = True

        with patch.object(controller.input_ctrl, "click") as mock_click, \
             patch.object(controller.input_ctrl, "press_key") as mock_key:

            success, stage, _ = controller.execute_complete_combat_turn(frame)

            self.assertFalse(success)
            self.assertEqual(stage, "TURN_LOCKED")
            mock_click.assert_not_called()
            mock_key.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST 4: BATTLE END RESTORES WORLD STATE
    # -------------------------------------------------------------------------
    def test_battle_end_restores_world_state(self) -> None:
        """Fim de batalha confirma saída da Battle UI e transiciona para EXPLORING."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        engine._running = True
        engine._paused = False
        engine.fsm.transition_to(BotState.BATTLE, reason="In BATTLE")

        # Frame de mundo aberto sem Battle UI
        world_frame = np.full((720, 1280, 3), (40, 150, 40), dtype=np.uint8)
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            battle_telemetry=BattleTelemetry(in_battle=False, player_hp_pct=0.90),
        )

        with patch.object(engine.screen_capture, "capture_frame", return_value=(world_frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot):

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)
            self.assertEqual(engine.health_monitor["state"], "EXPLORING")
            self.assertEqual(engine.health_monitor["battle_status"], "INACTIVE")

    # -------------------------------------------------------------------------
    # TEST 5: CRYSTAL REMAINS BLOCKED UNTIL WORLD CONFIRMED
    # -------------------------------------------------------------------------
    def test_crystal_remains_blocked_until_world_confirmed(self) -> None:
        """Cristal de cura permanece bloqueado se a tela ainda tiver resquícios de Battle UI."""
        landmark = LandmarkDetector()
        frame = np.full((720, 1280, 3), 100, dtype=np.uint8)

        # Enquanto in_battle == True -> Cristal estritamente bloqueado
        c_found, _, _ = landmark.detect_crystal(frame, in_battle=True)
        self.assertFalse(c_found)

        # Quando in_battle == False -> Detecção liberada
        c_found_world, _, _ = landmark.detect_crystal(frame, in_battle=False)
        # Retorna resultado normal de mundo
        self.assertIsInstance(c_found_world, bool)

    # -------------------------------------------------------------------------
    # TEST 6: BATTLE WATCHDOG TIMEOUT RECOVERY
    # -------------------------------------------------------------------------
    def test_battle_watchdog_timeout_recovery(self) -> None:
        """Watchdog de combate re-focaliza a janela e recupera de stall > 6s."""
        controller = BattleUIController(event_bus=self.event_bus, turn_timeout=6.0)
        controller._last_action_timestamp = time.time() - 7.0  # 7s atrás
        controller._is_waiting_turn_resolution = True

        with patch.object(controller.input_ctrl, "focus_game_window", return_value=True) as mock_focus, \
             patch.object(controller.input_ctrl.window_manager, "ensure_canvas_focus", return_value=True) as mock_canvas:

            handled = controller.handle_battle_watchdog()

            self.assertTrue(handled)
            self.assertFalse(controller.is_waiting_turn_resolution)
            mock_focus.assert_called_once()
            mock_canvas.assert_called_once()

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.BATTLE_WATCHDOG_TRIGGERED]
            self.assertGreaterEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
