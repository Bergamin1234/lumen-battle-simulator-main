# TARGET WINDOW ARCHITECTURE & DISCOVERY SYSTEM

## 1. Visão Geral e Regra Absoluta de Isolamento
No **Lumena Bot Control Center v3.0**, a janela do próprio aplicativo LumenaBot **NUNCA** pode ser selecionada como janela alvo (`Target Window`).

### Regra Anti-Self-Targeting:
1. **Rejeição por PID Próprio (`os.getpid()`):** Todo HWND pertencente ao processo atual do Python/LumenaBot é descartado imediatamente antes de qualquer tentativa de foco ou envio de evento.
2. **Rejeição por Título:** Qualquer janela cujo título contenha `"LumenaBot"`, `"Lumena Bot Control Center"` ou `"Autonomous Agent Suite"` é filtrada.
3. **Validação do Processo Real (`chrome.exe`):** O sistema inspeciona o executável de cada HWND ativo. Apenas janelas pertencentes a navegadores reais (`chrome.exe`, `msedge.exe`, `brave.exe`) e com dimensões mínimas ($> 200 \times 200$) são elegíveis.

---

## 2. Fluxo em 7 Etapas do Target Window Wizard

```
[STEP 1] Enumerar janelas ativas do Win32 (gw.getAllWindows())
   │
   ▼
[STEP 2] Filtrar e identificar processo chrome.exe (PID != os.getpid())
   │
   ▼
[STEP 3] Localizar aba candidata ao Lumena.gg
   │
   ▼
[STEP 4] Confirmar HWND, Visibilidade e Retângulo Cliente
   │
   ▼
[STEP 5] Solicitar elevação e primeiro plano (SW_RESTORE, AttachThreadInput, SetForegroundWindow)
   │
   ▼
[STEP 6] Verificar foco real no Windows: GetForegroundWindow() == target_hwnd
   │
   ▼
[STEP 7] Calibrar foco no Canvas WebGL via clique normalizado (0.5, 0.5)
```

---

## 3. Diferenciação Formal entre Solicitação e Confirmação de Foco

| Evento | Condição / Significado |
|---|---|
| `WINDOW_FOCUS_REQUESTED` | `SetForegroundWindow(hwnd)` e `SetFocus(hwnd)` foram chamados pelo Win32. |
| `WINDOW_FOCUS_VERIFIED` | `GetForegroundWindow() == target_hwnd` confirmado pelo sistema operacional. |
| `WINDOW_FOCUS_FAILED` | A janela não conseguiu primeiro plano (outra aplicação possui o foco ativo). |

---

## 4. Proteção Integrada com SafetyGuard
Antes de qualquer envio de tecla física (`press_key`, `hold_keys`, `click`), o `SafetyGuard.validate_can_dispatch()` valida:
- `is_emergency_stopped` é Falso.
- `target_pid != os.getpid()`.
- `target_title` não pertence ao Lumena Bot.
- `is_window_confirmed` é Verdadeiro.
- `GetForegroundWindow() == target_hwnd`.

Se qualquer checagem falhar, a entrada é **bloqueada atômica e imediatamente**, sem qualquer clique ou disparo indevido.
