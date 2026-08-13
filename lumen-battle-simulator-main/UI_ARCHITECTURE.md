# Arquitetura da Interface Gráfica — Lumena Bot Control Center v3.0

## 1. Visão Geral da Arquitetura do Frontend

O **Lumena Bot Control Center** foi projetado seguindo o padrão de arquitetura orientada a eventos (*Event-Driven UI*) desacoplada e estritamente thread-safe.

```
                      ┌──────────────────────────────────────────────┐
                      │             LumenaBotEngine                  │
                      │  (Thread de Trabalho / Closed Loop Principal)│
                      └──────────────────────┬───────────────────────┘
                                             │
                                             │ Publica Eventos
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │         src/core/event_bus.py                │
                      │        Barramento Central EventBus           │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             │ Fila Assíncrona Thread-Safe (queue.Queue)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │          ModernLumenaGUI (Tkinter)           │
                      │  UI Main Thread Loop (Polling a cada 50ms)   │
                      └──────────────────────┬───────────────────────┘
                                             │
      ┌──────────────┬──────────────┬────────┴─────┬──────────────┬──────────────┐
      ▼              ▼              ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ Dashboard │  │Bot Control│  │ Live Game │  │  Battle   │  │Navigation │  │Diagnostics│
│  6 Cards  │  │   D-Pad   │  │ Overlays  │  │ Weaknesses│  │  Routes   │  │ 17-Step   │
│ Live Feed │  │ Behavior  │  │ Delta View│  │  Timeline │  │  Timeline │  │  Wizard   │
└───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘
```

---

## 2. Princípios Fundamentais de Responsividade

1. **Zero Bloqueio na Thread Principal (Tkinter Mainloop):**  
   Nenhuma operação bloqueante (captura de tela, SendInput, OCR, leitura de janelas Win32, gravações de disco) é executada na thread de interface. Todas as ações do usuário que disparam rotinas de motor são despachadas em *daemon worker threads*.
2. **Consumo Thread-Safe via Fila de Eventos:**  
   O `EventBus` entrega eventos para uma `queue.Queue` dedicada da GUI. O método `_ui_telemetry_tick` consome todos os eventos pendentes sem travar o processamento da interface.
3. **Isolamento de Recursos Gráficos:**  
   Imagens de preview (`PIL.ImageTk.PhotoImage`) são instanciadas e limpas exclusivamente na thread da GUI para prevenir vazamentos de memória GDI no Windows.

---

## 3. Estrutura Modular das 12 Páginas

1. **Dashboard:** Visão consolidada, status global, 6 cards de desempenho e Live Activity Feed.
2. **Bot Control:** Seleção de modo (`AUTONOMOUS`, `ASSISTED`, `MANUAL`), D-Pad físico virtual e temporização.
3. **Live Game:** Viewport dedicado com resolução ampliada e overlays configuráveis.
4. **Battle Center:** Acompanhamento de combate, slots de golpe, cálculo de fraquezas e telemetria de dano.
5. **Navigation:** Gravador e gerenciador de rotas com timeline passo a passo (`STEP | KEY | DURATION`).
6. **Vision Center:** Tabela em tempo real de objetos semânticos detectados e congelamento de frame.
7. **Memory Center:** Mapa topológico de células visitadas, marcos recalibrados e colisões.
8. **Telemetry:** Gráficos e medidores de FPS, latência média e taxa de sucesso de input.
9. **Activity Feed:** Timeline histórica completa com categorização colorida.
10. **Log Center:** Console multi-canal com filtros de severidade e busca.
11. **Diagnostics:** Assistente com checklist de 19 pontos e teste físico guiado.
12. **Settings & Safety:** Gerenciador de configurações persistentes, perfis rápidos e exportação de diagnóstico.
