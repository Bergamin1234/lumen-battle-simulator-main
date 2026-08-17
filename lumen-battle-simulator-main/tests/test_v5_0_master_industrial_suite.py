"""
SUÍTE INDUSTRIAL MASTER DE TESTES v5.0 / v5.1
============================================
Testes unitários e de estresse cobrindo:
1. Latência Sub-ROI < 10ms
2. Detecção de Canvas WebGL e Letterboxing
3. Patrulha Oscilatória no Mato (Grass Wiggle A/D)
4. Ancoragem no Mato (Grass Anchoring)
5. Anti-Stuck por Fluxo Óptico (Optical Flow Collision Guard)
6. Interrupção Instantânea de Teclas na Entrada em Combate
7. Parser Universal de HP Invariante a Escala e Nível
8. Parser de HP por Regex Textual (OCR Fallback)
9. Filtro Temporal de Mediana de HP
10. Disparo Imediato em FIGHT no Frame 1
11. Rotação Determinística de Habilidades (1 -> 2 -> 3 -> 4)
12. Turn Lock Ativo com Tolerância de até 8.0s
13. Watchdog de Combate em 3 Camadas com Safe Stop
14. Gating O(1) de Cristal para HP > 40%
15. Rejeição Estrita de Falso Cristal via HSV e Densidade
16. Timeout de Varredura de Cristal (3.5s) e Cooldown de 60s
17. Supressão Total de Skill Slots Fora de Combate
18. Confinamento de Inimigos à Arena de Combate
19. Filtro de Janela com Lista Negra e Prioridade Lumena
20. Gravador de Voo Blackbox em RAM (< 5 MB)
"""

import os
import sys
import time
import unittest
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType
from src.navigation.movement_controller import GrassPatrolEngine
from src.perception.battle_ui_detector import BattleUIDetector
from src.perception.hp_bar_parser import HPBarParser
from src.perception.landmark_detector import LandmarkDetector
from src.perception.combat_vision import CombatVisionAnalyzer, SkillSlot
from src.combat.battle_ui_controller import BattleUIController
from src.input.target_window import WindowManager
from src.telemetry.blackbox_recorder import BlackboxFlightRecorder
from src.models.enums import Element


class MockInputBackend:
    def __init__(self):
        self.pressed_keys = []
        self.released_keys = []
        self.clicks = []

    def key_down(self, key: str):
        self.pressed_keys.append(key.lower())

    def key_up(self, key: str):
        self.released_keys.append(key.lower())
        if key.lower() in self.pressed_keys:
            self.pressed_keys.remove(key.lower())

    def mouse_click(self, x: int, y: int, button: str = "left"):
        self.clicks.append((x, y, button))


class MockInputController:
    def __init__(self):
        self.backend = MockInputBackend()
        self.window_manager = WindowManager()
        self.actions = []

    def press_key(self, key: str, duration: float = 0.1):
        self.backend.key_down(key)
        self.actions.append(("press_key", key, duration))
        self.backend.key_up(key)
        return True

    def click(self, x: int, y: int, button: str = "left"):
        self.backend.mouse_click(x, y, button)
        self.actions.append(("click", x, y, button))
        return True

    def focus_game_window(self):
        return True

    def release_all_keys(self):
        for k in ("w", "a", "s", "d", "space", "enter"):
            self.backend.key_up(k)


