# Arquitetura do Sistema - Lumen Battle Simulator

Este projeto adota os princípios de **Clean Architecture** e **SOLID** para garantir modularidade, isolamento de regras de negócio e testabilidade sem dependência de persistência externa.

## Camadas da Aplicação

1. **Models (`src/models/`)**: Entidades de domínio puras (`Lumen`, `Skill`, `LumenSpecies`) e enums.
2. **Core (`src/core/`)**: Motor do simulador. Contém fórmulas matemáticas de dano, cálculo de fraquezas elementais (18 tipos) e execução da batalha em turnos.
3. **AI (`src/ai/`)**: Estratégias de tomada de decisão baseadas no padrão Strategy (`Aggressive`, `Defensive`, `Balanced`, `Random`) e aprendizado por reforço (`QLearningAgent`).
4. **Services (`src/services/`)**: Casos de uso do sistema, como simulador massivo em lote e progressão de nível.
5. **UI (`src/ui/`)**: Interface CLI simples para navegação do usuário.

## Diagrama da Batalha em Memória

```text
[ CLI / Main ] ──> [ MassSimulator ] ──> [ BattleEngine ]
                                                │
                                 ┌──────────────┴──────────────┐
                                 ▼                             ▼
                          [ Lumen Models ]            [ AI Strategies ]





---

**`tests/test_ai.py`**

```python
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
        current_pp=15
    )
    s2 = Skill(
        name="Golpe Pesado", 
        element=Element.FIRE, 
        category=MoveCategory.SPECIAL, 
        power=60, 
        accuracy=0.8, 
        max_pp=5, 
        current_pp=5
    )
    return [s1, s2]

@pytest.fixture
def sample_lumen(sample_skills):
    species = LumenSpecies(
        codex_number=1,
        species_name="TestLumen",
        primary_type=Element.FIRE,
        base_hp=50, base_attack=50, base_defense=50,
        base_sp_attack=50, base_sp_defense=50, base_speed=50
    )
    return Lumen(
        id=1, 
        nickname="Tester", 
        species=species, 
        code_trait=CodeTraitGrade.C, 
        skills=sample_skills
    )

def test_aggressive_strategy_selects_highest_power(sample_lumen):
    strategy = AggressiveStrategy()
    chosen_skill = strategy.choose_action(sample_lumen, sample_lumen)
    assert chosen_skill.name == "Golpe Pesado"

def test_q_learning_agent_init():
    agent = QLearningAgent(actions_count=2)
    assert agent.actions_count == 2
    assert len(agent.q_table) == 0