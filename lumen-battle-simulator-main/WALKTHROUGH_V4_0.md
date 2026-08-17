# LUMENA BOT CONTROL CENTER v4.0 — WALKTHROUGH & USER MANUAL
**Versão**: v4.0.0 Stable  
**Data**: 17 de Agosto de 2026

---

## 1. O Que Há de Novo na v4.0

1. **Rotação Multi-Turno Inteligente de Habilidades**:
   - `SkillStrategyEngine` em `src/combat/skill_strategy.py` gerencia o cooldown interno de cada slot.
   - Suporte a prioridades de dano/efeito com fallback resiliente para ataques básicos caso slots primários estejam recarregando.

2. **Ciclo de Vida Autônomo Completo (World <-> Battle <-> Healing)**:
   - FSM estrita em `src/automation/state_machine.py` e `src/automation/bot_engine.py`.
   - Avaliação contínua de HP: ao vencer uma batalha ou durante exploração, se `HP <= 40%`, o bot suspende a busca por monstros e navega até o Cristal de Cura; restaurado o HP (`>= 90%`), retoma a exploração automaticamente.

3. **Despachador Bézier com Humanização Real**:
   - Movimentação do cursor em curvas de Bézier cúbicas suaves, perfil senoidal ease-in-out, micro-jitter estocástico e distribuição gaussiana de clique em `src/input/input_dispatcher.py`.

4. **Pipeline de Percepção Ultra-Rápido (< 5ms)**:
   - ROIs normalizadas e equalização de histograma adaptativa (CLAHE) para imunidade a brilhos e variações de iluminação de magias no WebGL.

5. **Killswitch com Limpeza Win32 de Emergência**:
   - Pressionar **F12** ou **ESC** interrompe imediatamente o motor, libera todas as teclas pressionadas no sistema operacional e gera um dump detalhado em `debug/emergency_stop.json`.

---

## 2. Como Executar

### Opção A: Executar via Python (Código Fonte)
```powershell
# Ativar ambiente ou executar diretamente:
py -3.12 main.py
```

### Opção B: Executar Executável Compilado de Produção
```powershell
.\dist\LumenaBot\LumenaBot.exe
```

### Opção C: Executar Validador de Sessão ao Vivo (Harness de 7 Passos)
```powershell
py -3.12 scripts/diagnostics/live_combat_loop_test.py
```

---

## 3. Comandos e Teclas de Atalho

- **F12 / ESC**: Parada de Emergência Instantânea (Emergency Killswitch).
- **W / A / S / D**: Teclas de movimentação física no mundo aberto.
- **E / Espaço**: Tecla de interação com o Cristal de Cura e dismiss de modais pós-batalha.
