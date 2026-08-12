import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

from src.models.enums import AgentState
from src.perception.screen_capture import ScreenCapture
from src.perception.ui_detector import UIDetector
from src.perception.battle_detector import BattleDetector
from src.perception.world_detector import WorldDetector
from src.perception.landmark_detector import LandmarkDetector
from src.perception.ocr import OCREngine
from src.perception.state_classifier import StateClassifier


class TestPerceptionFixtures(unittest.TestCase):
    def setUp(self):
        # Frame base 640x360 neutro (cinza)
        self.blank_frame = np.full((360, 640, 3), 100, dtype=np.uint8)

    # -------------------------------------------------------------
    # 1 & 2. ScreenCapture & Frame Diff
    # -------------------------------------------------------------
    @patch("mss.mss")
    def test_screen_capture_and_frame_diff(self, mock_mss_cls):
        mock_sct = MagicMock()
        mock_mss_cls.return_value = mock_sct
        mock_sct.monitors = [{"width": 1920, "height": 1080}, {"width": 1920, "height": 1080}]
        
        # Simula captura de imagem BGRA 100x100
        bgra_img = np.full((100, 100, 4), 128, dtype=np.uint8)
        mock_sct.grab.return_value = bgra_img

        sc = ScreenCapture(monitor_index=1)
        frame, ts = sc.capture_frame()

        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (100, 100, 3))
        self.assertGreater(ts, 0.0)

        # Test frame difference
        f1 = np.zeros((100, 100, 3), dtype=np.uint8)
        f2 = np.full((100, 100, 3), 255, dtype=np.uint8)
        diff_max = ScreenCapture.compute_frame_diff(f1, f2)
        diff_zero = ScreenCapture.compute_frame_diff(f1, f1)

        self.assertAlmostEqual(diff_max, 1.0, places=1)
        self.assertAlmostEqual(diff_zero, 0.0, places=2)

        # Tolerância a frames inválidos
        self.assertEqual(ScreenCapture.compute_frame_diff(None, f1), 0.0)
        sc.close()

    # -------------------------------------------------------------
    # 3. UIDetector
    # -------------------------------------------------------------
    def test_ui_detector_black_screen_and_dialog(self):
        detector = UIDetector()

        # Teste Tela Preta
        black_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        black_elem = detector.detect_black_screen(black_frame)
        self.assertIsNotNone(black_elem)
        self.assertEqual(black_elem.name, "black_screen")
        self.assertGreaterEqual(black_elem.confidence, 0.9)

        # Teste Caixa de Diálogo na parte inferior
        dialog_frame = self.blank_frame.copy()
        # Desenha retângulo escuro na região de diálogo (60% a 95% altura)
        cv2.rectangle(dialog_frame, (50, 240), (590, 340), (20, 20, 20), -1)
        dialog_elem = detector.detect_dialog_box(dialog_frame)
        self.assertIsNotNone(dialog_elem)
        self.assertEqual(dialog_elem.name, "dialog_box")

        # Teste Template Matching de UI
        tmpl = np.zeros((30, 80, 3), dtype=np.uint8)
        cv2.rectangle(tmpl, (2, 2), (78, 28), (220, 180, 50), -1)
        cv2.putText(tmpl, "OK", (25, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        frame_with_tmpl = self.blank_frame.copy()
        frame_with_tmpl[100:130, 100:180] = tmpl

        match = detector.match_template_element(frame_with_tmpl, "test_button", tmpl, threshold=0.85)
        self.assertIsNotNone(match)
        self.assertEqual(match.name, "test_button")
        self.assertEqual(match.bounding_box, (100, 100, 80, 30))

        # Tolerância a None
        self.assertEqual(len(detector.detect_all(None)), 0)


    # -------------------------------------------------------------
    # 4. BattleDetector
    # -------------------------------------------------------------
    def test_battle_detector_features(self):
        detector = BattleDetector()

        # Cria frame sintético de batalha com botão vermelho FIGHT no quadrante inferior
        battle_frame = self.blank_frame.copy()
        # Botão vermelho (BGR: 0, 0, 230)
        cv2.rectangle(battle_frame, (400, 260), (520, 310), (0, 0, 230), -1)

        # Barra de HP inimiga verde no topo direito (BGR: 0, 220, 0)
        cv2.rectangle(battle_frame, (420, 20), (580, 40), (0, 220, 0), -1)

        telemetry = detector.detect_battle_state(battle_frame)
        self.assertTrue(telemetry.in_battle)
        self.assertIsNotNone(telemetry.fight_button_pos)
        self.assertGreater(len(telemetry.available_moves), 0)

        # Teste de vitória (HP inimigo zerado / tela sem verde na barra)
        victory_frame = self.blank_frame.copy()
        cv2.rectangle(victory_frame, (400, 260), (520, 310), (0, 0, 230), -1)
        # Barra inimiga preta (HP 0%)
        cv2.rectangle(victory_frame, (420, 20), (580, 40), (0, 0, 0), -1)
        v_telemetry = detector.detect_battle_state(victory_frame)
        self.assertTrue(v_telemetry.victory_detected)

        # Tolerância a frame vazio
        empty_telemetry = detector.detect_battle_state(None)
        self.assertFalse(empty_telemetry.in_battle)

    # -------------------------------------------------------------
    # 5. WorldDetector
    # -------------------------------------------------------------
    def test_world_detector_grass_and_paths(self):
        detector = WorldDetector()

        # Cria frame com 80% de grama verde (BGR: 34, 139, 34)
        grass_frame = np.full((360, 640, 3), (34, 139, 34), dtype=np.uint8)
        features = detector.detect_world_features(grass_frame)

        self.assertTrue(features["has_grass"])
        self.assertGreater(features["grass_density"], 0.7)

        # Frame cinza sem grama
        barren_frame = np.full((360, 640, 3), (80, 80, 80), dtype=np.uint8)
        barren_features = detector.detect_world_features(barren_frame)
        self.assertFalse(barren_features["has_grass"])
        self.assertEqual(barren_features["grass_density"], 0.0)

        # Tolerância a None
        self.assertEqual(detector.compute_grass_density(None), 0.0)

    # -------------------------------------------------------------
    # 6. LandmarkDetector
    # -------------------------------------------------------------
    def test_landmark_detector_blue_crystal(self):
        detector = LandmarkDetector()

        # Cria frame com Cristal Azul Luminoso (Ciano BGR: 255, 210, 0 -> HSV ~ H:100, S:255, V:255)
        crystal_frame = self.blank_frame.copy()
        # Desenha retângulo de cristal azul no canto (200, 150) com tamanho 40x60
        cv2.rectangle(crystal_frame, (200, 150), (240, 210), (255, 210, 0), -1)

        found, rel_pos, elem = detector.detect_crystal(crystal_frame)
        self.assertTrue(found)
        self.assertIsNotNone(rel_pos)
        self.assertIsNotNone(elem)
        self.assertEqual(elem.name, "blue_crystal")
        self.assertGreaterEqual(elem.confidence, 0.6)

        # Frame sem cristal
        not_found, _, _ = detector.detect_crystal(self.blank_frame)
        self.assertFalse(not_found)

        # Tolerância a None
        self.assertFalse(detector.detect_crystal(None)[0])

    # -------------------------------------------------------------
    # 7. OCREngine
    # -------------------------------------------------------------
    def test_ocr_preprocessing_and_parsing_fallbacks(self):
        ocr = OCREngine()

        # Preprocessamento de ROI
        sample_roi = np.full((40, 100, 3), 200, dtype=np.uint8)
        processed = ocr.preprocess_roi(sample_roi, mode="digits")
        self.assertIsNotNone(processed)
        self.assertEqual(processed.shape, (80, 200))

        # Teste de Parsing de HP/PP em modo tolerante
        curr_hp, max_hp, pct = ocr.parse_hp(sample_roi)
        self.assertEqual(pct, 1.0)

        curr_pp, max_pp, avail = ocr.parse_pp(sample_roi)
        self.assertTrue(avail)

        # Tolerância a ROI vazia/None
        self.assertEqual(ocr.parse_hp(None), (None, None, 1.0))
        self.assertEqual(ocr.parse_pp(None), (None, None, True))
        self.assertEqual(ocr.read_text(None), "")

    # -------------------------------------------------------------
    # 8. StateClassifier
    # -------------------------------------------------------------
    def test_state_classifier_integration(self):
        classifier = StateClassifier()

        # A. Frame Preto -> CALIBRATING
        black_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        snap_calib = classifier.classify_frame(black_frame, timestamp=1.0)
        self.assertEqual(snap_calib.screen_state, AgentState.CALIBRATING)

        # B. Frame de Batalha (botão vermelho) -> BATTLE_DETECTED / BATTLE
        battle_frame = self.blank_frame.copy()
        cv2.rectangle(battle_frame, (400, 260), (520, 310), (0, 0, 230), -1)
        snap_battle = classifier.classify_frame(battle_frame, timestamp=2.0)
        self.assertIn(snap_battle.screen_state, [AgentState.BATTLE, AgentState.BATTLE_DETECTED])

        # C. Frame de Grama -> EXPLORING
        grass_frame = np.full((360, 640, 3), (34, 139, 34), dtype=np.uint8)
        snap_grass = classifier.classify_frame(grass_frame, timestamp=3.0)
        self.assertEqual(snap_grass.screen_state, AgentState.EXPLORING)
        self.assertGreater(snap_grass.grass_density, 0.5)

        # D. Frame de Cristal Azul -> SEARCHING_CRYSTAL
        crystal_frame = self.blank_frame.copy()
        cv2.rectangle(crystal_frame, (200, 150), (240, 210), (255, 210, 0), -1)
        snap_crystal = classifier.classify_frame(crystal_frame, timestamp=4.0)
        self.assertEqual(snap_crystal.screen_state, AgentState.SEARCHING_CRYSTAL)
        self.assertTrue(snap_crystal.crystal_detected)

        # E. Frame com Cristal + Diálogo -> HEALING
        heal_frame = crystal_frame.copy()
        cv2.rectangle(heal_frame, (50, 240), (590, 340), (20, 20, 20), -1)
        snap_heal = classifier.classify_frame(heal_frame, timestamp=5.0)
        self.assertEqual(snap_heal.screen_state, AgentState.HEALING)

        # F. Tolerância a Frame Vazio/None -> UNKNOWN_STATE
        snap_unknown = classifier.classify_frame(None, timestamp=6.0)
        self.assertEqual(snap_unknown.screen_state, AgentState.UNKNOWN_STATE)


if __name__ == "__main__":
    unittest.main()
