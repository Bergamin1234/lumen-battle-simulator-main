# LUMENA BOT CONTROL CENTER v3.5 — AUDIT REPORT (PHASE 0)
## Real-World Execution Architecture, Single Source of Truth, Gaps & Zero Fake Pass Analysis

**Date:** August 14, 2026  
**Engineering Lead:** Principal Autonomous Systems Engineer  
**Scope:** Complete repository audit of perception, decision, input dispatch, game response, visual verification, and physical evidence generation.

---

## 1. CURRENT SINGLE SOURCE OF TRUTH (SSOT)

The sole Single Source of Truth (SSOT) for the autonomous agent is:
- **Class:** `LumenaBotEngine`
- **Location:** [`src/automation/bot_engine.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/automation/bot_engine.py)

All operational loops, lifecycle transitions, state evaluation, error handling, watchdog timeouts, and subsystem delegations are orchestrated through `LumenaBotEngine`.

---

## 2. REAL EXECUTION PATH (END-TO-END)

```
[ModernLumenaGUI / CLI]
       │
       ▼
[BotController.start(mode)]
       │
       ▼
[LumenaBotEngine.run_loop()] ───> [_execute_autonomous_cycle()]
       │
       ├─► 1. [ScreenCapture.capture_frame()] (Win32 MSS / GDI BitBlt)
       │
       ├─► 2. [StateClassifier.classify_frame(frame)]
       │        ├─► [LandmarkDetector.detect_player()] ──> PlayerDetection (bbox, center, conf)
       │        ├─► [LandmarkDetector.detect_crystal()] ──> CrystalDetection (HEALING_CRYSTAL, vector)
       │        └─► [CombatVisionAnalyzer.detect_skill_slots()] ──> N SkillSlots
       │
       ├─► 3. Tactical Subsystem Evaluation:
       │        ├─► IF HP Critical / Team low ──► [_handle_healing_cycle()]
       │        │     └─► [HealingController.step()] ──► WASD micro-movement & Space Interaction
       │        ├─► IF Battle Screen ───────────► [_handle_battle_cycle()]
       │        │     └─► [CombatAgent.process_combat_snapshot()] ──► Skill selection & Pos
       │        └─► IF Overworld ───────────────► [_handle_overworld_cycle()]
       │
       ├─► 4. Physical Action Gating:
       │        └─► [SafetyGuard.validate_foreground(target_hwnd)]
       │              ├─► Is own PID / LumenaBot? ──► REJECT & BLOCK
       │              └─► GetForegroundWindow() == target_hwnd? ──► PROCEED / BLOCK
       │
       ├─► 5. Physical Dispatch (DirectInput SendInput):
       │        └─► [InputBackend.send_key_down / up] (0x11, 0x1E, 0x1F, 0x20, etc.)
       │
       ├─► 6. Visual Verification (Closed Loop):
       │        ├─► [ScreenCapture.capture_frame()] (frame_after)
       │        └─► [InputController.compute_visual_delta(before, after)]
       │              ├─► delta >= 0.005 ──► ACTION_VERIFIED
       │              └─► delta < 0.005  ──► ACTION_UNCONFIRMED
       │
       └─► 7. Telemetry & Evidence Recording:
                ├─► [TelemetryManager.record_action()] (Action Rate Counters)
                └─► [save_evidence_package()] (debug/evidence/<timestamp>/result.json)
```

---

## 3. AUDIT OF GAPS, FAKE-PASS RISKS & SIMULATIONS

| Area | Current Implementation | Risk / Gap Identified | Solution in v3.5 |
| :--- | :--- | :--- | :--- |
| **Window Targeting** | `TargetWindowManager` filters browsers and rejects self PID. | Windows containing debug titles could potentially be evaluated. | Explicit rejection list with strict title string matching and PID hierarchy checks. |
| **Foreground Check** | Calls `GetForegroundWindow() == target_hwnd`. | Mock HWND `1001` in unit test environment. | Ensure mock flag is explicit and production path strictly queries `user32.GetForegroundWindow()`. |
| **Game Canvas Detection** | Calculates normalized client coordinates $(0.5, 0.5)$. | Assumes centered canvas inside client rect. | Implemented `detect_and_save_canvas_diagnostic` extracting canvas bounding box and annotating `browser.png`. |
| **Player Detection** | `LandmarkDetector.detect_player` combines template, edge contour, and viewport fallback. | If player is obscured, fallback center confidence must be calibrated. | Added `PlayerDetection` dataclass with `detection_method` and `PLAYER_NOT_CONFIDENT` threshold gating. |
| **Healing Crystal** | Priority detection in `LandmarkDetector` with HSV mask and template. | Must prioritize over all ambient scenery objects. | Explicit `HEALING_CRYSTAL` semantic typing with strict HSV hue range ($[85, 120]$). |
| **Combat Skills** | Dynamic discovery of $N$ slots in HUD via contour clustering. | Hardcoded slot counts in legacy tests. | Support dynamic $N \in \{1, 2, 4, 6, 8, 10\}$ slots with visual click coordinate fallback (`screen_x, screen_y`). |
| **Action Verification** | `compute_visual_delta` calculates normalized mean pixel difference. | Synthetic tests use NumPy arrays. | Production tests use real video frame buffers with strict threshold $\ge 0.005$. |
| **Evidence Schema** | Standardized `result.json`. | Risk of inferring `action_verified` directly into `physically_validated`. | Strict separation: `action_requested`, `input_dispatched`, `action_verified`, `physically_validated` are independent booleans. |

---

## 4. CONCLUSION OF PHASE 0

The architectural foundation is robust. The next phases implement the refined dataclasses, canvas diagnostics, dynamic visual skill execution, 20-stage validation tool, and evidence persistence.
