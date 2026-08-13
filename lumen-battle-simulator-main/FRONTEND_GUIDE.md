# Guia de Operação do Lumena Bot Control Center v3.0

Este documento é o manual prático para operar a interface profissional **Lumena Bot Control Center**.

---

## 1. Visão Geral das Páginas

| Página | Ícone | Finalidade Principal |
|---|---|---|
| **Dashboard** | ◉ | Visão consolidada: Live Game View, Cards de Telemetria e Live Activity Feed. |
| **Bot Control** | 🤖 | Alternância de modos (*Autonomous, Assisted, Manual*), D-Pad e timing de ações. |
| **Live Game** | 📺 | Viewport expandido do jogo com overlays de detecção e comparador visual. |
| **Battle Center** | ⚔ | Monitor de combate com cálculo de fraquezas elementares e razão das decisões da IA. |
| **Navigation** | 🧭 | Gerenciador de rotas gravadas, tabela de passos (`STEP | KEY | DURATION`) e replay. |
| **Vision Center** | 👁 | Feed semântico de visão computacional e tabela de detecções ativas. |
| **Memory Center** | 🧠 | Mapa topológico de células visitadas, âncoras/marcos e colisões registradas. |
| **Telemetry** | 📈 | Gráficos e medidores em tempo real de FPS, latência média e taxa de sucesso. |
| **Activity Feed** | ⚡ | Linha do tempo completa e categorizada de eventos operacionais. |
| **Log Center** | 📜 | Console terminal multi-canal com filtros de nível (*INFO, WARN, ERROR*) e busca. |
| **Diagnostics** | 🩺 | Checklist de 19 pontos de sistema e assistente guiado de teste físico. |
| **Settings** | ⚙ | Presets rápidos de perfil (*Safe, Balanced, Aggressive*) e exportação de pacote de diagnóstico. |

---

## 2. Como Realizar o Teste Físico no Jogo Real

1. Abra o **Google Chrome** com o jogo [https://lumena.gg](https://lumena.gg) na tela principal.
2. Inicie o executável `dist/LumenaBot/LumenaBot.exe` ou `python main.py`.
3. Navegue até a página **🩺 Diagnostics** no menu lateral esquerdo.
4. Clique no botão **⚡ PHYSICAL INPUT TEST**.
5. No modal interativo, confirme o teste. O sistema trará o Chrome para primeiro plano, focará o canvas WebGL, enviará a tecla `W` por 0.50s e calculará a variação de pixels antes/depois.

---

## 3. Atalhos de Teclado Globais

- **F5:** Iniciar automação (*Start*)
- **F6:** Pausar / Retomar (*Pause / Resume*)
- **F7:** Parar automação (*Stop*)
- **ESC:** **PARADA DE EMERGÊNCIA IMEDIATA** (*Emergency Stop*)
