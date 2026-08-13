import unittest
from unittest.mock import MagicMock
from src.input.safety_guard import SafetyGuard


class TestSafetyGuard(unittest.TestCase):
    def test_safety_guard_emergency_stop(self):
        guard = SafetyGuard()
        self.assertFalse(guard.is_emergency_stopped)

        # Mock backend
        mock_backend = MagicMock()
        guard.track_key_down("w")
        guard.track_key_down("a")

        guard.trigger_emergency_stop(backend=mock_backend)
        self.assertTrue(guard.is_emergency_stopped)
        self.assertFalse(guard.validate_can_dispatch(is_window_confirmed=True))
        mock_backend.release_all.assert_called_once()

        # Reset
        guard.reset_emergency_stop()
        self.assertFalse(guard.is_emergency_stopped)
        self.assertTrue(guard.validate_can_dispatch(is_window_confirmed=True))

    def test_blocks_dispatch_when_window_not_confirmed(self):
        guard = SafetyGuard()
        self.assertFalse(guard.validate_can_dispatch(is_window_confirmed=False))


if __name__ == "__main__":
    unittest.main()
