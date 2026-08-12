import pytest
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


def test_lumen_properties_and_methods():
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

    assert lumen.name == "GrassBro"
    assert lumen.element == Element.GRASS
    assert lumen.is_alive() is True
    assert lumen.total_hp > 0
    assert lumen.hp_percentage == 1.0

    # Test damage and faint
    damage_dealt = lumen.take_damage(lumen.total_hp + 10)
    assert damage_dealt == lumen.total_hp
    assert lumen.current_hp == 0
    assert lumen.is_fainted is True
    assert lumen.is_alive() is False

    # Test heal and restore
    lumen.heal(10)
    assert lumen.current_hp == 10
    assert lumen.is_fainted is False
    assert lumen.is_alive() is True

    # Test skill use and restore
    assert skill.use() is True
    assert skill.current_pp == 19
    lumen.restore_all()
    assert lumen.current_hp == lumen.total_hp
    assert skill.current_pp == 20


def test_agent_telemetry_and_state_models():
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
    assert move_info.current_pp == 10

    telemetry = BattleTelemetry(
        in_battle=True,
        player_hp_pct=0.85,
        enemy_hp_pct=0.40,
        player_lumen_name="Infernus",
        enemy_lumen_name="Aquashell",
        available_moves=[move_info],
        victory_detected=False,
    )
    assert telemetry.in_battle is True

    snapshot = StateSnapshot(
        timestamp=1000.0,
        screen_state=AgentState.BATTLE,
        battle_telemetry=telemetry,
        crystal_detected=False,
        grass_density=0.75,
    )
    assert snapshot.screen_state == AgentState.BATTLE
    assert snapshot.grass_density == 0.75

    action = AtomicAction(
        action_type="KEY_PRESS",
        target=MoveDirection.UP.value,
        duration=0.2,
        expected_feedback="SCENE_SHIFT",
    )
    plan = ActionPlan(actions=[action], description="Step North")
    assert len(plan.actions) == 1
    assert plan.actions[0].target == "w"


def test_team_status_and_member_state():
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
    assert len(team.members) == 2
    assert team.team_alive_count == 1
