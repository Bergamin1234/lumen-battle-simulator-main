"""
LUMENA BOT v4.5 HOTFIX — DISPATCH SKILL ACTION & WINDOW TITLE FILTERING SUITE
==============================================================================
Validação formal das correções de runtime:
1. test_battle_ui_controller_has_dispatch_skill_action
2. test_window_manager_ignores_blacklisted_gemini_titles
3. test_window_manager_matches_lumena_title
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from src.core.event_bus import EventBus
from src.combat.battle_ui_controller import BattleUIController
from src.input.target_window import TargetWindowManager, TargetWindowInfo
from src.models.combat_vision import SkillSlot
from src.models.enums import Element


class TestLumenaBotV45Hotfix(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: BATTLE UI CONTROLLER HAS DISPATCH SKILL ACTION
    # -------------------------------------------------------------------------
    def test_battle_ui_controller_has_dispatch_skill_action(self) -> None:
        """Valida que BattleUIController expõe dispatch_skill_action e handle_post_battle_modal_dismissal."""
        controller = BattleUIController(event_bus=self.event_bus)

        self.assertTrue(hasattr(controller, "dispatch_skill_action"))
        self.assertTrue(callable(getattr(controller, "dispatch_skill_action")))

        self.assertTrue(hasattr(controller, "handle_post_battle_modal_dismissal"))
        self.assertTrue(callable(getattr(controller, "handle_post_battle_modal_dismissal")))

        # Testa execução do dispatch_skill_action com mock
        with patch.object(controller, "execute_skill", return_value=(True, 0.02, True)):
            success = controller.dispatch_skill_action(slot_index=2)
            self.assertTrue(success)

        # Testa execução do handle_post_battle_modal_dismissal com mock
        with patch.object(controller, "dismiss_post_battle_modal", return_value=(True, 0.03)):
            m_success = controller.handle_post_battle_modal_dismissal()
            self.assertTrue(m_success)

    # -------------------------------------------------------------------------
    # TEST 2: WINDOW MANAGER IGNORES BLACKLISTED GEMINI TITLES
    # -------------------------------------------------------------------------
    def test_window_manager_ignores_blacklisted_gemini_titles(self) -> None:
        """Valida que o gerenciador de janelas rejeita abas como Gemini, ChatGPT, Claude e VSCode."""
        win_mgr = TargetWindowManager()

        # Cria lista de janelas simuladas contendo abas da lista negra
        mock_candidates = [
            TargetWindowInfo(
                hwnd=5001,
                pid=1234,
                process_name="chrome.exe",
                executable_path="C:\\Program Files\\Google\\Chrome\\chrome.exe",
                window_title="Gemini - Conversa com IA - Google Chrome",
                class_name="Chrome_WidgetWin_1",
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_visible=True,
                is_minimized=False,
                is_foreground=True,
                is_browser=True,
                browser_type="chrome",
                is_self_process=False,
                is_valid_candidate=True,
            ),
            TargetWindowInfo(
                hwnd=5002,
                pid=1235,
                process_name="chrome.exe",
                executable_path="C:\\Program Files\\Google\\Chrome\\chrome.exe",
                window_title="ChatGPT - Google Chrome",
                class_name="Chrome_WidgetWin_1",
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_visible=True,
                is_minimized=False,
                is_foreground=False,
                is_browser=True,
                browser_type="chrome",
                is_self_process=False,
                is_valid_candidate=True,
            ),
            TargetWindowInfo(
                hwnd=5003,
                pid=1236,
                process_name="code.exe",
                executable_path="C:\\VSCode\\code.exe",
                window_title="lumen-battle-simulator - Visual Studio Code",
                class_name="Chrome_WidgetWin_1",
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_visible=True,
                is_minimized=False,
                is_foreground=False,
                is_browser=False,
                browser_type="other",
                is_self_process=False,
                is_valid_candidate=False,
            ),
        ]

        with patch.object(win_mgr, "list_browser_candidates", return_value=mock_candidates):
            target = win_mgr.find_target_window()
            self.assertIsNone(target, "O Window Manager não deve selecionar abas do Gemini/ChatGPT/VSCode!")

    # -------------------------------------------------------------------------
    # TEST 3: WINDOW MANAGER MATCHES LUMENA TITLE
    # -------------------------------------------------------------------------
    def test_window_manager_matches_lumena_title(self) -> None:
        """Valida que o gerenciador de janelas prioriza e seleciona a janela com título Lumena.gg."""
        win_mgr = TargetWindowManager()

        mock_candidates = [
            TargetWindowInfo(
                hwnd=5001,
                pid=1234,
                process_name="chrome.exe",
                executable_path="C:\\Program Files\\Google\\Chrome\\chrome.exe",
                window_title="Gemini - Google Chrome",
                class_name="Chrome_WidgetWin_1",
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_visible=True,
                is_minimized=False,
                is_foreground=True,
                is_browser=True,
                browser_type="chrome",
                is_self_process=False,
                is_valid_candidate=True,
            ),
            TargetWindowInfo(
                hwnd=7777,
                pid=5678,
                process_name="chrome.exe",
                executable_path="C:\\Program Files\\Google\\Chrome\\chrome.exe",
                window_title="Lumena.gg - Play Online - Google Chrome",
                class_name="Chrome_WidgetWin_1",
                left=100,
                top=100,
                width=1280,
                height=720,
                is_visible=True,
                is_minimized=False,
                is_foreground=False,
                is_browser=True,
                browser_type="chrome",
                is_self_process=False,
                is_valid_candidate=True,
            ),
        ]

        with patch.object(win_mgr, "list_browser_candidates", return_value=mock_candidates):
            target = win_mgr.find_target_window()
            self.assertIsNotNone(target)
            self.assertEqual(target.hwnd, 7777)
            self.assertIn("Lumena.gg", target.window_title)


if __name__ == "__main__":
    unittest.main()
