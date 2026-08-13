# Guia de Início Rápido (Quick Start) — Lumena Bot

Siga este roteiro simples de 5 passos para operar o Lumena Bot:

---

### Passo 1: Abrir o Jogo no Navegador
- Abra o **Google Chrome** e acesse [https://lumena.gg](https://lumena.gg).
- Faça login e posicione o personagem no mapa de farm (grama alta) ou na cidade.

---

### Passo 2: Iniciar o Lumena Bot
Execute o bot através do executável compilado ou pelo código fonte:
```powershell
# Executável portátil:
.\dist\LumenaBot\LumenaBot.exe

# Ou via Python:
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" main.py
```

---

### Passo 3: Executar Diagnósticos Preliminares
- Acesse o menu lateral **🩺 Diagnósticos**.
- Clique em **▶ RUN DIAGNOSTICS** para verificar se todos os módulos (Python, OpenCV, PyAutoGUI, Win32) estão operacionais.
- Clique em **⚡ PHYSICAL INPUT TEST** para validar se o Chrome recebe o foco e responde ao comando `W`.

---

### Passo 4: Iniciar a Automação
- Volte ao **📊 Dashboard**.
- Clique no botão verde **▶ INICIAR (F5)**.
- O bot passará pelo fluxo de ativação: `STARTING` ➔ `CONNECTING` ➔ `READY` ➔ `EXPLORING` / `BATTLE`.

---

### Passo 5: Parada e Controle de Emergência
- **Parar Normal:** Pressione **F6** ou clique em **⏹ PARAR**.
- **Parada de Emergência Imediata:** Pressione **ESC** a qualquer momento para liberar imediatamente todas as teclas e travar novas ações.
