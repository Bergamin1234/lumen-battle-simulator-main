# Protocolo de Teste do Loop Autônomo — LEVEL 7

**Objetivo:** Comprovar a execução contínua em malha fechada (*closed-loop*) do agente no jogo real, integrando observação, navegação, combate, vitória e retorno ao mundo.

---

## 1. Procedimento de Teste

1. Abra o **Google Chrome** no [Lumena.gg](https://lumena.gg) e posicione o personagem na grama alta.
2. Inicie o aplicativo **Lumena Bot**.
3. Verifique se o badge superior exibe `● CONECTADO`.
4. No Dashboard, clique em **▶ INICIAR (F5)** com modo `🤖 Autônomo`.
5. Observe a execução de pelo menos:
   - **10 ciclos de observação** com classificação de estado correta.
   - **3 movimentos de patrulha** no mundo aberto.
   - **1 combate completo:** detecção da batalha ➔ abertura do menu FIGHT ➔ seleção de golpe com multiplicador elementar ➔ confirmação de vitória ➔ retorno à exploração.

---

## 2. Registro de Evidências

Durante o teste autônomo, o sistema salva automaticamente:
- Screenshots de transição de combate em `debug/`.
- Histórico de eventos e telemetria no console da GUI.
- Atualização contínua de memória e contadores de vitórias/derrotas.
