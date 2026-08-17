# LUMENA BOT CONTROL CENTER v4.0 — EXECUTION TRACE & SYNTHETIC HARNESS REPORT
**Data**: 14 de Agosto de 2026  
**Simulador**: `tests/harness/synthetic_game_simulator.py` (35 Frames & 7 Fases de Estado)

---

## 1. Linha do Tempo de Transições da FSM

```mermaid
graph TD
    IDLE[IDLE] -->|Start Engine| EXPLORING[EXPLORING]
    EXPLORING -->|Arena Detectada (FIGHT Button)| ENGAGING_BATTLE[ENGAGING_BATTLE / BATTLE]
    ENGAGING_BATTLE -->|FIGHT Click + Skill Selected| TURN_LOCK[BATTLE_WAITING_TURN_RESOLUTION]
    TURN_LOCK -->|Turn Animation Resolves| MODAL[BATTLE_MODAL_DISMISSAL]
    MODAL -->|Space/Click Dismissal| POST_EVAL[POST_BATTLE_EVALUATION / OVERWORLD]
    POST_EVAL -->|HP <= 40%| HEALING[HEALING ROUTINE (Cristal)]
    POST_EVAL -->|HP > 40%| EXPLORING
    HEALING -->|Cristal Interacted + HP 100%| EXPLORING
    EXPLORING -->|F12 / Safe Stop| SAFE_STOP[SAFE_STOP]
```

---

## 2. Rastreamento Passo a Passo do Ciclo Completo de Simulação

| Passo (#) | Fase do Jogo | Estado da FSM | Ação Disparada | Validação Visual (Delta) | Resultado |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1-5** | OVERWORLD | `EXPLORING` | `KEY_PRESS('W')` | Δ = 0.0142 (Cenário Moveu) | `VERIFIED` |
| **6-8** | BATTLE_TRANSITION | `ENGAGING_BATTLE` | `WAIT_VISUAL_CONDITION` | Transição de Arena Detectada | `CONFIRMED` |
| **9-12** | BATTLE_IDLE | `BATTLE` | `CLICK(Fight Button)` | Δ = 0.0381 (Menu de Skills Aberto) | `VERIFIED` |
| **13-18** | SKILL_SELECTION | `BATTLE` | `CLICK(Skill #2 / #1)` | Δ = 0.0412 (Ataque Enviado) | `VERIFIED` |
| **19-21** | TURN_RESOLUTION | `WAITING_TURN_RESOLUTION` | `SUPPRESS_INPUTS` | Animação em Execução | `LOCKED` |
| **22-25** | VICTORY_MODAL | `MODAL_DISMISSAL` | `KEY_PRESS('SPACE')` | Δ = 0.0520 (Modal Fechado) | `DISMISSED` |
| **26-28** | OVERWORLD (LOW HP) | `POST_BATTLE_EVALUATION` | `EVALUATE_HP(30%)` | HP Crítico Detectado (<= 40%) | `TRIGGER_HEAL` |
| **29-32** | APPROACH_CRYSTAL | `HEALING` | `CLICK_INTERACT('E')` | Δ = 0.0195 (Aproximação Tática) | `ALIGNED` |
| **33-35** | HEALING_VERIFIED | `EXPLORING` | `EVALUATE_HP(100%)` | HP Totalmente Restaurado | `WORLD_RESUMED` |

---

## 3. Registros de Cooldown e Rotação Multi-Turno

- **Turno 1**: Selecionada Habilidade #1 (Ataque Primário). Registrado cooldown de 2 turnos.
- **Turno 2**: Habilidade #1 bloqueada em cache -> Rotação dinâmica seleciona Habilidade #2. Registrado cooldown de 2 turnos.
- **Turno 3**: Habilidade #1 liberada de cooldown -> Retorna à Habilidade #1.
- **Fallback Guard**: Caso todas as habilidades estejam em recarga, o motor dispara o slot básico garantido sem travar o loop de combate.
