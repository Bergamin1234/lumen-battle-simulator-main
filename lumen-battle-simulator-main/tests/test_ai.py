import pytest
from src.models.lumen import Lumen, Skill, LumenSpecies
from src.models.enums import Element, MoveCategory, CodeTraitGrade
from src.ai.strategy import AggressiveStrategy, DefensiveStrategy, BalancedStrategy
from src.ai.q_learning import QLearningAgent


@pytest.fixture
def sample_skills():
    s1 = Skill(
        name="Ataque Leve",
        element=Element.NORMAL,
        category=MoveCategory.PHYSICAL,
        power=20,
        accuracy=1.0,
        max_pp=15,
        current_pp=15,
        energy_cost=5,
    )
    s2 = Skill(
        name="Golpe Pesado",
        element=Element.FIRE,
        category=MoveCategory.SPECIAL,
        power=60,
        accuracy=0.8,
        max_pp=5,
        current_pp=5,
        energy_cost=15,
    )
    return [s1, s2]


@pytest.fixture
def sample_lumen(sample_skills):
    species = LumenSpecies(
        codex_number=1,
        species_name="TestLumen",
        primary_type=Element.FIRE,
        base_hp=50,
        base_attack=50,
        base_defense=50,
        base_sp_attack=50,
        base_sp_defense=50,
        base_speed=50,
    )
    return Lumen(
        id=1,
        nickname="Tester",
        species=species,
        code_trait=CodeTraitGrade.C,
        skills=sample_skills,
    )


def test_aggressive_strategy_selects_highest_power(sample_lumen):
    strategy = AggressiveStrategy()
    chosen_skill = strategy.choose_action(sample_lumen, sample_lumen)
    assert chosen_skill is not None
    assert chosen_skill.name == "Golpe Pesado"


def test_defensive_strategy_selects_lowest_cost(sample_lumen):
    strategy = DefensiveStrategy()
    chosen_skill = strategy.choose_action(sample_lumen, sample_lumen)
    assert chosen_skill is not None
    assert chosen_skill.name == "Ataque Leve"


def test_q_learning_agent_init():
    agent = QLearningAgent(actions_count=2)
    assert agent.actions_count == 2
    assert len(agent.q_table) == 0
