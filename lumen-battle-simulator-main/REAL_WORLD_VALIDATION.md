# GUIA PRÁTICO DE VALIDAÇÃO NO MUNDO REAL (LEVELS 1 — 7)

Este documento orienta a execução e verificação física do Lumena Bot no **Google Chrome** rodando o jogo **Lumena.gg**.

---

## 1. Matriz de Níveis de Validação

| Nível | Descrição | Status do Código | Como Validar Fisicamente |
|---|---|---|---|
| **LEVEL 1** | Modelos, FSM, Telemetria e Sintaxe | ✅ COMPROVADO (72/72 PASS) | Executar suíte de testes unitários. |
| **LEVEL 2** | InputController, Scancodes e SafetyGuard | ✅ COMPROVADO | Testes automatizados e diagnósticos de hardware. |
| **LEVEL 3** | Win32 API (AttachThreadInput, SetFocus) | ✅ COMPROVADO | Teste de elevação de janela. |
| **LEVEL 4** | Foco Real no Google Chrome (Rejeita LumenaBot) | ✅ LÓGICA CONFIRMADA | Abrir Chrome, rodar Wizard no Lumena Bot. |
| **LEVEL 5** | Foco no Canvas WebGL via Clique | ✅ LÓGICA CONFIRMADA | Verificar clique inicial no centro do canvas. |
| **LEVEL 6** | Movimento Físico com Delta Visual | ⏳ AGUARDA BROWSER REAL | Executar `scripts/real_world_test.py` com o jogo aberto. |
| **LEVEL 7** | Loop Autônomo Completo (Explorar/Lutar/Curar) | ⏳ AGUARDA BROWSER REAL | Pressionar START (F5) no Lumena Bot Control Center. |

---

## 2. Passo a Passo para Validação Física do Nível 6

1. Abra o **Google Chrome** no Windows.
2. Acesse `https://lumena.gg` e faça login com seu personagem.
3. Posicione seu personagem em uma área segura do mapa (longe de obstáculos).
4. Abra o **Lumena Bot Control Center** (`python main.py` ou `dist/LumenaBot/LumenaBot.exe`).
5. Acesse a aba **Validation Levels** ou **Diagnostics** e clique em **PHYSICAL INPUT TEST (Level 6)** (ou execute `python scripts/real_world_test.py`).
6. Observe:
   - A janela do Chrome será trazida para o primeiro plano.
   - O foco será verificado via `GetForegroundWindow()`.
   - Um frame de referência `before.png` será capturado.
   - A tecla **W** será pressionada por 0.50 segundos.
   - O frame final `after.png` será capturado e o `diff.png` gerado.
   - O relatório com as evidências será salvo em `debug/evidence/<timestamp>/`.

---

## 3. Estrutura do Pacote de Evidências (`debug/evidence/<timestamp>/`)

- `before.png`: Screenshot exato antes do envio da tecla.
- `after.png`: Screenshot após o envio da tecla.
- `diff.png`: Mapa térmico visual da variação de pixels.
- `input.json`: Detalhes do scancode, duração e timestamp de envio.
- `window.json`: HWND, PID, processo e confirmação de foreground.
- `telemetry.json`: Estado da telemetria no instante do teste.
- `result.json`: Veredito formal com a taxa de delta visual obtida.
