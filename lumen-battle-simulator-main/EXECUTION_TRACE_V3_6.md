# LUMENA BOT v3.6 — EXECUTION TRACE & DECISION LOGS

## 1. Trace de Execução: Caso Real 91/113 HP (~80.5%) em Batalha

Abaixo está o log de execução passo a passo do ciclo de controle v3.6:

```
[2026-08-14 12:00:00.100] [PERCEPTION] Frame capturado (1280x720) via DXGI ScreenCapture.
[2026-08-14 12:00:00.125] [PERCEPTION] TargetWindowManager: Janela 'IA Autônoma para Jogo - Google Chrome' (HWND: 132226) ativa.
[2026-08-14 12:00:00.145] [PERCEPTION] BattleDetector: in_battle=True, player_hp=91/113 (80.5%), enemy_hp=100/100 (100.0%).
[2026-08-14 12:00:00.160] [PERCEPTION] CombatVisionAnalyzer: Inimigo 'Wild FlameLumen' detectado em (675, 275), distância: 350px.
[2026-08-14 12:00:00.170] [PERCEPTION] SkillScanner: 6 slots dinâmicos detectados [1: WaterPulse (READY), 2: FlameBurst (READY), 3: LeafBlade (READY), 4: ThunderShock (READY), 5: Tackle (READY), 6: QuickAttack (READY)].
[2026-08-14 12:00:00.180] [DECISION] LumenaBotEngine: Avaliando hierarquia de objetivos:
                          • is_battle_active = True
                          • player_hp_pct = 0.805 > CRITICAL_HP_RATIO (0.20)
                          • SEARCHING_CRYSTAL = PROIBIDO (crystal_search_blocked=True)
                          • Objetivo Mandatório = COMBAT
                          • Alvo = ENEMY (Wild FlameLumen)
[2026-08-14 12:00:00.190] [DECISION] CombatDecisionEngine: Avaliando habilidades contra oponente do elemento FOGO:
                          • WaterPulse (Água) -> Multiplicador Elemental: 2.0x (SUPER EFETIVO)
                          • Score: 190.0 (Poder 60 + Elemental 2.0x + Ranged Bonus)
                          • Decisão Selecionada: USE_SKILL -> WaterPulse (Slot 1, Hotkey: '1')
[2026-08-14 12:00:00.200] [INPUT] SkillExecutor: Despachando input físico:
                          • InputController: Win32 SendInput (VK=0x31, Scan=0x02)
                          • Tempo de pressionamento: 0.15s
[2026-08-14 12:00:00.380] [VERIFICATION] CombatAgent: Verificação fechada com frame_before vs after_frame:
                          • Delta Visual Calculado: 0.0412 (> 0.0050)
                          • Ação Confirmada: COMBAT_VERIFIED
                          • HealthMonitor atualizado: last_action='USE_SKILL', time_since_last_action=0.0s
```

---

## 2. Trace de Execução: Caso Mundo Aberto com HP Saudável (80%) vs Objeto Azul

```
[2026-08-14 12:00:05.100] [PERCEPTION] Frame capturado no mundo aberto (grama / caminho).
[2026-08-14 12:00:05.130] [PERCEPTION] LandmarkDetector: Objeto azul detectado no cenário (dx=120, dy=-80).
[2026-08-14 12:00:05.140] [PERCEPTION] BattleDetector: in_battle=False, player_hp=80%.
[2026-08-14 12:00:05.150] [DECISION] LumenaBotEngine:
                          • is_battle_active = False
                          • player_hp_pct = 0.80 > HEALING_HP_RATIO (0.40)
                          • Cura Preventiva = DESNECESSÁRIA
                          • Busca de Cristal = BLOQUEADA (crystal_search='BLOCKED')
                          • Objetivo Selecionado = EXPLORE (Patrulha de Farm)
[2026-08-14 12:00:05.160] [INPUT] NavigationController: Despachando passo de patrulha WASD ('W', 0.25s).
[2026-08-14 12:00:05.450] [VERIFICATION] Delta de movimento confirmado (delta: 0.0238 > 0.0050).
```

---

## 3. Trace de Execução: Watchdog de Combate 5s (BATTLE_EXECUTION_STALLED)

```
[2026-08-14 12:00:10.000] [PERCEPTION] Batalha ativa contra 'Boss Lumen'. Inimigo visível.
[2026-08-14 12:00:15.100] [WATCHDOG] Inatividade de combate atingiu 5.1s (limiar: 5.0s).
[2026-08-14 12:00:15.110] [EVENT] EventType.BATTLE_EXECUTION_STALLED publicado no EventBus.
[2026-08-14 12:00:15.120] [RECOVERY] TargetWindowManager.ensure_canvas_focus:
                          • Re-foco forçado na janela alvo HWND 132226
                          • Clique no centro do canvas WebGL (960, 540)
                          • Rescan imediato de habilidades e re-despacho de input físico
[2026-08-14 12:00:15.350] [INPUT] Input físico de ataque reenviado com sucesso.
```
