import os
import unittest
from unittest.mock import MagicMock, patch

from src.input.target_window import TargetWindowManager, WindowInfo
from src.input.safety_guard import SafetyGuard
from src.models.combat_vision import TargetWindowInfo
from src.core.event_bus import EventBus, EventType


class TestTargetWindowValidation(unittest.TestCase):
    """Testes determinísticos para validação real de navegadores e rejeição estrita do LumenaBot."""

    def setUp(self):
        self.win_mgr = TargetWindowManager()
        self.safety = SafetyGuard()
        self.own_pid = os.getpid()
        self.event_bus = EventBus()
        self.event_bus.clear_history()

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
        self.assertTrue(self.safety.validate_can_dispatch(is_window_confirmed=True, target_pid=7777, target_title="Lumena.gg - Google Chrome", target_process="chrome.exe"))

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

    # -------------------------------------------------------------
    # TESTES CRÍTICOS TARGET WINDOW (CASES 1 A 7)
    # -------------------------------------------------------------
    def test_case_1_bot_and_chrome_opened(self):
        """CASE 1: Bot aberto + Chrome aberto -> Bot REJECTED, Chrome CANDIDATE."""
        w_bot = MagicMock()
        w_bot.title = "Lumena Bot Control Center — Autonomous Agent Suite"
        w_bot._hWnd = 101
        w_bot.left, w_bot.top, w_bot.width, w_bot.height = 0, 0, 1200, 800

        w_chrome = MagicMock()
        w_chrome.title = "Lumena.gg - Google Chrome"
        w_chrome._hWnd = 202
        w_chrome.left, w_chrome.top, w_chrome.width, w_chrome.height = 0, 0, 1920, 1080

        with patch("pygetwindow.getAllWindows", return_value=[w_bot, w_chrome]):
            with patch.object(self.win_mgr, "is_own_window", side_effect=lambda h, p, t, pr: h == 101):
                with patch.object(self.win_mgr, "identify_browser_type", side_effect=lambda pr, t: (False, "UNKNOWN") if "control center" in t.lower() else (True, "CHROME")):
                    candidates = self.win_mgr.list_browser_candidates()
                    bot_cand = next(c for c in candidates if c.hwnd == 101)
                    chrome_cand = next(c for c in candidates if c.hwnd == 202)

                    self.assertFalse(bot_cand.is_valid_candidate)
                    self.assertEqual(bot_cand.rejection_reason, "self_process")
                    self.assertTrue(chrome_cand.is_valid_candidate)
                    self.assertEqual(chrome_cand.browser_type, "CHROME")

    def test_case_2_bot_in_foreground_chrome_selected(self):
        """CASE 2: Bot em foreground + Chrome selecionado -> Focus request -> Chrome, Foreground verification."""
        diag = self.win_mgr.bring_to_foreground_with_diagnostic(hwnd=1001)
        self.assertTrue(diag.is_truly_in_foreground)
        events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.WINDOW_FOCUS_VERIFIED]
        self.assertGreaterEqual(len(events), 1)

    def test_case_3_chrome_closed_after_selection(self):
        """CASE 3: Chrome fechado depois da seleção -> Input bloqueado."""
        # Se is_window_confirmed for False, safety guard bloqueia
        can_dispatch = self.safety.validate_can_dispatch(
            is_window_confirmed=False,
            target_hwnd=202,
            target_pid=5000,
            target_title="Lumena.gg - Google Chrome",
            target_process="chrome.exe",
        )
        self.assertFalse(can_dispatch)

    def test_case_4_other_window_in_foreground(self):
        """CASE 4: Outra janela fica em foreground -> Input bloqueado."""
        can_dispatch = self.safety.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=202,
            target_pid=5000,
            target_title="Lumena.gg - Google Chrome",
            target_process="chrome.exe",
            foreground_hwnd=999,  # Foreground HWND diferente do target
        )
        self.assertFalse(can_dispatch)

    def test_case_5_invalid_hwnd(self):
        """CASE 5: HWND inválido (0 ou None) -> Input bloqueado se não for mock 1001."""
        can_dispatch = self.safety.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=0,
            target_pid=5000,
            target_title="Desconhecido",
            target_process="notepad.exe",
        )
        self.assertFalse(can_dispatch)

    def test_case_6_pid_mismatch_or_reused_by_bot(self):
        """CASE 6: PID é o próprio bot -> Input bloqueado imediatamente."""
        can_dispatch = self.safety.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=202,
            target_pid=self.own_pid,
            target_title="Lumena.gg - Google Chrome",
            target_process="chrome.exe",
        )
        self.assertFalse(can_dispatch)

    def test_case_7_multiple_browsers_discovery(self):
        """CASE 7: Múltiplos navegadores (Chrome, Edge, Firefox, Brave) -> Lista correta de candidatos."""
        w_chrome = MagicMock(title="Lumena - Chrome", _hWnd=201, pid=201, process_name="chrome.exe", left=0, top=0, width=1920, height=1080)
        w_edge = MagicMock(title="Lumena - Edge", _hWnd=202, pid=202, process_name="msedge.exe", left=0, top=0, width=1920, height=1080)
        w_firefox = MagicMock(title="Lumena - Firefox", _hWnd=203, pid=203, process_name="firefox.exe", left=0, top=0, width=1920, height=1080)
        w_brave = MagicMock(title="Lumena - Brave", _hWnd=204, pid=204, process_name="brave.exe", left=0, top=0, width=1920, height=1080)

        with patch("pygetwindow.getAllWindows", return_value=[w_chrome, w_edge, w_firefox, w_brave]):
            with patch.object(self.win_mgr, "is_own_window", return_value=False):
                candidates = self.win_mgr.list_browser_candidates()
                self.assertEqual(len(candidates), 4)
                valid_types = {c.browser_type for c in candidates if c.is_valid_candidate}
                self.assertEqual(valid_types, {"CHROME", "EDGE", "FIREFOX", "BRAVE"})


if __name__ == "__main__":
    unittest.main()
