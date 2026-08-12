import pytest
from unittest.mock import patch, MagicMock
from src.input.input_controller import InputController


def test_input_controller_initialization():
    ctrl = InputController(target_window_titles=["CustomGameWindow"])
    assert "CustomGameWindow" in ctrl.target_window_titles
    assert ctrl._is_window_focused is False


@patch("pyautogui.click")
@patch("pyautogui.size", return_value=(1920, 1080))
@patch("pygetwindow.getWindowsWithTitle")
def test_input_controller_click_bounds_and_normalized(mock_windows, mock_size, mock_click):
    # Mock active window
    mock_win = MagicMock()
    mock_win.isActive = True
    mock_windows.return_value = [mock_win]

    ctrl = InputController()

    # Test absolute click within bounds
    res = ctrl.click(500, 400, jitter=False)
    assert res is True
    mock_click.assert_called_with(500, 400)

    # Test normalized click
    res = ctrl.click_normalized(0.5, 0.5, frame_width=1920, frame_height=1080)
    assert res is True

    # Test get_screen_center
    cx, cy = ctrl.get_screen_center()
    assert cx == 960
    assert cy == 540


@patch("pyautogui.keyDown")
@patch("pyautogui.keyUp")
@patch("pygetwindow.getWindowsWithTitle")
def test_input_controller_press_and_hold_keys(mock_windows, mock_keyup, mock_keydown):
    mock_win = MagicMock()
    mock_win.isActive = True
    mock_windows.return_value = [mock_win]

    ctrl = InputController()

    # Test press_key
    res = ctrl.press_key("w", duration=0.05, jitter=False)
    assert res is True
    mock_keydown.assert_called_with("w")
    mock_keyup.assert_called_with("w")

    # Test hold_keys (diagonal movement)
    res = ctrl.hold_keys(["w", "a"], duration=0.05)
    assert res is True
    assert mock_keydown.call_count >= 3
    assert mock_keyup.call_count >= 3
