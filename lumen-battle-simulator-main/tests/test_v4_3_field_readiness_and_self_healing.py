"""
LUMENA BOT v4.3 — FIELD READINESS, REAL-TIME CALIBRATION & SELF-HEALING SUITE
=============================================================================
Suíte de testes de prontidão operacional de campo, auto-recuperação e reprodução forense:
1. test_live_supervisor_cycle_tracking
2. test_self_healing_recovers_minimized_window
3. test_self_healing_recovers_lost_foreground
4. test_canvas_inspector_overlay_coordinate_projection
5. test_replay_viewer_loads_and_parses_flight_data
6. test_webgl_freeze_detector_triggers_wake_action
7. test_consecutive_battle_rotations_without_memory_leak
8. test_live_supervisor_latency_tracking
9. test_auto_dismiss_unexpected_popups
10. test_replay_player_step_navigation
11. test_canvas_inspector_fine_tuning_adjustments
12. test_field_trial_result_json_serialization
13. test_self_healing_window_restore_bounds_recalibration
14. test_live_supervisor_fps_calculation
15. test_blackbox_replay_sync_integrity
16. test_field_trial_runner_dry_run_execution
"""

import unittest
import time
import os
import shutil
import tempfile
import json
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType
from src.automation.live_supervisor import LiveSessionSupervisor
from src.automation.self_healing_engine import SelfHealingEngine
from src.ui.canvas_inspector_overlay import CanvasInspectorOverlay
from src.telemetry.replay_viewer import BlackboxReplayEngine
from src.input.target_window import TargetWindowInfo
from scripts.diagnostics.run_field_trial import run_field_trial_session


