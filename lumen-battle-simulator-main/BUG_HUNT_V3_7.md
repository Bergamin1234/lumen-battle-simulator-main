# BUG HUNT REPORT — LUMENA BOT v3.7
## DIAGNÓSTICO DE CAUSA RAIZ E CORREÇÕES ARQUITETURAIS

---

### BUG #1: Vazamento de Contexto de Exploração para a Batalha (Falsos Positivos de Cristal)
* **Sintoma:** Durante batalhas com HP alto (~80.5%), o robô entrava em `SEARCHING_CRYSTAL` ou tentava navegar em direção a elementos azuis no fundo do cenário.
* **Causa Raiz:** O classificador de estado executava `landmark_detector.detect_crystal(frame)` em todos os frames sem verificar se a interface de batalha estava aberta.
* **Correção:** Em `LandmarkDetector.detect_crystal` e `StateClassifier`, adicionada a verificação `if in_battle: return False, None, None`. Quando em batalha, o detector de cristal é estritamente desligado (`DISABLED`).

---

### BUG #2: Inércia e "Observação Infinita" com Botão FIGHT Visível
* **Sintoma:** O bot detectava a batalha, mas permanecia em `OBSERVING` sem clicar em FIGHT.
* **Causa Raiz:** O motor dependia de um ciclo de decisão analítico complexo antes de interagir com o menu primário de combate.
* **Correção:** Implementado `BattleUIController.click_fight()` e regra prioritária em `LumenaBotEngine._handle_battle_cycle`: se o botão FIGHT estiver presente e o menu de habilidades não estiver aberto, o robô dispara imediatamente o clique físico com foco no canvas WebGL e verificação em malha fechada.

---

### BUG #3: Ambiguidade de Sprite entre Jogador de Mundo e Jogador de Batalha
* **Sintoma:** Caixas delimitadoras eram desenhadas em elementos do cenário ao tentar achar o jogador na arena de combate.
* **Causa Raiz:** O mesmo método de detecção centralizado era compartilhado entre overworld e combate.
* **Correção:** Separado em `detect_world_player(frame)` (centralizado na viewport de exploração) e `detect_battle_player(frame)` (focado no quadrante inferior esquerdo da arena).

---

### BUG #4: Avaliação de Cura Antes da Batalha
* **Sintoma:** Código antigo possuía branches condicionais onde a verificação de HP baixo ocorria antes de confirmar se a batalha estava ativa.
* **Causa Raiz:** Ausência de um resolvedor centralizado e estrito de prioridade de estado.
* **Correção:** Criada a função `resolve_high_level_state` com precedência imutável: `BATTLE > HEALING > WORLD`.
