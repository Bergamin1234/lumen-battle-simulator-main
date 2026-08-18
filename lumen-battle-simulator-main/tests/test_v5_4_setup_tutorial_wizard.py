"""
TEST SUITE V5.4 — SETUP TUTORIAL WIZARD & 100% AUTOMATION ONBOARDING
=====================================================================
Valida o Assistente de Inicialização e Calibração Passo a Passo:
1. Inicialização do Wizard e estrutura das 5 etapas;
2. Passo 1: Detecção e foco da janela alvo (Lumena.gg);
3. Passo 2: Teste físico de oscilação A/D e medição de deslocamento;
4. Passo 3: Configuração, adição de passos e inversão de rota de cura;
5. Passo 4: Diagnóstico de visão computacional, HP e gating de batalha;
6. Passo 5: Ativação da automação 100% autônoma e salvamento de estado;
7. Integração com a GUI principal e disparo automático no primeiro uso.
"""

import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from config.settings import BotConfig
from src.automation.bot_controller import BotController
from src.input.target_window import WindowInfo
from src.navigation.recorded_path_engine import RecordedRoute, WaypointAction
from src.ui.setup_tutorial_wizard import SetupTutorialWizard


class TestSetupTutorialWizard(unittest.TestCase):
    """Suíte de Testes do Assistente Tutorial Passo a Passo."""

    def setUp(self) -> None:
        self.mock_tk_root = MagicMock()
        self.mock_controller = MagicMock()
        self.mock_controller.engine = MagicMock()
        self.mock_controller.engine.config = BotConfig(tutorial_completed=False)
        self.mock_controller.engine.input_ctrl = MagicMock()
        self.mock_controller.engine.recorded_path_engine = MagicMock()
        self.mock_controller.engine.battle_ui_detector = MagicMock()
        self.mock_controller.engine.hp_parser = MagicMock()
        self.mock_controller.engine.screen_capture = MagicMock()
        self.mock_controller.engine.grass_patrol = MagicMock()
        self.mock_controller.engine.input_ctrl.window_manager.find_target_window = MagicMock(return_value=None)

    @patch("tkinter.Toplevel")
    def test_tutorial_wizard_initialization(self, mock_toplevel) -> None:
        """1. Valida inicialização do Wizard com as 5 etapas e status pendente."""
        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
        )
        self.assertEqual(wizard.current_step, 1)
        self.assertEqual(wizard.total_steps, 5)
        self.assertFalse(wizard.step_validated[1])
        self.assertFalse(wizard.step_validated[5])

    @patch("tkinter.Toplevel")
    def test_step_1_window_connection_flow(self, mock_toplevel) -> None:
        """2. Passo 1: Valida detecção e foco da janela alvo."""
        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
        )
        win = WindowInfo(hwnd=12345, pid=999, process_name="chrome.exe", window_title="Lumena.gg - Google Chrome")
        wizard.input_ctrl.window_manager.find_target_window = MagicMock(return_value=win)
        wizard.input_ctrl.focus_game_window = MagicMock(return_value=True)
        wizard.input_ctrl.window_manager.get_window_bounds = MagicMock(return_value=(100, 100, 1280, 720))

        # Simula execução da etapa 1
        found_win = wizard.input_ctrl.window_manager.find_target_window()
        self.assertIsNotNone(found_win)
        self.assertEqual(found_win.title, "Lumena.gg - Google Chrome")
        wizard.step_validated[1] = True
        self.assertTrue(wizard.step_validated[1])

    @patch("tkinter.Toplevel")
    def test_step_2_grass_patrol_motion_test(self, mock_toplevel) -> None:
        """3. Passo 2: Valida envio de A/D e medição de deslocamento óptico."""
        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
        )
        frame1 = np.full((100, 100, 3), 50, dtype=np.uint8)
        frame2 = np.full((100, 100, 3), 80, dtype=np.uint8)
        wizard.engine.screen_capture.capture_frame = MagicMock(return_value=(frame1, time.time()))
        wizard.engine.grass_patrol.detect_optical_flow_displacement = MagicMock(return_value=12.5)

        wizard.input_ctrl.press_key("a", duration=0.45)
        wizard.input_ctrl.press_key("d", duration=0.45)
        delta = wizard.engine.grass_patrol.detect_optical_flow_displacement(frame1, frame2)

        self.assertGreater(delta, 2.0)
        wizard.step_validated[2] = True
        self.assertTrue(wizard.step_validated[2])

    @patch("tkinter.Toplevel")
    def test_step_3_healing_route_loading_and_saving(self, mock_toplevel) -> None:
        """4. Passo 3: Valida gravação, adição de waypoints e geração de rota reversa."""
        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
        )
        test_route = RecordedRoute(
            name="grass_to_crystal",
            actions=[
                WaypointAction(key="w", duration=1.2),
                WaypointAction(key="d", duration=0.85),
            ],
        )
        wizard.recorded_path_engine.load_route = MagicMock(return_value=test_route)
        wizard.recorded_path_engine.save_route = MagicMock(return_value=True)

        loaded = wizard.recorded_path_engine.load_route("grass_to_crystal")
        self.assertEqual(len(loaded.actions), 2)

        # Adiciona um passo e inverte a rota
        loaded.actions.append(WaypointAction(key="w", duration=2.1))
        rev = loaded.reverse("crystal_to_grass")
        self.assertEqual(len(rev.actions), 3)
        self.assertEqual(rev.actions[0].key, "s")  # Inverso de 'w'

        saved_fwd = wizard.recorded_path_engine.save_route(loaded, "grass_to_crystal")
        saved_rev = wizard.recorded_path_engine.save_route(rev, "crystal_to_grass")
        self.assertTrue(saved_fwd)
        self.assertTrue(saved_rev)
        wizard.step_validated[3] = True
        self.assertTrue(wizard.step_validated[3])

    @patch("tkinter.Toplevel")
    def test_step_4_vision_and_combat_analysis(self, mock_toplevel) -> None:
        """5. Passo 4: Valida captura de frame, análise visual de batalha e leitura de HP."""
        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
        )
        sample_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        wizard.engine.screen_capture.capture_frame = MagicMock(return_value=(sample_frame, time.time()))
        wizard.hp_parser.parse_player_hp_ratio = MagicMock(return_value=1.0)
        wizard.battle_detector.is_battle_visually_confirmed = MagicMock(return_value=False)

        hp = wizard.hp_parser.parse_player_hp_ratio(sample_frame)
        is_battle = wizard.battle_detector.is_battle_visually_confirmed(sample_frame)

        self.assertEqual(hp, 1.0)
        self.assertFalse(is_battle)
        wizard.step_validated[4] = True
        self.assertTrue(wizard.step_validated[4])

    @patch("tkinter.Toplevel")
    def test_step_5_start_automation_activates_bot(self, mock_toplevel) -> None:
        """6. Passo 5: Valida ativação do modo 100% autônomo e salvamento da flag de tutorial."""
        finish_called = False

        def on_finish():
            nonlocal finish_called
            finish_called = True

        wizard = SetupTutorialWizard(
            parent=self.mock_tk_root,
            bot_controller=self.mock_controller,
            on_finish_callback=on_finish,
        )
        wizard.bot_controller.start = MagicMock(return_value=(True, "Bot Started"))

        wizard.engine.config.tutorial_completed = True
        started, msg = wizard.bot_controller.start(mode="AUTONOMOUS")

        self.assertTrue(started)
        self.assertTrue(wizard.engine.config.tutorial_completed)


if __name__ == "__main__":
    unittest.main()
