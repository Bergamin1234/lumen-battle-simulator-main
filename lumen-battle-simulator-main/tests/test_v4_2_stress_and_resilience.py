"""
LUMENA BOT v4.2 — STRESS, RESILIENCE & BLACKBOX HARNESS TESTS
==============================================================
Suíte de testes de estresse, adaptação visual e resiliência de produção:
1. test_letterboxing_and_aspect_ratio_normalization
2. test_hp_bar_parser_noise_and_flashing_resilience
3. test_loading_screen_suppresses_watchdog_stall
4. test_network_disconnect_detection_and_reconnect_trigger
5. test_blackbox_ring_buffer_persists_on_safe_stop
6. test_multi_target_arena_selection
7. test_canvas_bounds_coordinate_remapping
8. test_unresponsive_recovery_transition
9. test_blackbox_memory_footprint_capped
10. test_gui_bezier_renderer_data_feed
"""

import unittest
import time
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

from src.core.event_bus import EventBus
from src.automation.state_machine import BotState, BotStateMachine
from src.automation.bot_engine import LumenaBotEngine
from src.perception.screen_capture import ScreenCapture
from src.perception.hp_bar_parser import HPBarParser
from src.perception.battle_ui_detector import BattleUIDetector
from src.telemetry.blackbox_recorder import BlackboxFlightRecorder
from src.input.input_dispatcher import generate_cubic_bezier_trajectory


