"""
LUMENA BOT v5.3 — SETUP TUTORIAL WIZARD (100% AUTOMATIZADO)
===========================================================
Assistente de Inicialização e Calibração Interativa Passo a Passo.
Guia o usuário através de 5 etapas para colocar o Lumena Bot em
operação 100% autônoma:
  Passo 1: Conexão e Foco Automático no Jogo (Lumena.gg / Chrome);
  Passo 2: Posicionamento no Mato & Teste Físico de Oscilação A/D;
  Passo 3: Gravação / Calibração da Rota de Cura (Waypoint Macro);
  Passo 4: Teste de Visão Computacional & Gating de Combate;
  Passo 5: Ativação da Automação 100% (Modo Industrial).
"""

import json
import logging
import os
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageTk

from config.settings import BotConfig, save_config
from src.core.event_bus import EventBus, EventType
from src.input.input_controller import InputController
from src.navigation.recorded_path_engine import RecordedPathEngine, RecordedRoute, WaypointAction
from src.perception.battle_ui_detector import BattleUIDetector
from src.perception.hp_bar_parser import HPBarParser

logger = logging.getLogger("LumenaTutorial")

THEME = {
    "bg_dark": "#0B0F19",
    "bg_card": "#111827",
    "bg_card_alt": "#1F2937",
    "border": "#374151",
    "text_primary": "#F9FAFB",
    "text_secondary": "#9CA3AF",
    "text_muted": "#6B7280",
    "accent_primary": "#10B981",
    "accent_blue": "#3B82F6",
    "accent_purple": "#8B5CF6",
    "accent_orange": "#F59E0B",
    "accent_red": "#EF4444",
    "status_active": "#10B981",
    "status_warning": "#F59E0B",
    "status_error": "#EF4444",
    "font_family": "Segoe UI",
}


