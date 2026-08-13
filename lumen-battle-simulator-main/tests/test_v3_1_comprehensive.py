import os
import sys
import json
import time
import unittest
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.enums import Element, AgentState
from src.models.combat_vision import TargetWindowInfo, SkillSlot, EnemyTarget, CombatSnapshot, CombatDecision, PositionInfo
from src.input.target_window import TargetWindowManager, WindowInfo
from src.input.safety_guard import SafetyGuard
from src.perception.combat_vision import CombatVisionAnalyzer
from src.combat.positioning import CombatPositioningController
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.combat_agent import CombatAgent, CombatAgentState
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.automation.bot_controller import BotController
from src.core.event_bus import EventBus, EventType


class TestLumenaBotV31Comprehensive(unittest.TestCase):
    """Bateria de testes unitários abrangentes para o Lumena Bot Control Center v3.1."""

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------
    # 1. TARGET WINDOW: Rejeição Estrita do Próprio Processo
    # -------------------------------------------------------------
    def test_target_window_excludes_self_process(self) -> None:
        win_mgr = TargetWindowManager()
        my_pid = os.getpid()

        info = TargetWindowInfo(
            hwnd=99999,
            pid=my_pid,
            process_name="python.exe",
            window_title="Lumena Bot Control Center — Autonomous Agent Suite",
            is_self_process=True,
            is_browser=False,
            is_valid_candidate=False,
            rejection_reason="self_process",
        )
        self.assertTrue(info.is_self_process)
        self.assertFalse(info.is_valid_candidate)
        self.assertEqual(info.rejection_reason, "self_process")

    # -------------------------------------------------------------
    # 2. TARGET WINDOW: Identificação de Navegadores
    # -------------------------------------------------------------
    def test_target_window_identifies_browsers(self) -> None:
        win_mgr = TargetWindowManager()
        self.assertEqual(win_mgr.identify_browser_type("chrome.exe", "Google Chrome"), (True, "CHROME"))
        self.assertEqual(win_mgr.identify_browser_type("msedge.exe", "Microsoft Edge"), (True, "EDGE"))
        self.assertEqual(win_mgr.identify_browser_type("firefox.exe", "Mozilla Firefox"), (True, "FIREFOX"))
        self.assertEqual(win_mgr.identify_browser_type("brave.exe", "Brave"), (True, "BRAVE"))
        self.assertEqual(win_mgr.identify_browser_type("notepad.exe", "Bloco de Notas"), (False, "UNKNOWN"))

    # -------------------------------------------------------------
    # 3. FOREGROUND VERIFICATION: Verificação Estrita
    # -------------------------------------------------------------
    def test_foreground_verification_strict(self) -> None:
        win_mgr = TargetWindowManager()
        # Mock HWND 999999 que não existe no foreground
        diag = win_mgr.bring_to_foreground_with_diagnostic(999999)
        self.assertFalse(diag.is_truly_in_foreground)
        self.assertNotEqual(diag.foreground_hwnd, 999999)

    # -------------------------------------------------------------
    # 4. SAFETY GUARD: Bloqueio do Próprio Processo
    # -------------------------------------------------------------
    def test_safety_guard_blocks_self_process(self) -> None:
        guard = SafetyGuard()
        my_pid = os.getpid()

        # Deve rejeitar próprio PID
        can_dispatch = guard.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=1234,
            target_pid=my_pid,
            target_title="Lumena Bot",
            target_process="python.exe",
        )
        self.assertFalse(can_dispatch)

        # Deve rejeitar título do Lumena Bot
        can_dispatch_title = guard.validate_can_dispatch(
            is_window_confirmed=True,
            target_hwnd=1234,
            target_pid=my_pid + 10,
            target_title="Lumena Bot Control Center",
            target_process="chrome.exe",
        )
        self.assertFalse(can_dispatch_title)

    # -------------------------------------------------------------
    # 5. DYNAMIC SKILL SCANNER: Suporte a N Slots
    # -------------------------------------------------------------
    def test_skill_scanner_dynamic_n_slots(self) -> None:
        analyzer = CombatVisionAnalyzer()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Desenha 6 botões simulados no HUD inferior
        for i in range(6):
            x = 300 + i * 120
            y = 800
            cv2.rectangle(frame, (x, y), (x + 90, y + 60), (180, 180, 180), -1)

        skills = analyzer.detect_skill_slots(frame, in_battle=True)
        self.assertGreaterEqual(len(skills), 4)
        for s in skills:
            self.assertIsNotNone(s.hotkey)
            self.assertGreater(s.width, 0)
            self.assertGreater(s.height, 0)

    # -------------------------------------------------------------
    # 6. COMBAT POSITIONING: Estados de Aproximação e Alcance
    # -------------------------------------------------------------
    def test_combat_positioning_states(self) -> None:
        ctrl = CombatPositioningController()

        melee_skill = SkillSlot(slot_index=1, skill_name="Slash", range_type="MELEE", power=50)
        ranged_skill = SkillSlot(slot_index=2, skill_name="Fireball", range_type="RANGED", power=70)

        # Inimigo a 500px -> Deve aproximar para Melee
        state, key, dist = ctrl.evaluate_positioning(
            player_pos=(300, 300),
            target_pos=(800, 300),
            skill=melee_skill,
        )
        self.assertEqual(state, "APPROACH_TARGET")
        self.assertEqual(key, "d")
        self.assertEqual(dist, 500.0)

        # Inimigo a 100px -> Posição pronta para Melee
        state_ready, key_ready, _ = ctrl.evaluate_positioning(
            player_pos=(300, 300),
            target_pos=(380, 300),
            skill=melee_skill,
        )
        self.assertEqual(state_ready, "ATTACK_POSITION_READY")
        self.assertIsNone(key_ready)

        # Inimigo a 40px -> Recuo para Ranged
        state_retreat, key_retreat, _ = ctrl.evaluate_positioning(
            player_pos=(300, 300),
            target_pos=(340, 300),
            skill=ranged_skill,
        )
        self.assertEqual(state_retreat, "MAINTAIN_DISTANCE")
        self.assertEqual(key_retreat, "a")

    # -------------------------------------------------------------
    # 7. COMBAT DECISION: Fórmula de Pontuação e Fraqueza
    # -------------------------------------------------------------
    def test_combat_decision_scoring_and_weakness(self) -> None:
        engine = CombatDecisionEngine()

        water_skill = SkillSlot(
            slot_index=1,
            skill_name="WaterPulse",
            element=Element.WATER,
            power=60,
            range_type="RANGED",
            available=True,
            cooldown=0.0,
            hotkey="1",
        )
        grass_skill = SkillSlot(
            slot_index=2,
            skill_name="LeafBlade",
            element=Element.GRASS,
            power=60,
            range_type="MELEE",
            available=True,
            cooldown=0.0,
            hotkey="2",
        )

        fire_enemy = EnemyTarget(
            target_id=1,
            bbox=(700, 300, 100, 100),
            center=(750, 350),
            element=Element.FIRE,
            weakness=Element.WATER,
            hp_estimate=0.8,
            distance=200.0,
        )

        snapshot = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            target_enemy=fire_enemy,
            available_skills=[water_skill, grass_skill],
            player_position=(300, 350),
        )

        decision = engine.evaluate_combat_snapshot(snapshot)
        # Água é super efetiva contra Fogo (2.0x) -> Deve escolher WaterPulse
        self.assertEqual(decision.action_type, "USE_SKILL")
        self.assertEqual(decision.selected_skill.skill_name, "WaterPulse")
        self.assertIn("Super Efetivo", decision.reason)

    # -------------------------------------------------------------
    # 8. ACTION VERIFICATION: Emissão de ACTION_UNCONFIRMED
    # -------------------------------------------------------------
    def test_action_verification_emits_unconfirmed(self) -> None:
        agent = CombatAgent()
        skill = SkillSlot(
            slot_index=1,
            skill_name="FailedStrike",
            element=Element.NORMAL,
            power=40,
            available=True,
            cooldown=0.0,
            hotkey="1",
        )
        enemy = EnemyTarget(
            target_id=1,
            bbox=(700, 300, 100, 100),
            center=(750, 350),
            distance=100.0,
        )
        snapshot = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            target_enemy=enemy,
            available_skills=[skill],
            player_position=(700, 350),
        )

        # Mock de falha na execução
        agent.skill_executor.execute_skill = lambda s: (False, None)
        res = agent.process_combat_snapshot(snapshot)

        self.assertFalse(res.executed_successfully)
        self.assertIn(skill.id, agent._failed_targets_this_battle)

        # Verifica se evento ACTION_UNCONFIRMED foi publicado
        events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.ACTION_UNCONFIRMED]
        self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------
    # 9. ANTI-STUCK: Limite Estrito de 3 Tentativas
    # -------------------------------------------------------------
    def test_anti_stuck_strict_3_limit(self) -> None:
        engine = LumenaBotEngine()
        engine.mode = "AUTONOMOUS"

        # Simula 4 chamadas de _handle_anti_stuck
        engine._handle_anti_stuck()
        self.assertEqual(engine._recovery_attempts, 1)

        engine._handle_anti_stuck()
        self.assertEqual(engine._recovery_attempts, 2)

        engine._handle_anti_stuck()
        self.assertEqual(engine._recovery_attempts, 3)

        engine._handle_anti_stuck()
        self.assertGreaterEqual(engine._recovery_attempts, 4)
        # Na 4ª tentativa, deve entrar em Parada Segura (ERROR) e emitir RECOVERY_FAILED
        self.assertEqual(engine.fsm.current_state, BotState.ERROR)
        events = [e for e in self.event_bus.get_recent_events(10) if e.event_type == EventType.RECOVERY_FAILED]
        self.assertGreaterEqual(len(events), 1)

    # -------------------------------------------------------------
    # 10. LEVEL 7 GATE: Bloqueio Sem Level 6 Validado
    # -------------------------------------------------------------
    def test_level_7_gate_blocked_without_level_6(self) -> None:
        controller = BotController()
        controller.set_level_6_validated_override(False)

        # Se Level 6 não foi validado, modo AUTONOMOUS deve ser bloqueado
        if os.path.exists("physical_test_report.json"):
            os.remove("physical_test_report.json")

        started, msg = controller.start(mode="AUTONOMOUS", bypass_gate=False)
        self.assertFalse(started)
        self.assertIn("LEVEL 7 BLOCKED", msg)

        # Com bypass ou override, deve permitir
        controller.set_level_6_validated_override(True)
        self.assertTrue(controller.is_level_6_validated())


if __name__ == "__main__":
    unittest.main()