class TestLumenaBotV42StressAndResilience(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # TEST 1: LETTERBOXING & ASPECT RATIO NORMALIZATION
    # -------------------------------------------------------------------------
    def test_letterboxing_and_aspect_ratio_normalization(self) -> None:
        """Valida que o detector de Canvas isola a área ativa descartando barras pretas."""
        capture = ScreenCapture()

        # Simula janela 1920x1080 com jogo 1280x720 centralizado (Letterboxing + Pillarboxing)
        raw_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Preenche área do canvas ativo com imagem simulada (pixels não-pretos)
        raw_frame[180:900, 320:1600] = 120

        cb = capture.detect_webgl_canvas_bounds(raw_frame)
        self.assertEqual(cb[0], 320)
        self.assertEqual(cb[1], 180)
        self.assertEqual(cb[2], 1280)
        self.assertEqual(cb[3], 720)
        self.assertTrue(capture.is_letterboxed)

    # -------------------------------------------------------------------------
    # TEST 2: HP BAR PARSER NOISE & FLASHING RESILIENCE
    # -------------------------------------------------------------------------
    def test_hp_bar_parser_noise_and_flashing_resilience(self) -> None:
        """Valida que o filtro de mediana temporal suprime oscilações de animação de dano piscante."""
        parser = HPBarParser(history_len=3)

        # Cria uma barra de HP normal (verde, 80% cheia)
        bar_80 = np.zeros((30, 200, 3), dtype=np.uint8)
        bar_80[:, :160] = [0, 220, 0]  # Verde BGR
        bar_80[:, 160:] = [20, 20, 20]  # Background escuro

        # Cria um frame com flash branco/dano (ruído visual)
        bar_flash = np.full((30, 200, 3), 255, dtype=np.uint8)

        # Leitura 1: 80%
        r1 = parser.parse_hp_bar(bar_80, is_player=True, apply_temporal_filter=True)
        self.assertAlmostEqual(r1, 0.80, delta=0.08)

        # Leitura 2: Frame piscando em branco (flash)
        _ = parser.parse_hp_bar(bar_flash, is_player=True, apply_temporal_filter=True)

        # Leitura 3: 80%
        r3 = parser.parse_hp_bar(bar_80, is_player=True, apply_temporal_filter=True)
        # A mediana temporal deve amortecer o flash e permanecer próxima de 80%
        self.assertAlmostEqual(r3, 0.80, delta=0.08)

    # -------------------------------------------------------------------------
    # TEST 3: LOADING SCREEN SUPPRESSES WATCHDOG STALL
    # -------------------------------------------------------------------------
    def test_loading_screen_suppresses_watchdog_stall(self) -> None:
        """Garante que tela predominantemente preta transiciona para LOADING_SCREEN e reseta temporizador."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        engine._running = True

        # Frame predominantemente preto (> 85% pixels pretos)
        black_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(black_frame, time.time())):
            engine._execute_single_cycle()

        self.assertEqual(engine.fsm.current_state, BotState.LOADING_SCREEN)
        # Watchdog deve estar renovado
        self.assertLess(time.time() - engine._last_physical_action_time, 1.0)

    # -------------------------------------------------------------------------
    # TEST 4: NETWORK DISCONNECT DETECTION & RECONNECT TRIGGER
    # -------------------------------------------------------------------------
    def test_network_disconnect_detection_and_reconnect_trigger(self) -> None:
        """Valida que overlay cinza uniforme característico de desconexão ativa NETWORK_RECONNECTING."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        engine._running = True

        # Frame com overlay cinza uniforme
        gray_disconnect_frame = np.full((720, 1280, 3), 60, dtype=np.uint8)

        with patch.object(engine.input_ctrl, "press_key") as mock_key, \
             patch.object(engine.screen_capture, "capture_frame", return_value=(gray_disconnect_frame, time.time())):
            engine._execute_single_cycle()
            self.assertEqual(engine.fsm.current_state, BotState.NETWORK_RECONNECTING)
            mock_key.assert_called_with("f5", duration=0.2)

    # -------------------------------------------------------------------------
    # TEST 5: BLACKBOX RING BUFFER PERSISTS ON SAFE STOP
    # -------------------------------------------------------------------------
    def test_blackbox_ring_buffer_persists_on_safe_stop(self) -> None:
        """Valida que o gravador de voo mantém telemetria em RAM e descarrega em disco no Safe Stop."""
        recorder = BlackboxFlightRecorder(buffer_size=150)
        dummy_frame = np.full((360, 640, 3), 100, dtype=np.uint8)

        for i in range(10):
            recorder.record_step(
                frame=dummy_frame,
                state_name=f"STATE_{i}",
                last_input="W",
                events=[{"event": "STEP", "i": i}],
            )

        self.assertEqual(recorder.get_snapshot_count(), 10)

        dump_path = recorder.dump_blackbox(reason="TEST_SAFE_STOP", base_dir=self.temp_dir)
        self.assertIsNotNone(dump_path)
        self.assertTrue(os.path.exists(dump_path))
        self.assertTrue(os.path.exists(os.path.join(dump_path, "flight_data.json")))
        self.assertTrue(os.path.exists(os.path.join(dump_path, "frame_001.png")))

    # -------------------------------------------------------------------------
    # TEST 6: MULTI-TARGET ARENA SELECTION
    # -------------------------------------------------------------------------
    def test_multi_target_arena_selection(self) -> None:
        """Valida a detecção e ordenação de múltiplos alvos na arena."""
        detector = BattleUIDetector()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Desenha 2 alvos na região da arena (ROI_ARENA_TARGETS)
        # Alvo 1 em (800, 300) e Alvo 2 em (1100, 300)
        cv2.rectangle(frame, (780, 280), (840, 340), (200, 200, 200), -1)
        cv2.rectangle(frame, (1080, 280), (1140, 340), (200, 200, 200), -1)

        targets = detector.detect_active_targets(frame)
        self.assertGreaterEqual(len(targets), 1)
        # Devem estar ordenados horizontalmente
        for k in range(len(targets) - 1):
            self.assertLessEqual(targets[k][0], targets[k + 1][0])

    # -------------------------------------------------------------------------
    # TEST 7: CANVAS BOUNDS COORDINATE REMAPPING
    # -------------------------------------------------------------------------
    def test_canvas_bounds_coordinate_remapping(self) -> None:
        """Valida o remapeamento de coordenadas normalizadas para dentro do Canvas ativo."""
        capture = ScreenCapture()
        capture.current_canvas_bounds = (100, 50, 1000, 500)

        roi_norm = (0.5, 0.5, 0.2, 0.1)
        rx, ry, rw, rh = capture.map_normalized_roi_to_canvas(roi_norm)

        self.assertEqual(rx, 100 + 500)  # 600
        self.assertEqual(ry, 50 + 250)   # 300
        self.assertEqual(rw, 200)
        self.assertEqual(rh, 50)

    # -------------------------------------------------------------------------
    # TEST 8: UNRESPONSIVE RECOVERY TRANSITION
    # -------------------------------------------------------------------------
    def test_unresponsive_recovery_transition(self) -> None:
        """Valida que a FSM permite transição para UNRESPONSIVE_RECOVERY e retorno a EXPLORING."""
        fsm = BotStateMachine(initial_state=BotState.EXPLORING)
        res1 = fsm.transition_to(BotState.UNRESPONSIVE_RECOVERY, reason="Janela Congelada")
        self.assertTrue(res1)
        self.assertEqual(fsm.current_state, BotState.UNRESPONSIVE_RECOVERY)

        res2 = fsm.transition_to(BotState.EXPLORING, reason="Foco Restaurado")
        self.assertTrue(res2)
        self.assertEqual(fsm.current_state, BotState.EXPLORING)

    # -------------------------------------------------------------------------
    # TEST 9: BLACKBOX MEMORY FOOTPRINT CAPPED
    # -------------------------------------------------------------------------
    def test_blackbox_memory_footprint_capped(self) -> None:
        """Garante que o buffer circular descarta snapshots antigos mantendo limite rígido de 150."""
        recorder = BlackboxFlightRecorder(buffer_size=150)
        dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)

        for i in range(250):
            recorder.record_step(frame=dummy_frame, state_name=f"STEP_{i}")

        self.assertEqual(recorder.get_snapshot_count(), 150)

    # -------------------------------------------------------------------------
    # TEST 10: GUI BÉZIER RENDERER DATA FEED
    # -------------------------------------------------------------------------
    def test_gui_bezier_renderer_data_feed(self) -> None:
        """Valida que trajetórias Bézier cúbicas geram nós de interpolação matematicamente válidos."""
        p0, p3 = (150, 150), (650, 450)
        points = generate_cubic_bezier_trajectory(p0[0], p0[1], p3[0], p3[1], steps=20)

        self.assertGreaterEqual(len(points), 20)
        self.assertEqual(points[0], p0)
        self.assertEqual(points[-1], p3)


if __name__ == "__main__":
    unittest.main()
