"""
LUMENA BOT v3.9 — DYNAMIC SKILL ROIs, MODAL DISMISSAL & SAFETY UNIT TESTS
==========================================================================
Suíte de testes para validação das capacidades da versão v3.9:
1. test_dynamic_skill_slot_detection
2. test_victory_modal_detection_and_dismissal
3. test_emergency_killswitch_triggers_safe_stop
4. test_input_guard_rejects_out_of_bounds_clicks
5. test_turn_lock_maintains_suppression_until_modal_or_next_turn
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
from src.models.lumen import StateSnapshot, BattleTelemetry, UIElement
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.perception.battle_ui_detector import BattleUIDetector, BattleUIDetectionResult, BattleUIElement
from src.combat.battle_ui_controller import BattleUIController
from src.input.killswitch import EmergencyKillswitch


class TestLumenaBotV39ModalAndDynamicSkills(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: DYNAMIC SKILL SLOT DETECTION (Resoluções 720p, 1080p, 1440p)
    # -------------------------------------------------------------------------
    def test_dynamic_skill_slot_detection(self) -> None:
        """Validação de ROI dinâmico de skills resistente a diferentes resoluções."""
        controller = BattleUIController(event_bus=self.event_bus)

        for res in [(720, 1280), (1080, 1920), (1440, 2560)]:
            h, w = res
            frame = np.zeros((h, w, 3), dtype=np.uint8)

            skills = controller.find_available_skills(frame)
            self.assertGreaterEqual(len(skills), 4)

            # Verifica se todas as coordenadas estão dentro dos limites proporcionais
            for s in skills:
                self.assertGreater(s.screen_x, 0)
                self.assertLess(s.screen_x + s.width, w)
                self.assertGreater(s.screen_y, int(h * 0.50))
                self.assertLess(s.screen_y + s.height, h)

    # -------------------------------------------------------------------------
    # TEST 2: VICTORY MODAL DETECTION AND DISMISSAL
    # -------------------------------------------------------------------------
    def test_victory_modal_detection_and_dismissal(self) -> None:
        """Detecção de modal intermediário de vitória/recompensa e rotina de dismissal."""
        detector = BattleUIDetector(event_bus=self.event_bus)
        controller = BattleUIController(ui_detector=detector, event_bus=self.event_bus)

        # Frame com caixa modal no centro
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame, (400, 200), (880, 520), (220, 220, 220), -1)  # Caixa modal
        cv2.rectangle(frame, (540, 440), (740, 490), (50, 180, 50), -1)    # Botão OK/Claim

        has_modal, m_type, elem = detector.detect_post_battle_modal(frame)
        self.assertTrue(has_modal)
        self.assertIsNotNone(elem)

        with patch.object(controller.input_ctrl, "click", return_value=True), \
             patch.object(controller.input_ctrl, "press_key", return_value=True):

            dispatched, v_delta = controller.dismiss_post_battle_modal(frame)
            self.assertTrue(dispatched)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.MODAL_DISMISSED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 3: EMERGENCY KILLSWITCH TRIGGERS SAFE_STOP
    # -------------------------------------------------------------------------
    def test_emergency_killswitch_triggers_safe_stop(self) -> None:
        """Killswitch aciona SAFE_STOP, libera teclas e emite eventos de emergência."""
        engine = LumenaBotEngine(event_bus=self.event_bus)
        engine.fsm.transition_to(BotState.BATTLE, reason="In Battle")

        killswitch = engine.killswitch
        self.assertFalse(killswitch.is_triggered)

        # Aciona parada de emergência
        killswitch.trigger_emergency_stop(reason="TEST_KILLSWITCH_TRIGGER")

        self.assertTrue(killswitch.is_triggered)
        self.assertEqual(engine.fsm.current_state, BotState.SAFE_STOP)

        events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.KILLSWITCH_TRIGGERED]
        self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 4: INPUT GUARD REJECTS OUT OF BOUNDS CLICKS
    # -------------------------------------------------------------------------
    def test_input_guard_rejects_out_of_bounds_clicks(self) -> None:
        """Input Dispatcher Guard rejeita coordenadas que ultrapassam o canvas útil."""
        controller = BattleUIController(event_bus=self.event_bus)

        # Mock de limites de janela (x=100, y=100, w=1000, h=600)
        with patch.object(controller.input_ctrl.window_manager, "get_active_target", return_value=MagicMock(hwnd=12345)), \
             patch.object(controller.input_ctrl.window_manager, "get_window_bounds", return_value=(100, 100, 1000, 600)):

            # Coordenadas válidas (dentro da janela)
            valid = controller.validate_input_guard(500, 400)
            self.assertTrue(valid)

            # Coordenadas fora da janela (ex: x=1500, y=900)
            invalid = controller.validate_input_guard(1500, 900)
            self.assertFalse(invalid)

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.INPUT_GUARD_REJECTED]
            self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------------------
    # TEST 5: TURN LOCK MAINTAINS SUPPRESSION UNTIL MODAL OR NEXT TURN
    # -------------------------------------------------------------------------
    def test_turn_lock_maintains_suppression_until_modal_or_next_turn(self) -> None:
        """Turn Lock bloqueia comandos durante a animação e libera após reaparecimento dos controles."""
        controller = BattleUIController(event_bus=self.event_bus)
        controller._is_waiting_turn_resolution = True

        # Frame com animação em curso (sem botões nem controles)
        anim_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        done_during_anim = controller.process_turn_resolution_check(anim_frame)
        self.assertFalse(done_during_anim)
        self.assertTrue(controller.is_waiting_turn_resolution)

        # Frame com botão FIGHT reaparecido
        ready_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(ready_frame, (950, 550), (1100, 620), (30, 40, 220), -1)

        done_when_ready = controller.process_turn_resolution_check(ready_frame)
        self.assertTrue(done_when_ready)
        self.assertFalse(controller.is_waiting_turn_resolution)


if __name__ == "__main__":
    unittest.main()
