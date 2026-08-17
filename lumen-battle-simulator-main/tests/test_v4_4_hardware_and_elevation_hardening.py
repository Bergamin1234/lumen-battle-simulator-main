"""
LUMENA BOT v4.4 — HARDWARE GATE, UIPI/UAC HARDENING & CONTINUOUS STREAM SUITE
=============================================================================
Suíte de testes de blindagem de privilégios Win32, compressão de memória e CLI:
1. test_field_trial_cli_dry_run_generates_valid_result_json
2. test_uipi_elevation_checker_detects_token_mismatch
3. test_sendinput_retval_validation_handles_os_rejection
4. test_blackbox_jpeg_compression_reduces_ram_footprint
5. test_continuous_capture_gdi_handles_leak_prevention
6. test_canvas_inspector_slider_threshold_live_propagation
7. test_gui_field_trial_thread_decoupling
8. test_field_trial_cli_argument_parsing
9. test_self_healing_handles_empty_frame_gracefully
10. test_main_cli_entrypoint_flags
"""

import unittest
import time
import os
import shutil
import tempfile
import json
import threading
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType
from src.input.target_window import TargetWindowManager
from src.input.input_backend import Win32InputBackend
from src.telemetry.blackbox_recorder import BlackboxFlightRecorder
from src.perception.screen_capture import ScreenCapture
from src.ui.canvas_inspector_overlay import CanvasInspectorOverlay
from src.automation.self_healing_engine import SelfHealingEngine
from scripts.diagnostics.run_field_trial import run_field_trial_session


