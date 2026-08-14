"""
LUMENA BOT v3.6 — BATTLE OVERRIDE & HP POLICY UNIT TEST SUITE
=============================================================
Validates:
1. Active Battle Override over Healing/Crystal Searching when HP > 20%
2. Case 91/113 HP (~80.5%) in battle -> Mandates Combat, forbids crystal search
3. Emergency survival when HP <= 20% in combat
4. Preventive healing authorized only outside battle when HP <= 40%
5. Healthy overworld exploring when HP > 40% even if blue pixels exist
6. Environment grass classification
7. Dynamic N-slot skill scanning and scoring
8. 5-second combat action timeout watchdog (BATTLE_EXECUTION_STALLED)
9. Closed-loop action verification receiving frame_before
10. BattleContext and WorldState models
11. Centralized settings constants (CRITICAL_HP_RATIO=0.20, HEALING_HP_RATIO=0.40, COMBAT_ACTION_TIMEOUT=5.0)
12. Real-world HealthMonitor telemetry fields
"""

import unittest
import time
import numpy as np
import cv2
from unittest.mock import MagicMock, patch

from config.settings import (
    BotConfig,
    CRITICAL_HP_RATIO,
    HEALING_HP_RATIO,
    COMBAT_ACTION_TIMEOUT,
)
from src.models.enums import AgentState, Element
from src.models.lumen import (
    StateSnapshot,
    BattleTelemetry,
    UIElement,
    BattleContext,
    WorldState,
)
from src.models.combat_vision import (
    CombatSnapshot,
    EnemyTarget,
    SkillSlot,
    CombatDecision,
)
from src.automation.bot_engine import LumenaBotEngine, BotState
from src.perception.state_classifier import StateClassifier
from src.perception.combat_vision import CombatVisionAnalyzer
from src.combat.combat_agent import CombatAgent
from src.combat.decision_engine import CombatDecisionEngine
from src.core.event_bus import EventBus, EventType


