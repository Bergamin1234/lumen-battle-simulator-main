# EXECUTION TRACE — LUMENA BOT v3.8
## RASTREAMENTO DO CICLO COMPLETO DE COMBATE DETERMINÍSTICO

---

### DIAGRAMA DE SEQUÊNCIA v3.8

```mermaid
sequenceDiagram
    autonumber
    participant Screen as ScreenCapture
    participant Engine as LumenaBotEngine
    participant BUI as BattleUIDetector
    participant Ctrl as BattleUIController
    participant Guard as InputDispatcherGuard
    participant Win32 as Win32 (SendInput)
    participant Game as Chrome / WebGL

    Note over Screen,Game: 1. DETECÇÃO & ABERTURA DE MENU DE HABILIDADES
    Screen->>Engine: capture_frame()
    Engine->>BUI: analyze_battle_ui(frame)
    BUI-->>Engine: BattleUIDetectionResult(fight_button=PRESENT)
    Engine->>Ctrl: click_fight(frame)
    Ctrl->>Guard: validate_input_guard(fight_x, fight_y)
    Guard-->>Ctrl: Validated (Inside Canvas Bounds)
    Ctrl->>Win32: click(fight_x, fight_y)
    Win32->>Game: Mouse Down/Up
    Ctrl-->>Engine: fight_dispatched=True

    Note over Screen,Game: 2. SELEÇÃO PRIMÁRIA & DISPARO DE HABILIDADE
    Screen->>Engine: capture_frame()
    Engine->>Ctrl: find_available_skills(frame)
    Ctrl-->>Engine: [SkillSlot_1, SkillSlot_2, ...]
    Engine->>Ctrl: select_primary_skill(skills) -> SkillSlot_1
    Engine->>Ctrl: execute_skill(SkillSlot_1, frame)
    Ctrl->>Guard: validate_input_guard(skill_x, skill_y)
    Guard-->>Ctrl: Validated
    Ctrl->>Win32: press_key("1")
    Win32->>Game: WM_KEYDOWN (ScanCode=0x02)
    Ctrl-->>Engine: skill_dispatched=True (Turn Lock Activated)

    Note over Screen,Game: 3. TURN LOCK & SUPRESSÃO DE INPUTS (ANIMATION WAITING)
    loop Resolução de Turno
        Screen->>Engine: capture_frame()
        Engine->>Ctrl: process_turn_resolution_check(frame)
        alt Animação em Andamento
            Ctrl-->>Engine: is_waiting=True (Inputs Suppressed)
        else Controles Reapareceram
            Ctrl-->>Engine: is_waiting=False, Event(TURN_RESOLUTION_COMPLETED)
        else Batalha Encerrou
            Ctrl-->>Engine: is_waiting=False, Event(BATTLE_EXIT_DETECTED)
        end
    end

    Note over Screen,Game: 4. TRANSIÇÃO DE SAÍDA (BATTLE -> WORLD)
    Engine->>Ctrl: is_battle_finished(frame)
    Ctrl-->>Engine: True, Event(WORLD_RESUMED)
    Engine->>Engine: fsm.transition_to(BotState.EXPLORING)
    Note over Engine: Navigation AI Resumed / Crystal Detection Unblocked IF HP <= 40%
```

---

### TRACE DE EVENTOS GERADOS NO CICLO

1. `BATTLE_UI_DETECTED` $\rightarrow$ `BATTLE_UI_CONFIRMED` $\rightarrow$ `CRYSTAL_SEARCH_BLOCKED`
2. `FIGHT_DETECTED` $\rightarrow$ `FIGHT_CLICK_REQUESTED` $\rightarrow$ `FIGHT_CLICK_DISPATCHED` $\rightarrow$ `FIGHT_CLICK_VERIFIED`
3. `SKILL_UI_DETECTED` $\rightarrow$ `SKILL_SELECTED` $\rightarrow$ `SKILL_ACTION_REQUESTED` $\rightarrow$ `SKILL_ACTION_DISPATCHED`
4. `BATTLE_WAITING_TURN_RESOLUTION` (Turn Lock ativo)
5. `TURN_RESOLUTION_COMPLETED` (quando animação resolve)
6. `BATTLE_EXIT_DETECTED` $\rightarrow$ `BATTLE_FINISHED` $\rightarrow$ `WORLD_RESUMED`
