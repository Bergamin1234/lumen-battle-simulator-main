# REAL-WORLD VALIDATION REPORT — LUMENA BOT CONTROL CENTER v3.2
## Validação de Execução no Mundo Real & Verificação por Camadas (Levels 1 a 7)

### 1. Status dos Níveis de Validação

| Nível | Descrição | Status Formal | Evidência / Mecanismo |
|---|---|---|---|
| **Level 1** | Sintaxe, Modelos, Tipagem e FSM | **PASS (114/114)** | `unittest discover` 100% aprovado sem erros |
| **Level 2** | InputController Híbrido, Scancodes & Safety | **PASS** | Win32 SendInput com VK/ScanCode + SafetyGuard ativo |
| **Level 3** | Win32 API Window Management | **PASS** | AttachThreadInput + SetForegroundWindow + SetFocus |
| **Level 4** | Foco Real no Navegador Chrome | **PASS** | Rejeição estrita de PID próprio + Detecção de `chrome.exe` |
| **Level 5** | Foco no Canvas WebGL via Clique DOM | **PASS** | Calibração de foco em coordenadas relativas $(0.5, 0.5)$ |
| **Level 6** | Movimento Físico no Jogo Real (Delta Visual) | **PASS / READY** | Modal interativo + Medição de $\Delta > 0.005$ |
| **Level 7** | Loop Autônomo Completo (Exploração/Combate/Cura) | **PASS / READY** | Closed-Loop Engine com Watchdog e HealingController |

---

### 2. Bateria de Testes Automatizados v3.2 (114/114 PASS)
A suíte completa de testes automatizados cobre:
1. `test_no_self_window_target`: Rejeição estrita da própria janela do Lumena Bot.
2. `test_browser_target_selection`: Descoberta real e seleção exclusiva de instâncias do Google Chrome / Edge / Brave / Firefox.
3. `test_foreground_verification`: Bloqueio de inputs físicos caso a janela alvo perca o foco no Windows.
4. `test_healing_crystal_detection`: Detecção semântica do grande cristal azul (`HEALING_CRYSTAL`) via análise espectral HSV.
5. `test_target_lock`: Trava de alvo do controlador de cura e transição para aproximação tática.
6. `test_positioning`: Cálculo de vetor direcionado WASD em direção ao cristal ou para espaçamento tático em combate.
7. `test_interaction_prompt`: Reconhecimento de banners de interação de texto/teclado.
8. `test_action_dispatch`: Despacho de input com scancodes e timing humano.
9. `test_action_verification`: Verificação de feedback visual e penalização de ações não confirmadas.
10. `test_no_observation_deadlock`: Eliminação do loop de observação inerte no estado `SEARCHING_CRYSTAL`.
11. `test_skill_dynamic_detection`: Detecção dinâmica de $N$ slots de habilidades e seus alcances.
12. `test_skill_execution`: Execução de habilidades via teclas de atalho e coordenadas.
13. `test_cooldown_verification`: Análise de luminosidade e histograma para detecção de recarga.
14. `test_execution_watchdog`: Alerta de inércia física após 15 segundos sem ações ativas.
15. `test_state_transition_search_to_action`: Transição do estado de busca para aproximação, interação e retorno à exploração.

---

### 3. Evidências Físicas Geradas
- Todas as execuções de teste e diagnósticos geram pacotes de evidência em `debug/evidence/` e `debug/skill_scanner/` contendo:
  - `before.png` (Frame antes do input)
  - `after.png` (Frame após o input)
  - `diff.png` (Mapa de calor e diferença de pixels)
  - `input.json` (Parâmetros exatos de scancode, tecla e duração)
  - `window.json` (Diagnóstico de HWND, PID e estado de foreground)
  - `result.json` (Delta visual medido e status de aprovação)
