import unittest
from src.models.lumen import (
    Lumen,
    Skill,
    LumenSpecies,
    AtomicAction,
    ActionPlan,
    UIElement,
    MoveSlotInfo,
    BattleTelemetry,
    StateSnapshot,
    LumenMemberState,
    TeamStatus,
)
from src.models.enums import (
    Element,
    MoveCategory,
    CodeTraitGrade,
    StatusEffect,
    AgentState,
    MoveDirection,
)


class TestModelsAndTelemetry(unittest.TestCase):
    def test_lumen_properties_and_methods(self):
        species = LumenSpecies(
            codex_number=1,
            species_name="Sproutling",
            primary_type=Element.GRASS,
            secondary_type=Element.POISON,
            base_hp=45,
            base_attack=49,
            base_defense=49,
            base_sp_attack=65,
            base_sp_defense=65,
            base_speed=45,
            evolution_level=16,
        )
        skill = Skill(
            name="Vine Whip",
            element=Element.GRASS,
            category=MoveCategory.PHYSICAL,
            power=45,
            accuracy=1.0,
            max_pp=20,
            current_pp=20,
        )
        lumen = Lumen(
            id=1,
            nickname="GrassBro",
            species=species,
            level=5,
            code_trait=CodeTraitGrade.B,
            skills=[skill],
        )

        self.assertEqual(lumen.name, "GrassBro")
        self.assertEqual(lumen.element, Element.GRASS)
        self.assertTrue(lumen.is_alive())
        self.assertGreater(lumen.total_hp, 0)
        self.assertEqual(lumen.hp_percentage, 1.0)

        # Test damage and faint
        damage_dealt = lumen.take_damage(lumen.total_hp + 10)
        self.assertEqual(damage_dealt, lumen.total_hp)
        self.assertEqual(lumen.current_hp, 0)
        self.assertTrue(lumen.is_fainted)
        self.assertFalse(lumen.is_alive())

        # Test heal and restore
        lumen.heal(10)
        self.assertEqual(lumen.current_hp, 10)
        self.assertFalse(lumen.is_fainted)
        self.assertTrue(lumen.is_alive())

        # Test skill use and restore
        self.assertTrue(skill.use())
        self.assertEqual(skill.current_pp, 19)
        lumen.restore_all()
        self.assertEqual(lumen.current_hp, lumen.total_hp)
        self.assertEqual(skill.current_pp, 20)

    def test_agent_telemetry_and_state_models(self):
        element = Element.FIRE
        move_info = MoveSlotInfo(
            slot_index=0,
            name="Flamethrower",
            current_pp=10,
            max_pp=15,
            element=element,
            is_available=True,
            power=90,
            button_rect=(100, 200, 50, 30),
        )
        self.assertEqual(move_info.current_pp, 10)

        telemetry = BattleTelemetry(
            in_battle=True,
            player_hp_pct=0.85,
            enemy_hp_pct=0.40,
            player_lumen_name="Infernus",
            enemy_lumen_name="Aquashell",
            available_moves=[move_info],
            victory_detected=False,
        )
        self.assertTrue(telemetry.in_battle)

        snapshot = StateSnapshot(
            timestamp=1000.0,
            screen_state=AgentState.BATTLE,
            battle_telemetry=telemetry,
            crystal_detected=False,
            grass_density=0.75,
        )
        self.assertEqual(snapshot.screen_state, AgentState.BATTLE)
        self.assertEqual(snapshot.grass_density, 0.75)

        action = AtomicAction(
            action_type="KEY_PRESS",
            target=MoveDirection.UP.value,
            duration=0.2,
            expected_feedback="SCENE_SHIFT",
        )
        plan = ActionPlan(actions=[action], description="Step North")
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].target, "w")

    def test_team_status_and_member_state(self):
        member1 = LumenMemberState(
            slot=0,
            nickname="Lead",
            species_name="Infernus",
            primary_element=Element.FIRE,
            current_hp=80,
            max_hp=100,
            hp_percentage=0.8,
            is_fainted=False,
            is_active=True,
        )
        member2 = LumenMemberState(
            slot=1,
            nickname="Sub",
            species_name="Aquashell",
            primary_element=Element.WATER,
            current_hp=0,
            max_hp=90,
            hp_percentage=0.0,
            is_fainted=True,
            is_active=False,
        )
        team = TeamStatus(
            members=[member1, member2],
            active_slot=0,
            total_usable_pp=25,
            team_alive_count=1,
            requires_immediate_heal=False,
        )
        self.assertEqual(len(team.members), 2)
        self.assertEqual(team.team_alive_count, 1)


if __name__ == "__main__":
    unittest.main()

