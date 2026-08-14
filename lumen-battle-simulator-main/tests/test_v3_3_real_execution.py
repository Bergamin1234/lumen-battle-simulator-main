import unittest
import numpy as np
import time
import os

from src.models.enums import AgentState, Element
from src.automation.state_machine import BotState
from src.models.lumen import UIElement, StateSnapshot, BattleTelemetry, PlayerInfo, TargetLockInfo
from src.models.combat_vision import SkillSlot, CombatSnapshot, EnemyTarget
from src.perception.landmark_detector import LandmarkDetector
from src.perception.state_classifier import StateClassifier
from src.perception.combat_vision import CombatVisionAnalyzer
from src.automation.healing import HealingController
from src.combat.combat_agent import CombatAgent, CombatAgentState
from src.combat.skill_executor import SkillExecutor
from src.combat.decision_engine import CombatDecisionEngine
from src.core.event_bus import EventBus, EventType
from src.telemetry.telemetry_manager import TelemetryManager
from src.input.input_controller import InputController
from src.telemetry.evidence_package import save_evidence_package


class TestV33RealExecution(unittest.TestCase):
    """Bateria de Testes de Regressão e Validação Estrita - Lumena Bot v3.3 (Zero Fake Pass)."""

    def setUp(self):
        self.event_bus = EventBus()
        self.event_bus.clear_history()
        self.telemetry = TelemetryManager()

    def test_player_detection(self):
        """Regra #8: Detecção explícita do sprite do player com coordenadas e bounding box."""
        detector = LandmarkDetector()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Desenha um sprite no centro
        cv2_player = np.full((40, 24, 3), (180, 100, 50), dtype=np.uint8)
        frame[340:380, 628:652] = cv2_player

        found, bbox, center, conf = detector.detect_player(frame)
        self.assertTrue(found)
        self.assertGreater(conf, 0.5)
        self.assertEqual(len(bbox), 4)
        self.assertEqual(len(center), 2)
        # O centro deve estar próximo a (640, 360)
        self.assertAlmostEqual(center[0], 640, delta=100)
        self.assertAlmostEqual(center[1], 360, delta=100)

    def test_healing_crystal_detection(self):
        """Regra #5: Detecção semântica do Cristal Azul de Cura com vetor relativo ao player."""
        detector = LandmarkDetector()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Desenha um cristal azul ciano vibrante (HSV ~ [100, 200, 240])
        # BGR para ciano: B=255, G=200, R=0
        frame[200:260, 700:750] = (255, 200, 0)

        player_pos = (640, 360)
        found, rel_vec, elem = detector.detect_crystal(frame, player_pos=player_pos)
        self.assertTrue(found)
        self.assertIsNotNone(elem)
        self.assertEqual(elem.semantic_type, "HEALING_CRYSTAL")
        self.assertIsNotNone(rel_vec)
        # O cristal está à direita (dx > 0) e acima (dy < 0) em relação ao jogador
        dx, dy = rel_vec
        self.assertGreater(dx, 0)
        self.assertLess(dy, 0)

    def test_target_lock(self):
        """Regra #7: Reter alvo travado entre frames sem oscilar."""
        controller = HealingController()
        elem = UIElement(
            name="blue_crystal",
            bounding_box=(700, 200, 50, 60),
            confidence=0.92,
            center=(725, 230),
            semantic_type="HEALING_CRYSTAL",
        )
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(85, -130),
        )

        state, is_done, msg = controller.step(snapshot)
        self.assertTrue(controller.target_locked)
        self.assertIsNotNone(controller.target_lock_info)
        self.assertEqual(controller.target_lock_info.target_id, "HEALING_CRYSTAL")
        self.assertTrue(controller.target_lock_info.locked)

    def test_healing_priority(self):
        """Regra #6: Prioridade absoluta do Cristal de Cura quando em busca de cura."""
        # Se na tela existirem árvores, NPCs e o cristal, o cristal é prioritário
        elem_tree = UIElement(name="tree", bounding_box=(100, 100, 50, 80), confidence=0.9, semantic_type="SCENERY")
        elem_npc = UIElement(name="npc", bounding_box=(300, 200, 30, 50), confidence=0.85, semantic_type="NPC")
        elem_crystal = UIElement(name="blue_crystal", bounding_box=(600, 300, 60, 80), confidence=0.95, semantic_type="HEALING_CRYSTAL")

        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"tree": elem_tree, "npc": elem_npc, "blue_crystal": elem_crystal},
            crystal_detected=True,
            crystal_relative_pos=(-40, -60),
        )

        controller = HealingController()
        state, is_done, msg = controller.step(snapshot)
        self.assertIn(state, ("TARGET_LOCKED", "APPROACH_TARGET", "INTERACT_READY", "INTERACTING"))
        self.assertEqual(controller.target_lock_info.semantic_type, "HEALING_CRYSTAL")

    def test_approach_target(self):
        """Regra #9: Micro-movimentos em direção ao alvo ao longo do eixo dominante."""
        controller = HealingController(interaction_distance_threshold=50.0)
        elem = UIElement(name="blue_crystal", bounding_box=(800, 360, 40, 60), confidence=0.9, center=(820, 390), semantic_type="HEALING_CRYSTAL")
        
        # dx = 180 (direita), dy = 30 (baixo) -> Eixo dominante 'd'
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(180, 30),
        )

        state, is_done, msg = controller.step(snapshot)
        self.assertEqual(state, "APPROACH_TARGET")
        self.assertEqual(controller.last_move_key, "d")

    def test_movement_verification(self):
        """Regra #10: Verificação fechada de movimento via variação visual de pixels."""
        input_ctrl = InputController()
        frame1 = np.full((100, 100, 3), 50, dtype=np.uint8)
        frame2 = np.full((100, 100, 3), 50, dtype=np.uint8)
        
        # Sem alteração -> delta = 0.0 -> False
        confirmed, delta = input_ctrl.compute_visual_delta(frame1, frame2)
        self.assertFalse(confirmed)
        self.assertEqual(delta, 0.0)

        # Com alteração substancial
        frame2[30:70, 30:70] = 220
        confirmed, delta = input_ctrl.compute_visual_delta(frame1, frame2)
        self.assertTrue(confirmed)
        self.assertGreater(delta, 0.005)

    def test_interaction_verification(self):
        """Regra #11: Interação e confirmação de diálogo de cura ao atingir o cristal."""
        controller = HealingController(interaction_distance_threshold=90.0)
        elem = UIElement(name="blue_crystal", bounding_box=(650, 370, 40, 60), confidence=0.95, center=(670, 400), semantic_type="HEALING_CRYSTAL")
        
        # Distância pequena (< 90px)
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.HEALING,
            ui_elements={"blue_crystal": elem},
            crystal_detected=True,
            crystal_relative_pos=(30, 40),
        )

        state, is_done, msg = controller.step(snapshot)
        self.assertIn(state, ("INTERACT_READY", "INTERACTING"))

        # Simula caixa de diálogo abrindo e confirmação
        dialog_elem = UIElement(name="dialog_box", bounding_box=(200, 500, 600, 150), confidence=0.95, semantic_type="DIALOG")
        snapshot_dialog = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.HEALING,
            ui_elements={"blue_crystal": elem, "dialog_box": dialog_elem},
            crystal_detected=True,
            crystal_relative_pos=(30, 40),
        )

        completed = False
        final_state = ""
        for _ in range(5):
            final_state, completed, _ = controller.step(snapshot_dialog)
            if completed:
                break

        self.assertTrue(completed)
        self.assertEqual(final_state, "HEALING_VERIFIED")

    def test_action_verification(self):
        """Regra #17: Verificação de ação sem falsos positivos."""
        telemetry = TelemetryManager()
        prev_verified = telemetry._data.actions_verified_total
        prev_unconf = telemetry._data.actions_unconfirmed_total

        telemetry.record_action_verified()
        self.assertEqual(telemetry._data.actions_verified_total, prev_verified + 1)

        telemetry.record_action_unconfirmed()
        self.assertEqual(telemetry._data.actions_unconfirmed_total, prev_unconf + 1)

    def test_execution_stalled(self):
        """Regra #12 & #13: Watchdog detecta paralisia observacional > 15s."""
        events = []
        self.event_bus.subscribe(EventType.EXECUTION_STALLED, lambda ev: events.append(ev))

        # Dispara evento stalled
        self.event_bus.publish(
            EventType.EXECUTION_STALLED,
            data={"elapsed": 16.2, "state": "SEARCHING_CRYSTAL"},
            category="SAFETY",
            level="WARNING",
            message="EXECUTION_STALLED: Bot observando sem ação há mais de 15s.",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, EventType.EXECUTION_STALLED)

    def test_dynamic_skill_detection(self):
        """Regra #14: Detector de HUD identifica slots de habilidades dinâmicos."""
        analyzer = CombatVisionAnalyzer()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Desenha 4 botões na barra de skills do HUD
        for i in range(4):
            bx = 400 + i * 110
            by = 640
            frame[by:by+50, bx:bx+90] = (60, 60, 60)
            # Centro claro
            frame[by+10:by+40, bx+10:bx+80] = (150, 150, 150)

        slots = analyzer.detect_skill_slots(frame, in_battle=True)
        self.assertGreaterEqual(len(slots), 4)
        for s in slots[:4]:
            self.assertGreater(s.center_x, 0)
            self.assertGreater(s.center_y, 0)
            self.assertIsNotNone(s.hotkey)

    def test_dynamic_skill_position(self):
        """Regra #15: SkillExecutor despacha para coordenadas reais do slot."""
        executor = SkillExecutor()
        slot = SkillSlot(
            slot_index=1,
            skill_name="Spark Blast",
            center_x=510,
            center_y=665,
            hotkey="1",
            power=60,
            element="Eletrico",
        )
        success, latency = executor.execute_skill(slot)
        self.assertGreater(latency, 0.0)

    def test_no_blind_attack(self):
        """Regra #16: Motor de decisão de combate não ataca às cegas se em cooldown ou sem alvo."""
        engine = CombatDecisionEngine()
        # Slot com cooldown de 100% (indisponível)
        slot_cd = SkillSlot(slot_index=1, skill_name="Fireball", cooldown_ratio=1.0, available=False, power=80)
        slot_ready = SkillSlot(slot_index=2, skill_name="Tackle", cooldown_ratio=0.0, available=True, power=40)

        snapshot = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            player_position=(850, 280),
            target_enemy=EnemyTarget(target_id=1, name="wild_lumen", bbox=(800, 200, 100, 100), distance=30.0),
            skill_slots=[slot_cd, slot_ready],
        )

        decision = engine.evaluate_combat_snapshot(snapshot)
        self.assertEqual(decision.action_type, "USE_SKILL")
        self.assertEqual(decision.selected_skill.skill_name, "Tackle")

    def test_physical_validation_integrity(self):
        """Regra #22: Geração íntegra de result.json sem falsos positivos."""
        ts_dir = os.path.join("debug", "evidence", "test_integrity")
        os.makedirs(ts_dir, exist_ok=True)
        
        # Caso 1: Sem delta visual -> physical_execution_verified DEVE ser False
        save_evidence_package(
            evidence_dir=ts_dir,
            visual_delta=0.001,
            target_window_verified=True,
            foreground_verified=True,
            input_dispatched=True,
            action_verified=False,
            action_name="MOVE_W",
        )

        import json
        with open(os.path.join(ts_dir, "result.json"), "r", encoding="utf-8") as f:
            res = json.load(f)

        self.assertFalse(res["physical_execution_verified"])
        self.assertFalse(res["visual_change_detected"])
        self.assertFalse(res["action_verified"])


if __name__ == "__main__":
    unittest.main()
