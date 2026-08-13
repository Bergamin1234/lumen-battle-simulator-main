import unittest
import tkinter as tk
from src.ui.modern_gui import ModernLumenaGUI
from src.core.event_bus import EventBus, EventType


class TestGUIIntegration(unittest.TestCase):
    """Testes determinísticos de ciclo de vida e sincronização da interface gráfica."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Esconde a janela para testes headless
        self.gui = ModernLumenaGUI(self.root)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_gui_initialization(self):
        self.assertIsNotNone(self.gui)
        self.assertEqual(len(self.gui.page_frames), 14)
        self.assertIn("dashboard", self.gui.page_frames)
        self.assertIn("validation", self.gui.page_frames)
        self.assertIn("about", self.gui.page_frames)

    def test_page_switching(self):
        self.gui.show_page("validation")
        self.assertEqual(self.gui.current_page, "validation")
        self.gui.show_page("battle")
        self.assertEqual(self.gui.current_page, "battle")

    def test_event_consumption_in_gui(self):
        bus = EventBus()
        bus.publish(EventType.STATE_CHANGED, data={"new_state": "EXPLORING"}, message="Test Exploring", category="SYSTEM")
        self.gui._ui_telemetry_tick()
        self.assertTrue(self.gui.gui_event_queue.empty())


if __name__ == "__main__":
    unittest.main()
