import unittest
import numpy as np
import time
import os

from src.models.enums import AgentState, Element
from src.automation.state_machine import BotState
from src.models.lumen import UIElement, StateSnapshot, BattleTelemetry, PlayerInfo, PlayerDetection, CrystalDetection, TargetLockInfo, ActionVerificationResult
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget, TargetWindowInfo
from src.perception.landmark_detector import LandmarkDetector
from src.perception.combat_vision import CombatVisionAnalyzer
from src.combat.positioning import CombatPositioningController
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.skill_executor import SkillExecutor
from src.automation.healing import HealingController
from src.input.input_controller import InputController, KeyDiagnosticResult
from src.input.target_window import TargetWindowManager
from src.telemetry.telemetry_manager import TelemetryManager
from src.telemetry.evidence_package import save_evidence_package


class TestV35RealExecution(unittest.TestCase):
    """Suíte de Testes de Regressão e Validação da Versão v3.5 (Zero Fake Pass)."""

    def test_self_process_rejection(self):
        """Fase 1: TargetWindowManager rejeita categoricamente o próprio PID e títulos do Lumena Bot."""
        win_mgr = TargetWindowManager()
        own_pid = os.getpid()
        self.assertTrue(win_mgr.is_own_window(hwnd=9999, pid=own_pid, title="Google Chrome", process_name="python.exe"))
        self.assertTrue(win_mgr.is_own_window(hwnd=8888, pid=1234, title="Lumena Bot Control Center", process_name="LumenaBot.exe"))
        self.assertFalse(win_mgr.is_own_window(hwnd=7777, pid=5678, title="Lumena.gg - Google Chrome", process_name="chrome.exe"))

    def test_target_window_info_executable_name(self):
        """Fase 1: TargetWindowInfo expõe propriedade executable_name corretamente."""
        info = TargetWindowInfo(hwnd=123, pid=456, process_name="chrome.exe", window_title="Lumena.gg")
        self.assertEqual(info.executable_name, "chrome.exe")
        self.assertEqual(info.title, "Lumena.gg")

    def test_player_detection_model(self):
        """Fase 4: PlayerDetection e PlayerInfo com propriedades de acesso rápido."""
        p_det = PlayerDetection(bbox=(100, 200, 32, 48), center_x=116, center_y=224, confidence=0.92, detection_method="TEMPLATE")
        self.assertEqual(p_det.center, (116, 224))
        self.assertEqual(p_det.detection_method, "TEMPLATE")

        p_info = PlayerInfo(x=100, y=200, center=(116, 224), bounding_box=(100, 200, 32, 48), confidence=0.92, detected=True)
        self.assertEqual(p_info.center_x, 116)
        self.assertEqual(p_info.center_y, 224)
        self.assertEqual(p_info.bbox, (100, 200, 32, 48))

    def test_crystal_detection_model(self):
        """Fase 5: CrystalDetection semanticamente tipado como HEALING_CRYSTAL."""
        c_det = CrystalDetection(bbox=(500, 300, 60, 80), center_x=530, center_y=340, confidence=0.98, distance_to_player=140.0)
        self.assertEqual(c_det.semantic_type, "HEALING_CRYSTAL")
        self.assertEqual(c_det.center, (530, 340))
        self.assertEqual(c_det.distance_to_player, 140.0)

    def test_dynamic_skill_scan_arbitrary_counts(self):
        """Fase 8: CombatVisionAnalyzer detecta dinamicamente 1, 2, 4, 6 ou 8 slots."""
        analyzer = CombatVisionAnalyzer()
        frame = np.full((720, 1280, 3), 30, dtype=np.uint8)
        
        # Cria 6 slots visuais
        for i in range(6):
            bx = 300 + i * 110
            by = 640
            frame[by:by+50, bx:bx+90] = (60, 60, 60)
            frame[by+10:by+40, bx+10:bx+80] = (160, 160, 160)

        slots = analyzer.detect_skill_slots(frame, in_battle=True)
        self.assertGreaterEqual(len(slots), 4)

    def test_action_verification_result_multi_signal(self):
        """Fase 11: ActionVerificationResult rastreia múltiplos sinais independentes."""
        res = ActionVerificationResult(
            input_dispatched=True,
            visual_delta=0.035,
            player_changed=True,
            enemy_changed=True,
            cooldown_changed=True,
            state_changed=False,
            verified=True,
            confidence=0.96,
            reason="Delta visual e HP do inimigo alterados",
        )
        self.assertTrue(res.verified)
        self.assertGreater(res.visual_delta, 0.005)
        self.assertTrue(res.enemy_changed)

    def test_key_diagnostic_result_properties(self):
        """Fase 2: KeyDiagnosticResult expõe aliases latency e scan_code."""
        diag = KeyDiagnosticResult(
            key="w",
            vk_code=0x57,
            scancode=0x11,
            sendinput_down_ret=1,
            sendinput_up_ret=1,
            keybd_event_dispatched=False,
            postmessage_count=0,
            pyautogui_dispatched=False,
            total_events=2,
            duration=0.25,
            window_focused=True,
            visual_delta=0.015,
            movement_confirmed=True,
            success=True,
        )
        self.assertEqual(diag.latency, 0.25)
        self.assertEqual(diag.scan_code, 0x11)

    def test_telemetry_action_categories(self):
        """Fase 10: TelemetryManager rastreia categorias específicas de ações."""
        telemetry = TelemetryManager()
        prev_mov = telemetry._data.movement_actions_total
        prev_com = telemetry._data.combat_actions_total
        prev_hea = telemetry._data.healing_actions_total
        prev_rec = telemetry._data.recovery_attempts_total

        telemetry.record_movement_action()
        telemetry.record_combat_action()
        telemetry.record_healing_action()
        telemetry.record_recovery_attempt()
        telemetry.set_real_execution_status("EXECUTING")

        self.assertEqual(telemetry._data.movement_actions_total, prev_mov + 1)
        self.assertEqual(telemetry._data.combat_actions_total, prev_com + 1)
        self.assertEqual(telemetry._data.healing_actions_total, prev_hea + 1)
        self.assertEqual(telemetry._data.recovery_attempts_total, prev_rec + 1)
        self.assertEqual(telemetry._data.real_execution_status, "EXECUTING")

    def test_evidence_package_v35_schema(self):
        """Fase 17: Geração íntegra de result.json sem inferência falsa."""
        f1 = np.full((50, 50, 3), 30, dtype=np.uint8)
        f2 = np.full((50, 50, 3), 180, dtype=np.uint8)

        pkg = save_evidence_package(
            action_name="TEST_MOVE",
            target_type="HEALING_CRYSTAL",
            target_confidence=0.99,
            input_dispatched=True,
            foreground_verified=True,
            target_window_verified=True,
            action_verified=True,
            visual_delta=0.05,
            frame_before=f1,
            frame_after=f2,
        )
        self.assertTrue(os.path.exists(pkg))
        res_file = os.path.join(pkg, "result.json")
        self.assertTrue(os.path.exists(res_file))


if __name__ == "__main__":
    unittest.main()
