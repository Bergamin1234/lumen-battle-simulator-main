# 📖 LUMENA BOT CONTROL CENTER v4.4 — OPERATIONAL WALKTHROUGH
## Checklist Mestre para Execução ao Vivo com o Google Chrome & Hardening UIPI

---

## 1. Checklist Pré-Voo (Live Desktop Setup)

Antes de iniciar a sessão autônoma ao vivo:

1. **Privilégios Administrativos (UAC / UIPI)**:
   - Se o Google Chrome for iniciado como Administrador, o Lumena Bot **DEVE** ser executado como Administrador para evitar que o Windows UIPI descarte silenciosamente cliques de `SendInput`.
2. **Posicionamento da Janela do Chrome**:
   - Abra o jogo em `https://lumena.gg` (ou servidor de desenvolvimento).
   - Deixe a janela visível no monitor principal (ou monitor configurado no bot).
   - Evite cobrir a área do Canvas WebGL com outras janelas opacas durante os cliques de combate.
3. **Calibração Visual**:
   - Abra a aba **👁️ Visão** no Control Center e verifique as caixas coloridas sobrepostas no feed.

---

## 2. Como Executar o Field Trial via Linha de Comando (CLI)

### Modo Simulado (Headless / Dry-Run):
```powershell
py -3.12 scripts/diagnostics/run_field_trial.py --dry-run
```
Gera `debug/evidence/field_trial_dryrun/result.json` com `status: NO_TARGET_WINDOW_DETECTED` e `ready_for_live: true`.

### Modo de Teste Real no Jogo (3 Ciclos):
```powershell
py -3.12 scripts/diagnostics/run_field_trial.py --cycles 3 --save-replay
```
- Anexa automaticamente ao processo `chrome.exe`.
- Executa os 3 ciclos com monitoramento de FPS e latência.
- Salva o replay forense compactado do Blackbox em `debug/blackbox/`.
- Exporta o resultado formal para `result.json`.

---

## 3. Como Executar via Executável Compilado (`LumenaBot.exe`)

1. **Smoke Test de Versão**:
   ```powershell
   dist\LumenaBot\LumenaBot.exe --version
   ```
2. **Execução Direta do Field Trial via Binário**:
   ```powershell
   dist\LumenaBot\LumenaBot.exe --field-trial --dry-run
   ```
3. **Execução com Interface Gráfica Completa**:
   - Dê um duplo clique em `dist/LumenaBot/LumenaBot.exe`.
   - Navegue até a aba **👁️ Visão** e acione **⚡ FIELD TRIAL (3x)** ou inspecione o **🎬 BLACKBOX REPLAY**.
