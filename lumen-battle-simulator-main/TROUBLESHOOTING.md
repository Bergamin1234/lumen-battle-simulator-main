# Guia de Resolução de Problemas (Troubleshooting)

---

## 1. O personagem não se movimenta ao enviar WASD

### Causas Possíveis:
1. **Falta de foco no Canvas WebGL:** O Chrome pode receber o evento na janela de moldura externa, mas a aba interna ou o canvas não possuem o foco de teclado ativo.
   - *Solução:* O `TargetWindowManager` executa um clique central no canvas. Certifique-se de que a aba do jogo esteja visível e não coberta por outras janelas.
2. **Janela minimizada ou oculta:** O Windows bloqueia despachos de entrada para janelas completamente minimizadas.
   - *Solução:* O bot tenta restaurar a janela automaticamente (`SW_RESTORE`). Mantenha a janela visível no monitor principal.
3. **Restrição de Privilégio (UIPI) no Windows:** Se o navegador foi executado com privilégios de Administrador, o Python precisa estar no mesmo nível de privilégio.
   - *Solução:* Execute o terminal do PowerShell ou o `LumenaBot.exe` como Administrador caso o navegador esteja elevado.

---

## 2. Parada de Emergência Ativada

Se a mensagem `🛑 PARADA DE EMERGÊNCIA` for exibida no painel:
- **Como Desbloquear:**
  1. Clique em **REANUDAR / RETOMAR** no painel ou alterne o modo do bot.
  2. Todas as teclas físicas ativas foram liberadas no sistema operacional pelo `SafetyGuard`.

---

## 3. Detecção Incompleta de Telas de Batalha

- **Verificação:** Acesse a página **Visão (Live Preview)** na interface.
- Observe se o bounding box laranja ou verde aparece ao redor da interface de combate, barra de HP e botão FIGHT.
- Caso ocorra falha de classificação por 5 ciclos consecutivos, o sistema salva automaticamente um snapshot de depuração na pasta `debug/` no formato:
  `debug/AAAA-MM-DD_HH-MM-SS_cycle_error.png`.

---

## 4. O executável PyInstaller não inicia

- Verifique se a pasta `dist/LumenaBot` contém as bibliotecas dinâmicas do OpenCV (`cv2`) e Tkinter.
- Certifique-se de que arquivos de configuração `config/settings.json` estão presentes.
