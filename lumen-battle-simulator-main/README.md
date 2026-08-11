# Lumen Battle Simulator

Simulador de batalhas táticas entre criaturas autônomas (Lumens) utilizando Python 3.12, Arquitetura Limpa e Inteligência Artificial.

## Arquitetura das Classes

```text
  +---------------+             +------------------+
  |    Lumen      | 1 ------- * |      Skill       |
  +---------------+             +------------------+
  | - id          |             | - power          |
  | - element     |             | - energy_cost    |
  | - stats       |             +------------------+
  +---------------+
          | 1
          |
          | *
  +---------------+             +------------------+
  | BattleEngine  | ----------->|    BaseStrategy  |
  +---------------+             +------------------+
  | - run()       |             | + choose_action()|
  +---------------+             +------------------+
                                         ^
                                         |
                       +-----------------+-----------------+
                       |                 |                 |
             AggressiveStrategy  DefensiveStrategy  BalancedStrategy