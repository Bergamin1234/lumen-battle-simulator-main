"""
TEST SUITE V5.2 — VISUAL BATTLE GATING & MOVEMENT CONTINUITY
============================================================
Valida que:
1. O bot oscila A/D continuamente no estado EXPLORING sem transicionar por tempo ou fim de passo;
2. A transição para BATTLE exige estritamente elementos visuais reais (FIGHT, barras de HP ou arena);
3. O fim de combate interrompe o loop de batalha e retoma a oscilação A/D no mato.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from src.automation.bot_engine import LumenaBotEngine
from src.automation.state_machine import BotState
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.navigation.movement_controller import GrassPatrolEngine
from src.models import StateSnapshot, AgentState, BattleTelemetry, PlayerInfo


class TestV52VisualBattleGating(unittest.TestCase):
    """Testes unitários para comprovação de Zero Guesswork e Visual Gating v5.2."""

    def setUp(self) -> None:
        self.detector = BattleUIDetector()

    def test_battle_transition_requires_visual_elements_not_timer(self) -> None:
        """Comprova que um frame sem elementos visuais de combate retorna False (Zero Guesswork)."""
        # Frame de grama / overworld comum (verde, sem botões de HUD)
        overworld_frame = np.full((1080, 1920, 3), (40, 120, 50), dtype=np.uint8)

        # Sem elementos visuais -> deve retornar False
        is_confirmed = self.detector.is_battle_visually_confirmed(overworld_frame)
        self.assertFalse(is_confirmed, "Overworld comum não deve ser confirmado como batalha.")

        # Frame com botão FIGHT desenhado no quadrante de combate
        battle_frame = overworld_frame.copy()
        fx, fy, fw, fh = int(1920 * 0.75), int(1080 * 0.75), 180, 70
        cv2 = __import__("cv2")
        cv2.rectangle(battle_frame, (fx, fy), (fx + fw, fy + fh), (0, 0, 220), -1)  # Vermelho de botão FIGHT

        is_confirmed_battle = self.detector.is_battle_visually_confirmed(battle_frame)
        self.assertTrue(is_confirmed_battle, "Frame com elemento FIGHT deve ser confirmado como batalha.")

    def test_movement_loop_continues_infinitely_until_visual_battle_detected(self) -> None:
        """Comprova que múltiplos ciclos de patrulha no mato mantêm o estado EXPLORING e oscilam A -> D -> A -> D."""
        mock_input = MagicMock()
        patrol = GrassPatrolEngine(input_controller=mock_input)

        # Frame de grama com textura para cálculo de fluxo óptico
        rng = np.random.RandomState(42)
        overworld_frame = np.full((1080, 1920, 3), (40, 120, 50), dtype=np.uint8)
        overworld_frame[::4, ::4] = rng.randint(40, 160, (270, 480, 3), dtype=np.uint8)

        dispatched_keys = []
        for i in range(6):
            # Cria frame com deslocamento real de textura
            shifted_frame = np.roll(overworld_frame, shift=(i + 1) * 30, axis=1)
            k, _ = patrol.execute_patrol_step(current_frame=shifted_frame, prev_frame=overworld_frame)
            dispatched_keys.append(k)

        # Deve alternar estritamente A e D
        expected = ["a", "d", "a", "d", "a", "d"]
        self.assertEqual(dispatched_keys, expected, "Patrulha deve oscilar continuamente A/D sem transições espúrias.")

    def test_battle_end_resumes_grass_patrol(self) -> None:
        """Comprova que ao sumir a interface de combate, o bot retoma EXPLORING e solta teclas."""
        engine = LumenaBotEngine()
        engine.grass_patrol.release_all_movement_keys = MagicMock()
        engine.battle_ui_detector.is_battle_visually_confirmed = MagicMock(return_value=False)
        engine.battle_ui_controller.is_battle_finished = MagicMock(return_value=True)

        engine.fsm.transition_to(BotState.BATTLE, reason="Test BATTLE State")

        # Snapshot de transição de fim de combate
        snap = StateSnapshot(
            timestamp=1000.0,
            screen_state=AgentState.EXPLORING,
            ui_elements={},
            battle_telemetry=BattleTelemetry(in_battle=False),
            player_info=PlayerInfo(hp_ratio=1.0, detected=True),
        )
        overworld_frame = np.full((1080, 1920, 3), (40, 120, 50), dtype=np.uint8)

        engine._handle_battle_cycle(snapshot=snap, frame_before=overworld_frame)

        self.assertEqual(engine.fsm.current_state, BotState.EXPLORING, "Deve retornar imediatamente a EXPLORING.")
        engine.grass_patrol.release_all_movement_keys.assert_called()


if __name__ == "__main__":
    unittest.main()
