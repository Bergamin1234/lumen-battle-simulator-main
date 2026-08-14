# LUMENA BOT v3.6 — BUG HUNT & ROOT CAUSE ANALYSIS

## 1. Relatório de Investigação do Bug Observado

### Sintoma
No jogo `lumena.gg`, o jogador entrava em combate contra um Lumen selvagem. O oponente estava visível na arena, a interface de combate e botões de habilidade estavam presentes, e o personagem tinha aproximadamente **91/113 HP (~80.5%)**.
No entanto, o bot alternava para `SEARCHING_CRYSTAL`, procurava o cristal de cura azul no cenário e permanecia inerte sem atacar.

---

## 2. Rastreamento e Causa Raiz Linha a Linha

### Bug #1: Heurística HSV de Cristal Acionada por Elementos de Interface e Cenário
- **Arquivo:** [`src/perception/landmark_detector.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/perception/landmark_detector.py) / [`src/perception/state_classifier.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/perception/state_classifier.py)
- **Problema:** Durante o combate, ícones de habilidades de água, barras de mana ou elementos ciano da UI ativavam a máscara HSV `[85..135, 80..255, 120..255]`.
- **Consequência:** `crystal_found = True` e `snapshot.crystal_detected = True` eram gerados a cada ciclo.

### Bug #2: Decisão de Estado Incondicional no `StateClassifier`
- **Arquivo:** [`src/perception/state_classifier.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/perception/state_classifier.py) (antigas linhas 155-157)
- **Código Antigo:**
  ```python
  # D. Cristal Azul no Campo Visual
  if crystal_detected:
      return AgentState.SEARCHING_CRYSTAL
  ```
- **Consequência:** Sempre que `crystal_detected` fosse True, o estado da tela era classificado como `SEARCHING_CRYSTAL` mesmo com o HP em 80.5% ou em mundo aberto com grama.

### Bug #3: Hierarquia de Decisão Permissiva no `LumenaBotEngine`
- **Arquivo:** [`src/automation/bot_engine.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/automation/bot_engine.py) (antigas linhas 319-335)
- **Código Antigo:**
  ```python
  elif team_needs_heal or snapshot.screen_state in (AgentState.HEALING, AgentState.SEARCHING_CRYSTAL) or snapshot.crystal_detected:
      self.health_monitor["current_goal"] = "HEAL"
      self.health_monitor["current_target"] = "HEALING_CRYSTAL"
      self.fsm.transition_to(BotState.HEALING, reason="Ponto de Cura / Cristal Ativo")
      self._handle_healing_cycle(snapshot, frame)
  ```
- **Consequência:** Devido ao operador `or snapshot.crystal_detected`, qualquer frame com detecção de cristal (inclusive falso-positivo de UI) forçava o estado para `BotState.HEALING` e invocava `HealingController.step`. Como o jogo estava na tela de batalha, os inputs WASD do `HealingController` eram ignorados pelo canvas do jogo e nenhum ataque era despachado.

### Bug #4: Fallback de Alvos Inimigos sem Checar Batalha Ativa
- **Arquivo:** [`src/perception/combat_vision.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/perception/combat_vision.py) (antigas linhas 374-394)
- **Problema:** `detect_enemy_targets` gerava um `EnemyTarget` sintético padrão mesmo quando `in_battle` era falso e o frame estava totalmente preto ou fora de combate.

### Bug #5: Falta de `frame_before` na Verificação de Ataque
- **Arquivo:** [`src/automation/bot_engine.py`](file:///C:/Users/02555331280/Downloads/lumen-battle-simulator-main/lumen-battle-simulator-main/src/automation/bot_engine.py) (antiga linha 377)
- **Código Antigo:**
  ```python
  turn_res = self.combat_agent.process_combat_snapshot(combat_snapshot, screen_capture_func=self.screen_capture.capture_frame)
  ```
- **Problema:** O parâmetro `frame_before` não era passado, impossibilitando o cálculo de variação visual de pixels `compute_visual_delta(frame_before, after_frame)`.

---

## 3. Soluções de Engenharia Aplicadas

1. **HP Policy Centralizada:**
   - `CRITICAL_HP_RATIO = 0.20`
   - `HEALING_HP_RATIO = 0.40`
   - `COMBAT_ACTION_TIMEOUT = 5.0`
2. **Prioridade Absoluta de Combate:**
   - Se `is_battle_active == True` e `HP > 0.20` $\implies$ `current_goal = "COMBAT"`, `current_target = "ENEMY"`, `crystal_search = "BLOCKED"`.
3. **Cura Condicionada Fora de Batalha:**
   - O cristal de cura só é procurado/alcançado se `is_battle_active == False` e `HP <= 0.40`.
4. **Watchdog de Combate de 5 Segundos:**
   - Se `time.time() - self._last_combat_action_time > 5.0` em combate com inimigo $\implies$ Emite `EventType.BATTLE_EXECUTION_STALLED` e re-adquire o canvas WebGL.
5. **Passagem Real de `frame_before`:**
   - `turn_res = self.combat_agent.process_combat_snapshot(csnap, screen_capture_func=self.screen_capture.capture_frame, frame_before=frame_before)`
