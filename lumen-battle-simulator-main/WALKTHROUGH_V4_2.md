# 🚀 GUIA DE OPERAÇÃO & WALKTHROUGH — LUMENA BOT v4.2

Este guia orienta a inicialização e operação do **Lumena Bot Control Center v4.2** no ambiente de produção.

---

## 1. INICIALIZAÇÃO RÁPIDA

### Opção A: Executável Compilado (Sem Dependência de Python)
1. Navegue até a pasta `dist/LumenaBot/`.
2. Dê duplo clique em `LumenaBot.exe`.
3. A interface do **Lumena Bot Control Center** será aberta.

### Opção B: Execução Direta via Python
```powershell
py -3.12 main.py
```

---

## 2. FLUXO DE OPERAÇÃO EM SESSÃO REAL

1. **Abra o Navegador**: Inicie o Google Chrome e faça login no jogo `Lumena.gg`.
2. **Conecte a Janela**:
   - Na GUI do bot, observe o badge superior `🪟 TARGET`. Ele exibirá automaticamente `TARGET: Lumena (chrome.exe)` e o retângulo útil do `<canvas>` WebGL.
   - O indicador `CANVAS: (x, y, w, h) | LETTERBOX: OFF/ACTIVE` no Dashboard confirmará o enquadramento.
3. **Teste de Fumaça em Malha Fechada**:
   - Clique no botão azul `🚀 RUN LIVE COMBAT SMOKE TEST` no Dashboard.
   - O bot testará a aquisição do canvas, detecção de batalha e prontidão de input com feedback ao vivo no log.
4. **Inicie a Autonomia**:
   - Selecione o modo `AUTONOMOUS` e clique em `▶ START BOT`.
   - O bot gerenciará o ciclo completo: Exploração $\rightarrow$ Detecção de Combate $\rightarrow$ Clique no FIGHT $\rightarrow$ Seleção de Skill $\rightarrow$ Fechamento de Modais de Vitória/Recompensa $\rightarrow$ Cura preventiva no cristal se $\text{HP} \le 40\%$.
5. **Parada de Emergência**:
   - Pressione `ESC` ou clique no botão vermelho `🚨 EMERGENCY STOP` a qualquer momento para desengatar todos os inputs e gerar o dump forense no Blackbox Recorder.

---

## 3. AUDITORIA FORENSE COM O BLACKBOX RECORDER

Se ocorrer qualquer anomalia, stall prolongado ou parada de emergência:
1. O bot exportará automaticamente o pacote forense para:
   `debug/blackbox/<timestamp>_<reason>/`
2. Abra essa pasta para inspecionar:
   - `flight_data.json`: Linha do tempo dos últimos 150 passos, estados e comandos.
   - `frame_000.png` a `frame_149.png`: Sequência visual exata dos 15 segundos anteriores ao evento.
