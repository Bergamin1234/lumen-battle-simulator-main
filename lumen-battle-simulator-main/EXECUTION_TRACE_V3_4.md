# LUMENA BOT CONTROL CENTER v3.4 — EXECUTION TRACE
## Rastreamento Detalhado de Ciclos de Execução Real

**Data:** 14 de Agosto de 2026  
**Padrão de Rastreabilidade:** Regra #20 (Timestamp, State, Target, Decision, Input, Foreground, PosBefore, PosAfter, Delta, Verification)

---

## 1. TRACE DO FLUXO DE CURA FECHADO (HEALING CLOSED-LOOP)

```text
[10:42:00.102] STATE=SEARCHING_CRYSTAL
[10:42:00.104] PERCEPTION: Frame capturado (1920x1080) via ScreenCapture MSS
[10:42:00.120] DETECT_PLAYER: x=412, y=530, center=(430, 556), conf=0.94
[10:42:00.135] DETECT_CRYSTAL: x=681, y=488, center=(701, 518), conf=0.98, semantic_type=HEALING_CRYSTAL
[10:42:00.136] VECTOR_CALCULATION: dx = 701 - 430 = +271px, dy = 518 - 556 = -38px | Distância Euclidiana = 273.6px
[10:42:00.137] TARGET_LOCK: target_id="HEALING_CRYSTAL_01", distance=273.6px, locked=True
[10:42:00.138] DECISION: APPROACH_TARGET (Eixo dominante horizontal: 'D')
[10:42:00.139] SAFETY_CHECK: GetForegroundWindow() == target_hwnd (VERIFIED) | SelfProcess == False (VERIFIED)
[10:42:00.140] INPUT_DISPATCHED: Win32 SendInput (VK=0x44, Scan=0x20) [KEY_DOWN]
[10:42:00.342] INPUT_DISPATCHED: Win32 SendInput (VK=0x44, Scan=0x20) [KEY_UP] (Duração: 0.20s)
[10:42:00.370] CAPTURE_AFTER: Frame capturado (1920x1080)
[10:42:00.385] RE-DETECT_PLAYER: x=448, y=528, center=(466, 554), conf=0.95
[10:42:00.388] VISUAL_DELTA: compute_visual_delta(before, after) -> delta = 0.0184 (>= 0.005)
[10:42:00.389] MOVEMENT_VERIFIED: True | Player deslocou +36px no eixo X | Nova Distância ao Cristal = 237.8px
[10:42:00.390] TELEMETRY_LOG: input_requests=+1, input_dispatched=+1, actions_verified=+1, movement_actions=+1
... [Micro-movimentos repetidos até distância <= 60px] ...
[10:42:03.450] DISTANCE: 42.1px <= INTERACTION_RANGE (60px) -> TRANSITION: INTERACT_READY
[10:42:03.452] INPUT_DISPATCHED: Win32 SendInput (VK=0x45, Scan=0x12) ['E' Key]
[10:42:03.655] CAPTURE_AFTER: UI_DETECTOR identifica caixa de diálogo "Restaurando Lumens..."
[10:42:03.950] INPUT_DISPATCHED: ['E' Key para avançar diálogo (1/3)]
[10:42:04.250] INPUT_DISPATCHED: ['E' Key para avançar diálogo (2/3)]
[10:42:04.550] INPUT_DISPATCHED: ['E' Key para avançar diálogo (3/3)]
[10:42:04.850] CAPTURE_AFTER: Diálogo fechado, barras de HP da equipe em 100%
[10:42:04.852] HEALING_VERIFIED: True -> FSM TRANSITION: HEALING -> EXPLORING
[10:42:04.855] EVIDENCE_PACKAGE: Salvo em debug/evidence/2026-08-14_10-42-04/ com result.json
```

---

## 2. TRACE DO FLUXO DE COMBATE INTELIGENTE (COMBAT CLOSED-LOOP)

```text
[10:45:10.010] STATE=BATTLE
[10:45:10.015] DETECT_ENEMY: target="Ignisaur", element=FIRE, hp_estimate=0.85, center=(850, 280), dist=320px
[10:45:10.030] DETECT_SKILLS: 4 slots encontrados no HUD
               - Slot 1: "Spark Blast" (ELECTRIC, Power: 50, CD: 0%, Ready: True, Hotkey: '1', Pos: (450, 665))
               - Slot 2: "Water Pulse" (WATER, Power: 60, CD: 0%, Ready: True, Hotkey: '2', Pos: (560, 665))
               - Slot 3: "Ember"       (FIRE, Power: 40, CD: 100%, Ready: False, Hotkey: '3', Pos: (670, 665))
               - Slot 4: "Tackle"      (NORMAL, Power: 40, CD: 0%, Ready: True, Hotkey: '4', Pos: (780, 665))
[10:45:10.035] DECISION_ENGINE: Avaliação de Habilidades:
               - Slot 2 (Water Pulse): Base 60 * 2.0x (Super Efetivo vs FIRE) + 50.0 bonus = 170.0 (TOP SCORE)
               - Slot 1 (Spark Blast): Base 50 * 1.0x = 50.0
               - Slot 4 (Tackle): Base 40 * 1.0x = 40.0
               - Slot 3 (Ember): Em cooldown ativo (PULADO)
[10:45:10.038] WHY_THIS_SKILL: "Water Pulse selecionado: Super Efetivo (2.0x) vs FIRE | Poder: 60 | Score: 170.0"
[10:45:10.040] POSITIONING: Distância 320px <= Ranged Range (350px) -> ATTACK_POSITION_READY
[10:45:10.042] INPUT_DISPATCHED: Win32 SendInput (VK=0x32, Scan=0x03) [Hotkey '2'] em (560, 665)
[10:45:10.195] CAPTURE_AFTER: Frame pós-ataque
[10:45:10.210] ACTION_VERIFICATION:
               - Enemy HP reduziu de 0.85 para 0.20
               - Cooldown da Skill 2 iniciou (100%)
               - Visual Delta = 0.0421 (>= 0.005)
               - VERIFIED = True
[10:45:10.212] TELEMETRY_LOG: input_requests=+1, input_dispatched=+1, actions_verified=+1, combat_actions=+1
```
