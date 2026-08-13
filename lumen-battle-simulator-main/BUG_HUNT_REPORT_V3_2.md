# ================================================================
# LUMENA BOT CONTROL CENTER v3.2 — RELATÓRIO DE CAÇA A BUGS (BUG HUNT)
# ================================================================

Este relatório documenta todos os bugs reais reproduzidos, isolados, corrigidos e validados por testes de regressão na versão v3.2.

---

## 1. BUGS IDENTIFICADOS E CORRIGIDOS

### 🐛 BUG #1: Bypass Artificial em Janelas Mockadas no TargetWindowManager
- **Severidade**: ALTA (Arquitetural)
- **Arquivo**: `src/input/target_window.py`
- **Sintoma**: `list_browser_candidates()` continha verificações `if is_mock` que forçavam `proc_name = "chrome.exe"` e `is_self = False`, impedindo que testes unitários e rotinas com janelas simuladas validassem a verdadeira rejeição de `is_own_window()`.
- **Causa**: Resquício de desenvolvimento inicial que criava atalhos artificiais para mocks.
- **Correção**: Refatoração completa de `list_browser_candidates()` utilizando `user32.IsWindow(hwnd)` para diferenciar janelas ativas reais do sistema operacional e avaliar `is_own_window()` universalmente.
- **Validação**: Testes `test_case_1_bot_and_chrome_opened` e `test_case_7_multiple_browsers_discovery` agora passam com 100% de precisão.

---

### 🐛 BUG #2: Omissão de `foreground_hwnd` na Validação de Despacho de Input
- **Severidade**: CRÍTICA (Segurança)
- **Arquivo**: `src/input/input_controller.py`
- **Sintoma**: As funções `press_key_with_diagnostic`, `hold_keys` e `click` chamavam `safety_guard.validate_can_dispatch()` sem repassar o `foreground_hwnd` atual do Windows (`user32.GetForegroundWindow()`), permitindo que a checagem de primeiro plano ficasse restrita apenas a flags em cache.
- **Causa**: O parâmetro `foreground_hwnd` havia sido adicionado ao `SafetyGuard`, mas não estava sendo fornecido nas chamadas de `InputController`.
- **Correção**: Consulta dinâmica e repasse seguro de `fg_hwnd = user32.GetForegroundWindow()` em todos os métodos de despacho físico.
- **Validação**: Testes `test_case_4_other_window_in_foreground` e `test_foreground_verification_and_input_blocking` garantem bloqueio imediato se outra janela tomar o foco.

---

### 🐛 BUG #3: Instanciação Incompleta de Modelos de Combate (`CombatSnapshot`)
- **Severidade**: MÉDIA (Tipagem / Usabilidade)
- **Arquivo**: `src/models/combat_vision.py`
- **Sintoma**: `CombatSnapshot` exigia `timestamp` posicional obrigatório sem valor padrão, gerando `TypeError` em instanciações simplificadas.
- **Causa**: Falta de `default_factory=time.time` no campo `timestamp`.
- **Correção**: Adicionado `import time` e `timestamp: float = field(default_factory=time.time)`.
- **Validação**: `test_combat_decision_scoring_explainability` aprovado.

---

### 🐛 BUG #4: Conflito de Escopo com `user32` em `InputController`
- **Severidade**: ALTA (Runtime Crash)
- **Arquivo**: `src/input/input_controller.py`
- **Sintoma**: `NameError: name 'user32' is not defined` ao invocar `GetForegroundWindow()`.
- **Causa**: `user32 = ctypes.windll.user32` não estava declarado no escopo global de `input_controller.py`.
- **Correção**: Adicionada declaração segura `user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None` e verificações defensivas.
- **Validação**: Suíte completa de 99 testes executada com sucesso.

---

## 2. RESUMO DE REGRESSÃO

| Teste | Objetivo | Resultado |
| :--- | :--- | :--- |
| `test_case_1_bot_and_chrome_opened` | Garante que o bot é rejeitado e o Chrome é aceito | **PASS** |
| `test_case_4_other_window_in_foreground` | Bloqueia input quando outra janela está no topo | **PASS** |
| `test_case_6_pid_mismatch_or_reused_by_bot` | Bloqueia tentativa de input para o próprio PID | **PASS** |
| `test_case_7_multiple_browsers_discovery` | Enumera Chrome, Edge, Firefox, Brave | **PASS** |
| `test_antistuck_strict_limit_safe_stop` | Safe Stop imediato na 4ª tentativa de stuck | **PASS** |
| `test_level7_hard_gate_no_bypass` | Trava total do modo autônomo sem Level 6 físico | **PASS** |
