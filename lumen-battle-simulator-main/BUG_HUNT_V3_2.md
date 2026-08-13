# BUG HUNT REPORT — LUMENA BOT CONTROL CENTER v3.2
## Diagnóstico de Causas-Raiz e Correções de Execução em Malha Fechada

### 1. BUG #1 — Inércia de Execução no Estado `SEARCHING_CRYSTAL`
- **Sintoma Observado**: O bot detectava a presença do cristal no cenário e entrava no estado `SEARCHING_CRYSTAL`, mas ficava parado apenas observando a tela sem se mover em direção ao cristal.
- **Causa-Raiz**: No método `_handle_healing_cycle` anterior, o bot apenas chamava `input_ctrl.press_key('space')` estaticamente sem calcular a distância até o cristal e sem despachar teclas de navegação (`W`, `A`, `S`, `D`). Como o jogador estava a centenas de pixels de distância do cristal, o input de espaço não interagia com nada e no frame seguinte o ciclo se repetia eternamente em deadlock observacional.
- **Correção Aplicada**:
  - Implementado o `HealingController` de malha fechada em `src/automation/healing.py` com máquina de estados interna: `SEARCH_TARGET` ➔ `TARGET_LOCKED` ➔ `APPROACH_TARGET` ➔ `ALIGN_TARGET` ➔ `INTERACT_READY` ➔ `INTERACTING` ➔ `VERIFYING` ➔ `HEALING_VERIFIED`.
  - O controlador calcula a distância euclidiana até o cristal ($d = \sqrt{dx^2 + dy^2}$). Se $d > 80\text{px}$, despacha micro-movimentos direcionais na direção dominante. Quando $d \le 80\text{px}$ ou prompt contextual detectado, executa a interação de cura.

---

### 2. BUG #2 — Identificação do Cristal Azul e Prioridade Semântica
- **Sintoma Observado**: O cristal azul no centro do mapa era detectado como marco genérico de cenário sem garantia semântica.
- **Causa-Raiz**: O detector de marcos computava apenas contornos azuis sem tag semântica explícita e sem método para reconhecimento de caixas de prompt ("PRESS SPACE TO INTERACT").
- **Correção Aplicada**:
  - Atualizado `LandmarkDetector.detect_crystal` com pontuação multi-critério marcando `semantic_type = "HEALING_CRYSTAL"` e adicionado o método `detect_interaction_prompt(frame)`.

---

### 3. BUG #3 — Integração de Combate em Produção no BotEngine
- **Sintoma Observado**: O subsistema de combate dinâmico (`CombatVisionAnalyzer` e `CombatPositioningController`) estava desacoplado do ciclo de batalha do `LumenaBotEngine`.
- **Causa-Raiz**: O `BotEngine` usava instâncias antigas de telemetria de batalha em vez de alimentar o `CombatAgent` com o `CombatVisionAnalyzer.analyze_frame`.
- **Correção Aplicada**:
  - Conectado `self.combat_vision.analyze_frame(frame_before)` dentro de `_handle_battle_cycle` em `src/automation/bot_engine.py`. O pipeline de combate agora executa seleção dinâmica de habilidades, posicionamento tático e verificação pós-ação em malha fechada.

---

### 4. BUG #4 — Ausência de Watchdog de Inércia Física
- **Sintoma Observado**: Quando o bot entrava em loop de observação, não havia alerta ou recuperação caso ficasse muito tempo sem despachar ações físicas.
- **Causa-Raiz**: Falta de temporizador de última ação física.
- **Correção Aplicada**:
  - Implementado `self._last_physical_action_time` e verificação de inatividade de 15 segundos em `BotEngine._execute_single_cycle`. Dispara `EventType.EXECUTION_STALLED` e força refoco da janela para destravar o agente.
