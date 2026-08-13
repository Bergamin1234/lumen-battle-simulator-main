import unittest
import os
import shutil
from src.automation.navigation import RouteManager


class TestRouteManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/temp_routes"
        os.makedirs(self.test_dir, exist_ok=True)
        self.rm = RouteManager(routes_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_load_and_reverse_route(self):
        steps = [
            {"key": "w", "duration": 0.45},
            {"key": "d", "duration": 0.30},
        ]
        self.assertTrue(self.rm.save_route("test_route", steps))
        self.assertIn("test_route", self.rm.list_routes())

        loaded = self.rm.load_route("test_route")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["key"], "w")

        reversed_steps = self.rm.reverse_route(loaded)
        self.assertEqual(len(reversed_steps), 2)
        self.assertEqual(reversed_steps[0]["key"], "a")  # Inverso de d
        self.assertEqual(reversed_steps[1]["key"], "s")  # Inverso de w

    def test_recording_lifecycle(self):
        self.rm.start_recording()
        self.assertTrue(self.rm.is_recording)
        self.rm.add_recording_step("w", 0.5)
        self.rm.add_recording_step("s", 0.2)

        steps = self.rm.stop_recording("recorded_test")
        self.assertEqual(len(steps), 2)
        self.assertFalse(self.rm.is_recording)


if __name__ == "__main__":
    unittest.main()
