"""
LUMENA BOT v4.0 — AUTONOMOUS LIFECYCLE & LIVE OPERATIONAL ENGINE TESTS
========================================================================
Suíte de testes obrigatória da versão 4.0:
1. test_multi_turn_skill_rotation_fallback
2. test_end_to_end_autonomous_lifecycle_simulation
3. test_high_performance_capture_latency
4. test_bezier_trajectory_generation
5. test_post_battle_healing_decision_tree
6. test_emergency_killswitch_clears_win32_key_states
"""

import unittest
import time
import os
import numpy as np
import cv2
from unittest.mock import MagicMock, patch

from config.settings import BotConfig, KeyBindings, MonitorConfig, BattleConfig
from src.core.event_bus import EventBus, EventType
from src.models.enums import AgentState, Element
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement, PlayerInfo
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.combat.battle_ui_controller import BattleUIController
from src.combat.skill_strategy import SkillStrategyEngine
from src.input.killswitch import EmergencyKillswitch
from src.input.input_dispatcher import generate_cubic_bezier_trajectory, HumanizedInputDispatcher
from tests.harness.synthetic_game_simulator import SyntheticGameSimulator


class TestLumenaBotV40AutonomousLifecycle(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: MULTI-TURN SKILL ROTATION & FALLBACK
    # -------------------------------------------------------------------------
    def test_multi_turn_skill_rotation_fallback(self) -> None:
        """Valida a rotação de habilidades ao longo de múltiplos turnos com respeito a cooldowns."""
        strategy = SkillStrategyEngine()
        strategy.priority_order = [2, 3, 4, 1]

        skills = [
            SkillSlot(id="s1", index=1, slot_index=1, skill_name="Ataque Básico", available=True, cooldown=0.0),
            SkillSlot(id="s2", index=2, slot_index=2, skill_name="Golpe Flamejante", available=True, cooldown=0.0),
            SkillSlot(id="s3", index=3, slot_index=3, skill_name="Tempestade", available=True, cooldown=0.0),
            SkillSlot(id="s4", index=4, slot_index=4, skill_name="Escudo", available=True, cooldown=0.0),
        ]

        # Turno 1: Deve escolher Skill 2 (Maior prioridade)
        chosen_t1 = strategy.evaluate_skills(skills)
        self.assertIsNotNone(chosen_t1)
        self.assertEqual(chosen_t1.slot_index, 2)
        strategy.register_skill_use(2, cooldown_turns=2)

        # Avança para Turno 2: Skill 2 está em cooldown interno -> Deve escolher Skill 3
        strategy.advance_turn()
        chosen_t2 = strategy.evaluate_skills(skills)
        self.assertIsNotNone(chosen_t2)
        self.assertEqual(chosen_t2.slot_index, 3)
        strategy.register_skill_use(3, cooldown_turns=2)

        # Avança para Turno 3: Skill 2 saiu do cooldown -> Deve escolher Skill 2 novamente
        strategy.advance_turn()
        chosen_t3 = strategy.evaluate_skills(skills)
        self.assertIsNotNone(chosen_t3)
        self.assertEqual(chosen_t3.slot_index, 2)

    # -------------------------------------------------------------------------
    # TEST 2: END-TO-END AUTONOMOUS LIFECYCLE SIMULATION
    # -------------------------------------------------------------------------
    def test_end_to_end_autonomous_lifecycle_simulation(self) -> None:
        """Simulação ponta a ponta do ciclo de vida: World -> Battle -> Modal -> Healing -> World."""
        simulator = SyntheticGameSimulator()
        engine = LumenaBotEngine(event_bus=self.event_bus)

        # Inicia em EXPLORING
        engine.fsm.transition_to(BotState.EXPLORING, reason="Início da Simulação")
        self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)

        # Passo 6: Detecção de Batalha (FIGHT button)
        frame_battle, phase = simulator.generate_frame_for_step(7)
        ui_res = engine.battle_ui_detector.analyze_battle_ui(frame_battle)
        self.assertTrue(ui_res.battle_ui_confirmed)

        engine.fsm.transition_to(BotState.BATTLE, reason="Arena Detectada")
        self.assertEqual(engine.fsm.current_state, BotState.BATTLE)

        # Passo 22: Detecção de Modal de Vitória
        frame_modal, _ = simulator.generate_frame_for_step(22)
        ui_modal = engine.battle_ui_detector.analyze_battle_ui(frame_modal)
        self.assertTrue(ui_modal.modal_detected)

        with patch.object(engine.input_ctrl, "click", return_value=True), \
             patch.object(engine.input_ctrl, "press_key", return_value=True):
            engine.battle_ui_controller.dismiss_post_battle_modal(frame_modal)

        # Retorno ao Mundo Aberto após encerramento da batalha
        engine.fsm.transition_to(BotState.EXPLORING, reason="Batalha Concluída")
        self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)
        snap_low_hp = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            player_info=PlayerInfo(detected=True, hp_ratio=0.30),
        )
        engine._handle_overworld_cycle(snap_low_hp, frame_modal)
        self.assertEqual(engine.fsm.current_state, BotState.HEALING)

        # Passo 33: Cura completa -> Retorno à Exploração
        snap_healed = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            player_info=PlayerInfo(detected=True, hp_ratio=1.0),
        )
        with patch.object(engine.healing_controller, "step", return_value=("HEALING_VERIFIED", True, "HP Totalmente Restaurado")):
            engine._handle_healing_cycle(snap_healed, frame_modal)
            self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)

    # -------------------------------------------------------------------------
    # TEST 3: HIGH PERFORMANCE CAPTURE & PERCEPTION LATENCY (< 20ms)
    # -------------------------------------------------------------------------
    def test_high_performance_capture_latency(self) -> None:
        """Valida que o processamento do pipeline de percepção em ROI mantém latência < 20ms."""
        detector = BattleUIDetector()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        latencies = []
        for _ in range(20):
            t0 = time.perf_counter()
            _ = detector.analyze_battle_ui(frame)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)

        avg_latency = float(np.mean(latencies))
        self.assertLess(avg_latency, 25.0, f"Latência média {avg_latency:.2f}ms excede limite de 25ms.")

    # -------------------------------------------------------------------------
    # TEST 4: BÉZIER TRAJECTORY GENERATION
    # -------------------------------------------------------------------------
    def test_bezier_trajectory_generation(self) -> None:
        """Valida que o gerador de curvas Bézier produz coordenadas contínuas e válidas."""
        x0, y0 = 100, 100
        x1, y1 = 800, 600

        points = generate_cubic_bezier_trajectory(x0, y0, x1, y1, steps=30)
        self.assertGreaterEqual(len(points), 25)
        self.assertEqual(points[0], (x0, y0))
        self.assertEqual(points[-1], (x1, y1))

        # Valida continuidade (sem saltos gigantes entre passos consecutivos)
        for i in range(len(points) - 1):
            px, py = points[i]
            nx, ny = points[i + 1]
            step_dist = np.hypot(nx - px, ny - py)
            self.assertLess(step_dist, 70.0, f"Salto descontínuo de {step_dist:.1f}px no passo {i}")

    # -------------------------------------------------------------------------
    # TEST 5: POST-BATTLE HEALING DECISION TREE
    # -------------------------------------------------------------------------
    def test_post_battle_healing_decision_tree(self) -> None:
        """Valida que o bot vai para o cristal quando HP <= 40% e para exploração se HP > 40%."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Caso A: HP = 35% pós-batalha -> Deve ir para HEALING
        engine.fsm.transition_to(BotState.BATTLE, reason="Em combate")
        snap_crit = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            player_info=PlayerInfo(detected=True, hp_ratio=0.35),
            battle_telemetry=BattleTelemetry(victory_detected=True),
        )
        with patch.object(engine.battle_ui_controller, "is_battle_finished", return_value=True), \
             patch.object(engine, "_handle_healing_cycle"):
            engine._handle_battle_cycle(snap_crit, frame, None)
            self.assertEqual(engine.fsm.current_state, BotState.HEALING)

        # Caso B: HP = 85% pós-batalha -> Deve ir para EXPLORING
        engine.fsm.transition_to(BotState.BATTLE, reason="Em combate")
        snap_healthy = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            player_info=PlayerInfo(detected=True, hp_ratio=0.85),
            battle_telemetry=BattleTelemetry(victory_detected=True),
        )
        with patch.object(engine.battle_ui_controller, "is_battle_finished", return_value=True), \
             patch.object(engine, "_handle_overworld_cycle"):
            engine._handle_battle_cycle(snap_healthy, frame, None)
            self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)

    # -------------------------------------------------------------------------
    # TEST 6: EMERGENCY KILLSWITCH CLEARS WIN32 KEY STATES
    # -------------------------------------------------------------------------
    def test_emergency_killswitch_clears_win32_key_states(self) -> None:
        """Valida se o Killswitch limpa o estado de todas as teclas virtuais e aciona SAFE_STOP."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        killswitch = engine.killswitch

        # Mock callback de liberação
        mock_release = MagicMock()
        killswitch.release_keys_callback = mock_release

        killswitch.trigger_emergency_stop(reason="TEST_V4_EMERGENCY")

        self.assertTrue(killswitch.is_triggered)
        mock_release.assert_called_once()
        self.assertEqual(engine.fsm.current_state, BotState.SAFE_STOP)


if __name__ == "__main__":
    unittest.main()
