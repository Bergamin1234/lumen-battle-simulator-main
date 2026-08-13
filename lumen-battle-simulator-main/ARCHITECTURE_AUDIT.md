# Auditoria de Arquitetura — Lumena Bot

**Data:** 2026-08-13  
**Status do Projeto:** Transição para Sistema Autônomo Integrado de Alta Fidelidade

---

## 1. Diagnóstico do Estado Anterior

| Componente | Estado Anterior | Problemas Identificados |
|---|---|---|
| **Ponto de Entrada (GUI)** | `src/ui/app_gui.py` | Instanciava motor legado de macro determinístico sem vínculo com as camadas das Fases 1 a 4. Logs restritos apenas ao logger `LumenaMacro`. |
| **Ponto de Entrada (CLI/Scripts)** | `scripts/` e `main.py` | Desconexão entre a interface visual e os scripts de teste. |
| **Entrada Física (InputController)** | `src/input/input_controller.py` | Dependência inicial de `SendInput` com falhas de privilégio UIPI (Error 5) no Chromium e ausência de foco garantido no canvas WebGL. |
| **Gerenciamento de Janela** | `src/input/target_window.py` | Foco de janela básico sem detecção de DPI/escala, sem clique de ativação no DOM do Chrome e sem enumeração de `RenderWidgetHost`. |
| **Motor Principal** | `src/automation/bot_engine.py` | Loop simples sem máquina de estados formal, sem telemetria em tempo real e sem suporte a modo manual/assistido. |
| **Interface Visual** | `src/ui/app_gui.py` | Layout com poucas abas, sem visão computacional em tempo real, sem mapa de memória visual, sem diagnóstico integrado. |
| **Tratamento de Exceções** | Distribuído | Exceções podiam interromper loops silenciosamente sem acionar rotinas de recuperação ou gravação de screenshot de debug. |

---

## 2. Mapa de Dependências Alvo

```
                         ┌────────────────────────────────────────┐
                         │          src/ui/modern_gui.py          │
                         │    (Dashboard, Battle, Vision, etc.)   │
                         └───────────────────┬────────────────────┘
                                             │ Eventos e Telemetria (Queue)
                                             ▼
                         ┌────────────────────────────────────────┐
                         │   src/automation/bot_controller.py     │
                         │   (Thread-Safe, Emergency Stop, FSM)   │
                         └───────────────────┬────────────────────┘
                                             │
                                             ▼
                         ┌────────────────────────────────────────┐
                         │     src/automation/bot_engine.py       │
                         │     (Closed-Loop Autonomous Engine)    │
                         └───────────────────┬────────────────────┘
                                             │
      ┌────────────────────────┬─────────────┴────────────┬────────────────────────┐
      ▼                        ▼                          ▼                        ▼
┌──────────────┐      ┌─────────────────┐       ┌──────────────────┐     ┌──────────────────┐
│  Perception  │      │     Memory      │       │     Decision     │     │    Navigation    │
│ScreenCapture │      │  MemoryManager  │       │   CombatAgent    │     │Route Manager     │
│StateClassif. │      │   WorldMemory   │       │ DecisionEngine   │     │MovementController│
│  UIDetector  │      │ ExperienceStore │       │  ActionExecutor  │     │WASD Replay       │
└──────┬───────┘      └────────┬────────┘       └─────────┬────────┘     └────────┬─────────┘
       └───────────────────────┼──────────────────────────┴───────────────────────┘
                               ▼
                    ┌───────────────────────┐
                    │ src/input/safety.py   │
                    │    Safety Guard       │
                    └──────────┬────────────┘
                               ▼
                    ┌───────────────────────┐
                    │ src/input/controller  │
                    │    InputController    │
                    └──────────┬────────────┘
                               ▼
             ┌─────────────────┴─────────────────┐
             ▼                                   ▼
┌─────────────────────────┐             ┌─────────────────┐
│   Win32InputBackend     │             │ PyAutoGUIBackend│
│ (Scancodes, keybd_event,│             │   (Fallback)    │
│  PostMessage, Canvas)   │             └─────────────────┘
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Google Chrome (Canvas)  │
└─────────────────────────┘
```

---

## 3. Riscos e Mitigações

1. **Risco de Foco no Chrome:** O Chrome pode ignorar teclas se o canvas perder o foco.
   - *Mitigação:* `TargetWindowManager` executa sequência `SW_RESTORE` ➔ `AttachThreadInput` ➔ `SetForegroundWindow` ➔ `SetFocus` ➔ clique físico no canvas (`mouse_event`).
2. **Risco de Bloqueio da GUI por Threading:**
   - *Mitigação:* A GUI comunica-se com a thread do bot exclusivamente através de `queue.Queue` thread-safe, com polling de 50ms via `root.after()`.
3. **Risco de Travamento em Batalha ou Percepção:**
   - *Mitigação:* Timeouts em todas as micro-ações, limite de turnos máximos, fallbacks heurísticos e salvamento de screenshot de debug em `debug/`.
4. **Risco de DPI e Escala no Windows:**
   - *Mitigação:* Detecção de DPI via Win32 `GetDpiForWindow` e normalização das coordenadas relativas da janela.

---

## 4. Plano de Migração Incremental

- **Fase 1:** Camada de Entrada e Segurança (`InputBackend`, `InputController`, `TargetWindowManager`, `SafetyGuard`).
- **Fase 2:** Máquina de Estados e Telemetria (`AgentState`, `BotStateMachine`, `TelemetryManager`).
- **Fase 3:** Motor Unificado (`LumenaBotEngine`, `BotController`).
- **Fase 4:** Navegação e Gravador de Rotas Avançado (`NavigationController`, editor visual de rotas).
- **Fase 5:** Percepção e Visão Computacional com Anotações em Frame.
- **Fase 6:** Interface Gráfica Moderna Completa com 9 Páginas e Tema Dark.
- **Fase 7:** Scripts de Diagnóstico e Validação Física.
- **Fase 8:** Suíte de Testes Unitários e Integração.
- **Fase 9:** Empacotamento PyInstaller e Documentação Técnica.
