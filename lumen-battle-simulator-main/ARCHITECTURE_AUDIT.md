# ARCHITECTURE AUDIT — LUMENA BOT CONTROL CENTER v3.0

## 1. Inventário Completo de Módulos e Responsabilidades

### A. Núcleo de Automação e Lifecycle (`src/automation/`)
- `bot_engine.py` (**LumenaBotEngine — SSOT**): Único motor ativo de ciclo contínuo em malha fechada (*Observe ➔ Interpret ➔ Remember ➔ Decide ➔ Act ➔ Verify*).
- `bot_controller.py` (**BotController**): Gerenciador thread-safe do ciclo de vida do motor, controle de thread em background e ponte oficial para a GUI.
- `state_machine.py` (**BotStateMachine**): FSM centralizada com transições formais validadas e publicação no `EventBus`.
- `navigation.py` (**NavigationController & RouteManager**): Gravação de rotas, timeline de passos (`STEP | KEY | DURATION`), replay, reversão e desengate anti-stuck.

### B. Camada de Entrada Física e Foco (`src/input/`)
- `input_controller.py` (**InputController**): Orquestrador híbrido com medição de delta de frames antes/depois e controle de feedback visual.
- `target_window.py` (**TargetWindowManager**): Busca de janelas por título/classe, restauração `SW_RESTORE`, elevação via `AttachThreadInput` e clique calibrado no centro do canvas WebGL.
- `safety_guard.py` (**SafetyGuard**): Bloqueio de envio em janelas não confirmadas, liberação atômica em bloco `finally` e parada imediata via **ESC**.
- `input_backend.py` (**InputBackend, Win32InputBackend, PyAutoGUIInputBackend**): Despacho de scancodes de hardware DirectInput (`0x11` W, `0x1E` A, `0x1F` S, `0x20` D, `0x39` Space, `0x1C` Enter), `keybd_event` e `PostMessageW`.

### C. Camada de Percepção e Visão (`src/perception/`)
- `screen_capture.py` (**ScreenCapture**): Captura multi-monitor via MSS e cálculo de variação entre frames.
- `state_classifier.py` (**StateClassifier**): Classificação de telas (*Exploring, Battle, Healing, Dialog, Victory, Defeat*).
- `battle_detector.py`, `landmark_detector.py`, `ui_detector.py`, `world_detector.py`, `ocr.py`: Detectores semânticos com suporte a templates e heurísticas de cor/contorno.

### D. Camada de Combate Inteligente (`src/combat/`)
- `combat_agent.py` (**CombatAgent**): Tomada de decisão por fraquezas elementais, controle de PP, troca de Lumen e priorização.
- `decision_engine.py` (**DecisionEngine**): Avaliação de multiplicadores de dano e pontuação determinística.
- `action_executor.py` (**ActionExecutor**): Tradução de intenções de combate em sequências de input físico.

### E. Camada de Memória Topológica (`src/memory/`)
- `memory_manager.py` (**MemoryManager**): Integração de snapshots em memória operacional e persistente.
- `world_memory.py` (**WorldMemory**): Coordenadas $(X, Y)$, heading, âncoras/marcos, obstáculos e células exploradas.
- `experience_store.py` (**ExperienceStore**): Histórico de encontros e aprendizado de eficácia.

### F. Barramento Transversal e Telemetria (`src/core/` & `src/telemetry/`)
- `src/core/event_bus.py` (**EventBus**): Barramento assíncrono thread-safe com filas `queue.Queue` para a interface.
- `src/telemetry/telemetry_manager.py` (**TelemetryManager**): Métricas em tempo real de FPS, latências por subsistema, APM, vitórias/derrotas e recuperações.

### G. Interface Gráfica Profissional (`src/ui/`)
- `modern_gui.py` (**ModernLumenaGUI**): Control Center completo com 14 páginas, status bar inferior e monitoramento a 50ms.

---

## 2. Diagnóstico de Código Morto e Módulos Legados

1. **`src/ai/automation/`:** Contém apenas arquivos placeholders sem implementação. Não participam do fluxo oficial do bot e estão explicitamente isolados.
2. **`src/legacy/`:** Mantido apenas para compatibilidade de testes legados. Não há chamadas ativas do `LumenaBotEngine` para este diretório.
3. **`src/automation/input_controller.py`:** Atua como um shim de reexportação para `src.input.input_controller` para garantir que nenhum teste legado quebre.

---

## 3. Matriz de Conexão: GUI ➔ Backend ➔ Jogo

```
ModernLumenaGUI (Tkinter Mainloop)
    │
    │ Polling a cada 50ms via self.gui_event_queue.get_nowait()
    ▼
EventBus (Core) ◄─── Publicações Assíncronas ─── LumenaBotEngine & Subsystems
    │
    ▼ Comandos do Usuário (Start, Stop, Pause, D-Pad, Routes)
BotController (Worker Thread)
    │
    ▼
LumenaBotEngine (Closed-Loop Principal)
    │ 1. ScreenCapture.capture_frame() ➔ Frame Before
    │ 2. StateClassifier.classify_frame() ➔ StateSnapshot
    │ 3. MemoryManager.update_from_snapshot()
    │ 4. CombatAgent / NavigationController.decide()
    │ 5. ActionExecutor.execute() ➔ InputController
    │ 6. TargetWindowManager.verify_foreground() ➔ Win32 SendInput (Scancodes)
    │ 7. ScreenCapture.capture_frame() ➔ Frame After
    │ 8. InputController.compute_visual_delta() ➔ Verificação de Deslocamento
    ▼
Evidence Package ➔ debug/evidence/<timestamp>/ (before.png, after.png, diff.png, result.json)
```

---

## 4. Estado dos Testes Unitários e Integrados

- Total de testes identificados e validados: **59 testes**.
- Taxa de sucesso atual: **100% (59/59 PASS)**.
- Módulos testados: `CombatAgent`, `Perception`, `MemoryLayer`, `Evolution`, `InputController`, `SafetyGuard`, `StateMachine`, `Telemetry`, `RouteManager`, `ClosedLoop`, `EventBus`.
