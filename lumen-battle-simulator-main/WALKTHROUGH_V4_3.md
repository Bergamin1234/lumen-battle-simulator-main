# 📖 LUMENA BOT CONTROL CENTER v4.3 — OPERATIONAL WALKTHROUGH
## Guia de Operação da Validação de Campo, Calibração Visual e Replay Forense

---

## 1. Como Executar o Teste de Campo Supervisionado (Field Trial 3-Cycle)

### Opção A: Pela Interface Gráfica (Control Center)
1. Inicie o executável `dist/LumenaBot/LumenaBot.exe` ou execute `py -3.12 main.py`.
2. Abra o jogo no Google Chrome e navegue até uma área do mapa com encontros de batalha.
3. No menu lateral do Control Center, clique na aba **👁️ Visão / Calibração**.
4. No topo da página, clique no botão **⚡ FIELD TRIAL (3x)**.
5. Na janela aberta, clique em **▶ INICIAR TESTE DE CAMPO**.
6. O supervisor anexará ao Chrome, executará os 3 ciclos autônomos e gravará `result.json` com o status final.

### Opção B: Pela Linha de Comando (CLI)
Abra o terminal do Windows PowerShell e execute:
```powershell
py -3.12 scripts/diagnostics/run_field_trial.py --cycles 3
```
- Para testar sem a janela do jogo aberta (Modo Simulado):
```powershell
py -3.12 scripts/diagnostics/run_field_trial.py --dry-run
```

---

## 2. Como Utilizar o Canvas Inspector & Sliders de Calibração

1. Acesse a página **👁️ Visão** no Control Center.
2. O feed ao vivo exibirá as seguintes sobreposições coloridas:
   - 🟩 **Verde Claro**: Limites do Canvas WebGL útil (excluindo letterboxing).
   - 🟦 **Azul**: Botão de Combate `[FIGHT]`.
   - 🟨 **Amarelo**: Slots das 4 Habilidades `[SKILL #1]` a `[SKILL #4]`.
   - 🟧/🟦 **Laranja / Ciano**: Delimitadores das barras de HP de Jogador e Inimigo.
   - 🟪 **Magenta**: Caixas de Diálogo e Modais Pós-Batalha.
   - 🟥/🟩 **Vermelho e Verde**: Trajetória Bézier com nós de controle $P_0$ e $P_3$.
3. Ajuste os sliders em tempo real:
   - **Match Thresh**: Limiar de confiança de matching de templates ($0.50$ a $0.95$).
   - **HSV Tol**: Tolerância de cor HSV para detecção de HP e entidades ($5$ a $40$).
   - **Letterbox Thresh**: Sensibilidade de corte de bordas pretas ($5$ a $30$).

---

## 3. Como Inspecionar Falhas no Blackbox Session Replay Viewer

1. Acesse a página **👁️ Visão** ou **📊 Telemetria**.
2. Clique no botão **🎬 BLACKBOX REPLAY**.
3. Selecione qualquer dump forense salvo na caixa de seleção superior (ex: `debug/blackbox/20260817_120000_WATCHDOG_STALL`).
4. Utilize os controles:
   - **⏮ -1 Frame / ⏭ +1 Frame**: Navegação passo a passo quadro a quadro.
   - **▶ / ⏸ Play**: Reprodução contínua.
   - **Barra de Progresso (Slider)**: Salto direto para qualquer instante do buffer.
5. Inspecione o estado exato da FSM, o último input despachado e os eventos registrados em sincronia com cada imagem capturada.

---

## 4. Funcionamento do Self-Healing Daemon

O motor de resiliência atua automaticamente em segundo plano:
- **Janela Minimizada**: Restaura a janela via Win32 API (`ShowWindow`) e recalibra as dimensões do Canvas em 200ms.
- **Perda de Foco**: Suspende cliques pendentes, recupera o foco via `ensure_foreground` e reavalia a cena antes de reenviar qualquer comando.
- **Congelamento WebGL**: Detecta ausência de variação em 10 quadros e despacha micro-movimento para reativar o loop de renderização do Chrome.
- **Popups Inesperados**: Detecta modais intrusivos e envia tecla `ESC` para desobstruir o Canvas.
