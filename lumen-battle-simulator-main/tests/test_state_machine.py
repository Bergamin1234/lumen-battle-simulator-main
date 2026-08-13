import unittest
from src.automation.state_machine import BotState, BotStateMachine


class TestStateMachine(unittest.TestCase):
    def test_state_machine_initial_state(self):
        fsm = BotStateMachine(initial_state=BotState.STOPPED)
        self.assertEqual(fsm.current_state, BotState.STOPPED)

    def test_valid_transitions(self):
        fsm = BotStateMachine(initial_state=BotState.STOPPED)
        self.assertTrue(fsm.transition_to(BotState.STARTING, reason="Start"))
        self.assertEqual(fsm.current_state, BotState.STARTING)

        self.assertTrue(fsm.transition_to(BotState.CONNECTING, reason="Connecting"))
        self.assertEqual(fsm.current_state, BotState.CONNECTING)

        self.assertTrue(fsm.transition_to(BotState.READY, reason="Ready"))
        self.assertEqual(fsm.current_state, BotState.READY)

        self.assertTrue(fsm.transition_to(BotState.EXPLORING, reason="Exploring"))
        self.assertEqual(fsm.current_state, BotState.EXPLORING)

        self.assertTrue(fsm.transition_to(BotState.BATTLE, reason="Battle"))
        self.assertEqual(fsm.current_state, BotState.BATTLE)

        self.assertTrue(fsm.transition_to(BotState.VICTORY, reason="Victory"))
        self.assertEqual(fsm.current_state, BotState.VICTORY)

    def test_emergency_stop_from_any_state(self):
        fsm = BotStateMachine(initial_state=BotState.BATTLE)
        self.assertTrue(fsm.transition_to(BotState.EMERGENCY_STOP, reason="Emergency"))
        self.assertEqual(fsm.current_state, BotState.EMERGENCY_STOP)


if __name__ == "__main__":
    unittest.main()
