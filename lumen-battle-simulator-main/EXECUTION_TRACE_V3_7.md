# EXECUTION TRACE — LUMENA BOT v3.7
## RASTREAMENTO DETERMINÍSTICO DE COMBATE E BATTLE UI

---

### FLUXO COMPLETO v3.7

```mermaid
sequenceDiagram
    autonumber
    participant Screen as ScreenCapture
    participant Engine as LumenaBotEngine
    participant BUI as BattleUIDetector
    participant Ctrl as BattleUIController
    participant Win32 as Win32 (SendInput)
    participant Game as Chrome / WebGL

    Screen->>Engine: capture_frame() -> frame_before
    Engine->>BUI: analyze_battle_ui(frame_before)
    BUI-->>Engine: BattleUIDetectionResult(in_battle=True, fight_button=PRESENT)

    rect rgb(230, 245, 255)
        Note over Engine,Ctrl: PASSO 1: ENTRADA EM COMBATE DETERMINÍSTICA
        Engine->>Ctrl: click_fight(frame_before)
        Ctrl->>Win32: click(cx, cy)
        Win32->>Game: Mouse Down/Up
        Ctrl-->>Engine: dispatched=True, verified=True
    end

    Screen->>Engine: capture_frame() -> frame_after_fight
    Engine->>Ctrl: find_available_skills(frame_after_fight)
    Ctrl-->>Engine: [SkillSlot_1, SkillSlot_2, ..., SkillSlot_N]

    rect rgb(255, 240, 230)
        Note over Engine,Ctrl: PASSO 2: EXECUÇÃO FÍSICA DE SKILL
        Engine->>Ctrl: execute_skill(SkillSlot_1, frame_after_fight)
        Ctrl->>Win32: press_key("1") via SendInput ScanCode
        Win32->>Game: WM_KEYDOWN / KEYEVENTF_SCANCODE
        Ctrl->>Screen: capture_frame() -> frame_after_skill
        Ctrl->>Ctrl: compute_visual_delta(frame_after_fight, frame_after_skill)
        Ctrl-->>Engine: skill_dispatched=True, skill_verified=True (delta > 0.005)
    end
```

---

### EVENTOS EMITIDOS EM CADA ETAPA

1. **Detecção da Batalha:**
   - `BATTLE_UI_DETECTED` $\rightarrow$ `BATTLE_UI_CONFIRMED`
   - `CRYSTAL_SEARCH_BLOCKED`
   - `CRYSTAL_DETECTION_DISABLED_IN_BATTLE`
2. **Clique em FIGHT:**
   - `FIGHT_DETECTED` $\rightarrow$ `FIGHT_CLICK_REQUESTED` $\rightarrow$ `ACTION_REQUESTED`
   - `FIGHT_CLICK_DISPATCHED` $\rightarrow$ `ACTION_DISPATCHED`
   - `FIGHT_CLICK_VERIFIED` $\rightarrow$ `ACTION_VERIFIED`
3. **Seleção e Execução de Habilidade:**
   - `SKILL_UI_DETECTED` $\rightarrow$ `SKILL_SELECTED` $\rightarrow$ `SKILL_ACTION_REQUESTED`
   - `SKILL_ACTION_DISPATCHED`
   - `SKILL_ACTION_VERIFIED`
