# AUDITORIA FINAL DO SISTEMA — LUMENA BOT

**Data da Auditoria:** 2026-08-13  
**Engenharia Responsável:** Engenheiro Sênior de Automação, Sistemas Autônomos e Win32  
**Repositório:** `lumen-battle-simulator-main`

---

## 1. Auditoria da Interface Gráfica (GUI)

- **Qual botão inicia o bot?**  
  O botão `▶ INICIAR (F5)` no Dashboard ou `▶ Iniciar Bot` na página Bot Control do `src/ui/modern_gui.py`.
- **Qual método é chamado?**  
  `self.bot_controller.start(mode=mode)`.
- **Qual engine é criado?**  
  O `LumenaBotEngine` unificado (`src/automation/bot_engine.py`), gerenciado pelo `BotController` (`src/automation/bot_controller.py`).
- **Qual thread é criada?**  
  A worker thread `LumenaBotWorkerThread` (daemon=True), garantindo que o Tkinter não congele nem seja manipulado diretamente de threads secundárias.
- **Existe algum engine antigo ainda sendo utilizado?**  
  Não. O `LumenaAppGUI` legado em `src/ui/app_gui.py` foi redirecionado para instanciar e executar exclusivamente o `ModernLumenaGUI`.
- **Existe algum código morto no fluxo principal?**  
  Não. As antigas rotinas legadas foram arquivadas em `src/legacy/` e não são referenciadas pelo loop ativo.
- **Existe alguma chamada duplicada?**  
  Não. O `BotController` implementa padrão Singleton thread-safe com trava (`_lock`), garantindo que apenas uma instância de motor exista no processo.

---

## 2. Auditoria da Camada de Entrada (INPUT)

- **Qual backend é utilizado?**  
  O `InputController` utiliza primariamente o `Win32InputBackend` com injeção de hardware scancodes (`0x11` para W, `0x1E` para A, `0x1F` para S, `0x20` para D, `0x39` para Space, `0x1C` para Enter).
- **Win32 realmente é chamado?**  
  Sim, via `user32.SendInput` com scancodes de hardware e `user32.keybd_event` (DirectInput), além de `PostMessageW` para o `Chrome_RenderWidgetHostHWND`.
- **PyAutoGUI é fallback?**  
  Sim, encapsulado em `PyAutoGUIInputBackend`, mantendo `pyautogui.FAILSAFE = True`.
- **SafetyGuard está ativo?**  
  Sim (`src/input/safety_guard.py`), monitorando limite de taxa de ações por segundo, estado de emergência e bloqueando qualquer envio caso a janela alvo não esteja confirmada em primeiro plano.
- **Todas as teclas são liberadas em caso de erro?**  
  Sim. Todos os métodos de envio de tecla (`press_key`, `hold_keys`, `press_key_with_diagnostic`) possuem bloco `finally: self.release_all_keys()`.
- **Existe risco de tecla ficar pressionada?**  
  Não, o `SafetyGuard` rastreia atomicamente as teclas ativas em `_held_keys` e emite `key_up` para todas elas tanto no encerramento normal quanto em exceções ou parada de emergência.

---

## 3. Auditoria do Gerenciador de Janela (WINDOW)

- **Como a janela é localizada?**  
  O `TargetWindowManager` busca janelas pelos títulos prioritários: `Lumena.gg`, `Lumena`, `Google Chrome`, `Chrome`, `Brave`, `Edge` e títulos customizados pelo usuário.
- **Como o HWND é obtido?**  
  Através de `win._hWnd` do `pygetwindow` e enumeração nativa Win32 (`EnumWindows` / `EnumChildWindows`).
- **Como a janela é ativada?**  
  Executa a sequência Win32:
  1. `ShowWindow(hwnd, SW_RESTORE)` (se minimizada).
  2. `AttachThreadInput(current_thread, target_thread, True)`.
  3. `BringWindowToTop(hwnd)`.
  4. `SetForegroundWindow(hwnd)`.
  5. `SetFocus(hwnd)`.
  6. `AttachThreadInput(..., False)`.
- **Como o canvas recebe foco?**  
  Através de um clique físico central de ativação de DOM via `user32.mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP)` nas coordenadas relativas (0.5, 0.5) da área cliente do navegador.
