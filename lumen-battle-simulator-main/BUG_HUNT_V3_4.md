# LUMENA BOT CONTROL CENTER v3.4 — RELATÓRIO DE BUG HUNT
## Auditoria Contínua, Diagnóstico de Causa Raiz e Eliminação de Vulnerabilidades

**Data:** 14 de Agosto de 2026  
**Status Geral:** `0 BUGS ABERTOS / 100% CORRIGIDO`

---

## 1. HISTÓRICO DE BUGS IDENTIFICADOS E CORRIGIDOS

| Bug ID | Descrição do Problema | Impacto | Causa Raiz | Correção Aplicada |
| :---: | :--- | :--- | :--- | :--- |
| **BUG-01** | Bot entrava em `SEARCHING_CRYSTAL` e ficava estático | Paralisia Observacional | Vetor relativo dependia de $(w/2, h/2)$ sem rastrear o player e faltava busca ativa quando o cristal saía da tela. | Implementado `detect_player`, vetor $(dx, dy)$ relativo e rotina de varredura tática ativa. |
| **BUG-02** | Risco de auto-seleção da janela do Lumena Bot | Falha de Segurança | Processos com PID próprio poderiam ser avaliados se o título contivesse 'Chrome' em janelas de debug. | `TargetWindowManager` e `SafetyGuard` bloqueiam explicitamente o próprio PID, executável e títulos do Lumena Bot. |
| **BUG-03** | Falso positivo em `ACTION_VERIFIED` em pipelines legados | Distorção de Métricas | Chamadas de funções retornavam `True` sem validação de frames pré e pós input. | Introduzido `InputController.compute_visual_delta` ($\Delta \ge 0.005$). Se $\Delta < 0.005$, a ação torna-se `ACTION_UNCONFIRMED`. |
| **BUG-04** | Ataques às cegas em combate sem checar cooldown | Desperdício de Turno | Motor escolhia skill de maior poder sem conferir se o slot estava pronto. | `CombatDecisionEngine` filtra e penaliza skills com `cooldown_ratio > 0.1` ou `available == False`. |
| **BUG-05** | Loop infinito em situações de desengate anti-stuck | Bloqueio de Thread | Não havia teto máximo de tentativas de recuperação. | Adicionado limite estrito de 3 tentativas (`_handle_anti_stuck`), transitando para `BotState.ERROR` e `SAFE_STOP` em caso de falha. |
| **BUG-06** | Inércia em caso de perda de primeiro plano da janela | Perda de Ação | Bot continuava tentando despachar sem saber que o Windows havia mudado o foco. | Watchdog de 15s dispara `EXECUTION_STALLED` e re-solicita foco Win32 para o navegador alvo. |

---

## 2. AUDITORIA DE CÓDIGO CONTRA "FAKE PASS"

Todos os arquivos do projeto foram auditados:
- Nenhuma função emite `physically_validated = True` sem captura real e comparação visual em sessão desktop ativa.
- Todos os testes unitários em `tests/` são isolados e não poluem as métricas de validação física em disco.
