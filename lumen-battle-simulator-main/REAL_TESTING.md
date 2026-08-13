# Guia de Testes no Ambiente Real (Live Game Testing)

Este documento descreve o protocolo formal de testes no ambiente real com o jogo **Lumena.gg** aberto no Google Chrome.

---

## 1. Protocolo de Validação em 7 Níveis

| Nível | Descrição | Como Testar | Critério de Aprovação |
|---|---|---|---|
| **Nível 1** | Compilação e Importação | Executar suíte de testes unitários | 52/52 testes passando sem erros |
| **Nível 2** | `InputController` e Backends | Executar `test_input.py` | Scancodes mapeados e liberação em finally |
| **Nível 3** | Windows API e Segurança | Executar `test_safety_guard.py` | Emergency stop bloqueia e libera teclas |
| **Nível 4** | Foco Real no Chrome | Abrir Chrome e rodar `test_physical_input.py` | `SetForegroundWindow` e `is_truly_in_foreground = True` |
| **Nível 5** | Foco de Teclado no Canvas | Abrir Chrome e rodar `test_physical_input.py` | Clique central de ativação despachado no DOM |
| **Nível 6** | Resposta Física (Movimento) | Observar personagem no jogo real | Variação visual (Delta Frame > 0.005) e deslocamento |
| **Nível 7** | Automação Completa | Iniciar bot no modo `AUTONOMOUS` | Navegação, combate, vitória e cura em malha fechada |

---

## 2. Passo a Passo do Teste Físico

1. **Abra o Chrome:** Navegue até `https://lumena.gg` e faça login no jogo.
2. **Posicione o Personagem:** Coloque o personagem em uma área livre de obstáculos no mapa.
3. **Execute o Teste Isolado:**
   ```powershell
   & "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" scripts/test_physical_input.py
   ```
4. **Verifique a Sequência Executada:**
   - Script traz a janela para primeiro plano.
   - Script clica no centro da janela para focar o canvas.
   - Pressiona **W (2.0s)** ➔ **A (1.0s)** ➔ **D (1.0s)** ➔ **S (1.0s)**.
   - Captura frame antes e depois e calcula o índice de variação visual (*frame diff*).
   - Salva a evidência visual em `debug/live_input_test.png`.
