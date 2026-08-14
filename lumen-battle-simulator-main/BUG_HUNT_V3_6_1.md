# BUG HUNT REPORT — LUMENA BOT v3.6.1
## CAUSA RAIZ, ANÁLISE DE BUGS E SOLUÇÕES APLICADAS

---

### BUG #1: Falta de Validação Explícita do Personagem do Jogador em Combate (Prevenção de Ataque Cego)
* **Sintoma:** O analisador de combate identificava inimigos e habilidades, mas não validava a presença real do sprite do jogador na arena de combate, o que poderia permitir tentativas de ataque antes do carregamento completo da arena ou em transições de tela.
* **Causa Raiz:** O método `analyze_frame` não possuía um detector dedicado para o jogador na arena de combate, apenas estimava a posição de forma fixa.
* **Solução:** Implementado `detect_player_in_combat(frame)` em `CombatVisionAnalyzer` que analisa o quadrante inferior esquerdo com Canny Edge + Contornos semânticos, retornando `(player_detected, player_bbox, player_center, player_confidence)`. Se não detectado durante combate, o `CombatDecisionEngine` emite `EventType.PERCEPTION_FAILURE` e bloqueia ataques cegos.

---

### BUG #2: Discrepância de Identificadores e Eventos de Verificação de Ação
* **Sintoma:** A cadeia de eventos de ataque não registrava formalmente o ciclo `ACTION_REQUESTED -> ACTION_DISPATCHED -> ACTION_VERIFICATION_STARTED -> ACTION_VERIFIED / ACTION_UNCONFIRMED`.
* **Causa Raiz:** O `SkillExecutor` e `CombatAgent` emitiam eventos legados sem carregar o `action_id`, `target_hwnd`, `target_pid` e `visual_delta`.
* **Solução:** Unificada a emissão em `SkillExecutor.execute_skill` e `CombatAgent.process_combat_snapshot`. Todo ataque recebe um `action_id` único com timestamp milissegundo, target HWND e verificação em malha fechada pós-frame.

---

### BUG #3: Ausência de Prefixo Padronizado em Falta de Skills Disponíveis
* **Sintoma:** Quando todas as habilidades estavam em recarga (cooldown) e o botão FIGHT já estava aberto, o motor retornava razão genérica de espera sem a tag padronizada `NO_SKILL_AVAILABLE`.
* **Causa Raiz:** A regra de fallback em `CombatDecisionEngine` retornava apenas "Aguardando animação ou recarga de habilidades.".
* **Solução:** Atualizada a razão para `"NO_SKILL_AVAILABLE: Aguardando animação ou recarga de habilidades."` com pontuação neutra e score zero.

---

### BUG #4: Descoberta de Janelas e Alias de API
* **Sintoma:** Scripts externos que invocavam `win_mgr.discover_candidates` ou `win_mgr.get_active_target` falhavam com `AttributeError`.
* **Causa Raiz:** Métodos nomeados internamente como `list_browser_candidates` e `_current_target` sem wrappers públicos correspondentes.
* **Solução:** Adicionados aliases formais `discover_candidates` e `get_active_target` na classe `TargetWindowManager`.
