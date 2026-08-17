# EXECUTION TRACE — LUMENA BOT v3.9
## RASTREAMENTO DETALHADO DO CICLO DE COMBATE & TRATAMENTO DE MODAIS

---

### DIAGRAMA DE SEQUÊNCIA v3.9

```mermaid
sequenceDiagram
    autonumber
    participant Screen as ScreenCapture
    participant Engine as LumenaBotEngine
    participant Detector as BattleUIDetector
    participant Controller as BattleUIController
    participant Modal as ModalEngine
    participant Win32 as Win32 SendInput
    participant Killswitch as EmergencyKillswitch

    Note over Screen,Killswitch: 1. COMBATE & EXECUÇÃO DINÂMICA
    Screen->>Engine: capture_frame()
    Engine->>Detector: analyze_battle_ui(frame)
    Detector-->>Engine: BattleUIDetectionResult(fight=PRESENT, modal=NONE)
    Engine->>Controller: click_fight(frame)
    Controller->>Win32: click(fight_x, fight_y)
    Controller-->>Engine: fight_dispatched=True

    Note over Screen,Killswitch: 2. SELEÇÃO DE HABILIDADE DINÂMICA (DPI-INVARIANT)
    Screen->>Engine: capture_frame()
    Engine->>Controller: find_available_skills(frame)
    Controller-->>Engine: [SkillSlot_1 (ROI Dinâmico), ...]
    Engine->>Controller: select_primary_skill(skills) -> SkillSlot_1
    Engine->>Controller: execute_skill(SkillSlot_1, frame)
    Controller->>Win32: press_key("1")
    Controller-->>Engine: skill_dispatched=True (Turn Lock Activated)

    Note over Screen,Killswitch: 3. DETECÇÃO E DISPENSA DE MODAL PÓS-BATALHA
    Screen->>Engine: capture_frame()
    Engine->>Detector: analyze_battle_ui(frame)
    Detector-->>Engine: BattleUIDetectionResult(modal_detected=True, type="VICTORY_MODAL")
    Engine->>Controller: dismiss_post_battle_modal(frame)
    Controller->>Win32: click(confirm_x, confirm_y) + press_key("SPACE")
    Controller-->>Engine: modal_dismissed=True, Event(MODAL_DISMISSED)

    Note over Screen,Killswitch: 4. TRANSIÇÃO FINAL PARA O OVERWORLD
    Screen->>Engine: capture_frame()
    Engine->>Controller: is_battle_finished(frame)
    Controller-->>Engine: True (UI Fechada)
    Engine->>Engine: fsm.transition_to(BotState.EXPLORING)
    Note over Engine: Overworld Explorer Resumed / Crystal AI Guarded

    Note over Killswitch,Engine: 5. PROTOCOLO DE SEGURANÇA (KILLSWITCH)
    alt Hotkey F12 Pressionada
        Killswitch->>Win32: Release All Pressed Keys
        Killswitch->>Engine: fsm.transition_to(BotState.SAFE_STOP)
        Killswitch->>Killswitch: Save debug/emergency_stop.json
    end
```

---

### TRACE DE EVENTOS GERADOS NA V3.9

1. `BATTLE_UI_DETECTED` $\rightarrow$ `BATTLE_UI_CONFIRMED`
2. `FIGHT_CLICK_REQUESTED` $\rightarrow$ `FIGHT_CLICK_DISPATCHED` $\rightarrow$ `FIGHT_CLICK_VERIFIED`
3. `SKILL_UI_DETECTED` $\rightarrow$ `SKILL_SELECTED` $\rightarrow$ `SKILL_ACTION_REQUESTED` $\rightarrow$ `SKILL_ACTION_DISPATCHED`
4. `BATTLE_WAITING_TURN_RESOLUTION`
5. `MODAL_DETECTED` (tipo: `VICTORY_MODAL` / `REWARD_MODAL`)
6. `MODAL_DISMISSED`
7. `TURN_RESOLUTION_COMPLETED`
8. `BATTLE_EXIT_DETECTED` $\rightarrow$ `BATTLE_FINISHED` $\rightarrow$ `WORLD_RESUMED`
9. (Se aplicável) `KILLSWITCH_TRIGGERED` $\rightarrow$ `SAFE_STOP_TRIGGERED` $\rightarrow$ `EMERGENCY_STOP`
