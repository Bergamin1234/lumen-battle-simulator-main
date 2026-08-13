# DYNAMIC COMBAT VISION & DECISION ARCHITECTURE

## 1. Visão Geral (Vision-First Combat)
O sistema de combate do **Lumena Bot Control Center v3.0** adota uma abordagem **Vision-First**, onde a interface real do jogo define a quantidade e a disponibilidade de habilidades em tempo real, em vez de depender de uma lista estática de 2 ataques.

---

## 2. Modelos de Domínio Dinâmicos

### `SkillSlot`
- `slot_index`: Índice sequencial do slot na barra de ações ($1, 2, \dots, N$).
- `screen_x, screen_y, width, height`: Coordenadas absolutas e dimensões do botão.
- `center_x, center_y`: Ponto central para despacho de clique calibrado.
- `available`: Flag booleana indicando se o golpe está pronto para uso.
- `cooldown`: Tempo de recarga restante (calculado via brilho/máscara do slot).
- `element`: Tipo elemental (Água, Fogo, Planta, Elétrico, etc.).
- `power`: Poder base de dano.
- `range_type`: `MELEE`, `RANGED`, `HEAL`, `BUFF` ou `UTILITY`.
- `hotkey`: Tecla associada (ex: `"1"`, `"2"`, `"3"`).

### `EnemyTarget`
- `target_id`: Identificador do alvo na cena.
- `bbox`: Retângulo delimitador `(x, y, w, h)`.
- `center`: Ponto central do inimigo.
- `confidence`: Grau de certeza da detecção visual ($0.0 \dots 1.0$).
- `hp_estimate`: Estimativa da barra de vida do oponente.
- `distance`: Distância euclidiana em relação à posição do jogador.
- `element` e `weakness`: Tipos elementais deduzidos para cálculo de multiplicador.

---

## 3. Fluxo de Decisão em Malha Fechada

```
                 OBSERVE (ScreenCapture)
                           │
                           ▼
             DETECT (CombatVisionAnalyzer)
           • Scan N Skill Slots
           • Detect Cooldown Overlays
           • Detect Enemy Target & HP
                           │
                           ▼
           ANALYZE (CombatDecisionEngine)
           • Filtra Cooldowns > 0
           • Multiplicador Elemental (2.0x Super Efetivo)
           • Avaliação de Alcance (Ranged vs Distância)
           • Avaliação de Risco e Finalização
                           │
                           ▼
            EXECUTE (SkillExecutor / Win32)
           • Despacho via Hotkey ou Clique no Canvas
                           │
                           ▼
             VERIFY (Visual Delta Check)
           • Medição de variação de pixels após o ataque
                           │
                           ▼
                     UPDATE MEMORY
```

---

## 4. Transformação de Coordenadas e DPI-Awareness
O `CombatVisionAnalyzer` implementa conversões explícitas:
- `screen_to_client(point, window_origin)`
- `client_to_screen(point, window_origin)` com fator `_dpi_scale`.
