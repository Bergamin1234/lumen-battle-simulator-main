import os
import sys
import json
import time
import math
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.enums import Element, AgentState
from src.models.lumen import UIElement, StateSnapshot, BattleTelemetry
from src.models.combat_vision import TargetWindowInfo, SkillSlot, EnemyTarget, CombatSnapshot, CombatDecision, PositionInfo
from src.input.target_window import TargetWindowManager, WindowInfo
from src.input.safety_guard import SafetyGuard
from src.input.input_controller import InputController
from src.perception.landmark_detector import LandmarkDetector
from src.perception.combat_vision import CombatVisionAnalyzer
from src.automation.healing import HealingController
from src.combat.positioning import CombatPositioningController
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.combat_agent import CombatAgent
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.automation.bot_controller import BotController
from src.core.event_bus import EventBus, EventType, BotEvent


class TestLumenaBotV32RealWorldAudit(unittest.TestCase):
    """Bateria de testes unitários e de integração para a Auditoria Real v3.2."""

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # 1. TEST_NO_SELF_WINDOW_TARGET
    def test_no_self_window_target(self) -> None:
        win_mgr = TargetWindowManager()
        my_pid = os.getpid()
        self.assertTrue(win_mgr.is_own_window(hwnd=1001, pid=my_pid, title="Random Terminal", process_name="python.exe"))
        self.assertTrue(win_mgr.is_own_window(hwnd=1002, pid=5555, title="Lumena Bot Control Center — Autonomous Agent Suite"))

    # 2. TEST_BROWSER_TARGET_SELECTION
    def test_browser_target_selection(self) -> None:
        win_mgr = TargetWindowManager()
        w_chrome = MagicMock(title="Google Chrome - Lumena.gg", _hWnd=3001, pid=3001, process_name="chrome.exe", left=0, top=0, width=1920, height=1080)
        w_bot = MagicMock(title="Lumena Bot Control Center", _hWnd=3002, pid=os.getpid(), process_name="lumenabot.exe", left=0, top=0, width=1200, height=800)

        with patch("pygetwindow.getAllWindows", return_value=[w_chrome, w_bot]):
            candidates = win_mgr.list_browser_candidates()
            valid = [c for c in candidates if c.is_valid_candidate]
            self.assertEqual(len(valid), 1)
            self.assertEqual(valid[0].hwnd, 3001)
            self.assertEqual(valid[0].browser_type, "CHROME")

    # 3. TEST_FOREGROUND_VERIFICATION
    def test_foreground_verification(self) -> None:
        guard = SafetyGuard()
        # Bloqueia se foreground do Windows não for o target
        can_dispatch = guard.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=4001,
            target_pid=4001,
            target_title="Lumena - Chrome",
            target_process="chrome.exe",
            foreground_hwnd=9999,  # Mismatch
        )
        self.assertFalse(can_dispatch)

    # 4. TEST_HEALING_CRYSTAL_DETECTION
    def test_healing_crystal_detection(self) -> None:
        detector = LandmarkDetector()
        # Cria frame sintético com cristal azul (RGB: 0, 190, 255)
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2_bgr = (255, 190, 0) # BGR para azul/ciano elétrico
        frame[250:350, 350:450] = cv2_bgr

        found, rel_pos, elem = detector.detect_crystal(frame)
        self.assertTrue(found)
        self.assertIsNotNone(rel_pos)
        self.assertIsNotNone(elem)
        self.assertEqual(elem.semantic_type, "HEALING_CRYSTAL")
        self.assertGreater(elem.confidence, 0.60)

    # 5. TEST_TARGET_LOCK
    def test_target_lock(self) -> None:
        controller = HealingController()
        elem = UIElement(name="blue_crystal", bounding_box=(350, 250, 100, 100), confidence=0.92, center=(400, 300), semantic_type="HEALING_CRYSTAL")
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(200, 150),
        )
        state, is_done, msg = controller.step(snapshot)
        self.assertTrue(controller.target_locked)
        self.assertEqual(controller.state, "APPROACH_TARGET")
        events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.TARGET_LOCKED]
        self.assertGreaterEqual(len(events), 1)

    # 6. TEST_POSITIONING
    def test_positioning(self) -> None:
        controller = HealingController(interaction_distance_threshold=80.0)
        elem = UIElement(name="blue_crystal", bounding_box=(350, 250, 100, 100), confidence=0.92, center=(400, 300), semantic_type="HEALING_CRYSTAL")
        # Posição distante dx=200, dy=0 -> deve mover para a direita ('D')
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(200, 0),
        )
        state, is_done, msg = controller.step(snapshot)
        self.assertEqual(state, "APPROACH_TARGET")
        self.assertEqual(controller.last_move_key, "d")

    # 7. TEST_INTERACTION_PROMPT
    def test_interaction_prompt(self) -> None:
        detector = LandmarkDetector()
        # Cria frame com banner retangular contrastado simulando prompt
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        frame[400:440, 300:500] = 255 # Bloco branco em fundo preto

        found, prompt_text, bbox, conf = detector.detect_interaction_prompt(frame)
        self.assertTrue(found)
        self.assertIn("SPACE", prompt_text)

    # 8. TEST_ACTION_DISPATCH
    def test_action_dispatch(self) -> None:
        input_ctrl = InputController()
        with patch.object(input_ctrl.safety_guard, "validate_can_dispatch", return_value=True):
            diag = input_ctrl.press_key_with_diagnostic("w", duration=0.05, jitter=False)
            self.assertTrue(diag.success)
            self.assertEqual(diag.key.upper(), "W")

    # 9. TEST_ACTION_VERIFICATION
    def test_action_verification(self) -> None:
        agent = CombatAgent()
        skill = SkillSlot(id="sk_test", index=1, slot_index=1, skill_name="TestHit", element=Element.NORMAL, power=50, range_type="MELEE", available=True)
        target = EnemyTarget(name="Enemy1", element=Element.NORMAL, hp_estimate=1.0, center=(960, 480))
        pos_info = PositionInfo(player_pos=(960, 540), target_pos=(960, 480), distance=60.0, required_range=180.0, positioning_state="ATTACK_POSITION_READY")
        snapshot = CombatSnapshot(in_battle=True, target_enemy=target, available_skills=[skill], position_info=pos_info)

        # Mock de falha na verificação de ataque
        with patch.object(agent.skill_executor, "execute_skill", return_value=(False, None)):
            res = agent.process_combat_snapshot(snapshot)
            self.assertFalse(res.executed_successfully)
            events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.ACTION_UNCONFIRMED]
            self.assertGreaterEqual(len(events), 1)

    # 10. TEST_NO_OBSERVATION_DEADLOCK
    def test_no_observation_deadlock(self) -> None:
        engine = LumenaBotEngine()
        # Simula estado SEARCHING_CRYSTAL e verifica que ele não fica inerte
        elem = UIElement(name="blue_crystal", bounding_box=(350, 250, 100, 100), confidence=0.92, center=(400, 300), semantic_type="HEALING_CRYSTAL")
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(150, 0),
        )
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        engine._handle_healing_cycle(snapshot, frame)
        # Deve ter atualizado health_monitor com ação real de aproximação
        self.assertEqual(engine.health_monitor["last_action"], "APPROACH_TARGET")
        self.assertTrue(engine.health_monitor["action"])

    # 11. TEST_SKILL_DYNAMIC_DETECTION
    def test_skill_dynamic_detection(self) -> None:
        analyzer = CombatVisionAnalyzer()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        skills = analyzer.detect_skill_slots(frame, in_battle=True)
        self.assertGreaterEqual(len(skills), 4)
        for s in skills:
            self.assertIn(s.range_type, ("MELEE", "RANGED", "AOE", "LONG_RANGE"))

    # 12. TEST_SKILL_EXECUTION
    def test_skill_execution(self) -> None:
        agent = CombatAgent()
        skill = SkillSlot(id="sk_blast", index=1, slot_index=1, skill_name="FireBlast", element=Element.FIRE, power=80, hotkey="1", available=True)
        with patch.object(agent.skill_executor.input_ctrl, "press_key", return_value=True):
            ok, diag = agent.skill_executor.execute_skill(skill)
            self.assertTrue(ok)

    # 13. TEST_COOLDOWN_VERIFICATION
    def test_cooldown_verification(self) -> None:
        analyzer = CombatVisionAnalyzer()
        # ROI clara (habilidade disponível) vs ROI escura (em cooldown)
        bright_roi = np.full((50, 50, 3), 200, dtype=np.uint8)
        dark_roi = np.full((50, 50, 3), 30, dtype=np.uint8)
        self.assertFalse(analyzer.analyze_slot_cooldown(bright_roi))
        self.assertTrue(analyzer.analyze_slot_cooldown(dark_roi))

    # 14. TEST_EXECUTION_WATCHDOG
    def test_execution_watchdog(self) -> None:
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False
        # Simula inatividade física por 16 segundos
        engine._last_physical_action_time = time.time() - 16.0
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.UNKNOWN_STATE)
        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot):
            engine._execute_single_cycle()
            self.assertTrue(engine._stalled_warning_emitted)
            events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.EXECUTION_STALLED]
            self.assertGreaterEqual(len(events), 1)

    # 15. TEST_STATE_TRANSITION_SEARCH_TO_ACTION
    def test_state_transition_search_to_action(self) -> None:
        engine = LumenaBotEngine()
        engine.fsm._current_state = BotState.HEALING
        elem = UIElement(name="blue_crystal", bounding_box=(350, 250, 100, 100), confidence=0.95, center=(400, 300), semantic_type="HEALING_CRYSTAL")
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(20, 10), # Bem próximo (< 80px)
        )
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        # Executa múltiplos passos simulando interação completa
        for _ in range(5):
            engine._handle_healing_cycle(snapshot, frame)
        self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)
        self.assertEqual(engine.health_monitor["last_verified_action"], "HEALING_VERIFIED")


if __name__ == "__main__":
    unittest.main()
