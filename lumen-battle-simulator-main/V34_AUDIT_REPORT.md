# LUMENA BOT CONTROL CENTER v3.4 — RELATÓRIO DE AUDITORIA (FASE 0)
## Mapeamento Integral da Arquitetura, SSOT, Fluxos de Execução e Auditoria de Fake Pass

**Data:** 14 de Agosto de 2026  
**Engenheiro Responsável:** Principal Autonomous Systems Engineer  
**Objetivo:** Auditar a cadeia de execução de ponta a ponta (Percepção ➔ Decisão ➔ Input Físico ➔ Resposta do Jogo ➔ Verificação Visual ➔ Próxima Ação), identificando entry points, SSOT, loop principal, chamadores, pontos de despacho físico e potenciais riscos de falso sucesso.

---

## 1. MAPEAMENTO DA ÁRVORE DO PROJETO

```
lumen-battle-simulator-main/
├── config/
│   ├── __init__.py
│   └── settings.py               # BotConfig, Keybindings, Tolerâncias e Timeouts
├── src/
│   ├── automation/               # Automação e FSM
│   │   ├── __init__.py
│   │   ├── bot_controller.py     # Controlador intermediário da FSM
│   │   ├── bot_engine.py         # [SSOT] LumenaBotEngine - Motor Principal
│   │   ├── healing.py            # HealingController em malha fechada
│   │   ├── navigation.py         # NavigationController & RouteManager
│   │   └── state_machine.py      # BotStateMachine & Transições de Estado
│   ├── combat/                   # Subsistema de Combate
│   │   ├── __init__.py
│   │   ├── action_executor.py    # Despacho de ações de combate
│   │   ├── combat_agent.py       # Agente cognitivo de combate
│   │   ├── combat_positioning.py # Posicionamento tático e alcance
│   │   ├── decision_engine.py    # CombatDecisionEngine dinâmico e pontuação
│   │   └── skill_executor.py     # Executor de habilidades por coordenadas visuais
│   ├── core/                     # Regras de Domínio e Eventos
│   │   ├── __init__.py
│   │   └── event_bus.py          # EventBus desacoplado e logging
│   ├── database/                 # Persistência e Repositórios
│   ├── input/                    # Camada de Entrada e Janelas Win32
│   │   ├── __init__.py
│   │   ├── input_backend.py      # Win32 SendInput (DirectInput scancodes)
│   │   ├── input_controller.py   # Controlador de input com verificação visual
│   │   ├── safety_guard.py       # Interceptador e validador de foco
│   │   └── target_window.py      # TargetWindowManager e enumeração Win32
│   ├── memory/                   # Memória e Rastreamento de Mundo
│   │   ├── __init__.py
│   │   ├── experience_store.py   # Armazenamento de episódios e decisões
│   │   ├── memory_manager.py     # MemoryManager central
│   │   └── world_memory.py       # Mapa semântico e POIs
│   ├── models/                   # Dataclasses e Tipagens
│   │   ├── __init__.py
│   │   ├── combat_vision.py      # SkillSlot, TargetWindowInfo, CombatSnapshot
│   │   ├── enums.py              # BotState, AgentState, Element
│   │   └── lumen.py              # StateSnapshot, PlayerInfo, TargetLockInfo
│   ├── perception/               # Visão Computacional
│   │   ├── __init__.py
│   │   ├── battle_detector.py    # Reconhecimento de HUD de batalha
│   │   ├── combat_vision.py      # CombatVisionAnalyzer dinâmico
│   │   ├── debug_skill_scanner.py# Scanner anotador de slots de habilidades
│   │   ├── landmark_detector.py  # Detecção de Player, Cristal e POIs
│   │   ├── screen_capture.py     # Captura MSS / BitBlt com tolerância
│   │   ├── state_classifier.py   # Classificador de Estado da Tela
│   │   └── ui_detector.py        # Detecção de Caixas de Diálogo e Botões
│   ├── telemetry/                # Telemetria, Métricas e Evidências
│   │   ├── __init__.py
│   │   ├── evidence_package.py   # Geração padronizada de pacotes de evidência
│   │   └── telemetry_manager.py  # TelemetryManager e contadores de Action Rate
│   └── ui/                       # Interfaces com Usuário
│       ├── __init__.py
│       ├── app_gui.py            # GUI clássica
│       ├── cli.py                # Interface de linha de comando
│       └── modern_gui.py         # ModernLumenaGUI (Tkinter profissional)
├── scripts/                      # Diagnósticos e Validações
│   ├── debug_skill_scanner.py    # Scanner de HUD em arquivo/tela
│   ├── real_world_test.py        # Teste de validação física (Level 6)
│   ├── test_physical_input.py    # Diagnóstico de envio de scancodes
│   ├── validate_live_input.py    # Validação interativa de teclado/mouse
│   └── validate_real_integration.py # Validação de integração completa
├── tests/                        # 127 Testes Automatizados Unitários e de Integração
├── LumenaBot.spec                # Especificação de compilação PyInstaller
└── main.py                       # Ponto de Entrada Principal
```

---

## 2. ENTRY POINTS DO SISTEMA

| Entry Point | Localização | Propósito |
| :--- | :--- | :--- |
| **GUI Principal** | [`main.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/main.py) | Inicializa `ModernLumenaGUI` e conecta ao `LumenaBotEngine`. |
| **CLI / Automação Headless** | [`src/ui/cli.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/ui/cli.py) | Permite execução autônoma ou diagnóstica via terminal. |
| **Diagnóstico de Validação Física** | [`scripts/real_world_test.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/scripts/real_world_test.py) | Executa o teste de movimento físico Level 6 e gera `result.json`. |
| **Scanner de Habilidades** | [`scripts/debug_skill_scanner.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/scripts/debug_skill_scanner.py) | Detecta $N$ slots de habilidades no HUD da janela alvo. |
| **Executável Compilado** | `dist/LumenaBot/LumenaBot.exe` | Binário standalone para Windows 64-bit. |

