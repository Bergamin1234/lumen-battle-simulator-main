import unittest
from src.telemetry.telemetry_manager import TelemetryManager


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.telemetry = TelemetryManager()
        self.telemetry.reset()

    def test_telemetry_recording_and_snapshot(self):
        self.telemetry.record_tick()
        self.telemetry.record_action(success=True, latency=0.045, action_type="MOVE")
        self.telemetry.record_action(success=False, latency=0.100, action_type="CLICK")
        self.telemetry.record_input()
        self.telemetry.record_battle_result(is_victory=True)
        self.telemetry.record_recovery()
        self.telemetry.update_perception_confidence(0.95)
        self.telemetry.update_agent_status(
            state="BATTLE",
            objective="Lutando",
            decision="WaterPulse",
            reason="Super Effective",
        )
        self.telemetry.add_event("COMBAT", "Ataque executado")

        snap = self.telemetry.get_snapshot()
        self.assertEqual(snap["ticks"], 1)
        self.assertEqual(snap["actions_total"], 2)
        self.assertEqual(snap["actions_successful"], 1)
        self.assertEqual(snap["actions_failed"], 1)
        self.assertEqual(snap["battles_total"], 1)
        self.assertEqual(snap["victories_total"], 1)
        self.assertEqual(snap["recoveries_total"], 1)
        self.assertEqual(snap["inputs_total"], 1)
        self.assertEqual(snap["confidence"], 95.0)
        self.assertEqual(snap["state"], "BATTLE")
        self.assertEqual(snap["decision"], "WaterPulse")

        events = self.telemetry.get_recent_events()
        self.assertEqual(len(events), 1)
        self.assertIn("[COMBAT] Ataque executado", events[0])


if __name__ == "__main__":
    unittest.main()
