import unittest
import numpy as np

from src.models.enums import Element
from src.models.combat_vision import SkillSlot, EnemyTarget, CombatSnapshot, CombatDecision
from src.perception.combat_vision import CombatVisionAnalyzer
from src.combat.decision_engine import CombatDecisionEngine
from src.combat.skill_executor import SkillExecutor
from src.core.event_bus import EventBus, EventType


class TestCombatVision(unittest.TestCase):
    """Testes unitários determinísticos para o sistema de combate visual dinâmico."""

    def setUp(self):
        self.analyzer = CombatVisionAnalyzer()
        self.engine = CombatDecisionEngine()
        self.executor = SkillExecutor()
        self.bus = EventBus()
        self.bus.clear()

    def test_dynamic_skill_slots_generation(self):
        """Valida que o analisador detecta e sintetiza múltiplos slots dinâmicos (N >= 4)."""
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        snapshot = self.analyzer.analyze_frame(frame)

        self.assertIsNotNone(snapshot)
        self.assertGreaterEqual(len(snapshot.available_skills), 4)
        for s in snapshot.available_skills:
            self.assertGreater(s.width, 0)
            self.assertGreater(s.height, 0)
            self.assertIsNotNone(s.center_x)
            self.assertIsNotNone(s.center_y)

    def test_elemental_weakness_prioritization(self):
        """Valida que habilidades com super-efetividade (ex: Água vs Fogo) recebem prioridade máxima."""
        enemy = EnemyTarget(
            target_id=1,
            bbox=(800, 200, 200, 200),
            center=(900, 300),
            confidence=0.95,
            hp_estimate=1.0,
            distance=200.0,
            element=Element.FIRE,
            weakness=Element.WATER,
        )

        skill_water = SkillSlot(
            slot_index=1,
            screen_x=100,
            screen_y=600,
            width=60,
            height=60,
            center_x=130,
            center_y=630,
            available=True,
            cooldown=0.0,
            skill_name="WaterPulse",
            element=Element.WATER,
            power=60,
            range_type="RANGED",
        )

        skill_normal = SkillSlot(
            slot_index=2,
            screen_x=180,
            screen_y=600,
            width=60,
            height=60,
            center_x=210,
            center_y=630,
            available=True,
            cooldown=0.0,
            skill_name="Tackle",
            element=Element.NORMAL,
            power=40,
            range_type="MELEE",
        )

        snapshot = CombatSnapshot(
            timestamp=1000.0,
            in_battle=True,
            target_enemy=enemy,
            available_skills=[skill_normal, skill_water],
        )

        decision: CombatDecision = self.engine.evaluate_combat_snapshot(snapshot)
        self.assertEqual(decision.action_type, "USE_SKILL")
        self.assertIsNotNone(decision.selected_skill)
        self.assertEqual(decision.selected_skill.skill_name, "WaterPulse")
        self.assertIn("Super Efetivo", decision.reason)

    def test_cooldown_rejection(self):
        """Valida que habilidades em cooldown ativo não são selecionadas pelo motor."""
        enemy = EnemyTarget(
            target_id=1,
            bbox=(800, 200, 200, 200),
            center=(900, 300),
            element=Element.FIRE,
        )

        skill_water_on_cd = SkillSlot(
            slot_index=1,
            screen_x=100,
            screen_y=600,
            width=60,
            height=60,
            center_x=130,
            center_y=630,
            available=False,
            cooldown=4.5,
            skill_name="WaterPulse",
            element=Element.WATER,
            power=60,
        )

        skill_normal_available = SkillSlot(
            slot_index=2,
            screen_x=180,
            screen_y=600,
            width=60,
            height=60,
            center_x=210,
            center_y=630,
            available=True,
            cooldown=0.0,
            skill_name="Tackle",
            element=Element.NORMAL,
            power=40,
        )

        snapshot = CombatSnapshot(
            timestamp=1000.0,
            in_battle=True,
            target_enemy=enemy,
            available_skills=[skill_water_on_cd, skill_normal_available],
        )

        decision: CombatDecision = self.engine.evaluate_combat_snapshot(snapshot)
        self.assertEqual(decision.action_type, "USE_SKILL")
        self.assertEqual(decision.selected_skill.skill_name, "Tackle")

    def test_skill_executor_event_emission(self):
        """Valida que o SkillExecutor despacha eventos corretos para o EventBus."""
        skill = SkillSlot(
            slot_index=3,
            screen_x=300,
            screen_y=600,
            width=60,
            height=60,
            center_x=330,
            center_y=630,
            available=True,
            hotkey="3",
            skill_name="ThunderShock",
        )

        self.executor.execute_skill(skill)
        recent = self.bus.get_recent_events(10, category="COMBAT")
        self.assertTrue(any(e.event_type == EventType.BATTLE_ACTION_SELECTED for e in recent))


if __name__ == "__main__":
    unittest.main()