class TestLumenaBotV36BattlePriority(unittest.TestCase):

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.event_bus.clear_history()

    # -------------------------------------------------------------------------
    # TEST 1: BATALHA ATIVA COM HP 80.5% (CASO REAL 91/113 HP)
    # -------------------------------------------------------------------------
    def test_case_1_battle_override_high_hp(self) -> None:
        """Caso Real: Personagem com 91/113 HP (~80.5%) em combate NÃO pode buscar cristal."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        # Inimigo visível e combate ativo
        enemy = EnemyTarget(
            target_id=1,
            bbox=(600, 200, 150, 150),
            center=(675, 275),
            confidence=0.92,
            hp_estimate=1.0,
            distance=350.0,
            state="IDLE",
            element=Element.FIRE,
            name="Wild FlameLumen",
        )
        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            player_hp=91.0 / 113.0,  # ~80.5%
            target_enemy=enemy,
            detected_enemies=[enemy],
            available_skills=[
                SkillSlot(
                    id="skill_1", index=1, slot_index=1,
                    screen_x=400, screen_y=600, width=60, height=60,
                    center_x=430, center_y=630, available=True, cooldown=0.0,
                    confidence=0.95, hotkey="1", skill_name="WaterPulse",
                    element=Element.WATER, power=60,
                )
            ],
        )

        # Snapshot do classificador com batalha ativa e resquício de cor azul no mapa
        bt = BattleTelemetry(in_battle=True, player_hp_pct=91.0 / 113.0, enemy_hp_pct=1.0)
        crystal_elem = UIElement(name="blue_crystal", bounding_box=(100, 100, 50, 50), confidence=0.85, center=(125, 125))
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.BATTLE,
            battle_telemetry=bt,
            crystal_detected=True,
            crystal_relative_pos=(-400, -200),
            ui_elements={"blue_crystal": crystal_elem},
        )

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:
            
            mock_combat.return_value = MagicMock(executed_successfully=True, agent_state=MagicMock(name="EXECUTING_ACTION"), decision=CombatDecision(action_type="USE_SKILL", selected_skill=csnap.available_skills[0]))

            engine._execute_single_cycle()

            # Verificações Absolutas
            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)
            self.assertEqual(engine.health_monitor["current_goal"], "COMBAT")
            self.assertEqual(engine.health_monitor["current_target"], "ENEMY")
            self.assertEqual(engine.health_monitor["target_type"], "ENEMY")
            self.assertEqual(engine.health_monitor["crystal_search"], "BLOCKED")
            self.assertTrue(engine.health_monitor["crystal_search_blocked"])
            self.assertEqual(engine.health_monitor["healing_required"], "NO")
            self.assertIn("80.5%", engine.health_monitor["hp_ratio"])
            mock_combat.assert_called_once()

    # -------------------------------------------------------------------------
    # TEST 2: HP CRÍTICO EM BATALHA (EMERGÊNCIA <= 20%)
    # -------------------------------------------------------------------------
    def test_case_2_battle_emergency_low_hp(self) -> None:
        """HP <= 20% em combate ativa sinalização de EMERGÊNCIA."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.88)
        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            player_hp=0.15,  # 15% HP
            target_enemy=enemy,
        )
        bt = BattleTelemetry(in_battle=True, player_hp_pct=0.15)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=bt)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:
            
            mock_combat.return_value = MagicMock(executed_successfully=True, agent_state=MagicMock(name="EXECUTING_ACTION"), decision=None)

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.BATTLE)
            self.assertEqual(engine.health_monitor["healing_required"], "EMERGENCY")

    # -------------------------------------------------------------------------
    # TEST 3: OVERWORLD COM HP SAUDÁVEL E OBJETO AZUL NO CENÁRIO
    # -------------------------------------------------------------------------
    def test_case_3_overworld_healthy_hp_blue_object(self) -> None:
        """Fora de combate com HP > 40%, presença de objeto azul NÃO desvia para cura."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        csnap = CombatSnapshot(timestamp=time.time(), in_battle=False, player_hp=0.80, target_enemy=None)
        bt = BattleTelemetry(in_battle=False, player_hp_pct=0.80)
        crystal_elem = UIElement(name="blue_crystal", bounding_box=(200, 200, 40, 40), confidence=0.70, center=(220, 220))
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.EXPLORING,
            battle_telemetry=bt,
            crystal_detected=True,
            crystal_relative_pos=(100, 100),
            ui_elements={"blue_crystal": crystal_elem},
        )
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.input_ctrl, "press_key_with_diagnostic") as mock_key:
            
            mock_key.return_value = MagicMock(success=True)

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.EXPLORING)
            self.assertEqual(engine.health_monitor["current_goal"], "EXPLORE")
            self.assertEqual(engine.health_monitor["crystal_search"], "BLOCKED")
            self.assertTrue(engine.health_monitor["crystal_search_blocked"])
            self.assertEqual(engine.health_monitor["healing_required"], "NO")

    # -------------------------------------------------------------------------
    # TEST 4: OVERWORLD COM HP BAIXO (<= 40%) -> CURA PREVENTIVA AUTORIZADA
    # -------------------------------------------------------------------------
    def test_case_4_overworld_low_hp_crystal_seek(self) -> None:
        """Fora de combate com HP <= 40%, busca e aproximação do cristal são autorizadas."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        csnap = CombatSnapshot(timestamp=time.time(), in_battle=False, player_hp=0.35, target_enemy=None)
        bt = BattleTelemetry(in_battle=False, player_hp_pct=0.35)
        crystal_elem = UIElement(name="blue_crystal", bounding_box=(200, 200, 40, 40), confidence=0.90, center=(220, 220))
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.SEARCHING_CRYSTAL,
            battle_telemetry=bt,
            crystal_detected=True,
            crystal_relative_pos=(100, 100),
            ui_elements={"blue_crystal": crystal_elem},
        )
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.healing_controller, "step", return_value=("APPROACH_TARGET", False, "Aproximando")):

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.HEALING)
            self.assertEqual(engine.health_monitor["current_goal"], "HEAL")
            self.assertEqual(engine.health_monitor["current_target"], "HEALING_CRYSTAL")
            self.assertEqual(engine.health_monitor["crystal_search"], "ALLOWED")
            self.assertFalse(engine.health_monitor["crystal_search_blocked"])
            self.assertEqual(engine.health_monitor["healing_required"], "YES")

    # -------------------------------------------------------------------------
    # TEST 5: CLASSIFICAÇÃO DE GRAMA DO CENÁRIO (ENVIRONMENT_GRASS)
    # -------------------------------------------------------------------------
    def test_case_5_grass_texture_environment_grass(self) -> None:
        """Textura de grama/mato é classificada como exploração, sem acionar cura."""
        classifier = StateClassifier()
        grass_frame = np.full((360, 640, 3), (34, 139, 34), dtype=np.uint8)
        snapshot = classifier.classify_frame(grass_frame, timestamp=time.time())

        self.assertEqual(snapshot.screen_state, AgentState.EXPLORING)
        self.assertGreater(snapshot.grass_density, 0.10)
        self.assertFalse(snapshot.crystal_detected)

    # -------------------------------------------------------------------------
    # TEST 6: DYNAMIC SKILL SCANNER (N SLOTS DE HABILIDADE)
    # -------------------------------------------------------------------------
    def test_case_6_dynamic_skill_scanner_arbitrary_slots(self) -> None:
        """CombatVisionAnalyzer detecta e processa N slots arbitrários (ex: 6 slots)."""
        analyzer = CombatVisionAnalyzer()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        skills = analyzer.detect_skill_slots(frame, in_battle=True)

        self.assertGreaterEqual(len(skills), 4)
        for s in skills:
            self.assertTrue(s.available)
            self.assertIsNotNone(s.hotkey)
            self.assertGreater(s.center_x, 0)
            self.assertGreater(s.center_y, 0)

    # -------------------------------------------------------------------------
    # TEST 7: COMBAT WATCHDOG DE 5 SEGUNDOS (BATTLE_EXECUTION_STALLED)
    # -------------------------------------------------------------------------
    def test_case_7_combat_watchdog_5s_timeout(self) -> None:
        """Em combate ativo com inimigo, inatividade >= 5.0s dispara BATTLE_EXECUTION_STALLED."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False
        engine._last_combat_action_time = time.time() - 6.0  # 6 segundos sem ação de combate

        enemy = EnemyTarget(target_id=1, bbox=(600, 200, 100, 100), center=(650, 250), confidence=0.90, name="Boss Lumen")
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=True, target_enemy=enemy)
        bt = BattleTelemetry(in_battle=True)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE, battle_telemetry=bt)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap), \
             patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:
            
            mock_combat.return_value = MagicMock(executed_successfully=False, decision=None)

            engine._execute_single_cycle()

            events = [e for e in self.event_bus.get_recent_events(50) if e.event_type == EventType.BATTLE_EXECUTION_STALLED]
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0].category, "COMBAT")

    # -------------------------------------------------------------------------
    # TEST 8: ACTION VERIFICATION RECEBE FRAME_BEFORE REAL
    # -------------------------------------------------------------------------
    def test_case_8_action_verification_frame_before_passed(self) -> None:
        """_handle_battle_cycle passa frame_before real para process_combat_snapshot."""
        engine = LumenaBotEngine()
        frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.BATTLE)
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=True)

        with patch.object(engine.combat_agent, "process_combat_snapshot") as mock_combat:
            mock_combat.return_value = MagicMock(executed_successfully=True, agent_state=MagicMock(name="VERIFIED"), decision=None)

            engine._handle_battle_cycle(snapshot, frame_before=frame, combat_snapshot=csnap)

            mock_combat.assert_called_once()
            _, kwargs = mock_combat.call_args
            self.assertIn("frame_before", kwargs)
            self.assertTrue(np.array_equal(kwargs["frame_before"], frame))

    # -------------------------------------------------------------------------
    # TEST 9: MODELOS BATTLE_CONTEXT E WORLD_STATE
    # -------------------------------------------------------------------------
    def test_case_9_battle_context_and_world_state_models(self) -> None:
        """Valida integridade e inicialização dos modelos BattleContext e WorldState."""
        bc = BattleContext(
            battle_active=True,
            confidence=0.95,
            player_detected=True,
            enemy_detected=True,
            player_hp=91,
            player_max_hp=113,
            hp_ratio=91.0 / 113.0,
            enemy_hp=100,
            enemy_max_hp=100,
            enemy_hp_ratio=1.0,
            battle_ui_detected=True,
        )
        self.assertTrue(bc.battle_active)
        self.assertAlmostEqual(bc.hp_ratio, 0.8053, places=3)

        ws = WorldState(
            battle_active=False,
            player_detected=True,
            player_hp=113,
            hp_ratio=1.0,
            healing_required=False,
            crystal_detected=False,
            current_state="EXPLORING",
        )
        self.assertFalse(ws.healing_required)
        self.assertEqual(ws.current_state, "EXPLORING")

    # -------------------------------------------------------------------------
    # TEST 10: CONFIGURAÇÕES E CONSTANTES CENTRALIZADAS DE HP
    # -------------------------------------------------------------------------
    def test_case_10_centralized_hp_settings(self) -> None:
        """Valida que os limiares de HP e timeout estão estritamente definidos."""
        self.assertEqual(CRITICAL_HP_RATIO, 0.20)
        self.assertEqual(HEALING_HP_RATIO, 0.40)
        self.assertEqual(COMBAT_ACTION_TIMEOUT, 5.0)

        cfg = BotConfig()
        self.assertEqual(cfg.critical_hp_ratio, 0.20)
        self.assertEqual(cfg.healing_hp_ratio, 0.40)
        self.assertEqual(cfg.combat_action_timeout, 5.0)

    # -------------------------------------------------------------------------
    # TEST 11: INCERTEZA NUNCA PADRONIZA PARA CURA (INCERTEZA != CURA)
    # -------------------------------------------------------------------------
    def test_case_11_uncertain_perception_no_default_heal(self) -> None:
        """Frame vazio ou desconhecido deve entrar em OBSERVING e NUNCA em HEALING."""
        engine = LumenaBotEngine()
        engine._running = True
        engine._paused = False

        snapshot = StateSnapshot(timestamp=time.time(), screen_state=AgentState.UNKNOWN_STATE)
        csnap = CombatSnapshot(timestamp=time.time(), in_battle=False, target_enemy=None)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        with patch.object(engine.screen_capture, "capture_frame", return_value=(frame, time.time())), \
             patch.object(engine.state_classifier, "classify_frame", return_value=snapshot), \
             patch.object(engine.combat_vision, "analyze_frame", return_value=csnap):

            engine._execute_single_cycle()

            self.assertEqual(engine.fsm.current_state, BotState.OBSERVING)
            self.assertNotEqual(engine.health_monitor["state"], "HEALING")
            self.assertNotEqual(engine.health_monitor["current_goal"], "HEAL")

    # -------------------------------------------------------------------------
    # TEST 12: ANNOTATED FRAME ANOTA JOGADOR, INIMIGO E HABILIDADES
    # -------------------------------------------------------------------------
    def test_case_12_annotated_frame_visualization(self) -> None:
        """_generate_annotated_frame insere caixas e tags semânticas para a GUI."""
        engine = LumenaBotEngine()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        snapshot = StateSnapshot(
            timestamp=time.time(),
            screen_state=AgentState.BATTLE,
            ui_elements={"fight_btn": UIElement(name="fight_btn", bounding_box=(500, 500, 100, 40), confidence=0.90, center=(550, 520))},
        )
        enemy = EnemyTarget(target_id=1, bbox=(800, 200, 120, 120), center=(860, 260), name="Enemy", confidence=0.88)
        csnap = CombatSnapshot(
            timestamp=time.time(),
            in_battle=True,
            target_enemy=enemy,
            available_skills=[SkillSlot(id="s1", index=1, slot_index=1, screen_x=400, screen_y=600, width=50, height=50, available=True)],
        )

        annotated = engine._generate_annotated_frame(frame, snapshot, combat_snapshot=csnap)
        self.assertEqual(annotated.shape, frame.shape)
        # O frame anotado deve ter pixels modificados
        self.assertTrue(np.any(annotated > 0))

    # -------------------------------------------------------------------------
    # TEST 13: STATE CLASSIFIER HIERARQUIA DE OVERWORLD
    # -------------------------------------------------------------------------
    def test_case_13_state_classifier_hierarchy(self) -> None:
        """StateClassifier determina estados semânticos de overworld sem forçar cura."""
        classifier = StateClassifier()
        # Frame de caminho/estrada com densidade zero de grama -> SEARCHING_FARM
        road_frame = np.full((360, 640, 3), 100, dtype=np.uint8)
        snap = classifier.classify_frame(road_frame, timestamp=time.time())
        self.assertEqual(snap.screen_state, AgentState.SEARCHING_FARM)

    # -------------------------------------------------------------------------
    # TEST 14: TELEMETRIA EM TEMPO REAL NO HEALTH_MONITOR
    # -------------------------------------------------------------------------
    def test_case_14_health_monitor_telemetry_fields(self) -> None:
        """HealthMonitor expõe todas as variáveis operacionais necessárias para observabilidade."""
        engine = LumenaBotEngine()
        hm = engine.health_monitor

        required_keys = [
            "battle_status", "enemy_detected", "player_hp", "hp_ratio",
            "healing_required", "crystal_search", "crystal_search_blocked",
            "skills_detected", "skills_available", "selected_skill",
            "state", "current_goal", "current_target", "target_type",
            "foreground", "canvas", "input_dispatched", "visual_delta",
        ]

        for k in required_keys:
            self.assertIn(k, hm, f"Chave obrigatória ausente no health_monitor: {k}")


if __name__ == "__main__":
    unittest.main()