---

## 3. IDENTIFICAÇÃO DO SINGLE SOURCE OF TRUTH (SSOT) E LOOP PRINCIPAL

- **SSOT**: `LumenaBotEngine` localizado em [`src/automation/bot_engine.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/automation/bot_engine.py).
- **Loop Principal**: `LumenaBotEngine._step()` e `_execute_autonomous_cycle()`.
- **Fluxo do Ciclo Autônomo**:
  1. `ScreenCapture.capture()` captura o frame atual da janela alvo.
  2. `StateClassifier.classify_frame(frame)` extrai o `StateSnapshot` (incluindo `PlayerInfo`, `TargetLockInfo`, `UIElements` e `AgentState`).
  3. `LumenaBotEngine` avalia o estado:
     - Se `HEALING` / time com HP crítico ➔ `_handle_healing_cycle()`.
     - Se `BATTLE` ➔ `_handle_battle_cycle()`.
     - Se `EXPLORING` ➔ `_handle_exploration_cycle()`.
  4. O subsistema apropriado decide a ação, despacha micro-inputs físicos via `InputController`, captura o frame posterior e calcula `compute_visual_delta`.
  5. Telemetria e Execution Monitor são atualizados com os 17 campos em tempo real.
  6. O Watchdog avalia se o bot esteve $> 15s$ inerte, disparando `EXECUTION_STALLED` se necessário.

---

## 4. MAPEAMENTO DE CHAMADORES E COMPONENTES

| Componente | Instanciado Em | Chamado Por | Responsabilidade |
| :--- | :--- | :--- | :--- |
| `ScreenCapture` | `LumenaBotEngine`, `StateClassifier` | Loop principal | Captura de buffers GDI/MSS da janela alvo. |
| `LandmarkDetector` | `StateClassifier`, `HealingController` | Percepção | Detecção visual do Player, Cristal e POIs. |
| `CombatVisionAnalyzer` | `StateClassifier`, `CombatAgent` | Percepção de Combate | Detecção dinâmica dos slots de habilidades e status de inimigos. |
| `HealingController` | `LumenaBotEngine` | `_handle_healing_cycle` | Navegação em malha fechada até o Cristal, interação e cura. |
| `CombatAgent` | `LumenaBotEngine` | `_handle_battle_cycle` | Coordenação tática do combate. |
| `CombatDecisionEngine` | `CombatAgent` | `process_combat_snapshot` | Seleção ponderada de habilidades baseada em poder, elemento e fraqueza. |
| `InputController` | `BotEngine`, `HealingController`, `SkillExecutor` | Despacho de Ações | Envio de scancodes com verificação pós-ação via delta visual. |
| `TargetWindowManager` | `InputController`, `BotEngine` | Inicialização e foco | Enumeração e validação de janelas (Chrome, Edge, Firefox, Brave). |
| `SafetyGuard` | `InputController` | Todos os despachos de tecla | Bloqueio caso a janela em primeiro plano seja inválida ou do próprio bot. |
| `EvidencePackage` | `real_world_test.py`, `BotEngine` | Validação física | Salvamento de `before`, `after`, `diff`, `annotated` e `result.json`. |

---

## 5. PONTOS DE DESPACHO FÍSICO (DIRECTINPUT / SENDINPUT)

Todos os inputs físicos convergem para [`src/input/input_backend.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/input/input_backend.py):
- `send_key_down(vk_code, scan_code)`
- `send_key_up(vk_code, scan_code)`
- `send_mouse_click(x, y)`

Proteções ativas em tempo de execução:
- `SafetyGuard.validate_foreground(target_hwnd)` consulta `win32gui.GetForegroundWindow()`.
- Se `GetForegroundWindow() != target_hwnd`, o despacho é imediatamente abortado com `BLOCKED_NOT_FOREGROUND`.
- Se o HWND ou PID pertencer ao próprio processo do Lumena Bot, o despacho é bloqueado com `BLOCKED_SELF_PROCESS`.

---

## 6. AUDITORIA DE MOCKS, FAKES E RISCOS DE FALSO SUCESSO

1. **Testes Unitários**:
   - Os 127 testes em `tests/` utilizam frames sintéticos (NumPy) para validar a matemática dos algoritmos (ex: vetores, deltas, matrizes elementais, máquinas de estados).
   - **Garantia**: Esses testes são puramente de regressão algorítmica e **NÃO** geram arquivos `result.json` com `physical_execution_verified = True`.
2. **Hard Gate do Level 7**:
   - O modo autônomo total (Level 7) verifica explicitamente a existência de evidência física real em disco antes de ser habilitado.
3. **Delta Visual Real**:
   - `InputController.compute_visual_delta` calcula a diferença absoluta média normalizada (`cv2.absdiff`) entre `frame_before` e `frame_after`. Se $\Delta < 0.005$, a ação é categorizada como `ACTION_UNCONFIRMED`.

---

## 7. CONCLUSÃO DA FASE 0

A arquitetura do projeto é sólida, modular e livre de bypasses artificiais de sucesso físico. As próximas fases detalharão o aprimoramento contínuo das rotinas de Target Window, Input Real, Player Detection, Cristal de Cura, Combate Dinâmico, Watchdog e Validação em Mundo Real.
