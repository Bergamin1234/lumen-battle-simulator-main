import unittest
from unittest.mock import patch, MagicMock
from src.input.input_controller import InputController


class TestInputController(unittest.TestCase):
    def test_input_controller_initialization(self):
        ctrl = InputController(target_window_titles=["CustomGameWindow"])
        self.assertIn("CustomGameWindow", ctrl.target_window_titles)
        self.assertFalse(ctrl._is_window_focused)

    @patch("pyautogui.click")
    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pygetwindow.getWindowsWithTitle")
    def test_input_controller_click_bounds_and_normalized(self, mock_windows, mock_size, mock_click):
        # Mock active window
        mock_win = MagicMock()
        mock_win.isActive = True
        mock_windows.return_value = [mock_win]

        ctrl = InputController()

        # Test absolute click within bounds
        res = ctrl.click(500, 400, jitter=False)
        self.assertTrue(res)
        mock_click.assert_called_with(500, 400)

        # Test normalized click
        res = ctrl.click_normalized(0.5, 0.5, frame_width=1920, frame_height=1080)
        self.assertTrue(res)

        # Test get_screen_center
        cx, cy = ctrl.get_screen_center()
        self.assertEqual(cx, 960)
        self.assertEqual(cy, 540)

    @patch("pyautogui.keyDown")
    @patch("pyautogui.keyUp")
    @patch("pygetwindow.getWindowsWithTitle")
    def test_input_controller_press_and_hold_keys(self, mock_windows, mock_keyup, mock_keydown):
        mock_win = MagicMock()
        mock_win.isActive = True
        mock_windows.return_value = [mock_win]

        ctrl = InputController()

        # Test press_key
        res = ctrl.press_key("w", duration=0.05, jitter=False)
        self.assertTrue(res)
        mock_keydown.assert_called_with("w")
        mock_keyup.assert_called_with("w")

        # Test hold_keys (diagonal movement)
        res = ctrl.hold_keys(["w", "a"], duration=0.05)
        self.assertTrue(res)
        self.assertGreaterEqual(mock_keydown.call_count, 2)
        self.assertGreaterEqual(mock_keyup.call_count, 2)


if __name__ == "__main__":
    unittest.main()