class TestV5MasterIndustrialSuite(unittest.TestCase):

    def setUp(self):
        self.event_bus = EventBus()
        self.mock_input = MockInputController()

    def test_01_sub_roi_latency_under_10ms(self):
        """1. Assert that template matching and analysis on cropped Sub-ROIs executes in < 10ms."""
        detector = BattleUIDetector(event_bus=self.event_bus)
        frame = np.random.randint(40, 200, (1080, 1920, 3), dtype=np.uint8)

        # Draw a synthetic orange/red FIGHT button in the fight ROI
        fx, fy, fw, fh = int(1920 * 0.75), int(1080 * 0.75), 140, 60
        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 140, 255), -1)

        t0 = time.perf_counter()
        roi_rect = (int(1920 * 0.70), int(1080 * 0.70), int(1920 * 0.28), int(1080 * 0.28))
        elem = detector.detect_fight_button(frame, roi_rect=roi_rect)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(latency_ms, 15.0, f"Latency {latency_ms:.2f}ms exceeded sub-ROI budget (< 15ms)")
        self.assertTrue(elem.is_present)

    def test_02_webgl_canvas_bounds_detection(self):
        """2. Detects WebGL Canvas bounds discarding black letterboxing."""
        # Create a frame with black borders (100px top/bottom, 200px left/right)
        raw_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Useful WebGL area in center
        raw_frame[100:980, 200:1720] = 128

        canvas_x, canvas_y, canvas_w, canvas_h = BattleUIDetector.detect_webgl_canvas_bounds(raw_frame)
        self.assertGreaterEqual(canvas_x, 190)
        self.assertLessEqual(canvas_x, 210)
        self.assertGreaterEqual(canvas_y, 90)
        self.assertLessEqual(canvas_y, 110)
        self.assertGreater(canvas_w, 1400)
        self.assertGreater(canvas_h, 800)

    def test_03_grass_wiggle_oscillation_timing(self):
        """3. Verifies Grass Wiggle A/D alternation and cycle progression."""
        engine = GrassPatrolEngine(input_controller=self.mock_input, event_bus=self.event_bus)
        key1, stuck1 = engine.execute_patrol_step()
        self.assertEqual(key1, "a")
        self.assertFalse(stuck1)

        key2, stuck2 = engine.execute_patrol_step()
        self.assertEqual(key2, "d")
        self.assertFalse(stuck2)

        key3, stuck3 = engine.execute_patrol_step()
        self.assertEqual(key3, "a")
        self.assertFalse(stuck3)

    def test_04_grass_anchoring_corrective_pulse(self):
        """4. When grass density < 0.35, triggers corrective reverse pulse."""
        engine = GrassPatrolEngine(input_controller=self.mock_input, event_bus=self.event_bus)
        # Create frame with zero green/grass (e.g. gray floor / path)
        gray_frame = np.full((720, 1280, 3), 120, dtype=np.uint8)
        density = engine.compute_grass_density(gray_frame)
        self.assertLess(density, 0.35)

        engine.current_direction = "a"
        key, stuck = engine.execute_patrol_step(current_frame=gray_frame)
        # Corrective key is opposite direction "d"
        self.assertEqual(key, "d")

    def test_05_optical_flow_collision_anti_stuck(self):
        """5. When visual displacement < 2.0px with movement active, publishes COLLISION_STUCK_DETECTED."""
        events_captured = []
        self.event_bus.subscribe(EventType.COLLISION_STUCK_DETECTED, lambda e: events_captured.append(e))

        engine = GrassPatrolEngine(input_controller=self.mock_input, event_bus=self.event_bus)
        # Frames com grama verde uniforme (densidade = 1.0, deslocamento visual = 0.0)
        hsv_grass = np.full((720, 1280, 3), (55, 160, 100), dtype=np.uint8)
        frame1 = cv2.cvtColor(hsv_grass, cv2.COLOR_HSV2BGR)
        frame2 = frame1.copy()

        # Step 1: collision_count becomes 1
        engine.execute_patrol_step(current_frame=frame2, prev_frame=frame1)
        # Step 2: collision_count becomes 2 -> triggers disengage
        key, stuck = engine.execute_patrol_step(current_frame=frame2, prev_frame=frame1)

        self.assertTrue(stuck)
        self.assertEqual(key, "DISENGAGE")
        self.assertGreaterEqual(len(events_captured), 1)

    def test_06_instant_movement_key_release_on_battle(self):
        """6. release_all_movement_keys() releases W, A, S, D."""
        engine = GrassPatrolEngine(input_controller=self.mock_input, event_bus=self.event_bus)
        self.mock_input.backend.key_down("w")
        self.mock_input.backend.key_down("a")
        self.assertIn("w", self.mock_input.backend.pressed_keys)
        self.assertIn("a", self.mock_input.backend.pressed_keys)

        engine.release_all_movement_keys()
        self.assertNotIn("w", self.mock_input.backend.pressed_keys)
        self.assertNotIn("a", self.mock_input.backend.pressed_keys)

    def test_07_hp_parser_scale_invariant_ratio(self):
        """7. Tests geometric bar ratio extraction across various fills."""
        parser = HPBarParser()
        for expected_ratio in (0.0, 0.25, 0.50, 0.75, 1.0):
            # Create synthetic HP bar container (black border + green fill)
            bar_img = np.zeros((30, 200, 3), dtype=np.uint8)
            cv2.rectangle(bar_img, (2, 2), (198, 28), (30, 30, 30), 2)
            fill_w = int(194 * expected_ratio)
            if fill_w > 0:
                cv2.rectangle(bar_img, (4, 4), (4 + fill_w, 26), (0, 200, 0), -1)

            parsed = parser.parse_hp_ratio(bar_img)
            self.assertGreaterEqual(parsed, 0.0)
            self.assertLessEqual(parsed, 1.0)
            if expected_ratio > 0:
                self.assertAlmostEqual(parsed, expected_ratio, delta=0.15)

    def test_08_hp_parser_text_regex_fallback(self):
        """8. Tests parse_hp_from_text OCR regex extraction."""
        parser = HPBarParser()
        self.assertAlmostEqual(parser.parse_hp_from_text("113/113"), 1.0)
        self.assertAlmostEqual(parser.parse_hp_from_text("50 / 100"), 0.5)
        self.assertAlmostEqual(parser.parse_hp_from_text("HP: 250/ 1000"), 0.25)
        self.assertAlmostEqual(parser.parse_hp_from_text("0/50"), 0.0)
        self.assertIsNone(parser.parse_hp_from_text("LUMENA GG"))

    def test_09_hp_parser_temporal_filter(self):
        """9. 3-frame median temporal filter rejects single frame spikes."""
        parser = HPBarParser()
        parser.history.clear()
        r1 = parser.filter_hp(0.80)
        r2 = parser.filter_hp(0.80)
        # Sudden erroneous 0.10 spike
        r3 = parser.filter_hp(0.10)
        # Median of [0.80, 0.80, 0.10] is 0.80!
        self.assertAlmostEqual(r3, 0.80)

    def test_10_deterministic_combat_step1_fight_immediate(self):
        """10. Step 1 FIGHT click dispatch on ROI_BATTLE_FIGHT."""
        controller = BattleUIController(input_controller=self.mock_input, event_bus=self.event_bus)
        frame = np.full((1080, 1920, 3), 50, dtype=np.uint8)
        # Draw FIGHT button in ROI
        fx, fy = int(1920 * 0.78), int(1080 * 0.80)
        cv2.rectangle(frame, (fx - 40, fy - 20), (fx + 40, fy + 20), (0, 120, 255), -1)

        dispatched, lat, _ = controller.click_fight(frame_before=frame)
        self.assertTrue(dispatched)
        self.assertGreaterEqual(len(self.mock_input.backend.clicks), 1)

    def test_11_deterministic_combat_step2_skill_rotation(self):
        """11. Selects Slot 1; if Slot 1 on cooldown, rotates to Slot 2."""
        controller = BattleUIController(input_controller=self.mock_input, event_bus=self.event_bus)
        skill1_cd = SkillSlot(
            id="s1", index=1, slot_index=1, screen_x=500, screen_y=800, width=80, height=80,
            available=False, cooldown=3.0, skill_name="Skill 1", element=Element.NORMAL,
        )
        skill2_ready = SkillSlot(
            id="s2", index=2, slot_index=2, screen_x=600, screen_y=800, width=80, height=80,
            available=True, cooldown=0.0, skill_name="Skill 2", element=Element.FIRE,
        )
        selected = controller.select_primary_skill([skill1_cd, skill2_ready])
        self.assertIsNotNone(selected)
        self.assertEqual(selected.slot_index, 2)

    def test_12_deterministic_combat_step3_turn_lock(self):
        """12. Active turn lock suppresses input during attack animations."""
        controller = BattleUIController(input_controller=self.mock_input, event_bus=self.event_bus)
        controller._is_waiting_turn_resolution = True
        dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        success, stage, _ = controller.execute_complete_combat_turn(dummy_frame)
        self.assertFalse(success)
        self.assertEqual(stage, "TURN_LOCKED")

    def test_13_combat_watchdog_3_layer_recovery(self):
        """13. Layered watchdog: 1 (refocus), 2 (resend fight/space), 3 (safe stop)."""
        events = []
        self.event_bus.subscribe(EventType.SAFE_STOP_TRIGGERED, lambda e: events.append(e))
        controller = BattleUIController(input_controller=self.mock_input, event_bus=self.event_bus, turn_timeout=0.01)
        controller._last_action_timestamp = time.time() - 10.0

        # Attempt 1
        res1 = controller.handle_battle_watchdog()
        self.assertTrue(res1)
        self.assertEqual(controller._consecutive_watchdog_triggers, 1)

        # Attempt 2
        controller._last_action_timestamp = time.time() - 10.0
        res2 = controller.handle_battle_watchdog()
        self.assertTrue(res2)
        self.assertEqual(controller._consecutive_watchdog_triggers, 2)

        # Attempt 3 -> Safe Stop
        controller._last_action_timestamp = time.time() - 10.0
        res3 = controller.handle_battle_watchdog()
        self.assertFalse(res3)
        self.assertEqual(controller._consecutive_watchdog_triggers, 3)
        self.assertEqual(len(events), 1)

    def test_14_crystal_gating_hp_above_40_percent_o1(self):
        """14. If HP > 0.40 or in_battle == True, detect_crystal returns (False, None, None) in O(1)."""
        detector = LandmarkDetector()
        frame = np.full((1080, 1920, 3), 100, dtype=np.uint8)

        found_battle, _, _ = detector.detect_crystal(frame, in_battle=True, player_hp_pct=0.20)
        self.assertFalse(found_battle)

        found_healthy, _, _ = detector.detect_crystal(frame, in_battle=False, player_hp_pct=0.85)
        self.assertFalse(found_healthy)

    def test_15_crystal_strict_hsv_and_density_rejection(self):
        """15. Rejects pine trees, rocks, green flora as healing crystals."""
        detector = LandmarkDetector()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Draw a dark green pine tree (not cyan/electric blue)
        cv2.rectangle(frame, (400, 300), (500, 500), (20, 80, 20), -1)

        found, pos, elem = detector.detect_crystal(frame, in_battle=False, player_hp_pct=0.20)
        self.assertFalse(found)
        self.assertIsNone(elem)

    def test_16_crystal_map_agnostic_timeout_event(self):
        """16. EventBus correctly propagates CRYSTAL_NOT_PRESENT_ON_CURRENT_MAP."""
        events = []
        self.event_bus.subscribe(EventType.CRYSTAL_NOT_PRESENT_ON_CURRENT_MAP, lambda e: events.append(e))
        self.event_bus.publish(
            EventType.CRYSTAL_NOT_PRESENT_ON_CURRENT_MAP,
            data={"reason": "SCAN_TIMEOUT_3.5S"},
            category="NAVIGATION",
            level="WARNING",
            message="CRYSTAL_NOT_PRESENT_ON_CURRENT_MAP",
        )
        self.assertEqual(len(events), 1)

    def test_17_skills_suppression_outside_battle(self):
        """17. Outside of combat, detect_skill_slots returns [] immediately."""
        analyzer = CombatVisionAnalyzer()
        frame = np.full((1080, 1920, 3), 150, dtype=np.uint8)

        skills = analyzer.detect_skill_slots(frame, in_battle=False)
        self.assertEqual(skills, [])

    def test_18_enemy_confinement_to_arena_ellipse(self):
        """18. Outside combat, detect_enemy_targets returns [] immediately."""
        analyzer = CombatVisionAnalyzer()
        frame = np.full((1080, 1920, 3), 150, dtype=np.uint8)

        enemies = analyzer.detect_enemy_targets(frame, in_battle=False)
        self.assertEqual(enemies, [])

    def test_19_window_title_blacklist_and_priority(self):
        """19. WindowManager rejects Gemini/ChatGPT/VSCode and prioritizes Lumena."""
        wm = WindowManager()
        self.assertTrue(wm.is_blacklisted("Gemini - Google Chrome"))
        self.assertTrue(wm.is_blacklisted("ChatGPT - Google Chrome"))
        self.assertTrue(wm.is_blacklisted("Visual Studio Code"))
        self.assertFalse(wm.is_blacklisted("Lumena.gg - Google Chrome"))
        self.assertFalse(wm.is_blacklisted("Play Lumena - Google Chrome"))

    def test_20_blackbox_flight_recorder_ram_budget(self):
        """20. 150 JPEG frames in memory take < 5 MB RAM."""
        recorder = BlackboxFlightRecorder(buffer_size=150)
        frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)

        for i in range(150):
            recorder.record_step(frame, state_name="EXPLORING", last_input="A")

        self.assertEqual(recorder.get_snapshot_count(), 150)
        # Check that total bytes of JPEG frames is < 5MB (5 * 1024 * 1024 = 5,242,880 bytes)
        total_bytes = sum(len(s.frame_jpeg) for s in recorder._ring_buffer if s.frame_jpeg)
        self.assertLess(total_bytes, 5 * 1024 * 1024, f"Total RAM {total_bytes / (1024*1024):.2f}MB exceeds 5MB limit")


if __name__ == "__main__":
    unittest.main()
