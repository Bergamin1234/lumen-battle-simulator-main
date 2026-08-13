import os
import unittest
from unittest.mock import MagicMock, patch

from src.input.target_window import TargetWindowManager, WindowInfo
from src.input.safety_guard import SafetyGuard


class TestTargetWindowValidation(unittest.TestCase):
    """Testes determinísticos para a validação real de navegadores e rejeição estrita do LumenaBot."""

    def setUp(self):
        self.win_mgr = TargetWindowManager()
        self.safety = SafetyGuard()
        self.own_pid = os.getpid()

    def test_rejection_of_own_pid(self):
        """Valida que janelas pertencentes ao próprio processo do LumenaBot são sempre rejeitadas."""
        self.assertTrue(self.win_mgr.is_own_window(hwnd=1234, pid=self.own_pid, title="Random Title", process_name="python.exe"))
        self.assertTrue(self.win_mgr.is_own_window(hwnd=1234, pid=self.own_pid, title="LumenaBot", process_name="lumenabot.exe"))

    def test_rejection_of_lumenabot_titles(self):
        """Valida que qualquer janela contendo 'Lumena Bot Control Center' ou 'Autonomous Agent Suite' é rejeitada."""
        self.assertTrue(self.win_mgr.is_own_window(hwnd=5678, pid=9999, title="Lumena Bot Control Center — Autonomous Agent Suite", process_name="python.exe"))
        self.assertTrue(self.win_mgr.is_own_window(hwnd=5678, pid=9999, title="LumenaBot v3.0", process_name="lumenabot.exe"))

    def test_acceptance_of_chrome_window(self):
        """Valida que uma janela real do Chrome pertencente a outro PID é aceita como candidata válida."""
        self.assertFalse(self.win_mgr.is_own_window(hwnd=9999, pid=8888, title="Lumena.gg - Play Online - Google Chrome", process_name="chrome.exe"))

    def test_safety_guard_blocks_own_pid_and_title(self):
        """Valida que o SafetyGuard bloqueia o envio de entrada se o alvo for o próprio LumenaBot."""
        # Bloqueia por PID próprio
        self.assertFalse(self.safety.validate_can_dispatch(is_window_confirmed=True, target_pid=self.own_pid))

        # Bloqueia por título da própria aplicação
        self.assertFalse(self.safety.validate_can_dispatch(is_window_confirmed=True, target_title="Lumena Bot Control Center"))

        # Permite quando o alvo é um Chrome externo confirmado
        self.assertTrue(self.safety.validate_can_dispatch(is_window_confirmed=True, target_pid=7777, target_title="Lumena.gg - Google Chrome"))

    def test_find_target_window_prioritizes_chrome(self):
        """Simula lista de janelas e valida que o TargetWindowManager escolhe o Chrome com Lumena.gg."""
        mock_win_bot = MagicMock()
        mock_win_bot.title = "Lumena Bot Control Center — Autonomous Agent Suite"
        mock_win_bot._hWnd = 100
        mock_win_bot.left = 0
        mock_win_bot.top = 0
        mock_win_bot.width = 1200
        mock_win_bot.height = 800

        mock_win_chrome = MagicMock()
        mock_win_chrome.title = "Lumena.gg - WebGL Game - Google Chrome"
        mock_win_chrome._hWnd = 200
        mock_win_chrome.left = 100
        mock_win_chrome.top = 100
        mock_win_chrome.width = 1920
        mock_win_chrome.height = 1080

        with patch("pygetwindow.getAllWindows", return_value=[mock_win_bot, mock_win_chrome]):
            with patch.object(self.win_mgr, "get_process_name_by_pid", side_effect=lambda pid: "lumenabot.exe" if pid == 100 else "chrome.exe"):
                with patch.object(self.win_mgr, "is_own_window", side_effect=lambda h, p, t, pr: h == 100):
                    chosen = self.win_mgr.find_target_window()
                    self.assertIsNotNone(chosen)
                    self.assertEqual(chosen.hwnd, 200)
                    self.assertIn("lumena.gg", chosen.title.lower())


if __name__ == "__main__":
    unittest.main()
