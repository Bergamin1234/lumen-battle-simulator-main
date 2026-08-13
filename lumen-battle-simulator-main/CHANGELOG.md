# Registro de Alterações (Changelog)

## Versão 2.0.0 — Integração Total e Modernização de Frontend

### Adicionado
- **Interface Desktop Moderna em 9 Páginas (`src/ui/modern_gui.py`):**
  - Dashboard consolidado com telemetria e console em tempo real.
  - Página de Controle do Bot com D-Pad manual e seleção de modos (Autônomo, Assistido, Manual).
  - Painel de Batalha com acompanhamento de fraquezas e telemetria de combate.
  - Gerenciador de Navegação e Gravação de Rotas com reversão automática.
  - Feed de Visão Computacional ao vivo com overlay de bounding boxes.
  - Visualizador de Memória Topológica e histórico de experiência.
  - Log viewer multi-canal com filtros por subsistema.
  - Centro de Diagnósticos automatizado para validação de runtime.
  - Editor de Configurações com presets de perfil (*Safe, Balanced, Aggressive, Debug*).
- **Camada de Entrada Híbrida (`src/input/input_backend.py`):**
  - Despacho multi-camada: Win32 SendInput com scancodes de hardware (`0x11` para W, `0x1E` para A, `0x1F` para S, `0x20` para D), DirectInput `keybd_event`, `PostMessageW` para o `RenderWidgetHost` e PyAutoGUI fallback.
- **Guardião de Segurança (`src/input/safety_guard.py`):**
  - Interrupção imediata de emergência (ESC), liberação atômica de teclas em bloco `finally` e bloqueio de entradas em janelas não confirmadas.
- **Máquina de Estados Explícita (`src/automation/state_machine.py`):**
  - Gerenciamento de ciclo de vida com estados formais e transições auditadas.
- **Gerenciador de Telemetria (`src/telemetry/telemetry_manager.py`):**
  - Monitoramento contínuo de FPS, latência média de ações, contagem de vitórias e taxa de recuperação.
- **Scripts de Diagnóstico Real:**
  - `scripts/validate_live_input.py` e `scripts/test_physical_input.py`.
- **Suíte de Testes Expandida:**
  - 52 testes unitários cobrindo modelos, combate, percepção, memória, navegação, máquina de estados e segurança.

### Corrigido
- **Causa Raiz de Desconexão do Loop:** O botão Iniciar agora utiliza o mesmo `LumenaBotEngine` e `BotController` utilizado por testes e scripts de integração.
- **Retorno Oculto de SendInput (Error 5 / UIPI):** Substituído por injeção híbrida via scancodes de hardware e `keybd_event`.
- **Perda de Foco no Canvas:** Adicionada rotina de ativação do DOM via clique no centro da janela alvo.
- **Logs Incompletos na GUI:** Centralização global de todos os canais de logging.
