# Protocolo de Teste Físico de Movimento — LEVEL 6

**Objetivo:** Comprovar empiricamente que comandos de movimento enviados pelo Lumena Bot resultam em deslocamento físico real do personagem no canvas WebGL do jogo **Lumena.gg** no Google Chrome.

---

## 1. Pré-Requisitos

1. Google Chrome aberto com o jogo [Lumena.gg](https://lumena.gg) em primeiro plano.
2. Personagem posicionado em uma área aberta, sem obstáculos à frente.
3. Sessão do Windows ativa com display conectado.

---

## 2. Procedimento de Execução

### Opção A: Pela Interface Gráfica (Recomendada)
1. Execute o Lumena Bot (`python main.py` ou `dist/LumenaBot/LumenaBot.exe`).
2. Acesse a página **🩺 Diagnósticos** no menu lateral.
3. Clique no botão **⚡ PHYSICAL INPUT TEST**.
4. O sistema trará o Chrome para frente, focará o canvas, enviará a tecla `W` (0.5s) e comparará os frames antes/depois.

### Opção B: Por Linha de Comando (Interativo)
```powershell
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" scripts/real_world_test.py --interactive
```

---

## 3. Critérios de Aprovação

| Indicador | Critério de Sucesso | Evidência Gerada |
|---|---|---|
| **Foco da Janela** | `SetForegroundWindow = True` | Confirmação de HWND no relatório |
| **Foco do Canvas** | Clique de ativação no DOM | Registro `[CANVAS] Focused` |
| **Envio de Tecla** | Win32 Scancode `0x11` (W) | Registro `INPUT_DISPATCHED` |
| **Delta Visual** | Variação de Frame $> 0.005$ | Imagens em `debug/*_before.png` e `debug/*_after.png` |
| **Status Final** | `PASS (Movimento Físico Confirmado)` | Salvo em `physical_test_report.json` |