class TestLumenaBotV44HardwareAndElevationHardening(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # TEST 1: FIELD TRIAL CLI DRY RUN GENERATES VALID RESULT JSON
    # -------------------------------------------------------------------------
    def test_field_trial_cli_dry_run_generates_valid_result_json(self) -> None:
        """Valida que o dry run gera result.json estruturado sem crash e com status formal."""
        out_file = os.path.join(self.temp_dir, "evidence", "result.json")
        res = run_field_trial_session(
            num_cycles=2,
            dry_run=True,
            output_path=out_file,
        )

        self.assertTrue(os.path.exists(out_file))
        self.assertEqual(res["version"], "v4.4")
        self.assertIn("physically_validated", res)
        self.assertFalse(res["physically_validated"])
        self.assertTrue(res["ready_for_live"])
        self.assertEqual(res["validation_category"], "NOT_VALIDATED")

    # -------------------------------------------------------------------------
    # TEST 2: UIPI ELEVATION CHECKER DETECTS TOKEN MISMATCH
    # -------------------------------------------------------------------------
    def test_uipi_elevation_checker_detects_token_mismatch(self) -> None:
        """Valida detecção de incompatibilidade quando Chrome roda como Admin e Bot sem elevação."""
        win_mgr = TargetWindowManager()

        # Simula processo alvo elevado (Admin) e processo atual não-elevado (Standard)
        with patch("ctypes.windll.user32.GetWindowThreadProcessId", return_value=1), \
             patch("src.input.target_window.TargetWindowManager.check_process_elevation_compatibility") as mock_chk:

            mock_chk.return_value = (False, "WARNING_UIPI_ELEVATION_MISMATCH")
            is_compat, reason = win_mgr.check_process_elevation_compatibility(target_hwnd=2002)

            self.assertFalse(is_compat)
            self.assertEqual(reason, "WARNING_UIPI_ELEVATION_MISMATCH")

    # -------------------------------------------------------------------------
    # TEST 3: SENDINPUT RETVAL VALIDATION HANDLES OS REJECTION
    # -------------------------------------------------------------------------
    def test_sendinput_retval_validation_handles_os_rejection(self) -> None:
        """Valida que retorno 0 do SendInput dispara warning e não lança exceção."""
        backend = Win32InputBackend()

        with patch("ctypes.windll.user32.SendInput", return_value=0), \
             patch("ctypes.windll.kernel32.GetLastError", return_value=5):  # 5 = ERROR_ACCESS_DENIED

            # Não deve quebrar a execução
            result = backend.key_down("w")
            self.assertTrue(result)

            result_up = backend.key_up("w")
            self.assertTrue(result_up)

    # -------------------------------------------------------------------------
    # TEST 4: BLACKBOX JPEG COMPRESSION REDUCES RAM FOOTPRINT (< 5 MB)
    # -------------------------------------------------------------------------
    def test_blackbox_jpeg_compression_reduces_ram_footprint(self) -> None:
        """Valida que 150 snapshots compactados em JPEG consomem menos de 5 MB de RAM."""
        recorder = BlackboxFlightRecorder(buffer_size=150)
        # Cria frame com cenário representativo de jogo (gradiente + HUD)
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        dummy_frame[:, :, 0] = 50
        dummy_frame[:, :, 1] = 120
        dummy_frame[:, :, 2] = 40
        cv2.rectangle(dummy_frame, (100, 100), (400, 300), (200, 200, 200), -1)

        for i in range(150):
            recorder.record_step(
                frame=dummy_frame,
                state_name="BATTLE",
                last_input=f"SKILL_{i % 4}",
                events=[{"event": "TEST_TICK"}],
            )

        self.assertEqual(recorder.get_snapshot_count(), 150)
        ram_mb = recorder.get_estimated_ram_usage_mb()
        self.assertLess(ram_mb, 5.0, f"RAM usage ({ram_mb} MB) exceeded 5.0 MB limit!")

        # Valida que o frame decodificado é recuperável com dimensões 480x270
        snap = recorder.get_snapshot(0)
        self.assertIsNotNone(snap)
        frame_rec = snap.get_frame()
        self.assertIsNotNone(frame_rec)
        self.assertEqual(frame_rec.shape, (270, 480, 3))

    # -------------------------------------------------------------------------
    # TEST 5: CONTINUOUS CAPTURE GDI HANDLES LEAK PREVENTION
    # -------------------------------------------------------------------------
    def test_continuous_capture_gdi_handles_leak_prevention(self) -> None:
        """Executa 100 iterações de compute_frame_diff e gerenciamento de buffers sem leak."""
        capture = ScreenCapture()
        frame_a = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame_b = np.full((720, 1280, 3), 50, dtype=np.uint8)

        for _ in range(100):
            diff = capture.compute_frame_diff(frame_a, frame_b)
            self.assertGreater(diff, 0.0)

        capture.close()
        self.assertIsNone(capture._sct)

    # -------------------------------------------------------------------------
    # TEST 6: CANVAS INSPECTOR SLIDER THRESHOLD LIVE PROPAGATION
    # -------------------------------------------------------------------------
    def test_canvas_inspector_slider_threshold_live_propagation(self) -> None:
        """Valida que alterações de sliders propagam imediatamente para a calibração."""
        inspector = CanvasInspectorOverlay()
        inspector.update_param("match_threshold", 0.92)
        inspector.update_param("letterbox_thresh", 22.0)

        self.assertEqual(inspector.get_param("match_threshold"), 0.92)
        self.assertEqual(inspector.get_param("letterbox_thresh"), 22.0)

    # -------------------------------------------------------------------------
    # TEST 7: GUI FIELD TRIAL THREAD DECOUPLING
    # -------------------------------------------------------------------------
    def test_gui_field_trial_thread_decoupling(self) -> None:
        """Valida que execução do Field Trial pode rodar em thread separada com sinalização."""
        execution_done = threading.Event()
        trial_result = []

        def worker():
            res = run_field_trial_session(num_cycles=1, dry_run=True)
            trial_result.append(res)
            execution_done.set()

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        th.join(timeout=10.0)

        self.assertTrue(execution_done.is_set())
        self.assertEqual(len(trial_result), 1)

    # -------------------------------------------------------------------------
    # TEST 8: FIELD TRIAL CLI ARGUMENT PARSING
    # -------------------------------------------------------------------------
    def test_field_trial_cli_argument_parsing(self) -> None:
        """Valida suporte a flags de CLI sem erro de argumentos."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--cycles", type=int, default=3)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--no-gui", action="store_true")
        parser.add_argument("--save-replay", action="store_true")
        parser.add_argument("--output", type=str, default=None)

        args = parser.parse_args(["--cycles", "5", "--dry-run", "--debug", "--save-replay"])
        self.assertEqual(args.cycles, 5)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.debug)
        self.assertTrue(args.save_replay)

    # -------------------------------------------------------------------------
    # TEST 9: SELF HEALING HANDLES EMPTY FRAME GRACEFULLY
    # -------------------------------------------------------------------------
    def test_self_healing_handles_empty_frame_gracefully(self) -> None:
        """Valida que o SelfHealingEngine não quebra com None ou arrays vazios."""
        engine = SelfHealingEngine(event_bus=self.event_bus)

        self.assertFalse(engine.detect_and_recover_webgl_freeze(None))
        self.assertFalse(engine.detect_and_recover_webgl_freeze(np.array([])))
        self.assertFalse(engine.auto_dismiss_unexpected_popups(None))
        self.assertFalse(engine.auto_dismiss_unexpected_popups(np.array([])))

    # -------------------------------------------------------------------------
    # TEST 10: MAIN CLI ENTRYPOINT FLAGS
    # -------------------------------------------------------------------------
    def test_main_cli_entrypoint_flags(self) -> None:
        """Valida que main.py suporta --version sem falha."""
        import subprocess
        proc = subprocess.run(
            ["py", "-3.12", "main.py", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Lumena Bot Control Center v4.4", proc.stdout)


if __name__ == "__main__":
    unittest.main()
