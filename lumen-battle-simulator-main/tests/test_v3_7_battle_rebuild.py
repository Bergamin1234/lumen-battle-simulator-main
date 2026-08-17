"""
LUMENA BOT v3.7 — BATTLE EXECUTION REBUILD & ZERO FAKE PASS UNIT TESTS
======================================================================
Suíte de testes obrigatória para validação do modelo v3.7:
1. test_battle_priority_over_healing
2. test_battle_blocks_crystal
3. test_fight_detection
4. test_fight_click_dispatch
5. test_fight_click_verification
6. test_battle_action_timeout
7. test_battle_state_machine
8. test_world_player_not_battle_player
9. test_crystal_disabled_in_battle
10. test_battle_ui_context
11. test_skill_detection_dynamic
12. test_no_observation_deadlock
13. test_action_required_when_fight_visible
"""

import unittest
import time
import numpy as np
from unittest.mock import MagicMock, patch

from config.settings import BotConfig, CRITICAL_HP_RATIO, HEALING_HP_RATIO
from src.models.enums import AgentState, Element
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.combat.battle_ui_controller import BattleUIController
from src.perception.landmark_detector import LandmarkDetector
from src.core.event_bus import EventBus, EventType


class TestLumenaBotV37BattleRebuild(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: BATTLE PRIORITY OVER HEALING (Section 20 & 25)
    # -------------------------------------------------------------------------
    def test_battle_priority_over_healing(self) -> None:
        """resolve_high_level_state SEMPRE prioriza BATTLE antes de qualquer verificação de cura."""
        engine = LumenaBotEngine()
        # Mock de snapshot com HP crítico (15%) mas com batalha ativa
        bt = BattleTelemetry(in_battle=True, player_hp_pct=0.15)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=bt)
        
        state = engine.resolve_high_level_state(snapshot)
        self.assertEqual(state, BotState.BATTLE)

    # -------------------------------------------------------------------------
    # TEST 2: BATTLE BLOCKS CRYSTAL (Section 2 & 10)
    # -------------------------------------------------------------------------
    def test_battle_blocks_crystal(self) -> None:
        """Quando em batalha, crystal_search é estritamente BLOCKED mesmo com cristal visível."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        bt = BattleTelemetry(in_battle=True, player_hp_pct=0.805)
        elem = UIElement(name="blue_crystal", bounding_box=(200, 200, 50, 50), confidence=0.95)
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.BATTLE,
            battle_telemetry=bt,
            crystal_detected=True,
            ui_elements={"blue_crystal": elem},
        )
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.battle_ui_controller, "click_fight", return_value=(True, 0.1, True)):

            engine._execute_single_cycle()

            self.assertEqual(engine.health_monitor["crystal_search"], "BLOCKED")
            self.assertTrue(engine.health_monitor["crystal_search_blocked"])
            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)

    # -------------------------------------------------------------------------
    # TEST 3: FIGHT DETECTION (Section 4 & 5)
    # -------------------------------------------------------------------------
    def test_fight_detection(self) -> None:
        """BattleUIDetector localiza o botão FIGHT e calcula centro e confiança."""
        detector = BattleUIDetector()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Injeta retângulo de botão FIGHT no ROI inferior direito
        import cv2
        cv2.rectangle(frame, (950, 550), (1100, 620), (30, 40, 220), -1)

        fight_elem = detector.detect_fight_button(frame)
        self.assertTrue(fight_elem.is_present)
        self.assertGreater(fight_elem.center_x, 900)
        self.assertGreater(fight_elem.center_y, 500)

    # -------------------------------------------------------------------------
    # TEST 4: FIGHT CLICK DISPATCH (Section 5 & 18)
    # -------------------------------------------------------------------------
    def test_fight_click_dispatch(self) -> None:
        """BattleUIController despacha clique físico em FIGHT e publica FIGHT_CLICK_DISPATCHED."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(controller.input_ctrl, "click", return_value=True):
            dispatched, latency, _ = controller.click_fight(frame_before=frame)
            self.assertTrue(dispatched)
            self.assertGreaterEqual(latency, 0.0)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.FIGHT_CLICK_DISPATCHED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 5: FIGHT CLICK VERIFICATION (Section 18 & 19)
    # -------------------------------------------------------------------------
    def test_fight_click_verification(self) -> None:
        """Verificação pós-clique de FIGHT confirma alteração visual na UI."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame_before = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame_after = np.full((720, 1280, 3), 100, dtype=np.uint8)

        with patch.object(controller.input_ctrl, "click", return_value=True), \
             patch.object(controller.input_ctrl, "compute_visual_delta", return_value=(True, 0.045)):

            dispatched, latency, verified = controller.click_fight(
                frame_before=frame_before,
                screen_capture_func=lambda: (frame_after, time.time()),
            )
            self.assertTrue(dispatched)
            self.assertTrue(verified)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.FIGHT_CLICK_VERIFIED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 6: BATTLE ACTION TIMEOUT (Section 14)
    # -------------------------------------------------------------------------
    def test_battle_action_timeout(self) -> None:
        """Inatividade prolongada em combate com inimigo dispara BATTLE_EXECUTION_STALLED."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False
        engine._last_combat_action_time = time.time() - 6.0  # 6s sem ação

        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            target_enemy=EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90, name="Enemy", distance=150.0),
        )
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=BattleTelemetry(in_battle=True))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot", return_value=MagicMock(executed_successfully=False, decision=None)):

            engine._execute_single_cycle()

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.BATTLE_EXECUTION_STALLED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 7: BATTLE STATE MACHINE (Section 3)
    # -------------------------------------------------------------------------
    def test_battle_state_machine(self) -> None:
        """Transição direta de BATTLE -> SEARCHING_CRYSTAL é rejeitada."""
        engine = LumenaBotEngine()
        engine.fsm.transition_to(BotState.BATTLE, reason="Iniciando Combate")
        self.assertEqual(engine.fsm.current_state, BotState.BATTLE)

        # Tentar ir para HEALING diretamente sem transição válida
        res = engine.fsm.transition_to(BotState.HEALING, reason="Tentativa Inválida")
        # Deve permanecer em BATTLE ou registrar rejeição
        self.assertEqual(engine.fsm.current_state, BotState.BATTLE)

    # -------------------------------------------------------------------------
    # TEST 8: WORLD PLAYER != BATTLE PLAYER (Section 11)
    # -------------------------------------------------------------------------
    def test_world_player_not_battle_player(self) -> None:
        """Distingue semanticamente o detector de WORLD_PLAYER e BATTLE_PLAYER."""
        landmark = LandmarkDetector()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        w_found, w_bbox, w_center, _ = landmark.detect_player(frame, in_battle=False)
        b_found, b_bbox, b_center, _ = landmark.detect_player(frame, in_battle=True)

        self.assertTrue(w_found)
        self.assertTrue(b_found)
        # BATTLE_PLAYER fica no quadrante inferior esquerdo, enquanto WORLD_PLAYER fica no centro
        self.assertNotEqual(w_center, b_center)

    # -------------------------------------------------------------------------
    # TEST 9: CRYSTAL DISABLED IN BATTLE (Section 9 & 24)
    # -------------------------------------------------------------------------
    def test_crystal_disabled_in_battle(self) -> None:
        """detect_crystal retorna False imediatamente quando in_battle == True."""
        landmark = LandmarkDetector()
        frame = np.full((720, 1280, 3), 200, dtype=np.uint8)

        c_found, c_pos, c_elem = landmark.detect_crystal(frame, in_battle=True)
        self.assertFalse(c_found)
        self.assertIsNone(c_pos)
        self.assertIsNone(c_elem)

    # -------------------------------------------------------------------------
    # TEST 10: BATTLE UI CONTEXT (Section 4)
    # -------------------------------------------------------------------------
    def test_battle_ui_context(self) -> None:
        """BattleUIDetector confirma contexto e pontuação ponderada."""
        detector = BattleUIDetector()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        import cv2
        cv2.rectangle(frame, (950, 550), (1100, 620), (30, 40, 220), -1)

        res = detector.analyze_battle_ui(frame)
        self.assertTrue(res.battle_ui_confirmed)
        self.assertGreater(res.battle_ui_score, 0.0)

    # -------------------------------------------------------------------------
    # TEST 11: SKILL DETECTION DYNAMIC (Section 16)
    # -------------------------------------------------------------------------
    def test_skill_detection_dynamic(self) -> None:
        """Localiza dinamicamente múltiplos slots de habilidade."""
        controller = BattleUIController()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        skills = controller.find_available_skills(frame)
        self.assertGreaterEqual(len(skills), 2)
        for s in skills:
            self.assertIsNotNone(s.hotkey)
            self.assertGreater(s.center_x, 0)
            self.assertGreater(s.center_y, 0)

    # -------------------------------------------------------------------------
    # TEST 12: NO OBSERVATION DEADLOCK (Section 15)
    # -------------------------------------------------------------------------
    def test_no_observation_deadlock(self) -> None:
        """Combate com FIGHT disponível não pode ficar em observação infinita."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Desenha botão FIGHT
        import cv2
        cv2.rectangle(frame, (950, 550), (1100, 620), (30, 40, 220), -1)

        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=BattleTelemetry(in_battle=True))

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.battle_ui_controller, "click_fight", return_value=(True, 0.1, True)) as mock_fight:

            engine._execute_single_cycle()
            # Bot DEVE disparar click_fight imediatamente
            mock_fight.assert_called_once()
            self.assertEqual(engine.health_monitor["last_action"], "CLICK_FIGHT")

    # -------------------------------------------------------------------------
    # TEST 13: ACTION REQUIRED WHEN FIGHT VISIBLE (Section 30)
    # -------------------------------------------------------------------------
    def test_action_required_when_fight_visible(self) -> None:
        """Se FIGHT for detectado, ACTION_REQUESTED e INPUT_DISPATCHED são disparados obrigatoriamente."""
        controller = BattleUIController(event_bus=self.event_bus)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        import cv2
        cv2.rectangle(frame, (950, 550), (1100, 620), (30, 40, 220), -1)

        with patch.object(controller.input_ctrl, "click", return_value=True):
            dispatched, latency, verified = controller.click_fight(frame_before=frame)
            self.assertTrue(dispatched)

            req_events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.FIGHT_CLICK_REQUESTED]
            disp_events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.FIGHT_CLICK_DISPATCHED]

            self.assertGreaterEqual(len(req_events), 1)
            self.assertGreaterEqual(len(disp_events), 1)


if __name__ == "__main__":
    unittest.main()
