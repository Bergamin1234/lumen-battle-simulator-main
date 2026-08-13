# EXECUTION TRACE — LUMENA BOT CONTROL CENTER v3.2
## Rastreabilidade de Execução em Malha Fechada (Closed-Loop Real-World Execution)

### 1. Cadeia de Execução Formal (Closed Loop)
```
PERCEPÇÃO REAL
    ↓ (ScreenCapture MSS / LandmarkDetector / CombatVisionAnalyzer)
DECISÃO REAL
    ↓ (CombatDecisionEngine / RouteManager / HealingController)
AÇÃO REAL
    ↓ (ActionExecutor / InputController / SafetyGuard)
INPUT REAL
    ↓ (Win32 SendInput Hardware Scancodes / DirectInput)
MUDANÇA REAL NA TELA
    ↓ (Deslocamento de Coordenadas / Redução de HP / Mudança de Cooldown)
VERIFICAÇÃO VISUAL
    ↓ (Frame Difference / Delta Visual > 0.005 / Cooldown Confirmado)
PRÓXIMO ESTADO
    ↓ (BotStateMachine Transition)
```

---

### 2. Trace do Ciclo de Cura no Cristal Azul (`HEALING_CRYSTAL`)
1. **Perception**:
   - `LandmarkDetector.detect_crystal(frame)` executa segmentação HSV `[80, 60, 90]` a `[135, 255, 255]`.
   - Classifica semântica com `semantic_type = "HEALING_CRYSTAL"` e calcula vetor `(dx, dy)`.
2. **Decision**:
   - `HealingController.step(snapshot, frame)` avalia distância euclidiana $d = \sqrt{dx^2 + dy^2}$.
   - Se $d > 80.0\text{px}$: Transiciona para `APPROACH_TARGET`, calcula eixo dominante e determina tecla direcional (`W`, `A`, `S` ou `D`).
   - Se $d \le 80.0\text{px}$ ou prompt detectado: Transiciona para `INTERACTING` e despacha tecla de interação (`E` / `Space`).
3. **Execution & Input**:
   - `InputController.press_key(key, duration=0.20)` foca a janela Chrome/Lumena (`AttachThreadInput` + `SetForegroundWindow`).
   - Despacha `KEY_DOWN` via Win32 Scancode com timing humano de 200ms e garante `KEY_UP`.
4. **Verification**:
   - Mede se a distância diminuiu ou se a tela de diálogo/cura foi confirmada.
   - Quando concluído, transiciona FSM para `BotState.EXPLORING` e registra `last_verified_action = "HEALING_VERIFIED"`.

---

### 3. Trace do Ciclo de Combate Dinâmico
1. **Perception**:
   - `CombatVisionAnalyzer.detect_skill_slots(frame)` reconhece $N$ slots dinâmicos no HUD, caixas delimitadoras e cooldowns em tempo real.
   - `CombatVisionAnalyzer.detect_enemies(frame)` localiza o inimigo ativo e calcula vetor de distância em relação ao jogador.
2. **Decision**:
   - `CombatDecisionEngine.evaluate_combat_snapshot(snapshot)` avalia a fraqueza elementar, cooldown e alcance efetivo (`positioning_ctrl.evaluate_positioning`).
   - Se fora de alcance: Despacha `APPROACH_TARGET` ou `MAINTAIN_DISTANCE`.
   - Se em alcance: Seleciona a melhor habilidade disponível e gera `CombatDecision(action_type="USE_SKILL")`.
3. **Execution & Input**:
   - `SkillExecutor.execute_skill(skill)` despacha a tecla de atalho (`1`–`9`) ou clique nas coordenadas centrais do slot.
4. **Verification**:
   - Captura frame pós-ataque e compara `visual_delta`. Se a habilidade entrar em cooldown ou o HP do inimigo sofrer alteração, confirma `BATTLE_ACTION_EXECUTED`.
   - Se o frame não sofrer alteração, emite `EventType.ACTION_UNCONFIRMED` e penaliza a habilidade no próximo turno.

---

### 4. Watchdog & Execution Health Monitor
- Se o bot permanecer por mais de 15 segundos em loop de observação sem nenhuma ação física despachada, o Watchdog emite `EventType.EXECUTION_STALLED`.
- A GUI atualiza em tempo real o painel `REAL EXECUTION HEALTH MONITOR` (Perception, Target, Positioning, Focus, Input, Action, Verification).
