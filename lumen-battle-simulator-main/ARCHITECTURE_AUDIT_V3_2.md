# ================================================================
# LUMENA BOT CONTROL CENTER v3.2 — AUDITORIA DE ARQUITETURA
# ================================================================
## Pipeline Vision-First, Closed-Loop, Target-Safe & Fail-Safe

---

## 1. TOPOLOGIA DO SISTEMA & SINGLE SOURCE OF TRUTH (SSOT)

O projeto consolida uma arquitetura unidirecional e auditável, garantindo que nenhum subsistema desvie do pipeline oficial:

```
[ GUI / Wizard ] 
       │
       ▼
[ BotController (Thread Manager & Level 7 Gate) ]
       │
       ▼
[ LumenaBotEngine (SSOT do Ciclo de Automação) ]
       ├── Perception (ScreenCapture + StateClassifier + CombatVision + OCR)
       ├── Memory (ShortTermMemory + LongTermMemory + SpatialMemory)
       ├── Decision (CombatDecisionEngine + NavigationController)
       ├── Action (CombatAgent + PositioningController + SkillExecutor)
       ├── Input (InputController + Win32/DirectInput Backend)
       └── Verification (Closed-Loop Visual Delta + Action Verification)
       │
       ▼
[ SafetyGuard (Foreground Match + Self-PID Block + ESC Emergency Stop) ]
       │
       ▼
[ EventBus & TelemetryManager ] ──► [ Queue ] ──► [ GUI Tick (50ms) ]
```

---

## 2. INVENTÁRIO DE MÓDULOS E AUDITORIA DETALHADA

| Módulo | Responsabilidade | Status de Integridade | SSOT & Segurança |
| :--- | :--- | :--- | :--- |
| `src/automation/bot_engine.py` | Motor central da máquina de estados (FSM) e ciclo closed-loop | **ATIVO & ESTÁVEL** | Controla Anti-Stuck (limite rígido 3) e transições seguras. |
| `src/automation/bot_controller.py` | Gerenciamento do ciclo de vida em background thread e portão Level 7 | **ATIVO & BLINDADO** | Gate Level 7 travado sem validação física comprovada. |
| `src/input/target_window.py` | Descoberta real de navegadores e rejeição de processo próprio | **ATIVO & CORRIGIDO** | Rejeição por PID (`os.getpid()`), executável e títulos do bot. |
| `src/input/safety_guard.py` | Validação de foreground, rate limit, liberação de teclas e parada emergencial | **ATIVO & BLINDADO** | Bloqueia input se `GetForegroundWindow() != target_hwnd`. |
| `src/input/input_controller.py` | Controlador híbrido com scancodes de hardware e `try...finally` | **ATIVO & CORRIGIDO** | Valida foco e passa `foreground_hwnd` em todo dispatch. |
| `src/perception/combat_vision.py` | Visão computacional dinâmica para $N$ slots, HP, jogador e inimigo | **ATIVO & EXPANSÍVEL** | Detecção dinâmica via luminosidade, sem limites fixos. |
| `src/perception/debug_skill_scanner.py`| Scanner visual de habilidades com anotações e exportação JSON | **ATIVO & AUDITÁVEL** | Salva em `debug/skill_scanner/<timestamp>/`. |
| `src/combat/positioning.py` | Controlador tático de alcance e movimentação (Approach/Retreat) | **ATIVO & INTEGRADO** | Compara distância euclidiana com alcance da habilidade. |
| `src/combat/decision_engine.py` | Motor explicável de ranking com fraquezas, cura e penalidades | **ATIVO & EXPLICÁVEL** | Fórmula matemática determinística sem sequências cegas. |
| `src/combat/combat_agent.py` | Agente executor em malha fechada e Action Verification | **ATIVO & AUDITÁVEL** | Emite `ACTION_UNCONFIRMED` e penaliza falhas visuais. |
| `src/ui/modern_gui.py` | Control Center Desktop moderno em Tkinter com consumo por fila | **ATIVO & THREAD-SAFE** | Atualização em 50ms via `Queue` sem tocar widgets em worker. |

---

## 3. AUDITORIA DE CÓDIGO MORTO E LEGADO
- Módulos em `src/legacy/` permanecem isolados e não são importados pelo fluxo oficial de produção.
- Todos os endpoints e modelos utilizam `src.models.combat_vision` e `src.models.enums`.