- **Como o sistema confirma que a janela correta está ativa?**  
  Compara `user32.GetForegroundWindow() == target_hwnd`. Se falso, bloqueia o envio de teclas e marca `TARGET WINDOW LOST`.

---

## 4. Auditoria da Camada de Percepção (PERCEPTION)

- **Como a tela é capturada?**  
  Via `ScreenCapture` utilizando `mss` de alta performance com fallback para `PIL.ImageGrab`.
- **Qual resolução?**  
  Resolução nativa da tela/janela (1920x1080 calibrada com suporte a escala DPI).
- **Qual monitor?**  
  Monitor 1 por padrão (configurável em `config/settings.json`).
- **Como batalha é detectada?**  
  Pelo `BattleDetector` através da detecção combinada de: barra de HP do inimigo, barra de HP do jogador, botão FIGHT e área de diálogo.
- **Como HP é detectado?**  
  Por análise de pixels verdes/vermelhos da barra de vida e leitura OCR com filtros morfológicos.
- **Como FIGHT é detectado?**  
  Por template matching e OCR na região inferior direita da tela.
- **Como os slots de golpes são detectados?**  
  Por segmentação espacial dos 4 slots de ataque e extração de PP via OCR/heurística.
- **Como vitória/derrota são detectadas?**  
  Pela presença de banners de EXP/vitória ou tela de desmaio do Lumen ativo.

---

## 5. Auditoria da Tomada de Decisão (DECISION)

- **Como o bot escolhe uma ação?**  
  O `CombatAgent` e `CombatDecisionEngine` avaliam o `StateSnapshot` atual e pontuam todas as opções disponíveis.
- **Qual prioridade?**  
  1. Finalizar o inimigo se estiver com HP crítico (*Kill Shot*).
  2. Aplicar golpe super efetivo (multiplicador 2.0x).
  3. Usar golpe de maior poder base neutro com PP disponível.
  4. Trocar de Lumen se o HP atual for inferior a 25% e houver companheiro saudável.
- **Como fraqueza elemental é considerada?**  
  Matriz de multiplicadores elementais completa de 18 tipos (`src/combat/combat_engine.py`).
- **Como PP é considerado?**  
  Golpes com PP = 0 recebem pontuação zero e são descartados.
- **Como HP crítico é tratado?**  
  Gera intenção de cura ou troca emergencial de Lumen.

---

## 6. Auditoria de Navegação (NAVIGATION)

- **Como o bot anda?**  
  Através de comandos WASD temporizados com injeção de scancodes via `NavigationController`.
- **Ele usa rota gravada?**  
  Sim, via `RouteManager`, capaz de gravar, salvar em JSON, carregar e reverter rotas automaticamente.
- **Ele usa navegação fechada?**  
  Sim, em modo exploração combina passos de random walk com mapa topológico em `WorldMemory`.
- **Como sabe que realmente se moveu?**  
  Pelo subsistema de feedback visual comparando o frame antes e depois do envio de input (*frame difference* $> 0.005$).
- **Como detecta obstáculo?**  
  Após 3 tentativas de movimento na mesma direção sem variação visual de frame, registra a coordenada como obstáculo na memória topológica.
- **Como evita loop?**  
  Aplica penalidade de repetição (*anti-loop penalty*) nas direções falhas.

---

## 7. Auditoria da Interface do Usuário (GUI)

- **A interface mostra estado real?** Sim, conectado à máquina de estados (`BotStateMachine`).
- **Mostra FPS?** Sim, calculado em tempo real via `TelemetryManager`.
- **Mostra ação atual?** Sim, exibido nos cards do Dashboard e na página Bot Control.
- **Mostra estado do jogo?** Sim (`OVERWORLD`, `BATTLE`, `HEALING`, `DIALOG`, etc.).
- **Mostra HP e Lumen?** Sim, na página de Batalha e no resumo do Dashboard.
- **Mostra último input?** Sim, no console de eventos e no D-Pad.
- **Mostra erro?** Sim, no badge de status e na página Diagnostics.
- **Mostra screenshot?** Sim, feed em tempo real com bounding boxes na página Vision.