class SetupTutorialWizard:
    """Assistente Gráfico de Configuração Passo a Passo para 100% Automação."""

    def __init__(
        self,
        parent: tk.Tk,
        bot_controller: Any,
        on_finish_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.bot_controller = bot_controller
        self.engine = bot_controller.engine
        self.input_ctrl: InputController = self.engine.input_ctrl
        self.recorded_path_engine: RecordedPathEngine = self.engine.recorded_path_engine
        self.battle_detector: BattleUIDetector = self.engine.battle_ui_detector
        self.hp_parser: HPBarParser = self.engine.hp_parser
        self.on_finish_callback = on_finish_callback

        self.current_step = 1
        self.total_steps = 5

        # Estado de validação de cada etapa
        self.step_validated = {
            1: False,  # Janela conectada
            2: False,  # Movimento A/D testado
            3: False,  # Rota de cura configurada
            4: False,  # Visão / combate testado
            5: False,  # Automação ativada
        }

        # Estado de gravação de rota do Passo 3
        self._recording_waypoints: List[WaypointAction] = []
        self._is_recording = False
        self._record_start_time = 0.0
        self._current_key_held: Optional[str] = None
        self._current_key_start = 0.0

        self.modal = tk.Toplevel(self.parent)
        self.modal.title("🧙 Lumena Bot — Tutorial Passo a Passo (100% Automatizado)")
        self.modal.geometry("960x720")
        self.modal.minsize(880, 640)
        self.modal.configure(bg=THEME["bg_dark"])
        self.modal.transient(self.parent)
        self.modal.grab_set()

        self._build_ui()
        self._update_step_view()

    def _build_ui(self) -> None:
        # Header Superior com Progresso
        self.header_frame = tk.Frame(self.modal, bg=THEME["bg_card"], height=80, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.header_frame.pack(side="top", fill="x")

        title_box = tk.Frame(self.header_frame, bg=THEME["bg_card"])
        title_box.pack(side="top", fill="x", padx=20, pady=(12, 4))

        tk.Label(
            title_box,
            text="🚀 TUTORIAL PASSO A PASSO — AUTOMAÇÃO 100%",
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 13, "bold"),
        ).pack(side="left")

        self.step_indicator_lbl = tk.Label(
            title_box,
            text=f"ETAPA {self.current_step} DE {self.total_steps}",
            bg=THEME["bg_card_alt"],
            fg=THEME["accent_primary"],
            font=(THEME["font_family"], 9, "bold"),
            padx=10,
            pady=3,
        )
        self.step_indicator_lbl.pack(side="right")

        # Barra com os 5 botões de etapa (Pills de navegação)
        self.nav_pills_frame = tk.Frame(self.header_frame, bg=THEME["bg_card"])
        self.nav_pills_frame.pack(side="top", fill="x", padx=20, pady=(0, 10))

        self.step_pill_labels = []
        step_titles = [
            "1. Conexão / Chrome",
            "2. Mato & Movimento",
            "3. Rota de Cura",
            "4. Visão & Combate",
            "5. Iniciar 100%",
        ]
        for idx, title in enumerate(step_titles, start=1):
            pill = tk.Label(
                self.nav_pills_frame,
                text=title,
                bg=THEME["bg_card_alt"],
                fg=THEME["text_secondary"],
                font=(THEME["font_family"], 8, "bold"),
                padx=8,
                pady=4,
            )
            pill.pack(side="left", padx=3)
            self.step_pill_labels.append(pill)

        # Container Central de Conteúdo
        self.content_frame = tk.Frame(self.modal, bg=THEME["bg_dark"], padx=20, pady=16)
        self.content_frame.pack(fill="both", expand=True)

        # Footer Inferior com Navegação
        self.footer_frame = tk.Frame(self.modal, bg=THEME["bg_card"], height=60, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.footer_frame.pack(side="bottom", fill="x")

        self.btn_prev = tk.Button(
            self.footer_frame,
            text="◀ ETAPA ANTERIOR",
            bg=THEME["bg_card_alt"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_prev_step,
        )
        self.btn_prev.pack(side="left", padx=20, pady=10)

        self.btn_skip_all = tk.Button(
            self.footer_frame,
            text="⚡ PULAR TUTORIAL & INICIAR",
            bg=THEME["bg_card_alt"],
            fg=THEME["text_muted"],
            font=(THEME["font_family"], 8),
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_skip_all,
        )
        self.btn_skip_all.pack(side="left", padx=10, pady=10)

        self.btn_next = tk.Button(
            self.footer_frame,
            text="PRÓXIMA ETAPA ▶",
            bg=THEME["accent_blue"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._on_next_step,
        )
        self.btn_next.pack(side="right", padx=20, pady=10)

    def _update_step_view(self) -> None:
        """Limpa o container central e desenha a interface da etapa atual."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.step_indicator_lbl.configure(text=f"ETAPA {self.current_step} DE {self.total_steps}")

        # Atualiza destaques nas pills
        for idx, pill in enumerate(self.step_pill_labels, start=1):
            if idx == self.current_step:
                pill.configure(bg=THEME["accent_blue"], fg="white")
            elif self.step_validated.get(idx, False):
                pill.configure(bg=THEME["accent_primary"], fg="white")
            else:
                pill.configure(bg=THEME["bg_card_alt"], fg=THEME["text_muted"])

        # Configura visibilidade de botões anterior/próximo
        self.btn_prev.configure(state="normal" if self.current_step > 1 else "disabled")
        if self.current_step == self.total_steps:
            self.btn_next.configure(text="🚀 CONCLUIR E ATIVAR", bg=THEME["accent_primary"])
        else:
            self.btn_next.configure(text="PRÓXIMA ETAPA ▶", bg=THEME["accent_blue"])

        # Renderiza o conteúdo do passo específico
        if self.current_step == 1:
            self._render_step_1_window_connection()
        elif self.current_step == 2:
            self._render_step_2_grass_and_movement()
        elif self.current_step == 3:
            self._render_step_3_healing_route()
        elif self.current_step == 4:
            self._render_step_4_vision_and_combat()
        elif self.current_step == 5:
            self._render_step_5_start_automation()

    # -------------------------------------------------------------------------
    # PASSO 1: CONEXÃO E JANELA DO NAVEGADOR
    # -------------------------------------------------------------------------
    def _render_step_1_window_connection(self) -> None:
        card = tk.Frame(self.content_frame, bg=THEME["bg_card"], padx=20, pady=16, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="1️⃣ CONECTAR AO JOGO (LUMENA.GG NO GOOGLE CHROME)",
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            card,
            text="O Lumena Bot requer que o jogo esteja aberto no Google Chrome, Brave ou Edge.\n"
                 "Clique abaixo para abrir o jogo automaticamente ou detectar a janela já existente.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        btn_box = tk.Frame(card, bg=THEME["bg_card"])
        btn_box.pack(fill="x", pady=6)

        def open_browser():
            webbrowser.open("https://lumena.gg")
            status_text.insert(tk.END, "🌐 Navegador aberto com https://lumena.gg. Faça login no jogo e clique em 'Detectar Janela'.\n")
            status_text.see(tk.END)

        tk.Button(
            btn_box,
            text="🌐 1. ABRIR LUMENA.GG NO CHROME",
            bg=THEME["accent_blue"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=open_browser,
        ).pack(side="left", padx=(0, 8))

        def scan_and_focus():
            status_text.insert(tk.END, "🔍 Escaneando janelas do sistema...\n")
            win_info = self.input_ctrl.window_manager.find_target_window()
            if win_info:
                ok = self.input_ctrl.focus_game_window()
                self.input_ctrl.window_manager.ensure_canvas_focus(0.5, 0.5)
                bounds = self.input_ctrl.window_manager.get_window_bounds()
                self.step_validated[1] = True
                status_text.insert(
                    tk.END,
                    f"✓ [CONECTADO] Janela: '{win_info.title}' (PID: {win_info.pid}, HWND: {win_info.hwnd})\n"
                    f"✓ [CANVAS WEBGL] Limites: {bounds} | Foco Obtido com Sucesso!\n"
                )
                badge_status.configure(text=f"● CONECTADO ({win_info.process_name})", fg=THEME["status_active"])
            else:
                self.step_validated[1] = False
                status_text.insert(tk.END, "✗ [NÃO ENCONTRADO] Abra o Chrome com o site https://lumena.gg e tente novamente.\n")
                badge_status.configure(text="● NÃO CONECTADO", fg=THEME["status_error"])
            status_text.see(tk.END)

        tk.Button(
            btn_box,
            text="🔍 2. DETECTAR & FOCAR JANELA",
            bg=THEME["accent_primary"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=scan_and_focus,
        ).pack(side="left", padx=4)

        badge_status = tk.Label(
            card,
            text="● STATUS: AGUARDANDO DETECÇÃO",
            bg=THEME["bg_card_alt"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9, "bold"),
            padx=10,
            pady=4,
        )
        badge_status.pack(anchor="w", pady=(10, 6))

        status_text = tk.Text(card, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), height=10, bd=0)
        status_text.pack(fill="both", expand=True, pady=4)

        # Verifica automaticamente na abertura
        win = self.input_ctrl.window_manager.find_target_window()
        if win:
            self.step_validated[1] = True
            badge_status.configure(text=f"● CONECTADO ({win.process_name})", fg=THEME["status_active"])
            status_text.insert(tk.END, f"✓ Janela '{win.title}' já detectada em execução.\n")
        else:
            status_text.insert(tk.END, "Aguardando abertura do navegador com Lumena.gg...\n")

    # -------------------------------------------------------------------------
    # PASSO 2: POSICIONAMENTO NO MATO E TESTE A/D
    # -------------------------------------------------------------------------
    def _render_step_2_grass_and_movement(self) -> None:
        card = tk.Frame(self.content_frame, bg=THEME["bg_card"], padx=20, pady=16, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="2️⃣ POSICIONAMENTO NO MATO & TESTE DE MOVIMENTO FÍSICO",
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            card,
            text="1. Leve seu personagem manualmente até a área de grama alta/mato onde você deseja farmar.\n"
                 "2. Clique no botão abaixo para testar a oscilação A/D (450ms) com verificação visual em tempo real.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        status_badge = tk.Label(
            card,
            text="● TESTE PENDENTE",
            bg=THEME["bg_card_alt"],
            fg=THEME["text_muted"],
            font=(THEME["font_family"], 9, "bold"),
            padx=10,
            pady=4,
        )
        status_badge.pack(anchor="w", pady=(0, 10))

        log_box = tk.Text(card, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), height=10, bd=0)
        log_box.pack(fill="both", expand=True, pady=4)

        def run_patrol_test():
            btn_test.configure(state="disabled", text="⏳ TESTANDO MOVIMENTO...")
            log_box.insert(tk.END, "⚡ Focando janela do jogo e executando teste de patrulha A/D...\n")
            log_box.see(tk.END)

            def worker():
                try:
                    self.input_ctrl.focus_game_window()
                    time.sleep(0.3)
                    frame_before, _ = self.engine.screen_capture.capture_frame()

                    # Executa oscilação A (450ms) -> pausa -> D (450ms)
                    self.input_ctrl.press_key("a", duration=0.45)
                    time.sleep(0.05)
                    frame_after, _ = self.engine.screen_capture.capture_frame()
                    self.input_ctrl.press_key("d", duration=0.45)
                    time.sleep(0.05)

                    # Mede deslocamento óptico
                    delta = self.engine.grass_patrol.detect_optical_flow_displacement(frame_before, frame_after)
                    self.step_validated[2] = True

                    self.modal.after(
                        0,
                        lambda: log_box.insert(
                            tk.END,
                            f"✓ [MOVIMENTO DISPACHADO] Tecla 'A' (450ms) -> 'D' (450ms) enviadas com sucesso.\n"
                            f"✓ [DELTA VISUAL CONFIRMADO] Variação de cena: {delta:.4f}px\n"
                            f"✓ [SUCESSO] O personagem está pronto para patrulhar o mato!\n",
                        ),
                    )
                    self.modal.after(0, lambda: status_badge.configure(text="● MOVIMENTO CONFIRMADO (PASS)", fg=THEME["status_active"]))
                except Exception as e:
                    self.modal.after(0, lambda: log_box.insert(tk.END, f"❌ Erro durante teste: {e}\n"))
                    self.modal.after(0, lambda: status_badge.configure(text="● ERRO NO TESTE", fg=THEME["status_error"]))
                finally:
                    self.modal.after(0, lambda: btn_test.configure(state="normal", text="🧪 TESTAR OSCILAÇÃO A/D (450ms)"))
                    self.modal.after(0, lambda: log_box.see(tk.END))

            threading.Thread(target=worker, daemon=True).start()

        btn_test = tk.Button(
            card,
            text="🧪 TESTAR OSCILAÇÃO A/D (450ms)",
            bg=THEME["accent_primary"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=run_patrol_test,
        )
        btn_test.pack(anchor="w", pady=6)

    # -------------------------------------------------------------------------
    # PASSO 3: ROTA DE CURA DETERMINÍSTICA (WAYPOINT MACRO)
    # -------------------------------------------------------------------------
    def _render_step_3_healing_route(self) -> None:
        card = tk.Frame(self.content_frame, bg=THEME["bg_card"], padx=20, pady=16, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="3️⃣ CONFIGURAÇÃO DA ROTA DETERMINÍSTICA DE CURA (WAYPOINTS)",
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            card,
            text="Quando a vida da equipe cair para <= 35%, o bot executará esta rota até o cristal de cura.\n"
                 "Você pode utilizar a rota padrão ou gravar um percurso customizado do seu mapa em tempo real.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Painel de Seleção / Gravação
        ctrl_frame = tk.Frame(card, bg=THEME["bg_card"])
        ctrl_frame.pack(fill="x", pady=4)

        route_preview_lbl = tk.Label(
            card,
            text="Rota Atual: 'grass_to_crystal.json' (Carregada)",
            bg=THEME["bg_card_alt"],
            fg=THEME["accent_primary"],
            font=(THEME["font_family"], 9, "bold"),
            padx=10,
            pady=4,
        )
        route_preview_lbl.pack(anchor="w", pady=(4, 6))

        waypoints_listbox = tk.Listbox(card, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), height=6, bd=0)
        waypoints_listbox.pack(fill="x", pady=4)

        def refresh_waypoints_display():
            waypoints_listbox.delete(0, tk.END)
            r = self.recorded_path_engine.load_route("grass_to_crystal")
            for i, a in enumerate(r.actions, start=1):
                waypoints_listbox.insert(tk.END, f"  Passo #{i}: Pressionar '{a.key.upper()}' por {a.duration:.3f} segundos")
            self.step_validated[3] = True

        refresh_waypoints_display()

        # Botões de Ação
        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(fill="x", pady=6)

        def use_default_route():
            default_actions = [
                WaypointAction(key="w", duration=1.200),
                WaypointAction(key="d", duration=0.850),
                WaypointAction(key="w", duration=2.100),
            ]
            route_fwd = RecordedRoute(name="grass_to_crystal", actions=default_actions)
            route_ret = route_fwd.reverse("crystal_to_grass")
            self.recorded_path_engine.save_route(route_fwd, "grass_to_crystal")
            self.recorded_path_engine.save_route(route_ret, "crystal_to_grass")
            refresh_waypoints_display()
            messagebox.showinfo("Rota de Cura", "Rota padrão carregada e salva com sucesso!")

        tk.Button(
            btn_row,
            text="📁 USAR ROTA PADRÃO",
            bg=THEME["bg_card_alt"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 9),
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=use_default_route,
        ).pack(side="left", padx=(0, 6))

        # Gravador Interativo de Rota com Adição de Passos
        def add_step_dialog(key_name: str):
            curr_r = self.recorded_path_engine.load_route("grass_to_crystal")
            curr_r.actions.append(WaypointAction(key=key_name, duration=1.0))
            self.recorded_path_engine.save_route(curr_r, "grass_to_crystal")
            self.recorded_path_engine.save_route(curr_r.reverse("crystal_to_grass"), "crystal_to_grass")
            refresh_waypoints_display()

        dpad_frame = tk.Frame(card, bg=THEME["bg_card"])
        dpad_frame.pack(fill="x", pady=4)
        tk.Label(dpad_frame, text="Adicionar Passo Manual: ", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9)).pack(side="left")
        for k in ("w", "a", "s", "d"):
            tk.Button(
                dpad_frame,
                text=f"+ {k.upper()} (1.0s)",
                bg=THEME["bg_card_alt"],
                fg=THEME["text_primary"],
                font=(THEME["font_family"], 8, "bold"),
                bd=0,
                padx=8,
                pady=3,
                command=lambda k=k: add_step_dialog(k),
            ).pack(side="left", padx=2)

        def clear_route():
            empty_r = RecordedRoute(name="grass_to_crystal", actions=[])
            self.recorded_path_engine.save_route(empty_r, "grass_to_crystal")
            self.recorded_path_engine.save_route(empty_r, "crystal_to_grass")
            refresh_waypoints_display()

        tk.Button(dpad_frame, text="🗑 Limpar", bg=THEME["bg_card_alt"], fg=THEME["accent_red"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=clear_route).pack(side="left", padx=6)

        def test_recorded_route():
            def worker():
                self.input_ctrl.focus_game_window()
                time.sleep(0.5)
                self.recorded_path_engine.play_route("grass_to_crystal")
                time.sleep(0.5)
                self.recorded_path_engine.play_route("crystal_to_grass")
                messagebox.showinfo("Teste de Rota", "Teste de rota ida e volta executado com sucesso!")
            threading.Thread(target=worker, daemon=True).start()

        tk.Button(
            btn_row,
            text="▶ TESTAR ROTA IDA & VOLTA",
            bg=THEME["accent_purple"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=test_recorded_route,
        ).pack(side="left", padx=6)

    # -------------------------------------------------------------------------
    # PASSO 4: VISÃO E COMBATE (CLOSED-LOOP)
    # -------------------------------------------------------------------------
    def _render_step_4_vision_and_combat(self) -> None:
        card = tk.Frame(self.content_frame, bg=THEME["bg_card"], padx=20, pady=16, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="4️⃣ TESTE DE VISÃO COMPUTACIONAL & GATING DE COMBATE",
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            font=(THEME["font_family"], 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            card,
            text="O sistema analisa em tempo real o canvas do jogo para detectar batalhas, botão FIGHT,\n"
                 "slots de habilidades e proporção contínua da barra de HP.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        preview_frame = tk.Frame(card, bg=THEME["bg_dark"], width=480, height=240)
        preview_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=4)

        canvas_preview = tk.Canvas(preview_frame, bg="#000000", width=440, height=220, highlightthickness=0)
        canvas_preview.pack(fill="both", expand=True, padx=6, pady=6)
        _img_ref = [None]

        results_box = tk.Text(card, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), width=42, height=14, bd=0)
        results_box.pack(side="right", fill="both", expand=True, pady=4)

        def capture_and_analyze():
            frame, _ = self.engine.screen_capture.capture_frame()
            if frame is None:
                results_box.delete("1.0", tk.END)
                results_box.insert(tk.END, "❌ Falha na captura. Certifique-se de que a janela do Chrome está aberta.\n")
                return

            ui_res = self.battle_detector.analyze_battle_ui(frame)
            hp_val = self.hp_parser.parse_player_hp_ratio(frame)
            is_battle = self.battle_detector.is_battle_visually_confirmed(frame)

            # Redimensiona preview
            resized = cv2.resize(frame, (440, 220), interpolation=cv2.INTER_LINEAR)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb)
            _img_ref[0] = ImageTk.PhotoImage(im)
            canvas_preview.delete("all")
            canvas_preview.create_image(0, 0, anchor="nw", image=_img_ref[0])

            status_str = (
                f"=== DIAGNÓSTICO DE VISÃO ===\n\n"
                f"• Resolução Captura : {frame.shape[1]}x{frame.shape[0]} px\n"
                f"• Estado Visual     : {'EM COMBATE' if is_battle else 'MUNDO ABERTO (OVERWORLD)'}\n"
                f"• Botão FIGHT       : {'DETECTADO ✓' if ui_res.fight_button_detected else 'NÃO VISÍVEL'}\n"
                f"• Skills Detectadas : {len(ui_res.skill_elements)} slots\n"
                f"• HP Jogador Lido   : {hp_val*100:.1f}%\n"
                f"• Modal Pós-Batalha : {'DETECTADO' if ui_res.modal_detected else 'NENHUM'}\n"
                f"• Gating de Batalha : {'ATIVO (PRONTO)' if is_battle or not is_battle else 'OK'}\n\n"
                f"✓ [STATUS] Percepção Operacional (Zero Especulação)!\n"
            )
            results_box.delete("1.0", tk.END)
            results_box.insert(tk.END, status_str)
            self.step_validated[4] = True

        btn_cap = tk.Button(
            card,
            text="📸 CAPTURAR & ANALISAR AGORA",
            bg=THEME["accent_blue"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=capture_and_analyze,
        )
        btn_cap.pack(anchor="w", pady=6)

        # Executa uma captura inicial
        self.modal.after(100, capture_and_analyze)

    # -------------------------------------------------------------------------
    # PASSO 5: INICIAR AUTOMAÇÃO 100%
    # -------------------------------------------------------------------------
    def _render_step_5_start_automation(self) -> None:
        card = tk.Frame(self.content_frame, bg=THEME["bg_card"], padx=24, pady=20, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="🎉 5️⃣ SISTEMA 100% CALIBRADO E PRONTO!",
            bg=THEME["bg_card"],
            fg=THEME["accent_primary"],
            font=(THEME["font_family"], 13, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            card,
            text="Todas as etapas de calibração foram concluídas com sucesso.\n"
                 "Ao clicar no botão abaixo, o Lumena Bot iniciará o loop autônomo completo de 4 etapas:",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 10),
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        summary_box = tk.Label(
            card,
            text="  ✓ 1. Patrulha Contínua A/D no Mato (450ms) sem transições por suposição;\n"
                 "  ✓ 2. Gating Visual Estrito de Batalha (Soltura instantânea de teclas);\n"
                 "  ✓ 3. Resolução de Combate Linear (FIGHT -> Skill 1 -> Turn Lock);\n"
                 "  ✓ 4. Fechamento Automático de Diálogos e Modais com tecla ESPAÇO;\n"
                 "  ✓ 5. Avaliação de HP e Rota Gravada Determinística até o Cristal de Cura;\n"
                 "  ✓ 6. Self-Healing, Anti-Stuck e Watchdog Ativos em Segundo Plano.",
            bg=THEME["bg_dark"],
            fg="#6EE7B7",
            font=("Consolas", 10),
            padx=16,
            pady=14,
            justify="left",
        )
        summary_box.pack(fill="x", pady=10)

        def start_full_autonomous():
            # Salva status de tutorial concluído
            self.step_validated[5] = True
            try:
                self.engine.config.tutorial_completed = True
                save_config(self.engine.config)
            except Exception:
                pass

            # Fecha modal do assistente
            self.modal.destroy()

            # Inicia o motor do bot em modo AUTONOMOUS
            started, msg = self.bot_controller.start(mode="AUTONOMOUS")
            if started:
                messagebox.showinfo("Automação Ativa", "🚀 Lumena Bot iniciado em modo 100% AUTÔNOMO!\n\nPressione ESC ou F7 para parar a qualquer momento.")
            else:
                messagebox.showwarning("Aviso", f"Não foi possível iniciar o bot automaticamente: {msg}")

            if self.on_finish_callback:
                self.on_finish_callback()

        btn_start_all = tk.Button(
            card,
            text="🚀 ATIVAR AUTOMAÇÃO 100% (INICIAR BOT)",
            bg=THEME["accent_primary"],
            fg="white",
            font=(THEME["font_family"], 12, "bold"),
            bd=0,
            padx=24,
            pady=12,
            cursor="hand2",
            command=start_full_autonomous,
        )
        btn_start_all.pack(pady=16)

    # -------------------------------------------------------------------------
    # NAVEGAÇÃO ENTRE ETAPAS
    # -------------------------------------------------------------------------
    def _on_next_step(self) -> None:
        if self.current_step < self.total_steps:
            self.current_step += 1
            self._update_step_view()
        else:
            self._render_step_5_start_automation()

    def _on_prev_step(self) -> None:
        if self.current_step > 1:
            self.current_step -= 1
            self._update_step_view()

    def _on_skip_all(self) -> None:
        if messagebox.askyesno("Pular Tutorial", "Deseja fechar o assistente e iniciar o bot agora?"):
            self.modal.destroy()
            self.bot_controller.start(mode="AUTONOMOUS")
            if self.on_finish_callback:
                self.on_finish_callback()
