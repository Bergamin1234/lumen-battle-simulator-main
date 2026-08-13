import unittest
import numpy as np
from unittest.mock import MagicMock, patch

from src.automation.bot_engine import LumenaBotEngine
from src.automation.state_machine import BotState
from src.input.input_controller import InputController
from src.models import StateSnapshot, BattleTelemetry, AgentState
from src.core.event_bus import EventBus, EventType


class TestClosedLoopAndRecovery(unittest.TestCase):
    """Testes unitários determinísticos para o loop fechado, anti-stuck e recuperação autônoma."""

    def setUp(self):
        self.engine = LumenaBotEngine()
        self.bus = EventBus()
        self.bus.clear()

    def test_visual_delta_calculation(self):
        frame_a = np.zeros((100, 100, 3), dtype=np.uint8)
        frame_b = np.full((100, 100, 3), 255, dtype=np.uint8)

        confirmed, delta = self.engine.input_ctrl.compute_visual_delta(frame_a, frame_b)
        self.assertTrue(confirmed)
        self.assertAlmostEqual(delta, 1.0, places=2)

        confirmed_same, delta_same = self.engine.input_ctrl.compute_visual_delta(frame_a, frame_a)
        self.assertFalse(confirmed_same)
        self.assertAlmostEqual(delta_same, 0.0, places=2)

    def test_anti_stuck_routine_trigger(self):
        with patch.object(self.engine.input_ctrl, "press_key", return_value=True) as mock_press:
            self.engine._consecutive_no_movement = 5
            self.engine._handle_anti_stuck()
            self.assertEqual(self.engine._consecutive_no_movement, 0)
            self.assertGreaterEqual(mock_press.call_count, 3)

    def test_emergency_stop_releases_all_and_sets_state(self):
        with patch.object(self.engine.input_ctrl, "emergency_stop") as mock_emg:
            self.engine.emergency_stop()
            self.assertEqual(self.engine.current_state, BotState.EMERGENCY_STOP)
            mock_emg.assert_called_once()

    def test_anti_stuck_finite_limit_and_safe_stop(self):
        # Valida que após 3 tentativas de recuperação consecutivas sem sucesso, o bot transiciona para ERROR/SAFE STOP
        with patch.object(self.engine.input_ctrl, "press_key", return_value=True):
            self.engine._recovery_attempts = 3
            self.engine._handle_anti_stuck()
            self.assertEqual(self.engine.current_state, BotState.ERROR)


if __name__ == "__main__":
    unittest.main()
