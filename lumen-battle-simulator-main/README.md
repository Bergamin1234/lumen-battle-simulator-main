# Lumena Bot — Plataforma de Automação & Combate Inteligente

O **Lumena Bot** é uma aplicação desktop autônoma em malha fechada (*closed-loop*) projetada para controle em tempo real, percepção multimodal, navegação no mundo aberto e combate automatizado para o jogo **Lumena.gg** no Google Chrome (Windows).

---

## 🚀 Funcionalidades Principais

- **Interface Desktop Profissional em 10 Páginas:**
  - **◉ Dashboard:** Live Game View com overlays semânticos, 6 cards de telemetria em tempo real e Live Activity Feed.
  - **🤖 Bot Control:** Seleção de modos (*Manual, Assisted, Autonomous*), D-Pad físico virtual e parâmetros de temporização.
  - **⚔ Battle:** Monitor de combate com acompanhamento de fraquezas elementares, PP, HP e razão das decisões da IA.
  - **🧭 Navigation:** Gerenciador de rotas gravadas, tabela passo a passo (`STEP | KEY | DURATION`), replay e inversão automática.
  - **👁 Vision:** Preview ao vivo com overlays (`[PLAYER]`, `[ENEMY]`, `[HP]`, `[FIGHT]`, `[CRYSTAL]`, `[DIALOG]`) e botão para salvar frame de depuração em `debug/`.
  - **🧠 Memory:** Posição topológica em tempo real, marcos (*landmarks*), obstáculos e histórico de experiência.
  - **📈 Telemetry:** Métricas operacionais em tempo real (FPS, latência de ação em ms, vitórias/derrotas, recuperações).
  - **📜 Logs:** Terminal visual multi-canal com filtros (*ALL, INPUT, VISION, COMBAT, NAVIGATION, ERROR*), busca, cópia e exportação.
  - **🩺 Diagnostics:** Varredura completa do sistema com badges (*PASS, WARN, FAIL*) e modal de **⚡ TESTE DE INPUT FÍSICO GUIADO**.
  - **⚙ Settings:** Presets rápidos (*SAFE, BALANCED, AGGRESSIVE, DEBUG*) e persistência em `config/settings.json`.
- **Despacho Físico de Entrada Win32:** Injeção de scancodes de hardware DirectInput (`0x11` para W, `0x1E` para A, `0x1F` para S, `0x20` para D, `0x39` para Space, `0x1C` para Enter), DirectInput `keybd_event`, `PostMessageW` e fallback PyAutoGUI.
- **SafetyGuard & Parada Imediata:** A tecla **ESC** ou o botão vermelho da interface interrompem imediatamente qualquer ação e executam `release_all_keys()` garantido em bloco `finally`.
- **Validação de Feedback Visual (Closed Loop):** Cálculo de delta de pixels antes/depois de cada ação ($> 0.005$) para confirmação real de movimento físico.
- **Executável Portátil:** Distribuição binária para Windows gerada via PyInstaller (`dist/LumenaBot/LumenaBot.exe`).

---

## 🛠️ Como Executar

### Opção 1: Executável Compilado (Recomendado)
```powershell
.\dist\LumenaBot\LumenaBot.exe
```

### Opção 2: Pelo Código Fonte (Python 3.12+)
```powershell
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" main.py
```

### Opção 3: Teste Físico Isolado em 17 Etapas
```powershell
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" scripts/real_world_test.py --interactive
```

---

## ⌨️ Atalhos Globais de Teclado
- **F5:** Iniciar automação (*Start*)
- **F6:** Pausar / Retomar (*Pause / Resume*)
- **F7:** Parar automação (*Stop*)
- **ESC:** **PARADA DE EMERGÊNCIA IMEDIATA** (*Emergency Stop — libera todas as teclas físicas*)