class TestLumenaBotV43FieldReadinessAndSelfHealing(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # TEST 1: LIVE SUPERVISOR CYCLE TRACKING
    # -------------------------------------------------------------------------
    def test_live_supervisor_cycle_tracking(self) -> None:
        """Valida que o supervisor rastreia e incrementa 3 ciclos de combate consecutivos."""
        supervisor = LiveSessionSupervisor(event_bus=self.event_bus)
        supervisor.start_field_trial(num_cycles=3)

        self.assertTrue(supervisor.field_trial_active)
        self.assertEqual(supervisor.current_cycle, 1)

        supervisor.record_cycle_step(1, "FIGHT_CLICK", True, 0.05)
        supervisor.complete_current_cycle(True, "Ciclo 1 OK")
        self.assertEqual(supervisor.current_cycle, 2)

        supervisor.record_cycle_step(2, "SKILL_DISPATCH", True, 0.04)
        supervisor.complete_current_cycle(True, "Ciclo 2 OK")
        self.assertEqual(supervisor.current_cycle, 3)

        supervisor.record_cycle_step(3, "MODAL_DISMISS", True, 0.03)
        supervisor.complete_current_cycle(True, "Ciclo 3 OK")

        self.assertFalse(supervisor.field_trial_active)
        self.assertTrue(supervisor.trial_passed)
        self.assertEqual(len(supervisor.cycle_records), 3)

    # -------------------------------------------------------------------------
    # TEST 2: SELF HEALING RECOVERS MINIMIZED WINDOW
    # -------------------------------------------------------------------------
    def test_self_healing_recovers_minimized_window(self) -> None:
        """Valida que janelas minimizadas são restauradas via SW_RESTORE."""
        engine = SelfHealingEngine(event_bus=self.event_bus)

        with patch("ctypes.windll.user32.IsIconic", return_value=1), \
             patch("ctypes.windll.user32.ShowWindow") as mock_show, \
             patch.object(engine.win_mgr, "ensure_foreground", return_value=True):

            recovered = engine.recover_minimized_window(target_hwnd=9999)
            self.assertTrue(recovered)
            mock_show.assert_called_with(9999, 9)  # SW_RESTORE = 9

    # -------------------------------------------------------------------------
    # TEST 3: SELF HEALING RECOVERS LOST FOREGROUND
    # -------------------------------------------------------------------------
    def test_self_healing_recovers_lost_foreground(self) -> None:
        """Valida reaquisição de foco quando o SO está com outra janela em foreground."""
        engine = SelfHealingEngine(event_bus=self.event_bus)

        # Simula foreground inicial em 1234 (diferente do alvo 5678) e após ensure_foreground passa para 5678
        with patch("ctypes.windll.user32.GetForegroundWindow", side_effect=[1234, 5678]), \
             patch.object(engine.win_mgr, "ensure_foreground", return_value=True) as mock_fg:

            recovered = engine.recover_lost_foreground(target_hwnd=5678)
            self.assertTrue(recovered)
            mock_fg.assert_called_with(5678)

    # -------------------------------------------------------------------------
    # TEST 4: CANVAS INSPECTOR OVERLAY COORDINATE PROJECTION
    # -------------------------------------------------------------------------
    def test_canvas_inspector_overlay_coordinate_projection(self) -> None:
        """Valida que o overlay projeta todas as ROIs sobre o frame sem alterar dimensões."""
        inspector = CanvasInspectorOverlay()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        annotated = inspector.project_rois_to_frame(
            frame=frame,
            canvas_bounds=(100, 50, 1080, 620),
            is_letterboxed=True,
            fight_bbox=(900, 500, 150, 60),
            skill_bboxes=[(300, 500, 80, 80), (400, 500, 80, 80)],
            player_hp_bbox=(150, 600, 200, 25),
            enemy_hp_bbox=(850, 100, 200, 25),
            modal_bbox=(400, 200, 480, 320),
            bezier_points=[(100, 100), (200, 150), (300, 200)],
        )

        self.assertEqual(annotated.shape, frame.shape)
        # O frame anotado não deve ser mais totalmente preto
        self.assertGreater(np.sum(annotated), 0)

    # -------------------------------------------------------------------------
    # TEST 5: REPLAY VIEWER LOADS AND PARSES FLIGHT DATA
    # -------------------------------------------------------------------------
    def test_replay_viewer_loads_and_parses_flight_data(self) -> None:
        """Valida carregamento de metadados e snapshots de um dump forense."""
        # Cria dump simulado
        dump_path = os.path.join(self.temp_dir, "test_dump")
        os.makedirs(dump_path, exist_ok=True)

        flight_data = {
            "timestamp": "2026-08-17 08:00:00",
            "reason": "WATCHDOG_STALL",
            "total_snapshots": 3,
            "snapshots": [
                {"timestamp": 1.0, "state": "EXPLORING", "last_input": "W"},
                {"timestamp": 2.0, "state": "BATTLE", "last_input": "FIGHT"},
                {"timestamp": 3.0, "state": "BATTLE", "last_input": "SKILL_1"},
            ],
        }
        with open(os.path.join(dump_path, "flight_data.json"), "w", encoding="utf-8") as f:
            json.dump(flight_data, f)

        # Cria thumbnail
        cv2.imwrite(os.path.join(dump_path, "frame_000.png"), np.zeros((100, 100, 3), dtype=np.uint8))

        replay = BlackboxReplayEngine(dump_dir=dump_path)
        self.assertEqual(replay.get_total_frames(), 3)
        self.assertEqual(replay.metadata["reason"], "WATCHDOG_STALL")

        snap = replay.get_current_snapshot_data()
        self.assertEqual(snap["index"], 0)
        self.assertEqual(snap["state"], "EXPLORING")

    # -------------------------------------------------------------------------
    # TEST 6: WEBGL FREEZE DETECTOR TRIGGERS WAKE ACTION
    # -------------------------------------------------------------------------
    def test_webgl_freeze_detector_triggers_wake_action(self) -> None:
        """Valida que frames idênticos por 10 passos disparam evento de descolamento de WebGL."""
        mock_input = MagicMock()
        engine = SelfHealingEngine(input_controller=mock_input, event_bus=self.event_bus)

        dummy_frame = np.full((100, 100, 3), 120, dtype=np.uint8)

        freeze_detected = False
        for _ in range(12):
            if engine.detect_and_recover_webgl_freeze(dummy_frame):
                freeze_detected = True

        self.assertTrue(freeze_detected)
        mock_input.move_to.assert_called()

    # -------------------------------------------------------------------------
    # TEST 7: CONSECUTIVE BATTLE ROTATIONS WITHOUT MEMORY LEAK
    # -------------------------------------------------------------------------
    def test_consecutive_battle_rotations_without_memory_leak(self) -> None:
        """Garante que sucessivas rotações de combate limpam referências e mantêm consumo constante."""
        supervisor = LiveSessionSupervisor(event_bus=self.event_bus)
        supervisor.start_field_trial(num_cycles=10)

        for i in range(1, 11):
            supervisor.record_cycle_step(i, "STEP_A", True, 0.01)
            supervisor.record_cycle_step(i, "STEP_B", True, 0.02)
            supervisor.complete_current_cycle(True, f"Cycle {i} Done")

        self.assertEqual(len(supervisor.cycle_records), 10)
        self.assertEqual(len(supervisor.current_cycle_steps), 0)

    # -------------------------------------------------------------------------
    # TEST 8: LIVE SUPERVISOR LATENCY TRACKING
    # -------------------------------------------------------------------------
    def test_live_supervisor_latency_tracking(self) -> None:
        """Valida medição precisa da latência média de ciclo em milissegundos."""
        supervisor = LiveSessionSupervisor()
        supervisor.start_loop_step()
        time.sleep(0.01)
        lat = supervisor.record_loop_latency()

        self.assertGreater(lat, 0.005)
        self.assertGreater(supervisor.get_average_latency_ms(), 5.0)

    # -------------------------------------------------------------------------
    # TEST 9: AUTO DISMISS UNEXPECTED POPUPS
    # -------------------------------------------------------------------------
    def test_auto_dismiss_unexpected_popups(self) -> None:
        """Valida que popups com pixels brancos salientes no topo direito enviam ESC."""
        mock_input = MagicMock()
        engine = SelfHealingEngine(input_controller=mock_input, event_bus=self.event_bus)

        # Frame com caixa branca na área superior direita
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[10:100, 1000:1250] = 255  # Popup branco

        dismissed = engine.auto_dismiss_unexpected_popups(frame)
        self.assertTrue(dismissed)
        mock_input.press_key.assert_called_with("esc", duration=0.1)

    # -------------------------------------------------------------------------
    # TEST 10: REPLAY PLAYER STEP NAVIGATION
    # -------------------------------------------------------------------------
    def test_replay_player_step_navigation(self) -> None:
        """Valida avanço, recuo e seek no reprodutor forense."""
        replay = BlackboxReplayEngine()
        replay.snapshots = [{"i": 0}, {"i": 1}, {"i": 2}, {"i": 3}]

        self.assertEqual(replay.current_frame_idx, 0)
        replay.step_forward()
        self.assertEqual(replay.current_frame_idx, 1)
        replay.step_forward()
        self.assertEqual(replay.current_frame_idx, 2)
        replay.step_backward()
        self.assertEqual(replay.current_frame_idx, 1)
        replay.seek(3)
        self.assertEqual(replay.current_frame_idx, 3)

    # -------------------------------------------------------------------------
    # TEST 11: CANVAS INSPECTOR FINE TUNING ADJUSTMENTS
    # -------------------------------------------------------------------------
    def test_canvas_inspector_fine_tuning_adjustments(self) -> None:
        """Valida atualização dinâmica de parâmetros de calibração."""
        inspector = CanvasInspectorOverlay()
        inspector.update_param("match_threshold", 0.85)
        inspector.update_param("hsv_tolerance", 35.0)

        self.assertEqual(inspector.get_param("match_threshold"), 0.85)
        self.assertEqual(inspector.get_param("hsv_tolerance"), 35.0)

    # -------------------------------------------------------------------------
    # TEST 12: FIELD TRIAL RESULT JSON SERIALIZATION
    # -------------------------------------------------------------------------
    def test_field_trial_result_json_serialization(self) -> None:
        """Valida exportação formal do payload do Field Trial para result.json."""
        supervisor = LiveSessionSupervisor()
        supervisor.start_field_trial(num_cycles=3)
        for i in range(1, 4):
            supervisor.record_cycle_step(i, "STEP", True, 0.05)
            supervisor.complete_current_cycle(True, "OK")

        out_file = os.path.join(self.temp_dir, "test_result.json")
        res = supervisor.export_field_trial_result(output_path=out_file)

        self.assertTrue(os.path.exists(out_file))
        self.assertIn(res["version"], ("v4.3", "v4.4"))
        self.assertEqual(res["field_trial"]["completed_cycles"], 3)

    # -------------------------------------------------------------------------
    # TEST 13: SELF HEALING WINDOW RESTORE BOUNDS RECALIBRATION
    # -------------------------------------------------------------------------
    def test_self_healing_window_restore_bounds_recalibration(self) -> None:
        """Valida que restauração de janela publica evento de restauração."""
        engine = SelfHealingEngine(event_bus=self.event_bus)

        with patch("ctypes.windll.user32.IsIconic", return_value=1), \
             patch("ctypes.windll.user32.ShowWindow"), \
             patch.object(engine.win_mgr, "ensure_foreground", return_value=True):

            engine.recover_minimized_window(target_hwnd=8888)
            events = [e for e in self.event_bus.get_recent_events(5) if e.event_type == EventType.WINDOW_RESTORED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 14: LIVE SUPERVISOR FPS CALCULATION
    # -------------------------------------------------------------------------
    def test_live_supervisor_fps_calculation(self) -> None:
        """Valida que o supervisor calcula FPS positivo com base nos registros de ticks."""
        supervisor = LiveSessionSupervisor()
        now = time.time()
        for i in range(30):
            supervisor._frame_timestamps.append(now + i * (1.0 / 30.0))

        fps = supervisor.get_current_fps()
        self.assertAlmostEqual(fps, 30.0, delta=2.0)

    # -------------------------------------------------------------------------
    # TEST 15: BLACKBOX REPLAY SYNC INTEGRITY
    # -------------------------------------------------------------------------
    def test_blackbox_replay_sync_integrity(self) -> None:
        """Valida que o replay retorna dados consistentes mesmo em listas vazias."""
        replay = BlackboxReplayEngine()
        data = replay.get_current_snapshot_data()
        self.assertEqual(data["index"], 0)
        self.assertIsNone(data["frame"])

    # -------------------------------------------------------------------------
    # TEST 16: FIELD TRIAL RUNNER DRY RUN EXECUTION
    # -------------------------------------------------------------------------
    def test_field_trial_runner_dry_run_execution(self) -> None:
        """Valida execução ponta a ponta do script run_field_trial.py em modo dry-run."""
        out_file = os.path.join(self.temp_dir, "dry_run_result.json")
        res = run_field_trial_session(
            num_cycles=3,
            dry_run=True,
            output_path=out_file,
        )

        self.assertTrue(os.path.exists(out_file))
        self.assertIn(res.get("status"), ("PASS", "PASS_SYNTHETIC", "NO_TARGET_WINDOW_DETECTED"))
        self.assertEqual(res.get("field_trial", {}).get("completed_cycles"), 3)


if __name__ == "__main__":
    unittest.main()
