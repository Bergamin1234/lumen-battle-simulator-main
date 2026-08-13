import unittest
from src.core.event_bus import EventBus, EventType, BotEvent


class TestEventBus(unittest.TestCase):
    """Testes unitários determinísticos para o Barramento de Eventos (EventBus)."""

    def setUp(self):
        self.bus = EventBus()
        self.bus.clear()

    def test_singleton_instance(self):
        bus2 = EventBus()
        self.assertIs(self.bus, bus2)

    def test_publish_and_subscribe(self):
        received = []

        def on_event(ev: BotEvent):
            received.append(ev)

        self.bus.subscribe(EventType.BOT_STARTED, on_event)
        self.bus.publish(EventType.BOT_STARTED, data={"mode": "AUTONOMOUS"}, message="Bot iniciado")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, EventType.BOT_STARTED)
        self.assertEqual(received[0].data.get("mode"), "AUTONOMOUS")

    def test_subscriber_queue(self):
        q = self.bus.get_or_create_queue("test_sub")
        self.bus.publish(EventType.STATE_CHANGED, data={"new_state": "BATTLE"}, message="Batalha iniciada")

        self.assertFalse(q.empty())
        ev = q.get_nowait()
        self.assertEqual(ev.event_type, EventType.STATE_CHANGED)
        self.assertEqual(ev.data.get("new_state"), "BATTLE")

    def test_recent_events_buffer(self):
        self.bus.publish(EventType.INPUT_SENT, message="Input 1", category="INPUT")
        self.bus.publish(EventType.INPUT_SENT, message="Input 2", category="INPUT")
        self.bus.publish(EventType.BATTLE_STARTED, message="Batalha", category="COMBAT")

        recent = self.bus.get_recent_events(max_count=10)
        self.assertEqual(len(recent), 3)

        combat_only = self.bus.get_recent_events(max_count=10, category="COMBAT")
        self.assertEqual(len(combat_only), 1)
        self.assertEqual(combat_only[0].category, "COMBAT")


if __name__ == "__main__":
    unittest.main()
