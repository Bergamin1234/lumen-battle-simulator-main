# ⚡ Lumena Bot Control Center v3.0

> **Production-Grade Closed-Loop Autonomous Automation Platform for Lumena.gg**

![Lumena Bot Banner](logo.png.png)

---

## 📖 Visão Geral

O **Lumena Bot Control Center v3.0** é uma plataforma modular de automação em malha fechada (*closed-loop*), visão computacional, telemetria em tempo real e combate inteligente projetada para o jogo WebGL **Lumena.gg**.

O sistema opera sob o princípio estrito:
$$\text{OBSERVE} \longrightarrow \text{INTERPRET} \longrightarrow \text{REMEMBER} \longrightarrow \text{DECIDE} \longrightarrow \text{ACT} \longrightarrow \text{VERIFY}$$

---

## 🏗️ Arquitetura do Sistema

```
                    MODERN GUI (14 Páginas)
                               │
                               ▼
                        BotController
                               │
                               ▼
                       LumenaBotEngine (SSOT)
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
    Perception               Memory                 Combat
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
                          Navigation
                               │
                               ▼
                         ActionExecutor
                               │
                               ▼
                         InputController
                           /          \
                          /            \
                TargetWindow        SafetyGuard
                          \            /
                           \          /
                             Win32
```

---

## 🚀 Como Iniciar

### 1. Executável Compilado (Standalone)
Execute diretamente o executável embutido:
```powershell
.\dist\LumenaBot\LumenaBot.exe
```

### 2. Ambiente de Desenvolvimento (Python 3.12+)
```powershell
# Ativar ambiente virtual se necessário
python -m pip install -r requirements.txt

# Iniciar Control Center GUI
python main.py

# Rodar a suíte completa de 63 testes unitários
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 🎮 Guia de Uso Rápido

1. **Abrir o Jogo:** Abra o **Google Chrome** no [https://lumena.gg](https://lumena.gg), realize o login e coloque o personagem em uma área segura.
2. **Target Window Wizard:** No topo da GUI, clique em **🧙 TARGET WIZARD** para detectar e calibrar a janela do jogo.
3. **Teste de Entrada Física (Level 6):** Acesse a página **🧪 Validation Levels** e clique em **▶ RUN LEVEL 6 (FÍSICO)** para despachar a tecla `W` (0.5s) e medir o delta visual com geração de evidências.
4. **Modo Autônomo (Level 7):** Pressione **F5** ou clique em **▶ START** para iniciar a exploração e combate contínuos.
5. **Parada de Emergência:** Pressione a tecla **ESC** a qualquer momento para interrupção imediata e liberação atômica de todas as teclas.