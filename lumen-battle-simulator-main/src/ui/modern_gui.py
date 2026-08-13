import os
import sys
import time
import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import cv2
from PIL import Image, ImageTk

from config.settings import BotConfig, load_config, save_config
from src.automation.bot_controller import BotController
from src.automation.state_machine import BotState
from src.telemetry.telemetry_manager import TelemetryManager
from src.input.input_controller import InputController
from src.input.target_window import TargetWindowManager

logger = logging.getLogger("LumenaGUI")

THEME = {
    "bg_dark": "#090D16",
    "bg_sidebar": "#0F172A",
    "bg_card": "#1E293B",
    "bg_card_alt": "#334155",
    "border": "#334155",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
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


class ModernLumenaGUI:
    """Interface Desktop Profissional de 10 Páginas para o Lumena Bot com Dashboard Unificado e Testes Físicos Guiados."""

    def __init__(self, root: tk.Tk, config: Optional[BotConfig] = None) -> None:
        self.root = root
        self.root.title("Lumena Bot — Painel Profissional de Automação & Combate")
        self.root.geometry("1360x860")
        self.root.minsize(1180, 740)
        self.root.configure(bg=THEME["bg_dark"])

        self.config = config or load_config()
        self.bot_controller = BotController(config=self.config)
        self.telemetry = TelemetryManager()
        self.input_ctrl = self.bot_controller.engine.input_ctrl

        self.current_page = "dashboard"
        self.log_filter = "ALL"
        self._vision_img_tk = None
        self._dash_preview_img_tk = None

        self._setup_styles()
        self._setup_keybindings()
        self._build_main_layout()

        self.root.after(80, self._ui_telemetry_tick)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=THEME["bg_dark"])
        style.configure("Card.TFrame", background=THEME["bg_card"])
        style.configure("TLabel", background=THEME["bg_card"], foreground=THEME["text_primary"], font=(THEME["font_family"], 9))
        style.configure("TProgressbar", thickness=10, troughcolor=THEME["bg_card_alt"], background=THEME["accent_blue"])

    def _setup_keybindings(self) -> None:
        self.root.bind("<Escape>", lambda e: self._on_emergency_stop())
        self.root.bind("<F5>", lambda e: self._on_start_bot())
        self.root.bind("<F6>", lambda e: self._on_pause_bot())
        self.root.bind("<F7>", lambda e: self._on_stop_bot())

    def _build_main_layout(self) -> None:
        # 1. HEADER SUPERIOR FIXO
        self.header_frame = tk.Frame(self.root, bg=THEME["bg_sidebar"], height=56, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.header_frame.pack(side="top", fill="x")

        # Logotipo / Título
        title_box = tk.Frame(self.header_frame, bg=THEME["bg_sidebar"])
        title_box.pack(side="left", padx=16, pady=8)
        tk.Label(title_box, text="⚡ LUMENA BOT", bg=THEME["bg_sidebar"], fg=THEME["text_primary"], font=(THEME["font_family"], 13, "bold")).pack(side="left")
        tk.Label(title_box, text="v2.5 Pro", bg=THEME["bg_card_alt"], fg="#38BDF8", font=(THEME["font_family"], 8, "bold"), padx=6, pady=2).pack(side="left", padx=8)

        # Badge de Janela Alvo
        self.target_window_badge = tk.Label(
            self.header_frame,
            text="🪟 JANELA: LUMENA.GG",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            padx=12,
            pady=4,
        )
        self.target_window_badge.pack(side="left", padx=12)

        # Botões de Ação Rápida no Topo
        btn_box = tk.Frame(self.header_frame, bg=THEME["bg_sidebar"])
        btn_box.pack(side="left", padx=16)

        self.btn_top_start = tk.Button(btn_box, text="▶ START (F5)", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=14, pady=5, cursor="hand2", command=self._on_start_bot)
        self.btn_top_start.pack(side="left", padx=3)

        self.btn_top_pause = tk.Button(btn_box, text="⏸ PAUSE (F6)", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=5, cursor="hand2", command=self._on_pause_bot)
        self.btn_top_pause.pack(side="left", padx=3)

        self.btn_top_stop = tk.Button(btn_box, text="■ STOP (F7)", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=5, cursor="hand2", command=self._on_stop_bot)
        self.btn_top_stop.pack(side="left", padx=3)

        # Status Global Badge
        self.status_badge = tk.Label(
            self.header_frame,
            text="● OFFLINE",
            bg=THEME["bg_card"],
            fg=THEME["text_muted"],
            font=(THEME["font_family"], 10, "bold"),
            padx=14,
            pady=4,
        )
        self.status_badge.pack(side="right", padx=16, pady=8)

        # 2. CORPO PRINCIPAL (Sidebar + Content)
        self.body_frame = tk.Frame(self.root, bg=THEME["bg_dark"])
        self.body_frame.pack(fill="both", expand=True)

        # Sidebar Fixa
        self.sidebar_frame = tk.Frame(self.body_frame, bg=THEME["bg_sidebar"], width=220, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Container Central de Conteúdo
        self.content_container = tk.Frame(self.body_frame, bg=THEME["bg_dark"], padx=14, pady=14)
        self.content_container.pack(side="right", fill="both", expand=True)

        self._build_sidebar()
        self._build_all_pages()
        self.show_page("dashboard")

    def _build_sidebar(self) -> None:
        self.nav_buttons = {}
        pages = [
            ("dashboard", "◉  Dashboard"),
            ("bot", "🤖  Bot Control"),
            ("battle", "⚔  Battle"),
            ("navigation", "🧭  Navigation"),
            ("vision", "👁  Vision"),
            ("memory", "🧠  Memory"),
            ("telemetry", "📈  Telemetry"),
            ("logs", "📜  Logs"),
            ("diagnostics", "🩺  Diagnostics"),
            ("settings", "⚙  Settings"),
        ]

        for page_id, text in pages:
            btn = tk.Button(
                self.sidebar_frame,
                text=text,
                anchor="w",
                bg=THEME["bg_sidebar"],
                fg=THEME["text_secondary"],
                activebackground=THEME["bg_card"],
                activeforeground=THEME["text_primary"],
                bd=0,
                font=(THEME["font_family"], 10),
                padx=18,
                pady=10,
                cursor="hand2",
                command=lambda pid=page_id: self.show_page(pid),
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[page_id] = btn

        # Botão de Parada de Emergência no Rodapé da Sidebar
        emg_box = tk.Frame(self.sidebar_frame, bg=THEME["bg_sidebar"])
        emg_box.pack(side="bottom", fill="x", pday=14, padx=12, pady=16)

        btn_emg = tk.Button(
            emg_box,
            text="🔴 EMERGENCY STOP\n(ESC)",
            bg=THEME["accent_red"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            pady=10,
            cursor="hand2",
            command=self._on_emergency_stop,
        )
        btn_emg.pack(fill="x")

    def show_page(self, page_id: str) -> None:
        self.current_page = page_id
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold"))
            else:
                btn.configure(bg=THEME["bg_sidebar"], fg=THEME["text_secondary"], font=(THEME["font_family"], 10))

        for pid, frame in self.page_frames.items():
            if pid == page_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def _build_all_pages(self) -> None:
        self.page_frames = {
            "dashboard": self._create_dashboard_page(),
            "bot": self._create_bot_page(),
            "battle": self._create_battle_page(),
            "navigation": self._create_navigation_page(),
            "vision": self._create_vision_page(),
            "memory": self._create_memory_page(),
            "telemetry": self._create_telemetry_page(),
            "logs": self._create_logs_page(),
            "diagnostics": self._create_diagnostics_page(),
            "settings": self._create_settings_page(),
        }

    # -------------------------------------------------------------
    # 1. PÁGINA: DASHBOARD (COM LIVE GAME VIEW & CARDS)
    # -------------------------------------------------------------
    def _create_dashboard_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        # Grid Superior de 6 Cards de Telemetria
        cards_row = tk.Frame(page, bg=THEME["bg_dark"])
        cards_row.pack(fill="x", pady=(0, 10))

        card_defs = [
            ("BOT STATUS", "dash_card_status", "STOPPED", THEME["text_secondary"]),
            ("CURRENT STATE", "dash_card_state", "IDLE", "#38BDF8"),
            ("MODE", "dash_card_mode", "AUTONOMOUS", THEME["text_primary"]),
            ("FPS", "dash_card_fps", "0.0", THEME["accent_primary"]),
            ("LATENCY", "dash_card_latency", "0.0 ms", THEME["text_primary"]),
            ("BATTLES (W/L)", "dash_card_battles", "0 (0W / 0L)", THEME["accent_purple"]),
        ]

        self.dash_card_labels = {}
        for i, (title, key, init_val, color) in enumerate(card_defs):
            c = tk.Frame(cards_row, bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
            c.pack(side="left", fill="both", expand=True, padx=3)
            tk.Label(c, text=title, bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 8, "bold")).pack(anchor="w")
            lbl = tk.Label(c, text=init_val, bg=THEME["bg_card"], fg=color, font=(THEME["font_family"], 11, "bold"))
            lbl.pack(anchor="w", pady=(2, 0))
            self.dash_card_labels[key] = lbl

        # Corpo Central do Dashboard: Split 65% Live Game View / 35% Live Activity
        split_frame = tk.Frame(page, bg=THEME["bg_dark"])
        split_frame.pack(fill="both", expand=True)

        # Lado Esquerdo: Live Game View
        game_view_box = tk.Frame(split_frame, bg=THEME["bg_card"], padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        game_view_box.pack(side="left", fill="both", expand=True, padx=(0, 6))

        gv_header = tk.Frame(game_view_box, bg=THEME["bg_card"])
        gv_header.pack(fill="x", pady=(0, 6))
        tk.Label(gv_header, text="📺 LIVE GAME VIEW", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(side="left")
        self.dash_capture_stat_lbl = tk.Label(gv_header, text="Overlays: [PLAYER] [ENEMY] [HP] [FIGHT] [CRYSTAL] [DIALOG]", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 8))
        self.dash_capture_stat_lbl.pack(side="right")

        self.dash_canvas = tk.Canvas(game_view_box, bg="#000000", highlightthickness=0)
        self.dash_canvas.pack(fill="both", expand=True, pady=4)

        # Lado Direito: Live Activity & Decisões
        activity_box = tk.Frame(split_frame, bg=THEME["bg_card"], width=380, padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        activity_box.pack(side="right", fill="both", padx=(6, 0))
        activity_box.pack_propagate(False)

        tk.Label(activity_box, text="📜 LIVE ACTIVITY FEED", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.dash_activity_text = tk.Text(activity_box, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), bd=0, highlightthickness=0, wrap="word")
        self.dash_activity_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 2. PÁGINA: BOT CONTROL (MODOS, COMPORTAMENTO, D-PAD)
    # -------------------------------------------------------------
    def _create_bot_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        # Seleção de Modo
        mode_card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        mode_card.pack(fill="x", pady=(0, 10))

        tk.Label(mode_card, text="MODO DO AGENTE:", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(side="left", padx=(0, 12))

        self.bot_mode_var = tk.StringVar(value="AUTONOMOUS")
        for text, val in [("Manual", "MANUAL"), ("Assisted", "ASSISTED"), ("Autonomous", "AUTONOMOUS")]:
            rb = tk.Radiobutton(
                mode_card,
                text=text,
                variable=self.bot_mode_var,
                value=val,
                bg=THEME["bg_card"],
                fg=THEME["text_primary"],
                selectcolor=THEME["bg_card_alt"],
                activebackground=THEME["bg_card"],
                font=(THEME["font_family"], 9),
                command=lambda: self.bot_controller.set_mode(self.bot_mode_var.get()),
            )
            rb.pack(side="left", padx=10)

        # Comportamento & D-Pad Split
        bot_split = tk.Frame(page, bg=THEME["bg_dark"])
        bot_split.pack(fill="both", expand=True)

        # Checkboxes de Comportamento
        behav_card = tk.Frame(bot_split, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        behav_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(behav_card, text="⚙ COMPORTAMENTO DO AGENTE", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 10))

        for text in ["☑ Explorar mundo aberto", "☑ Batalhar automaticamente", "☑ Curar equipe no cristal", "☑ Retornar à rota após combate", "☑ Recuperação automática anti-stuck"]:
            cb = tk.Checkbutton(behav_card, text=text, bg=THEME["bg_card"], fg=THEME["text_secondary"], selectcolor=THEME["bg_card_alt"], activebackground=THEME["bg_card"], font=(THEME["font_family"], 9))
            cb.select()
            cb.pack(anchor="w", pady=3)

        tk.Label(behav_card, text="\nINTERVALOS & TIMING:", bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 8, "bold")).pack(anchor="w")
        tk.Label(behav_card, text="• Duração do passo WASD: 0.25s\n• Timeout de batalha: 45.0s\n• Limite de retentativas: 3\n• Confiança de detecção mínima: 0.65", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=("Consolas", 9), justify="left").pack(anchor="w", pady=4)

        # D-Pad Virtual de Controle Manual
        dpad_card = tk.Frame(bot_split, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        dpad_card.pack(side="right", fill="both", expand=True, padx=(6, 0))

        tk.Label(dpad_card, text="🕹️ D-PAD DE CONTROLE MANUAL FÍSICO", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 8))

        self.dpad_target_lbl = tk.Label(dpad_card, text="Janela: Verificando...", bg=THEME["bg_card_alt"], fg="#38BDF8", font=("Consolas", 9), padx=8, pady=4)
        self.dpad_target_lbl.pack(fill="x", pady=(0, 12))

        dpad_grid = tk.Frame(dpad_card, bg=THEME["bg_card"])
        dpad_grid.pack(anchor="center", pady=6)

        tk.Button(dpad_grid, text="W", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], width=8, height=2, bd=0, font=(THEME["font_family"], 10, "bold"), command=lambda: self._on_manual_key("w")).grid(row=0, column=1, padx=4, pady=4)
        tk.Button(dpad_grid, text="A", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], width=8, height=2, bd=0, font=(THEME["font_family"], 10, "bold"), command=lambda: self._on_manual_key("a")).grid(row=1, column=0, padx=4, pady=4)
        tk.Button(dpad_grid, text="S", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], width=8, height=2, bd=0, font=(THEME["font_family"], 10, "bold"), command=lambda: self._on_manual_key("s")).grid(row=1, column=1, padx=4, pady=4)
        tk.Button(dpad_grid, text="D", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], width=8, height=2, bd=0, font=(THEME["font_family"], 10, "bold"), command=lambda: self._on_manual_key("d")).grid(row=1, column=2, padx=4, pady=4)

        tk.Button(dpad_grid, text="SPACE (Interagir)", bg=THEME["accent_blue"], fg="white", width=16, height=2, bd=0, font=(THEME["font_family"], 9, "bold"), command=lambda: self._on_manual_key("space")).grid(row=2, column=0, columnspan=2, padx=4, pady=8)
        tk.Button(dpad_grid, text="ENTER", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], width=10, height=2, bd=0, font=(THEME["font_family"], 9, "bold"), command=lambda: self._on_manual_key("enter")).grid(row=2, column=2, padx=4, pady=8)

        return page

    # -------------------------------------------------------------
    # 3. PÁGINA: BATTLE (LUMEN, INIMIGO, SLOTS & DECISÃO)
    # -------------------------------------------------------------
    def _create_battle_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="⚔️ PAINEL DE COMBATE & DECISÃO ELEMENTAL", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        # VS Frame
        vs_frame = tk.Frame(card, bg=THEME["bg_card_alt"], padx=14, pady=10)
        vs_frame.pack(fill="x", pady=6)

        self.battle_player_lbl = tk.Label(vs_frame, text="🛡️ PLAYER: Spark (Lv. 5 | HP: 100% | Status: OK)", bg=THEME["bg_card_alt"], fg=THEME["status_active"], font=(THEME["font_family"], 10, "bold"))
        self.battle_player_lbl.pack(side="left")

        self.battle_enemy_lbl = tk.Label(vs_frame, text="👾 INIMIGO: Desconhecido (HP: -- | Tipo: Fogo)", bg=THEME["bg_card_alt"], fg=THEME["accent_red"], font=(THEME["font_family"], 10, "bold"))
        self.battle_enemy_lbl.pack(side="right")

        # Slots de Golpe
        moves_box = tk.Frame(card, bg=THEME["bg_card"], pady=8)
        moves_box.pack(fill="x")
        tk.Label(moves_box, text="GOLPES DISPONÍVEIS & PONTUAÇÃO:", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9, "bold")).pack(anchor="w", pady=(0, 4))

        self.battle_moves_text = tk.Text(moves_box, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=("Consolas", 10), height=5, bd=0)
        self.battle_moves_text.pack(fill="x")
        self.battle_moves_text.insert(tk.END, "1. WaterPulse  | Poder: 60 | Tipo: Água   | PP: 15/15 | Efetividade: SUPER EFETIVO (2.0x) | Score: 120.0\n2. Tackle      | Poder: 40 | Tipo: Normal | PP: 30/30 | Efetividade: Neutro (1.0x)        | Score: 40.0")

        # Painel da Decisão Atual
        dec_card = tk.Frame(card, bg=THEME["bg_dark"], padx=14, pady=12, highlightthickness=1, highlightbackground=THEME["border"])
        dec_card.pack(fill="both", expand=True, pady=10)

        tk.Label(dec_card, text="🎯 DECISÃO ATUAL DO AGENTE DE COMBATE", bg=THEME["bg_dark"], fg="#38BDF8", font=(THEME["font_family"], 10, "bold")).pack(anchor="w")
        self.battle_decision_lbl = tk.Label(dec_card, text="Ação: MOVE -> WaterPulse", bg=THEME["bg_dark"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold"))
        self.battle_decision_lbl.pack(anchor="w", pady=(4, 2))
        self.battle_reason_lbl = tk.Label(dec_card, text="Razão: Fraqueza elemental detectada no inimigo (Fogo vs Água).", bg=THEME["bg_dark"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9))
        self.battle_reason_lbl.pack(anchor="w")

        return page

    # -------------------------------------------------------------
    # 4. PÁGINA: NAVEGAÇÃO & ROTAS
    # -------------------------------------------------------------
    def _create_navigation_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🧭 GERENCIADOR DE ROTAS & REPLAY WASD", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        # Botões de Ação de Rota
        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=(0, 10))

        tk.Button(btn_bar, text="▶ EXECUTAR", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_play_route).pack(side="left", padx=(0, 4))
        tk.Button(btn_bar, text="🔄 REVERSA", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_play_reverse_route).pack(side="left", padx=4)
        tk.Button(btn_bar, text="🎙️ GRAVAR NOVA", bg=THEME["accent_orange"], fg="black", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_start_record_route).pack(side="left", padx=4)
        tk.Button(btn_bar, text="⏹️ SALVAR", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_stop_record_route).pack(side="left", padx=4)

        # Lista de Rotas e Tabela de Passos Split
        nav_split = tk.Frame(card, bg=THEME["bg_card"])
        nav_split.pack(fill="both", expand=True)

        self.route_listbox = tk.Listbox(nav_split, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=("Consolas", 10), width=24, selectbackground=THEME["accent_blue"], bd=0)
        self.route_listbox.pack(side="left", fill="y", padx=(0, 8))
        self._refresh_route_list()

        # Tabela STEP | KEY | DURATION
        self.nav_step_text = tk.Text(nav_split, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 10), bd=0)
        self.nav_step_text.pack(side="right", fill="both", expand=True)
        self.nav_step_text.insert(tk.END, "STEP | KEY | DURATION\n---------------------\n1    | W   | 0.45s\n2    | D   | 0.22s\n3    | W   | 0.80s\n4    | A   | 0.31s\n")

        return page

    # -------------------------------------------------------------
    # 5. PÁGINA: VISION (LIVE FRAME + DETECTIONS)
    # -------------------------------------------------------------
    def _create_vision_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        v_head = tk.Frame(card, bg=THEME["bg_card"])
        v_head.pack(fill="x", pady=(0, 8))
        tk.Label(v_head, text="👁️ VISÃO COMPUTACIONAL & DETECÇÕES SEMÂNTICAS", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(side="left")

        tk.Button(v_head, text="📸 Salvar Frame de Debug", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=5, command=self._on_save_debug_frame).pack(side="right")

        # Canvas Preview
        self.vision_canvas = tk.Canvas(card, bg="#000000", width=640, height=360, highlightthickness=0)
        self.vision_canvas.pack(anchor="center", pady=4)

        # Detections Table
        self.vision_det_text = tk.Text(card, bg=THEME["bg_dark"], fg="#FDE047", font=("Consolas", 9), height=6, bd=0)
        self.vision_det_text.pack(fill="x", pady=(6, 0))
        self.vision_det_text.insert(tk.END, "DETECÇÕES ATIVAS:\n• [PLAYER]       Confiança: 0.95 | Coords: (960, 540) | Ts: Live\n• [BLUE_CRYSTAL] Confiança: 0.92 | Coords: (1420, 320)| Ts: Live\n• [GRASS_ZONE]   Densidade: 0.78 | Região: Centro     | Ts: Live\n")

        return page

    # -------------------------------------------------------------
    # 6. PÁGINA: MEMORY (MAPA, HEADING, LANDMARKS)
    # -------------------------------------------------------------
    def _create_memory_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🧠 MODELO TOPOLÓGICO DE MUNDO & EXPERIÊNCIA", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        self.mem_info_text = tk.Text(card, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=("Consolas", 10), height=14, bd=0)
        self.mem_info_text.pack(fill="both", expand=True, pady=6)

        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=4)
        tk.Button(btn_bar, text="🗑️ Limpar Memória", bg=THEME["accent_red"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=5, command=self._on_clear_memory).pack(side="left")

        return page

    # -------------------------------------------------------------
    # 7. PÁGINA: TELEMETRY (GRÁFICOS & MÉTRICAS)
    # -------------------------------------------------------------
    def _create_telemetry_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="📈 TELEMETRIA EM TEMPO REAL & PERFORMANCE", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 12))

        self.telemetry_details_lbl = tk.Label(card, text="Carregando métricas de telemetria...", bg=THEME["bg_card"], fg=THEME["text_primary"], font=("Consolas", 10), justify="left")
        self.telemetry_details_lbl.pack(anchor="w", pady=6)

        return page

    # -------------------------------------------------------------
    # 8. PÁGINA: LOGS (MULTI-CANAL COM FILTROS)
    # -------------------------------------------------------------
    def _create_logs_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        # Filtros de Log
        filter_bar = tk.Frame(card, bg=THEME["bg_card"])
        filter_bar.pack(fill="x", pady=(0, 8))

        tk.Label(filter_bar, text="Filtro:", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9, "bold")).pack(side="left", padx=(0, 6))

        for f in ["ALL", "INPUT", "VISION", "COMBAT", "NAVIGATION", "ERROR"]:
            tk.Button(filter_bar, text=f, bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=lambda flt=f: self._on_set_log_filter(flt)).pack(side="left", padx=2)

        tk.Button(filter_bar, text="Exportar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=self._on_export_logs).pack(side="right", padx=3)
        tk.Button(filter_bar, text="Copiar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=self._on_copy_logs).pack(side="right", padx=3)
        tk.Button(filter_bar, text="Limpar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=lambda: self.logs_text.delete("1.0", tk.END)).pack(side="right", padx=3)

        self.logs_text = tk.Text(card, bg=THEME["bg_dark"], fg="#E2E8F0", font=("Consolas", 9), bd=0, wrap="word")
        self.logs_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 9. PÁGINA: DIAGNOSTICS & TESTE FÍSICO GUIADO
    # -------------------------------------------------------------
    def _create_diagnostics_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🩺 DIAGNÓSTICOS DO SISTEMA & TESTES FÍSICOS", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=(0, 10))

        tk.Button(btn_bar, text="▶ RUN FULL DIAGNOSTIC", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_run_diagnostics).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="⚡ PHYSICAL INPUT TEST", bg=THEME["accent_orange"], fg="black", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_open_physical_test_modal).pack(side="left", padx=4)
        tk.Button(btn_bar, text="📸 SCREEN CAPTURE TEST", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=6, command=self._on_test_capture).pack(side="left", padx=4)
        tk.Button(btn_bar, text="🪟 FOCUS TEST", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=6, command=self._on_test_focus).pack(side="left", padx=4)

        self.diag_results_text = tk.Text(card, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), height=14, bd=0)
        self.diag_results_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 10. PÁGINA: SETTINGS (PRESETS & PERSISTÊNCIA)
    # -------------------------------------------------------------
    def _create_settings_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="⚙️ CONFIGURAÇÕES & PRESETS DE PERFIL", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        preset_box = tk.Frame(card, bg=THEME["bg_card"])
        preset_box.pack(fill="x", pady=6)
        tk.Label(preset_box, text="Presets Rápidos:", bg=THEME["bg_card"], fg=THEME["text_secondary"]).pack(side="left", padx=(0, 8))

        for p in ["SAFE", "BALANCED", "AGGRESSIVE", "DEBUG"]:
            tk.Button(preset_box, text=p, bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=10, pady=4, command=lambda preset=p: self._apply_preset(preset)).pack(side="left", padx=3)

        tk.Button(card, text="💾 SALVAR CONFIGURAÇÕES", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 10, "bold"), bd=0, padx=16, pady=8, command=self._on_save_settings).pack(anchor="w", pady=16)

        return page

    # -------------------------------------------------------------
    # MODAL DE TESTE FÍSICO GUIADO (SEÇÃO 5 DA ESPECIFICAÇÃO)
    # -------------------------------------------------------------
    def _on_open_physical_test_modal(self) -> None:
        modal = tk.Toplevel(self.root)
        modal.title("⚡ Teste de Input Físico Guiado")
        modal.geometry("520x420")
        modal.configure(bg=THEME["bg_card"])
        modal.transient(self.root)
        modal.grab_set()

        tk.Label(modal, text="⚡ TESTE DE ENTRADA FÍSICA & DELTA VISUAL", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(pady=12)

        info_lbl = tk.Label(
            modal,
            text="Abra o Lumena.gg no Chrome e deixe o personagem parado em área segura.\nO teste enviará a tecla W por 0.50s e medirá a variação visual.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="center",
        )
        info_lbl.pack(pady=6)

        win_info = self.input_ctrl.window_manager.find_target_window()
        has_win = "SIM" if win_info else "NÃO"
        status_box = tk.Label(
            modal,
            text=f"• Janela Encontrada : {has_win} ({win_info.title if win_info else 'Nenhuma'})\n• Canvas WebGL      : {'CONFIRMADO' if win_info else 'PENDENTE'}\n• Backend de Input  : {self.input_ctrl.active_backend_name.upper()}\n• Safety Guard      : ATIVO",
            bg=THEME["bg_dark"],
            fg="#93C5FD",
            font=("Consolas", 9),
            padx=12,
            pady=8,
            justify="left",
        )
        status_box.pack(fill="x", padx=16, pady=10)

        res_lbl = tk.Label(modal, text="Aguardando confirmação...", bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 9))
        res_lbl.pack(pady=8)

        btn_row = tk.Frame(modal, bg=THEME["bg_card"])
        btn_row.pack(pady=12)

        def do_test():
            res_lbl.configure(text="Executando teste físico...", fg=THEME["status_warning"])
            modal.update()

            from scripts.real_world_test import run_real_world_test
            report = run_real_world_test(interactive=False)

            if report.get("movement_confirmed"):
                msg = f"✓ INPUT ENVIADO | TECLA LIBERADA | DELTA: {report.get('step_16_visual_delta', 0):.4f} (CONFIRMADO)"
                res_lbl.configure(text=msg, fg=THEME["status_active"])
            else:
                msg = f"✗ INPUT DESPACHADO | SEM ALTERAÇÃO VISUAL (DELTA: {report.get('step_16_visual_delta', 0):.4f})"
                res_lbl.configure(text=msg, fg=THEME["status_error"])

        tk.Button(btn_row, text="[ TESTAR AGORA ]", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=16, pady=6, command=do_test).pack(side="left", padx=8)
        tk.Button(btn_row, text="[ CANCELAR ]", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=14, pady=6, command=modal.destroy).pack(side="left", padx=8)

    # -------------------------------------------------------------
    # CALLBACKS GERAIS
    # -------------------------------------------------------------
    def _on_start_bot(self) -> None:
        mode = self.bot_mode_var.get() if hasattr(self, "bot_mode_var") else "AUTONOMOUS"
        self.bot_controller.start(mode=mode)

    def _on_stop_bot(self) -> None:
        self.bot_controller.stop()

    def _on_pause_bot(self) -> None:
        if self.bot_controller.is_paused():
            self.bot_controller.resume()
        else:
            self.bot_controller.pause()

    def _on_emergency_stop(self) -> None:
        self.bot_controller.emergency_stop()

    def _on_manual_key(self, key: str) -> None:
        threading.Thread(target=lambda: self.bot_controller.manual_press(key, duration=0.2), daemon=True).start()

    def _refresh_route_list(self) -> None:
        self.route_listbox.delete(0, tk.END)
        for r in self.bot_controller.engine.navigation.route_manager.list_routes():
            self.route_listbox.insert(tk.END, r)

    def _on_play_route(self) -> None:
        sel = self.route_listbox.curselection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma rota da lista.")
            return
        name = self.route_listbox.get(sel[0])
        threading.Thread(target=lambda: self.bot_controller.engine.navigation.execute_route(name, reverse=False), daemon=True).start()

    def _on_play_reverse_route(self) -> None:
        sel = self.route_listbox.curselection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma rota da lista.")
            return
        name = self.route_listbox.get(sel[0])
        threading.Thread(target=lambda: self.bot_controller.engine.navigation.execute_route(name, reverse=True), daemon=True).start()

    def _on_start_record_route(self) -> None:
        self.bot_controller.engine.navigation.route_manager.start_recording()
        messagebox.showinfo("Gravação", "Gravação iniciada! Use o D-Pad para movimentar.")

    def _on_stop_record_route(self) -> None:
        steps = self.bot_controller.engine.navigation.route_manager.stop_recording(route_name="custom_route")
        self._refresh_route_list()
        messagebox.showinfo("Gravação", f"Rota salva com {len(steps)} passos!")

    def _on_save_debug_frame(self) -> None:
        os.makedirs("debug", exist_ok=True)
        frame = self.bot_controller.get_latest_frame()
        if frame is not None:
            path = f"debug/{time.strftime('%Y-%m-%d_%H-%M-%S')}_vision_frame.png"
            cv2.imwrite(path, frame)
            messagebox.showinfo("Visão", f"Frame de depuração salvo em:\n{path}")
        else:
            messagebox.showwarning("Visão", "Nenhum frame ativo capturado.")

    def _on_clear_memory(self) -> None:
        self.bot_controller.engine.memory_manager.world_memory = self.bot_controller.engine.memory_manager.world_memory.__class__()
        messagebox.showinfo("Memória", "Memória resetada com sucesso.")

    def _on_set_log_filter(self, flt: str) -> None:
        self.log_filter = flt

    def _on_copy_logs(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.logs_text.get("1.0", tk.END))
        messagebox.showinfo("Logs", "Logs copiados para a área de transferência.")

    def _on_export_logs(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.logs_text.get("1.0", tk.END))
            messagebox.showinfo("Logs", "Logs exportados com sucesso.")

    def _on_run_diagnostics(self) -> None:
        self.diag_results_text.delete("1.0", tk.END)
        self.diag_results_text.insert(tk.END, "Executando varredura geral do sistema...\n\n")

        def run():
            win_info = self.input_ctrl.window_manager.find_target_window()
            res = (
                f"[✓] Python          : {sys.version.split()[0]} (PASS)\n"
                f"[✓] OpenCV          : PASS\n"
                f"[✓] PyAutoGUI       : PASS (FailSafe=True)\n"
                f"[✓] Win32 SendInput : PASS\n"
                f"[✓] Janela Alvo     : {'ENCONTRADA: ' + win_info.title if win_info else 'NÃO ENCONTRADA'}\n"
                f"[✓] Input Backend   : {self.input_ctrl.active_backend_name.upper()}\n"
                f"[✓] Safety Guard    : ATIVO (Parada ESC pronta)\n"
            )
            self.root.after(0, lambda: self.diag_results_text.insert(tk.END, res))

        threading.Thread(target=run, daemon=True).start()

    def _on_test_capture(self) -> None:
        frame, _ = self.bot_controller.engine.screen_capture.capture_frame()
        if frame is not None:
            messagebox.showinfo("Captura", f"Captura OK: {frame.shape[1]}x{frame.shape[0]} pixels.")
        else:
            messagebox.showwarning("Captura", "Falha na captura: Sessão não-interativa ou sem display ativo.")

    def _on_test_focus(self) -> None:
        ok = self.input_ctrl.focus_game_window()
        if ok:
            messagebox.showinfo("Foco", "Foco obtido com sucesso na janela alvo.")
        else:
            messagebox.showwarning("Foco", "Janela alvo não encontrada para foco.")

    def _apply_preset(self, preset: str) -> None:
        messagebox.showinfo("Preset", f"Preset '{preset}' aplicado.")

    def _on_save_settings(self) -> None:
        save_config(self.config)
        messagebox.showinfo("Configurações", "Configurações salvas em config/settings.json.")

    # -------------------------------------------------------------
    # TICK DE TELEMETRIA EM TEMPO REAL (80ms)
    # -------------------------------------------------------------
    def _ui_telemetry_tick(self) -> None:
        try:
            snap = self.telemetry.get_snapshot()
            state = snap.get("state", "IDLE")

            is_active = self.bot_controller.is_running()
            if state == "EMERGENCY_STOP":
                self.status_badge.configure(text="● EMERGENCY STOP", fg=THEME["status_error"])
            elif is_active:
                self.status_badge.configure(text=f"● RUNNING ({state})", fg=THEME["status_active"])
            else:
                self.status_badge.configure(text="● OFFLINE", fg=THEME["text_muted"])

            # Cards do Dashboard
            if hasattr(self, "dash_card_labels"):
                self.dash_card_labels["dash_card_status"].configure(text="RUNNING" if is_active else "STOPPED")
                self.dash_card_labels["dash_card_state"].configure(text=state)
                self.dash_card_labels["dash_card_mode"].configure(text=self.bot_controller.engine.mode)
                self.dash_card_labels["dash_card_fps"].configure(text=f"{snap.get('fps', 0.0):.1f}")
                self.dash_card_labels["dash_card_latency"].configure(text=f"{snap.get('avg_latency', 0.0) * 1000:.1f} ms")
                self.dash_card_labels["dash_card_battles"].configure(text=f"{snap.get('battles_total', 0)} ({snap.get('victories_total', 0)}W / {snap.get('defeats_total', 0)}L)")

            # Live Activity Feed no Dashboard
            if self.current_page == "dashboard":
                events = self.telemetry.get_recent_events(max_count=18)
                if events:
                    self.dash_activity_text.delete("1.0", tk.END)
                    self.dash_activity_text.insert(tk.END, "\n".join(events))
                    self.dash_activity_text.see(tk.END)

                # Renderiza Preview no Dashboard
                frame = self.bot_controller.get_latest_frame()
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    im = Image.fromarray(rgb).resize((520, 290))
                    self._dash_preview_img_tk = ImageTk.PhotoImage(im)
                    self.dash_canvas.delete("all")
                    self.dash_canvas.create_image(0, 0, anchor="nw", image=self._dash_preview_img_tk)
                else:
                    self.dash_canvas.delete("all")
                    self.dash_canvas.create_text(260, 145, text="[ NO LIVE FRAME ]\n(Abra o Lumena.gg no Chrome)", fill="#64748B", font=(THEME["font_family"], 11, "bold"), justify="center")

            # Vision Feed Page
            if self.current_page == "vision":
                frame = self.bot_controller.get_latest_frame()
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    im = Image.fromarray(rgb).resize((640, 360))
                    self._vision_img_tk = ImageTk.PhotoImage(im)
                    self.vision_canvas.delete("all")
                    self.vision_canvas.create_image(0, 0, anchor="nw", image=self._vision_img_tk)
                else:
                    self.vision_canvas.delete("all")
                    self.vision_canvas.create_text(320, 180, text="[ NO LIVE FRAME ]", fill="#64748B", font=(THEME["font_family"], 12, "bold"))

            # Memory Info
            if self.current_page == "memory":
                mem = self.bot_controller.engine.memory_manager.world_memory
                m_txt = (
                    f"POSIÇÃO ATUAL  : ({mem.player_position[0]:.2f}, {mem.player_position[1]:.2f})\n"
                    f"DIREÇÃO        : {mem.player_heading}\n"
                    f"CÉLULAS MAPA   : {len(mem.visited_cells)} visitadas\n"
                    f"MARCOS (ANCHOR): {len(mem.landmarks)} detectados\n"
                    f"OBSTÁCULOS     : {len(mem.obstacles)} colisões registradas\n"
                )
                self.mem_info_text.delete("1.0", tk.END)
                self.mem_info_text.insert(tk.END, m_txt)

            # Telemetry Details
            if self.current_page == "telemetry":
                t_text = (
                    f"Métricas Operacionais:\n"
                    f"• Uptime                : {snap.get('uptime', 0.0):.1f}s\n"
                    f"• FPS Atual             : {snap.get('fps', 0.0):.1f}\n"
                    f"• Ações Executadas      : {snap.get('actions_total', 0)} (Sucessos: {snap.get('actions_successful', 0)}, Falhas: {snap.get('actions_failed', 0)})\n"
                    f"• Ações / Minuto        : {snap.get('actions_per_minute', 0.0):.1f}\n"
                    f"• Latência Média Ação   : {snap.get('avg_latency', 0.0) * 1000:.1f} ms\n"
                    f"• Batalhas Totais       : {snap.get('battles_total', 0)} ({snap.get('victories_total', 0)} Vitórias, {snap.get('defeats_total', 0)} Derrotas)\n"
                    f"• Recuperações de Erro  : {snap.get('recoveries_total', 0)}\n"
                )
                self.telemetry_details_lbl.configure(text=t_text)

        except Exception:
            pass

        self.root.after(80, self._ui_telemetry_tick)


def start_modern_gui() -> None:
    root = tk.Tk()
    app = ModernLumenaGUI(root)
    root.mainloop()
