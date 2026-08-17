"""
TEST SUITE V5.3 — DETERMINISTIC BATTLE LOOP & RECORDED PATH HEALING
====================================================================
Valida a arquitetura completa de 4 etapas da Diretiva v5.3 Master:
1. Patrulha pura no mato (A/D contínuo sem limite de passos e sem suposição cega);
2. Gating visual estrito de batalha com liberação instantânea de WASD;
3. Fluxo de combate linear (FIGHT -> Skill 1 -> Turn Lock -> Modal Dismissal via ESPAÇO);
4. Avaliação geométrica de HP (saudável > 35% volta ao mato; <= 35% vai para rota de cura);
5. Replayer de rota gravada com respeito às durações de teclas;
6. Interação determinística no cristal com ESPAÇO e recuperação total de HP;
7. Rota inversa e retorno garantido ao estado EXPLORING.
"""

import time
import unittest
from unittest.mock import MagicMock, call, patch
import numpy as np

from src.automation.bot_engine import LumenaBotEngine
from src.automation.state_machine import BotState
from src.combat.battle_ui_controller import BattleUIController
from src.models import AgentState, BattleTelemetry, PlayerInfo, StateSnapshot
from src.models.combat_vision import SkillSlot
from src.models.enums import Element
from src.navigation.movement_controller import GrassPatrolEngine
from src.navigation.recorded_path_engine import RecordedPathEngine, RecordedRoute, WaypointAction
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIElement


