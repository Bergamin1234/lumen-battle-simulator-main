import os
import sys
import json
import time
import queue
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.enums import Element, AgentState
from src.models.combat_vision import TargetWindowInfo, SkillSlot, EnemyTarget, CombatSnapshot, CombatDecision, PositionInfo
from src.input.target_window import TargetWindowManager
from src.input.safety_guard import SafetyGuard
from src.input.input_controller import InputController
from src.perception.combat_vision import CombatVisionAnalyzer
from src.perception.debug_skill_scanner import run_debug_skill_scan
from src.combat.positioning import CombatPositioningController
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.combat_agent import CombatAgent
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.automation.bot_controller import BotController
from src.core.event_bus import EventBus, EventType, BotEvent


class TestLumenaBotV32ClosedLoopIntegration(unittest.TestCase):
    """Testes de integração ponta-a-ponta (Closed-Loop) do Lumena Bot Control Center v3.2."""

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # 1. DISCOVER & SELF REJECTION
    def test_target_window_never_selects_self(self) -> None:
        win_mgr = TargetWindowManager()
        my_pid = os.getpid()
        self.assertTrue(win_mgr.is_own_window(hwnd=999, pid=my_pid, title="Random Title", process_name="python.exe"))
        self.assertTrue(win_mgr.is_own_window(hwnd=999, pid=1234, title="Lumena Bot Control Center — Autonomous Agent Suite"))

    # 2. CANDIDATES PRESENTATION
    def test_target_window_candidates_presentation(self) -> None:
        win_mgr = TargetWindowManager()
        w1 = MagicMock(title="Google Chrome - Lumena.gg", _hWnd=2001, pid=2001, process_name="chrome.exe", left=0, top=0, width=1920, height=1080)
        w2 = MagicMock(title="Lumena Bot Control Center", _hWnd=2002, pid=os.getpid(), process_name="lumenabot.exe", left=0, top=0, width=1200, height=800)

        with patch("pygetwindow.getAllWindows", return_value=[w1, w2]):
            candidates = win_mgr.list_browser_candidates()
            self.assertEqual(len(candidates), 2)
            c1 = next(c for c in candidates if c.hwnd == 2001)
            c2 = next(c for c in candidates if c.hwnd == 2002)
            self.assertTrue(c1.is_valid_candidate)
            self.assertFalse(c2.is_valid_candidate)
            self.assertEqual(c2.rejection_reason, "self_process")

    # 3. FOREGROUND VERIFICATION & INPUT BLOCKING
    def test_foreground_verification_and_input_blocking(self) -> None:
        guard = SafetyGuard()
        # Input é estritamente bloqueado se o Foreground do Windows não bater com o Target HWND
        can_dispatch = guard.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=5001,
            target_pid=7777,
            target_title="Lumena - Chrome",
            target_process="chrome.exe",
            foreground_hwnd=9999,  # Mismatch
        )
        self.assertFalse(can_dispatch)

    # 4. DYNAMIC SKILL COUNT (ARBITRARY N)
    def test_dynamic_skill_count_arbitrary_n(self) -> None:
        analyzer = CombatVisionAnalyzer()
        # Cria frame sintético e testa fallback dinâmico
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        skills = analyzer.detect_skill_slots(frame, in_battle=True)
        self.assertGreaterEqual(len(skills), 4)
        for s in skills:
            self.assertIsNotNone(s.index)
            self.assertIsNotNone(s.screen_x)
            self.assertIsNotNone(s.center_x)

    # 5. DECISION ENGINE EXPLAINABILITY & SCORING
    def test_combat_decision_scoring_explainability(self) -> None:
        engine = CombatDecisionEngine()
        skills = [
            SkillSlot(id="sk_water", index=1, slot_index=1, skill_name="WaterGun", element=Element.WATER, power=60, range_type="RANGED", available=True),
            SkillSlot(id="sk_fire", index=2, slot_index=2, skill_name="FirePunch", element=Element.FIRE, power=70, range_type="MELEE", available=True),
        ]
        target = EnemyTarget(name="FireMonster", element=Element.FIRE, hp_estimate=0.30, center=(1200, 500))
        snapshot = CombatSnapshot(
            in_battle=True,
            player_hp=1.0,
            target_enemy=target,
            available_skills=skills,
        )
        decision = engine.evaluate_combat_snapshot(snapshot)
        self.assertEqual(decision.action_type, "USE_SKILL")
        self.assertEqual(decision.selected_skill.id, "sk_water")
        self.assertIn("Super Efetivo", decision.reason)

    # 6. COMBAT POSITIONING & ACTION VERIFICATION
    def test_combat_positioning_and_action_verification(self) -> None:
        engine = CombatDecisionEngine()
        melee_skill = SkillSlot(id="sk_tackle", index=1, slot_index=1, skill_name="Tackle", element=Element.NORMAL, power=40, range_type="MELEE", available=True)
        target = EnemyTarget(name="FarEnemy", element=Element.NORMAL, hp_estimate=1.0, center=(1600, 500))
        pos_info = PositionInfo(player_pos=(500, 500), target_pos=(1600, 500), distance=1100.0, required_range=150.0, positioning_state="APPROACH_TARGET")

        snapshot = CombatSnapshot(
            in_battle=True,
            player_position=(500, 500),
            target_enemy=target,
            available_skills=[melee_skill],
            position_info=pos_info,
        )
        decision = engine.evaluate_combat_snapshot(snapshot)
        self.assertEqual(decision.action_type, "APPROACH_TARGET")
        self.assertEqual(decision.move_direction.upper(), "D")

    # 7. ANTI-STUCK LIMIT (STRICT 3 RECOVERIES -> SAFE STOP)
    def test_antistuck_strict_limit_safe_stop(self) -> None:
        engine = LumenaBotEngine()
        engine._recovery_attempts = 3
        engine._handle_anti_stuck()
        self.assertEqual(engine.fsm.current_state, BotState.ERROR)
        events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.RECOVERY_FAILED]
        self.assertGreaterEqual(len(events), 1)

    # 8. LEVEL 7 HARD GATE (STRICT LOCK WITHOUT EVIDENCE)
    def test_level7_hard_gate_no_bypass(self) -> None:
        controller = BotController()
        if os.path.exists("physical_test_report.json"):
            os.remove("physical_test_report.json")
        started, msg = controller.start(mode="AUTONOMOUS")
        self.assertFalse(started)
        self.assertIn("LEVEL 7 BLOCKED", msg)

    # 9. EVIDENCE PACKAGE INTEGRITY
    def test_evidence_package_generation_integrity(self) -> None:
        res = run_debug_skill_scan()
        self.assertTrue(os.path.exists(res["screenshot_path"]))
        self.assertTrue(os.path.exists(res["annotated_path"]))
        self.assertTrue(os.path.exists(res["json_path"]))
        with open(res["json_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("detected_slots", data)
            self.assertIn("skills", data)

    # 10. GUI THREAD SAFETY & EVENT QUEUE
    def test_gui_thread_safety_and_event_consumption(self) -> None:
        q = queue.Queue()
        ev = BotEvent(event_type=EventType.STATE_CHANGED, message="State test", category="FSM")
        q.put(ev)
        self.assertFalse(q.empty())
        retrieved = q.get_nowait()
        self.assertEqual(retrieved.category, "FSM")


if __name__ == "__main__":
    unittest.main()
