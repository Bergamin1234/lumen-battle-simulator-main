# Arquitetura do Lumena Bot

## Visão Geral do Sistema

O **Lumena Bot** é uma plataforma autônoma em malha fechada (*closed-loop*) para percepção, navegação, combate inteligente e controle físico de jogos baseados em navegador (Lumena.gg / Google Chrome no Windows).

---

## Diagrama da Arquitetura

```
                    ┌────────────────────────────────────────┐
                    │      src/ui/modern_gui.py              │
                    │   Painel de Controle em 9 Páginas      │
                    └───────────────────┬────────────────────┘
                                        │ Telemetria e Comandos (Queue / Thread-Safe)
                                        ▼
                    ┌────────────────────────────────────────┐
                    │   src/automation/bot_controller.py     │
                    │   Gerenciador de Lifecycle do Bot      │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │     src/automation/bot_engine.py       │
                    │   Motor Unificado em Malha Fechada     │
                    └───────────────────┬────────────────────┘
                                        │
      ┌────────────────────────┬────────┴────────┬────────────────────────┐
      ▼                        ▼                 ▼                        ▼
┌──────────────┐      ┌─────────────────┐  ┌───────────────┐     ┌──────────────────┐
│  Perception  │      │     Memory      │  │   Decision    │     │    Navigation    │
│ScreenCapture │      │  MemoryManager  │  │  CombatAgent  │     │Route Manager     │
│StateClassif. │      │   WorldMemory   │  │DecisionEngine │     │Replay WASD       │
│  UIDetector  │      │ ExperienceStore │  │ActionExecutor │     │Exploração        │
└──────┬───────┘      └────────┬────────┘  └───────┬───────┘     └────────┬─────────┘
       └───────────────────────┼───────────────────┴──────────────────────┘
                               ▼
                    ┌────────────────────────────────────────┐
                    │      src/input/safety_guard.py         │
                    │  Guardião de Segurança e Rate Limit    │
                    └───────────────────┬────────────────────┘
                                        ▼
                    ┌────────────────────────────────────────┐
                    │      src/input/input_controller.py     │
                    │  Controlador de Entrada Híbrido        │
                    └───────────────────┬────────────────────┘
                                        ▼
                   ┌────────────────────┴────────────────────┐
                   ▼                                         ▼
        ┌───────────────────────┐                 ┌────────────────────┐
        │   Win32InputBackend   │                 │PyAutoGUIInputBack. │
        │ Scancodes / keybd_ev. │                 │   (Fallback)       │
        │ PostMessage / Canvas  │                 └────────────────────┘
        └──────────┬────────────┘
                   ▼
        ┌───────────────────────┐
        │   Google Chrome       │
        │   (Canvas WebGL)      │
        └───────────────────────┘
```

---

## Componentes Principais

### 1. Camada de Apresentação (Frontend)
- **`src/ui/modern_gui.py`**: Interface gráfica desktop moderna com tema escuro técnico (*Dark Technical Theme*), separada em 9 páginas:
  - **Dashboard:** Visão geral, controles principais e telemetria consolidada.
  - **Controle do Bot:** Alternância entre modos (Autônomo, Assistido, Manual) e D-Pad virtual.
  - **Batalha:** Monitor de combate, fraquezas elementares, PP, HP e razão das decisões.
  - **Navegação:** Gerenciador de rotas gravadas, gravação interativa e replay.
  - **Visão:** Preview em tempo real com overlay de bounding boxes e detecções semânticas.
  - **Memória:** Visualização de posição topológica, marcos (*landmarks*), obstáculos e células visitadas.
  - **Logs:** Log viewer com filtros multi-canal e exportação.
  - **Diagnósticos:** Varredura em tempo real do ecossistema de software e hardware.
  - **Configurações:** Presets (*Safe, Balanced, Aggressive, Debug*) e persistência JSON.

### 2. Camada de Automação e Orquestração
- **`src/automation/bot_controller.py`**: Intermediário thread-safe entre a GUI e a thread de trabalho em background.
- **`src/automation/bot_engine.py`**: Loop contínuo fechado:
  $$\text{Captura} \rightarrow \text{Classificação} \rightarrow \text{Memória} \rightarrow \text{Decisão} \rightarrow \text{Execução} \rightarrow \text{Observação}$$
- **`src/automation/state_machine.py`**: Máquina de estados explícita (`STOPPED`, `STARTING`, `CONNECTING`, `READY`, `EXPLORING`, `BATTLE`, `VICTORY`, `DEFEAT`, `HEALING`, `DIALOG`, `RECOVERING`, `ERROR`, `EMERGENCY_STOP`).
- **`src/telemetry/telemetry_manager.py`**: Coleta de métricas e indicadores de desempenho (FPS, latência de ação, contagem de batalhas/vitórias, confiança).

### 3. Camada de Entrada e Foco
- **`src/input/target_window.py`**: Localização de janelas, restauração de minimizada, elevação de prioridade (`AttachThreadInput`), foco de primeiro plano e clique calibrado no canvas.
- **`src/input/input_backend.py`**: Múltiplos backends de hardware (Win32 Scancode DirectInput, `keybd_event`, `PostMessageW` para o `RenderWidgetHost` do Chromium).
- **`src/input/safety_guard.py`**: Proteção contra envio de teclas em janelas não confirmadas, liberação garantida de teclas em bloco `finally` e parada imediata de emergência (ESC).