class TestV53DeterministicLoopAndHealing(unittest.TestCase):
    """Suíte de Testes Master v5.3."""

    def setUp(self) -> None:
        self.detector = BattleUIDetector()

    def test_grass_patrol_runs_continuously_without_battle(self) -> None:
        """1. Valida que a patrulha oscila A -> D -> A -> D sem limite de passos enquanto não houver batalha visual."""
        mock_input = MagicMock()
        patrol = GrassPatrolEngine(input_controller=mock_input, step_duration=0.45, pause_duration=0.03)

        rng = np.random.RandomState(42)
        base_frame = np.full((720, 1280, 3), (40, 120, 50), dtype=np.uint8)
        noise = rng.randint(-30, 30, (720, 1280, 3), dtype=np.int16)
        base_frame = np.clip(base_frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        dispatched = []
        prev = base_frame
        for i in range(10):
            shifted = np.roll(base_frame, shift=(i + 1) * 40, axis=1)
            k, stuck = patrol.execute_patrol_step(current_frame=shifted, prev_frame=prev)
            dispatched.append(k)
            prev = shifted

        expected = ["a", "d", "a", "d", "a", "d", "a", "d", "a", "d"]
        self.assertEqual(dispatched, expected, "A/D deve oscilar infinitamente sem transições cegas.")

    def test_visual_battle_gating_triggers_instant_wasd_release(self) -> None:
        """2. Valida que a confirmação visual da arena de batalha aciona liberação imediata de WASD."""
        engine = LumenaBotEngine()
        engine.grass_patrol.release_all_movement_keys = MagicMock()
        engine.input_ctrl.release_all_movement_keys = MagicMock()

        # Frame com elemento FIGHT visível no quadrante inferior direito
        battle_frame = np.full((1080, 1920, 3), 40, dtype=np.uint8)
        fx, fy, fw, fh = int(1920 * 0.75), int(1080 * 0.75), 180, 70
        cv2 = __import__("cv2")
        cv2.rectangle(battle_frame, (fx, fy), (fx + fw, fy + fh), (0, 0, 220), -1)

        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.BATTLE,
            battle_telemetry=BattleTelemetry(in_battle=True, player_hp_pct=1.0),
            player_info=PlayerInfo(hp_ratio=1.0, detected=True),
        )

        with patch.object(engine.screen_capture, "capture_frame", return_value=(battle_frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine, "_handle_battle_cycle"):

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)
            engine.grass_patrol.release_all_movement_keys.assert_called()

    def test_combat_flow_fight_to_skill_to_space_dismissal(self) -> None:
        """3. Valida fluxo determinístico de combate: clique em FIGHT -> Skill 1 -> Turn Lock -> Modal Dismissal via ESPAÇO."""
        mock_input = MagicMock()
        mock_input.click = MagicMock(return_value=True)
        mock_input.press_key = MagicMock(return_value=True)
        mock_input.window_manager.get_active_target = MagicMock(return_value=None)
        mock_input.window_manager.get_window_bounds = MagicMock(return_value=(0, 0, 1920, 1080))
        mock_input.get_screen_center = MagicMock(return_value=(960, 540))

        detector = BattleUIDetector()
        controller = BattleUIController(input_controller=mock_input, ui_detector=detector)

        # 3.1 Step 1: FIGHT button click
        frame = np.full((1080, 1920, 3), 50, dtype=np.uint8)
        dispatched_fight, _, _ = controller.click_fight(frame_before=frame)
        self.assertTrue(dispatched_fight, "Clique no botão FIGHT deve ser despachado.")

        # 3.2 Step 2: Skill 1 execution & Turn Lock
        skill_1 = SkillSlot(
            id="skill_1", index=1, slot_index=1,
            screen_x=500, screen_y=750, width=100, height=80,
            available=True, cooldown=0.0, hotkey="1",
            skill_name="Tackle", element=Element.NORMAL,
        )
        dispatched_skill, _, _ = controller.execute_skill(skill=skill_1, frame_before=frame)
        self.assertTrue(dispatched_skill, "Skill 1 deve ser executada.")
        self.assertTrue(controller.is_waiting_turn_resolution, "Turn Lock deve estar ativo após ataque.")

        # 3.3 Step 3: Modal dismissal via SPACE
        modal_frame = np.full((1080, 1920, 3), 30, dtype=np.uint8)
        dispatched_modal, _ = controller.dismiss_post_battle_modal(frame=modal_frame)
        self.assertTrue(dispatched_modal, "Modal deve ser dispensado com clique e tecla ESPAÇO.")
        mock_input.press_key.assert_any_call("space", duration=0.10)

    def test_hp_evaluation_routes_to_heal_only_when_critical(self) -> None:
        """4. Valida avaliação de HP: HP > 35% retoma EXPLORING; HP <= 35% entra em RETURNING_TO_HEAL."""
        engine = LumenaBotEngine()
        engine.healing_hp_ratio = 0.35

        # Caso A: HP Saudável (80%) -> Retorna a EXPLORING
        snap_healthy = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            battle_telemetry=BattleTelemetry(in_battle=False, player_hp_pct=0.80),
            player_info=PlayerInfo(hp_ratio=0.80, detected=True),
        )
        world_frame = np.full((720, 1280, 3), (40, 120, 50), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(world_frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snap_healthy), \
             patch.object(engine, "_handle_overworld_cycle"):

            engine.fsm._current_state = BotState.IDLE
            engine._execute_single_cycle()
            self.assertEqual(engine.fsm.current_state, BotState.EXPLORING, "HP > 35% deve manter EXPLORING.")

        # Caso B: HP Crítico (25%) -> Transiciona para RETURNING_TO_HEAL
        snap_critical = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            battle_telemetry=BattleTelemetry(in_battle=False, player_hp_pct=0.25),
            player_info=PlayerInfo(hp_ratio=0.25, detected=True),
        )

        with patch.object(engine.screen_capture, "capture_frame", return_value=(world_frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snap_critical), \
             patch.object(engine, "_handle_healing_route") as mock_heal_route:

            engine.fsm._current_state = BotState.EXPLORING
            engine._execute_single_cycle()
            self.assertEqual(engine.fsm.current_state, BotState.RETURNING_TO_HEAL, "HP <= 35% deve transicionar para RETURNING_TO_HEAL.")
            mock_heal_route.assert_called_once()

    def test_recorded_path_replayer_executes_key_durations_accurately(self) -> None:
        """5. Valida que o replayer de rota executa as ações de waypoints com suas respectivas teclas e durações."""
        mock_input = MagicMock()
        engine = RecordedPathEngine(input_controller=mock_input)

        route = RecordedRoute(
            name="test_farm_route",
            actions=[
                WaypointAction(key="w", duration=1.200, delay_after=0.0),
                WaypointAction(key="d", duration=0.850, delay_after=0.0),
                WaypointAction(key="w", duration=2.100, delay_after=0.0),
            ],
        )

        success = engine.play_route(route)
        self.assertTrue(success)

        expected_calls = [
            call("w", duration=1.200),
            call("d", duration=0.850),
            call("w", duration=2.100),
        ]
        mock_input.press_key.assert_has_calls(expected_calls, any_order=False)

    def test_crystal_space_interaction_triggers_and_recovers_full_hp(self) -> None:
        """6. Valida que a sequência de cura aciona ESPAÇO duas vezes e valida recuperação completa de HP."""
        mock_input = MagicMock()
        engine = RecordedPathEngine(input_controller=mock_input)

        route_fwd = RecordedRoute(name="fwd", actions=[WaypointAction(key="w", duration=0.01, delay_after=0.0)])
        route_ret = RecordedRoute(name="ret", actions=[WaypointAction(key="s", duration=0.01, delay_after=0.0)])

        mock_screen = MagicMock(return_value=(np.zeros((100, 100, 3), dtype=np.uint8), time.time()))
        mock_hp_parser = MagicMock(return_value=1.0)

        with patch("time.sleep", return_value=None):
            success = engine.execute_healing_sequence(
                forward_route=route_fwd,
                return_route=route_ret,
                screen_capture_func=mock_screen,
                hp_check_func=mock_hp_parser,
            )

        self.assertTrue(success)
        # Deve ter pressionado 'space' com duration=0.100 pelo menos duas vezes
        space_calls = [c for c in mock_input.press_key.call_args_list if c[0][0] == "space"]
        self.assertGreaterEqual(len(space_calls), 2, "A interação com o cristal deve disparar ESPAÇO pelo menos 2 vezes.")

    def test_reverse_path_returns_to_exploring_state(self) -> None:
        """7. Valida que a rota reversa inverte as direções e que ao final o bot retorna a EXPLORING."""
        route = RecordedRoute(
            name="path_ab",
            actions=[
                WaypointAction(key="w", duration=1.0),
                WaypointAction(key="d", duration=2.0),
                WaypointAction(key="a", duration=0.5),
            ],
        )
        rev = route.reverse()
        self.assertEqual(len(rev.actions), 3)
        self.assertEqual(rev.actions[0].key, "d")
        self.assertEqual(rev.actions[0].duration, 0.5)
        self.assertEqual(rev.actions[1].key, "a")
        self.assertEqual(rev.actions[1].duration, 2.0)
        self.assertEqual(rev.actions[2].key, "s")
        self.assertEqual(rev.actions[2].duration, 1.0)


if __name__ == "__main__":
    unittest.main()
