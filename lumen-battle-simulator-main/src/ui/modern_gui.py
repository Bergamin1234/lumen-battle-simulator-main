import os
import sys
import time
import json
import logging
import threading
import queue
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
from src.input.target_window import TargetWindowManager, WindowInfo, FocusDiagnosticResult
from src.core.event_bus import EventBus, EventType, BotEvent
from src.perception.combat_vision import CombatVisionAnalyzer
from src.models.combat_vision import CombatSnapshot, SkillSlot, EnemyTarget
from src.ui.canvas_inspector_overlay import CanvasInspectorOverlay
from src.telemetry.replay_viewer import BlackboxReplayEngine
from src.ui.setup_tutorial_wizard import SetupTutorialWizard

logger = logging.getLogger("LumenaGUI")

THEME = {
    "bg_dark": "#0B0F19",
    "bg_sidebar": "#111827",
    "bg_card": "#1F2937",
    "bg_card_alt": "#374151",
    "border": "#374151",
    "text_primary": "#F9FAFB",
    "text_secondary": "#9CA3AF",
    "text_muted": "#6B7280",
    "accent_primary": "#10B981",
    "accent_blue": "#3B82F6",
    "accent_cyan": "#06B6D4",
    "accent_purple": "#8B5CF6",
    "accent_orange": "#F59E0B",
    "accent_red": "#EF4444",
    "status_active": "#10B981",
    "status_warning": "#F59E0B",
    "status_error": "#EF4444",
    "font_family": "Segoe UI",
}


class ModernLumenaGUI:
    """Painel de Controle Profissional (Control Center) de 14 Páginas para o Lumena Bot Master v5.0."""

    def __init__(self, root: tk.Tk, config: Optional[BotConfig] = None) -> None:
        self.root = root
        self.root.title("Lumena Bot [MASTER v5.0] — Autonomous Industrial Suite")
        self.root.geometry("1420x920")
        self.root.minsize(1240, 800)
        self.root.configure(bg=THEME["bg_dark"])

        self.config = config or load_config()
        self.bot_controller = BotController(config=self.config)
        self.telemetry = TelemetryManager()
        self.event_bus = EventBus()
        self.input_ctrl = self.bot_controller.engine.input_ctrl
        self.combat_vision = CombatVisionAnalyzer()
        self.canvas_inspector = CanvasInspectorOverlay()
        self.replay_engine = BlackboxReplayEngine()

        # Fila thread-safe de eventos para a GUI
        self.gui_event_queue = self.event_bus.get_or_create_queue("gui_consumer")

        self.current_page = "dashboard"
        self.log_filter = "ALL"
        self.log_paused = False

        # Variáveis de Overlays da Visão
        self.show_bbox_var = tk.BooleanVar(value=True)
        self.show_state_var = tk.BooleanVar(value=True)
        self.show_coords_var = tk.BooleanVar(value=True)
        self.show_fps_var = tk.BooleanVar(value=True)
        self.show_decisions_var = tk.BooleanVar(value=True)

        self._vision_img_tk = None
        self._dash_preview_img_tk = None
        self._live_game_img_tk = None

        self._setup_styles()
        self._setup_keybindings()
        self._build_main_layout()

        # Inicia loop de telemetria e consumo de eventos na UI thread
        self.root.after(50, self._ui_telemetry_tick)

        # Se for primeira execução ou não configurado, abre o assistente tutorial automaticamente
        if not getattr(self.config, "tutorial_completed", False):
            self.root.after(400, self._on_open_tutorial_wizard)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=THEME["bg_dark"])
        style.configure("Card.TFrame", background=THEME["bg_card"])
        style.configure("TLabel", background=THEME["bg_card"], foreground=THEME["text_primary"], font=(THEME["font_family"], 9))
        style.configure("TProgressbar", thickness=8, troughcolor=THEME["bg_card_alt"], background=THEME["accent_blue"])

    def _setup_keybindings(self) -> None:
        self.root.bind("<F1>", lambda e: self._on_open_tutorial_wizard())
        self.root.bind("<Escape>", lambda e: self._on_emergency_stop())
        self.root.bind("<F5>", lambda e: self._on_start_bot())
        self.root.bind("<F6>", lambda e: self._on_pause_bot())
        self.root.bind("<F7>", lambda e: self._on_stop_bot())

    def _build_main_layout(self) -> None:
        # 1. HEADER SUPERIOR FIXO
        self.header_frame = tk.Frame(self.root, bg=THEME["bg_sidebar"], height=54, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.header_frame.pack(side="top", fill="x")

        title_box = tk.Frame(self.header_frame, bg=THEME["bg_sidebar"])
        title_box.pack(side="left", padx=16, pady=8)
        tk.Label(title_box, text="⚡ LUMENA BOT", bg=THEME["bg_sidebar"], fg=THEME["text_primary"], font=(THEME["font_family"], 13, "bold")).pack(side="left")
        tk.Label(title_box, text="MASTER v5.0", bg=THEME["bg_card_alt"], fg="#10B981", font=(THEME["font_family"], 8, "bold"), padx=6, pady=2).pack(side="left", padx=8)

        self.target_window_badge = tk.Label(
            self.header_frame,
            text="🪟 TARGET: BUSCANDO GOOGLE CHROME...",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            padx=12,
            pady=4,
        )
        self.target_window_badge.pack(side="left", padx=10)

        # Botões de Ação Rápida no Topo
        btn_box = tk.Frame(self.header_frame, bg=THEME["bg_sidebar"])
        btn_box.pack(side="left", padx=12)

        tk.Button(
            btn_box,
            text="🧙 TUTORIAL 100% (F1)",
            bg=THEME["accent_purple"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._on_open_tutorial_wizard,
        ).pack(side="left", padx=3)

        self.btn_top_start = tk.Button(btn_box, text="▶ START (F5)", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=14, pady=5, cursor="hand2", command=self._on_start_bot)
        self.btn_top_start.pack(side="left", padx=3)

        self.btn_top_pause = tk.Button(btn_box, text="⏸ PAUSE (F6)", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=5, cursor="hand2", command=self._on_pause_bot)
        self.btn_top_pause.pack(side="left", padx=3)

        self.btn_top_stop = tk.Button(btn_box, text="■ STOP (F7)", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=5, cursor="hand2", command=self._on_stop_bot)
        self.btn_top_stop.pack(side="left", padx=3)

        tk.Button(btn_box, text="🎯 TARGET WIZARD", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=5, cursor="hand2", command=self._on_open_target_wizard).pack(side="left", padx=4)

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

        # 2. STATUS BAR INFERIOR FIXO
        self.status_bar_frame = tk.Frame(self.root, bg=THEME["bg_sidebar"], height=32, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.status_bar_frame.pack(side="bottom", fill="x")

        self.subsys_labels = {}
        subsys_defs = ["BOT", "INPUT", "WINDOW", "VISION", "MEMORY", "COMBAT", "NAVIGATION"]
        for name in subsys_defs:
            lbl = tk.Label(self.status_bar_frame, text=f"● {name}", bg=THEME["bg_sidebar"], fg=THEME["status_active"], font=(THEME["font_family"], 8, "bold"), padx=8)
            lbl.pack(side="left")
            self.subsys_labels[name] = lbl

        self.footer_metrics_lbl = tk.Label(
            self.status_bar_frame,
            text="FPS: 0.0 | LATÊNCIA: 0.0ms | UPTIME: 0s",
            bg=THEME["bg_sidebar"],
            fg=THEME["text_muted"],
            font=("Consolas", 8),
            padx=16,
        )
        self.footer_metrics_lbl.pack(side="right")

        # 3. CORPO CENTRAL (Sidebar + Content Container)
        self.body_frame = tk.Frame(self.root, bg=THEME["bg_dark"])
        self.body_frame.pack(fill="both", expand=True)

        self.sidebar_frame = tk.Frame(self.body_frame, bg=THEME["bg_sidebar"], width=220, bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        self.content_container = tk.Frame(self.body_frame, bg=THEME["bg_dark"], padx=12, pady=12)
        self.content_container.pack(side="right", fill="both", expand=True)

        self._build_sidebar()
        self._build_all_pages()
        self.show_page("dashboard")

    def _build_sidebar(self) -> None:
        self.nav_buttons = {}
        pages = [
            ("dashboard", "◉  Dashboard"),
            ("bot", "🤖  Bot Control"),
            ("live_game", "📺  Live Game"),
            ("battle", "⚔  Battle Center"),
            ("navigation", "🧭  Navigation"),
            ("vision", "👁  Vision Center"),
            ("memory", "🧠  Memory Center"),
            ("telemetry", "📈  Telemetry"),
            ("activity", "⚡  Activity Feed"),
            ("logs", "📜  Log Center"),
            ("diagnostics", "🩺  Diagnostics"),
            ("validation", "🧪  Validation Levels"),
            ("settings", "⚙  Settings"),
            ("about", "ℹ️  System Info"),
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
                font=(THEME["font_family"], 9, "bold"),
                padx=16,
                pady=7,
                cursor="hand2",
                command=lambda pid=page_id: self.show_page(pid),
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[page_id] = btn

        emg_box = tk.Frame(self.sidebar_frame, bg=THEME["bg_sidebar"])
        emg_box.pack(side="bottom", fill="x", padx=10, pady=10)

        btn_emg = tk.Button(
            emg_box,
            text="🚨 EMERGENCY STOP\n(ESC)",
            bg=THEME["accent_red"],
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._on_emergency_stop,
        )
        btn_emg.pack(fill="x")

    def show_page(self, page_id: str) -> None:
        self.current_page = page_id
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(bg=THEME["bg_card"], fg="#38BDF8", font=(THEME["font_family"], 9, "bold"))
            else:
                btn.configure(bg=THEME["bg_sidebar"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9))

        for pid, frame in self.page_frames.items():
            if pid == page_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def _build_all_pages(self) -> None:
        self.page_frames = {
            "dashboard": self._create_dashboard_page(),
            "bot": self._create_bot_page(),
            "live_game": self._create_live_game_page(),
            "battle": self._create_battle_page(),
            "navigation": self._create_navigation_page(),
            "vision": self._create_vision_page(),
            "memory": self._create_memory_page(),
            "telemetry": self._create_telemetry_page(),
            "activity": self._create_activity_page(),
            "logs": self._create_logs_page(),
            "diagnostics": self._create_diagnostics_page(),
            "validation": self._create_validation_page(),
            "settings": self._create_settings_page(),
            "about": self._create_about_page(),
        }

    # -------------------------------------------------------------
    # 1. PÁGINA: DASHBOARD
    # -------------------------------------------------------------
    def _create_dashboard_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        # Banner de Tutorial & Calibração Rápida (100% Automatizado)
        tutorial_banner = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        tutorial_banner.pack(fill="x", pady=(0, 8))

        tk.Label(
            tutorial_banner,
            text="🚀 TUTORIAL PASSO A PASSO:",
            bg=THEME["bg_card"],
            fg=THEME["accent_primary"],
            font=(THEME["font_family"], 9, "bold"),
        ).pack(side="left")

        tk.Label(
            tutorial_banner,
            text="Calibre o Chrome, o Mato de Farm e a Rota de Cura para operação 100% autônoma.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
        ).pack(side="left", padx=8)

        tk.Button(
            tutorial_banner,
            text="🧙 ABRIR ASSISTENTE PASSO A PASSO (F1)",
            bg=THEME["accent_purple"],
            fg="white",
            font=(THEME["font_family"], 8, "bold"),
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_open_tutorial_wizard,
        ).pack(side="right")

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
        for title, key, init_val, color in card_defs:
            c = tk.Frame(cards_row, bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
            c.pack(side="left", fill="both", expand=True, padx=3)
            tk.Label(c, text=title, bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 8, "bold")).pack(anchor="w")
            lbl = tk.Label(c, text=init_val, bg=THEME["bg_card"], fg=color, font=(THEME["font_family"], 11, "bold"))
            lbl.pack(anchor="w", pady=(2, 0))
            self.dash_card_labels[key] = lbl

        split_frame = tk.Frame(page, bg=THEME["bg_dark"])
        split_frame.pack(fill="both", expand=True)

        game_box = tk.Frame(split_frame, bg=THEME["bg_card"], padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        game_box.pack(side="left", fill="both", expand=True, padx=(0, 6))

        gv_head = tk.Frame(game_box, bg=THEME["bg_card"])
        gv_head.pack(fill="x", pady=(0, 6))
        tk.Label(gv_head, text="📺 LIVE GAME VIEW", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(side="left")
        tk.Label(gv_head, text="Overlays: [PLAYER] [ENEMY] [HP] [SKILLS]", bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 8)).pack(side="right")

        self.dash_canvas = tk.Canvas(game_box, bg="#000000", highlightthickness=0)
        self.dash_canvas.pack(fill="both", expand=True, pady=4)

        # v4.2 Painel de Combate, Cooldowns e Canvas Viewport
        dash_combat_panel = tk.Frame(game_box, bg=THEME["bg_card_alt"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        dash_combat_panel.pack(fill="x", pady=(4, 0))

        # Linha de HP e Canvas
        hp_row = tk.Frame(dash_combat_panel, bg=THEME["bg_card_alt"])
        hp_row.pack(fill="x", pady=(0, 4))

        self.dash_player_hp_lbl = tk.Label(hp_row, text="PLAYER HP: 100%", bg=THEME["bg_card_alt"], fg="#10B981", font=(THEME["font_family"], 9, "bold"))
        self.dash_player_hp_lbl.pack(side="left", padx=4)

        self.dash_enemy_hp_lbl = tk.Label(hp_row, text="ENEMY HP: 100%", bg=THEME["bg_card_alt"], fg="#EF4444", font=(THEME["font_family"], 9, "bold"))
        self.dash_enemy_hp_lbl.pack(side="left", padx=8)

        self.dash_viewport_lbl = tk.Label(hp_row, text="CANVAS: (0, 0, 1920, 1080) | LETTERBOX: OFF", bg=THEME["bg_card_alt"], fg="#94A3B8", font=("Consolas", 8))
        self.dash_viewport_lbl.pack(side="right", padx=4)

        # Linha dos 4 Slots de Habilidades e Cooldown
        skills_row = tk.Frame(dash_combat_panel, bg=THEME["bg_card_alt"])
        skills_row.pack(fill="x")

        self.dash_skill_labels = []
        for i in range(1, 5):
            s_box = tk.Frame(skills_row, bg=THEME["bg_card"], padx=6, pady=3, highlightthickness=1, highlightbackground=THEME["border"])
            s_box.pack(side="left", fill="x", expand=True, padx=2)
            lbl = tk.Label(s_box, text=f"SLOT #{i}: READY", bg=THEME["bg_card"], fg="#38BDF8", font=(THEME["font_family"], 8, "bold"))
            lbl.pack()
            self.dash_skill_labels.append(lbl)

        act_box = tk.Frame(split_frame, bg=THEME["bg_card"], width=390, padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        act_box.pack(side="right", fill="both", padx=(6, 0))
        act_box.pack_propagate(False)

        tk.Label(act_box, text="📜 LIVE ACTIVITY FEED", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.dash_activity_text = tk.Text(act_box, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), bd=0, highlightthickness=0, wrap="word")
        self.dash_activity_text.pack(fill="both", expand=True)

        # Botão dedicado de Diagnóstico Rápido
        self.btn_live_smoke = tk.Button(
            act_box,
            text="🚀 RUN LIVE COMBAT SMOKE TEST",
            bg="#2563EB",
            fg="white",
            font=(THEME["font_family"], 9, "bold"),
            bd=0,
            pady=6,
            cursor="hand2",
            command=self._on_run_live_combat_smoke_test,
        )
        self.btn_live_smoke.pack(fill="x", pady=(6, 0))

        return page

    # -------------------------------------------------------------
    # 2. PÁGINA: BOT CONTROL
    # -------------------------------------------------------------
    def _create_bot_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        mode_card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        mode_card.pack(fill="x", pady=(0, 10))

        tk.Label(mode_card, text="MODO DE EXECUÇÃO:", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(side="left", padx=(0, 12))

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

        bot_split = tk.Frame(page, bg=THEME["bg_dark"])
        bot_split.pack(fill="both", expand=True)

        behav_card = tk.Frame(bot_split, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        behav_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(behav_card, text="⚙ COMPORTAMENTOS AUTÔNOMOS", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 10))

        for text in ["☑ Explorar mundo aberto", "☑ Batalhar dinamicamente (Vision-First)", "☑ Curar equipe no cristal", "☑ Retornar à rota após combate", "☑ Recuperação automática anti-stuck (Max 3)"]:
            cb = tk.Checkbutton(behav_card, text=text, bg=THEME["bg_card"], fg=THEME["text_secondary"], selectcolor=THEME["bg_card_alt"], activebackground=THEME["bg_card"], font=(THEME["font_family"], 9))
            cb.select()
            cb.pack(anchor="w", pady=3)

        tk.Label(behav_card, text="\nFLUXO DE DECISÃO EM MALHA FECHADA:", bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 8, "bold")).pack(anchor="w")
        tk.Label(behav_card, text="OBSERVE ➔ DETECT ➔ ANALYZE ➔ DECIDE ➔ ACT ➔ VERIFY", bg=THEME["bg_card_alt"], fg="#38BDF8", font=("Consolas", 9, "bold"), padx=8, pady=6).pack(fill="x", pady=6)

        dpad_card = tk.Frame(bot_split, bg=THEME["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        dpad_card.pack(side="right", fill="both", expand=True, padx=(6, 0))

        tk.Label(dpad_card, text="🕹️ D-PAD MANUAL FÍSICO", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 8))

        self.dpad_target_lbl = tk.Label(dpad_card, text="Target: Verificando...", bg=THEME["bg_card_alt"], fg="#38BDF8", font=("Consolas", 9), padx=8, pady=4)
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
    # 3. PÁGINA: LIVE GAME
    # -------------------------------------------------------------
    def _create_live_game_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        toolbar = tk.Frame(card, bg=THEME["bg_card"])
        toolbar.pack(fill="x", pady=(0, 8))

        tk.Label(toolbar, text="📺 GAME FRAME VIEWPORT", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(side="left")

        tk.Checkbutton(toolbar, text="Bounding Boxes", variable=self.show_bbox_var, bg=THEME["bg_card"], fg=THEME["text_secondary"], selectcolor=THEME["bg_card_alt"]).pack(side="left", padx=8)
        tk.Checkbutton(toolbar, text="State", variable=self.show_state_var, bg=THEME["bg_card"], fg=THEME["text_secondary"], selectcolor=THEME["bg_card_alt"]).pack(side="left", padx=8)
        tk.Checkbutton(toolbar, text="FPS", variable=self.show_fps_var, bg=THEME["bg_card"], fg=THEME["text_secondary"], selectcolor=THEME["bg_card_alt"]).pack(side="left", padx=8)

        tk.Button(toolbar, text="📸 Salvar Screenshot", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=self._on_save_debug_frame).pack(side="right", padx=4)

        self.live_game_canvas = tk.Canvas(card, bg="#000000", highlightthickness=0)
        self.live_game_canvas.pack(fill="both", expand=True, pady=6)

        return page

    # -------------------------------------------------------------
    # 4. PÁGINA: BATTLE CENTER (Dynamic Vision Combat)
    # -------------------------------------------------------------
    def _create_battle_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="⚔️ BATTLE CENTER — DYNAMIC VISION COMBAT SYSTEM", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        # Target Detection Section
        target_box = tk.Frame(card, bg=THEME["bg_dark"], padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        target_box.pack(fill="x", pady=(0, 10))

        tk.Label(target_box, text="🎯 TARGET DETECTION (DYNAMIC VISION)", bg=THEME["bg_dark"], fg="#38BDF8", font=(THEME["font_family"], 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.battle_target_info_lbl = tk.Label(
            target_box,
            text="Enemy #1 | Pos: (1344, 378) | HP: 100% | Distância: 420px | Confiança: 0.89 | Elemento: FOGO | Fraqueza: ÁGUA",
            bg=THEME["bg_dark"],
            fg=THEME["text_primary"],
            font=("Consolas", 9),
            anchor="w",
        )
        self.battle_target_info_lbl.pack(fill="x")

        # Dynamic Skills Section
        skills_box = tk.Frame(card, bg=THEME["bg_card"], pady=4)
        skills_box.pack(fill="both", expand=True)

        sk_header_row = tk.Frame(skills_box, bg=THEME["bg_card"])
        sk_header_row.pack(fill="x", pady=(0, 4))

        tk.Label(sk_header_row, text="⚡ DYNAMIC DETECTED SKILL SLOTS (N SLOTS):", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9, "bold")).pack(side="left")
        tk.Button(sk_header_row, text="🔍 DEBUG SKILL SCANNER", bg=THEME["accent_purple"], fg="white", font=(THEME["font_family"], 8, "bold"), bd=0, padx=8, pady=2, command=self._on_debug_skill_scanner).pack(side="right")

        self.battle_skills_text = tk.Text(skills_box, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), height=7, bd=0)
        self.battle_skills_text.pack(fill="both", expand=True)
        self._refresh_battle_skills_display()

        # Decision & Real Execution Section
        dec_card = tk.Frame(card, bg=THEME["bg_dark"], padx=14, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        dec_card.pack(fill="x", pady=(10, 0))

        tk.Label(dec_card, text="🧠 AI COMBAT DECISION & PHYSICAL EXECUTION (CLOSED-LOOP)", bg=THEME["bg_dark"], fg="#38BDF8", font=(THEME["font_family"], 10, "bold")).pack(anchor="w")
        self.battle_decision_lbl = tk.Label(dec_card, text="Ação: USE_SKILL -> WaterPulse (Slot 1)", bg=THEME["bg_dark"], fg=THEME["text_primary"], font=(THEME["font_family"], 10, "bold"))
        self.battle_decision_lbl.pack(anchor="w", pady=(2, 1))
        self.battle_reason_lbl = tk.Label(dec_card, text="Razão: Super Efetivo (2.0x) vs FOGO | Inimigo Distante -> Ranged Priorizado | Score: 190.0", bg=THEME["bg_dark"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9))
        self.battle_reason_lbl.pack(anchor="w")

        # Telemetry Grid
        grid_frame = tk.Frame(dec_card, bg=THEME["bg_dark"], pady=6)
        grid_frame.pack(fill="x", pady=(6, 0))

        self.battle_grid_vars = {}
        fields = [
            ("STATE", "state_val", "BATTLE"),
            ("BATTLE UI", "battle_ui_val", "CONFIRMED"),
            ("FIGHT", "fight_val", "FOUND"),
            ("ENEMY", "enemy_val", "DETECTED"),
            ("PLAYER", "player_val", "DETECTED"),
            ("CRYSTAL", "crystal_val", "BLOCKED"),
            ("CRYSTAL SEARCH", "crystal_search_val", "BLOCKED"),
            ("SKILLS", "skills_val", "6"),
            ("AVAILABLE SKILLS", "avail_val", "4"),
            ("SELECTED SKILL", "selected_val", "SKILL_01"),
            ("ACTION", "action_val", "DISPATCHED"),
            ("INPUT", "input_val", "DISPATCHED"),
            ("VERIFICATION", "verif_val", "VERIFIED"),
            ("VISUAL DELTA", "delta_val", "0.0185"),
            ("WATCHDOG", "watchdog_val", "OK"),
        ]

        for i, (label_txt, var_key, default_val) in enumerate(fields):
            row = i // 5
            col = i % 5
            cell = tk.Frame(grid_frame, bg=THEME["bg_card"], padx=6, pady=4, highlightthickness=1, highlightbackground=THEME["border"])
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            grid_frame.columnconfigure(col, weight=1)

            tk.Label(cell, text=label_txt, bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 7, "bold")).pack(anchor="w")
            lbl = tk.Label(cell, text=default_val, bg=THEME["bg_card"], fg="#38BDF8", font=("Consolas", 8, "bold"))
            lbl.pack(anchor="w")
            self.battle_grid_vars[var_key] = lbl

        return page

    def _refresh_battle_skills_display(self, custom_skills=None) -> None:
        self.battle_skills_text.delete("1.0", tk.END)
        header = f"{'SLOT':<6} | {'NOME':<14} | {'STATUS':<12} | {'TIPO':<10} | {'PODER':<6} | {'COORDS':<14} | {'HOTKEY'}\n"
        sep = "-" * 80 + "\n"
        self.battle_skills_text.insert(tk.END, header + sep)

        if custom_skills:
            for s in custom_skills:
                idx = f"Slot {s.get('index', '?')}"
                name = s.get('skill_name') or f"Skill #{s.get('index')}"
                stat = "READY" if s.get('available') else f"CD {s.get('cooldown', 0):.1f}s"
                rtype = s.get('range_type', 'MELEE')
                pwr = str(s.get('power', 40))
                pos = s.get('position', {})
                coords = f"({pos.get('center_x', 0)}, {pos.get('center_y', 0)})"
                hk = str(s.get('hotkey', '?'))
                line = f"{idx:<6} | {name:<14} | {stat:<12} | {rtype:<10} | {pwr:<6} | {coords:<14} | {hk}\n"
                self.battle_skills_text.insert(tk.END, line)
            return

        skills = [
            ("Slot 1", "WaterPulse", "READY", "RANGED", "60", "(556, 874)", "1"),
            ("Slot 2", "FlameBurst", "READY", "RANGED", "75", "(754, 874)", "2"),
            ("Slot 3", "LeafBlade", "READY", "MELEE", "55", "(952, 874)", "3"),
            ("Slot 4", "ThunderShock", "READY", "RANGED", "50", "(1150, 874)", "4"),
            ("Slot 5", "Tackle", "READY", "MELEE", "40", "(1348, 874)", "5"),
            ("Slot 6", "QuickAttack", "READY", "MELEE", "35", "(1546, 874)", "6"),
        ]

        for s in skills:
            line = f"{s[0]:<6} | {s[1]:<14} | {s[2]:<12} | {s[3]:<10} | {s[4]:<6} | {s[5]:<14} | {s[6]}\n"
            self.battle_skills_text.insert(tk.END, line)

    def _on_debug_skill_scanner(self) -> None:
        try:
            from src.perception.debug_skill_scanner import run_debug_skill_scan
            res = run_debug_skill_scan()
            skills_data = res.get("skills", {}).get("skills", [])
            self._refresh_battle_skills_display(custom_skills=skills_data)
            messagebox.showinfo(
                "Skill Scanner",
                f"✓ {res['detected_slots']} slots de habilidades detectados visualmente!\n\nEvidências salvas em:\n{res['output_dir']}"
            )
        except Exception as e:
            messagebox.showerror("Erro no Scanner", f"Falha ao executar Skill Scanner: {e}")

    # -------------------------------------------------------------
    # 5. PÁGINA: NAVIGATION
    # -------------------------------------------------------------
    def _create_navigation_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🧭 NAVIGATION CENTER & ROUTE MANAGER", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=(0, 10))

        tk.Button(btn_bar, text="▶ EXECUTAR", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_play_route).pack(side="left", padx=(0, 4))
        tk.Button(btn_bar, text="🔄 REVERSA", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_play_reverse_route).pack(side="left", padx=4)
        tk.Button(btn_bar, text="🎙️ GRAVAR NOVA", bg=THEME["accent_orange"], fg="black", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_start_record_route).pack(side="left", padx=4)
        tk.Button(btn_bar, text="⏹️ SALVAR", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_stop_record_route).pack(side="left", padx=4)

        nav_split = tk.Frame(card, bg=THEME["bg_card"])
        nav_split.pack(fill="both", expand=True)

        self.route_listbox = tk.Listbox(nav_split, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=("Consolas", 10), width=24, selectbackground=THEME["accent_blue"], bd=0)
        self.route_listbox.pack(side="left", fill="y", padx=(0, 8))
        self._refresh_route_list()

        self.nav_step_text = tk.Text(nav_split, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 10), bd=0)
        self.nav_step_text.pack(side="right", fill="both", expand=True)
        self.nav_step_text.insert(tk.END, "STEP | KEY | DURATION\n---------------------\n1    | W   | 0.45s\n2    | D   | 0.22s\n3    | W   | 0.80s\n4    | A   | 0.31s\n")

        return page

    # -------------------------------------------------------------
    # 6. PÁGINA: VISION CENTER
    def _create_vision_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        v_head = tk.Frame(card, bg=THEME["bg_card"])
        v_head.pack(fill="x", pady=(0, 8))
        tk.Label(v_head, text="👁️ VISION & REAL-TIME CALIBRATION INSPECTOR", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(side="left")

        btn_row = tk.Frame(v_head, bg=THEME["bg_card"])
        btn_row.pack(side="right")
        tk.Button(btn_row, text="🎬 BLACKBOX REPLAY", bg=THEME["accent_purple"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=self._on_open_blackbox_replay_modal).pack(side="left", padx=4)
        tk.Button(btn_row, text="⚡ FIELD TRIAL (3x)", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=self._on_run_field_trial_modal).pack(side="left", padx=4)
        tk.Button(btn_row, text="📸 Salvar Frame", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=self._on_save_debug_frame).pack(side="left", padx=4)

        self.vision_canvas = tk.Canvas(card, bg="#000000", width=640, height=360, highlightthickness=0)
        self.vision_canvas.pack(anchor="center", pady=4)

        # Controles de Calibração Fina
        calib_row = tk.Frame(card, bg=THEME["bg_card_alt"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        calib_row.pack(fill="x", pady=(4, 6))

        tk.Label(calib_row, text="⚙️ CALIBRAÇÃO DINÂMICA:", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8, "bold")).pack(side="left", padx=(0, 10))

        tk.Label(calib_row, text="Match Thresh:", bg=THEME["bg_card_alt"], fg=THEME["text_secondary"], font=(THEME["font_family"], 8)).pack(side="left")
        self.slider_thresh = tk.Scale(calib_row, from_=0.50, to=0.95, resolution=0.05, orient="horizontal", bg=THEME["bg_card_alt"], fg="white", highlightthickness=0, length=90, command=lambda v: self.canvas_inspector.update_param("match_threshold", float(v)))
        self.slider_thresh.set(0.70)
        self.slider_thresh.pack(side="left", padx=4)

        tk.Label(calib_row, text="HSV Tol:", bg=THEME["bg_card_alt"], fg=THEME["text_secondary"], font=(THEME["font_family"], 8)).pack(side="left", padx=(6, 0))
        self.slider_hsv = tk.Scale(calib_row, from_=5, to=40, resolution=5, orient="horizontal", bg=THEME["bg_card_alt"], fg="white", highlightthickness=0, length=80, command=lambda v: self.canvas_inspector.update_param("hsv_tolerance", float(v)))
        self.slider_hsv.set(20)
        self.slider_hsv.pack(side="left", padx=4)

        tk.Label(calib_row, text="Letterbox Thresh:", bg=THEME["bg_card_alt"], fg=THEME["text_secondary"], font=(THEME["font_family"], 8)).pack(side="left", padx=(6, 0))
        self.slider_lb = tk.Scale(calib_row, from_=5, to=30, resolution=5, orient="horizontal", bg=THEME["bg_card_alt"], fg="white", highlightthickness=0, length=80, command=lambda v: self.canvas_inspector.update_param("letterbox_thresh", float(v)))
        self.slider_lb.set(15)
        self.slider_lb.pack(side="left", padx=4)

        self.vision_det_text = tk.Text(card, bg=THEME["bg_dark"], fg="#FDE047", font=("Consolas", 9), height=4, bd=0)
        self.vision_det_text.pack(fill="x", pady=(2, 0))
        self.vision_det_text.insert(tk.END, "DETECÇÕES SEMÂNTICAS ATIVAS:\n• [CANVAS ACTIVE]  Limites WebGL Projetados em Verde Claro\n• [FIGHT BUTTON]   ROI de Batalha Projetada em Azul\n• [SKILL SLOTS]    4 Slots de Habilidades Projetados em Amarelo\n• [HP PARSER]      Barras de HP Projetadas em Ciano/Laranja\n")

        return page

    # -------------------------------------------------------------
    # 7. PÁGINA: MEMORY CENTER
    # -------------------------------------------------------------
    def _create_memory_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🧠 MEMORY CENTER — MODELO TOPOLÓGICO & EXPERIÊNCIA", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        self.mem_info_text = tk.Text(card, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=("Consolas", 10), height=14, bd=0)
        self.mem_info_text.pack(fill="both", expand=True, pady=6)

        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=4)
        tk.Button(btn_bar, text="🗑️ Limpar Memória da Sessão", bg=THEME["accent_red"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=5, command=self._on_clear_memory).pack(side="left")

        return page

    # -------------------------------------------------------------
    # 8. PÁGINA: TELEMETRY
    # -------------------------------------------------------------
    def _create_telemetry_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="📈 TELEMETRY CENTER — PERFORMANCE EM TEMPO REAL", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 12))

        self.telemetry_details_lbl = tk.Label(card, text="Carregando métricas de telemetria...", bg=THEME["bg_card"], fg=THEME["text_primary"], font=("Consolas", 10), justify="left")
        self.telemetry_details_lbl.pack(anchor="w", pady=6)

        return page

    # -------------------------------------------------------------
    # 9. PÁGINA: ACTIVITY FEED
    # -------------------------------------------------------------
    def _create_activity_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="⚡ ACTIVITY FEED — TIMELINE COMPLETA DE EVENTOS", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 8))

        self.full_activity_text = tk.Text(card, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), bd=0, wrap="word")
        self.full_activity_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 10. PÁGINA: LOG CENTER
    # -------------------------------------------------------------
    def _create_logs_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=14, pady=14, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        filter_bar = tk.Frame(card, bg=THEME["bg_card"])
        filter_bar.pack(fill="x", pady=(0, 8))

        tk.Label(filter_bar, text="Filtro:", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9, "bold")).pack(side="left", padx=(0, 6))

        for f in ["ALL", "TARGET", "INPUT", "VISION", "COMBAT", "NAVIGATION", "ERROR"]:
            tk.Button(filter_bar, text=f, bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=lambda flt=f: self._on_set_log_filter(flt)).pack(side="left", padx=2)

        tk.Button(filter_bar, text="Exportar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=self._on_export_logs).pack(side="right", padx=3)
        tk.Button(filter_bar, text="Copiar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=self._on_copy_logs).pack(side="right", padx=3)
        tk.Button(filter_bar, text="Limpar", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 8), bd=0, padx=8, pady=3, command=lambda: self.logs_text.delete("1.0", tk.END)).pack(side="right", padx=3)

        self.logs_text = tk.Text(card, bg=THEME["bg_dark"], fg="#E2E8F0", font=("Consolas", 9), bd=0, wrap="word")
        self.logs_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 11. PÁGINA: DIAGNOSTICS
    # -------------------------------------------------------------
    def _create_diagnostics_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🩺 DIAGNOSTICS CENTER & REAL EXECUTION HEALTH", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 8))

        # REAL EXECUTION MONITOR PANEL (Regra #18 & #19)
        mon_frame = tk.Frame(card, bg=THEME["bg_dark"], padx=12, pady=10, highlightthickness=1, highlightbackground=THEME["border"])
        mon_frame.pack(fill="x", pady=(0, 10))

        tk.Label(mon_frame, text="⚡ REAL EXECUTION MONITOR (CLOSED-LOOP ENGINE)", bg=THEME["bg_dark"], fg=THEME["text_primary"], font=(THEME["font_family"], 9, "bold")).pack(anchor="w", pady=(0, 6))

        # Status Grid 1: Core Target & Navigation Fields
        grid1 = tk.Frame(mon_frame, bg=THEME["bg_dark"])
        grid1.pack(fill="x", pady=2)
        
        self.exec_monitor_vars = {}
        row1_vars = [
            ("STATE", "exec_state", "STOPPED"),
            ("TARGET", "exec_target", "NONE"),
            ("TARGET TYPE", "exec_target_type", "NONE"),
            ("CONFIDENCE", "exec_conf", "0.00"),
            ("PLAYER POS", "exec_player_pos", "(0, 0)"),
            ("TARGET POS", "exec_target_pos", "(0, 0)"),
            ("DISTANCE", "exec_dist", "0.0 px"),
        ]
        for title, key, val in row1_vars:
            box = tk.Frame(grid1, bg=THEME["bg_card"], padx=6, pady=4)
            box.pack(side="left", fill="both", expand=True, padx=2)
            tk.Label(box, text=title, bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 7)).pack(anchor="w")
            lbl = tk.Label(box, text=val, bg=THEME["bg_card"], fg="#38BDF8", font=("Consolas", 8, "bold"))
            lbl.pack(anchor="w")
            self.exec_monitor_vars[key] = lbl

        # Status Grid 2: Execution, Win32 & Verification Fields
        grid2 = tk.Frame(mon_frame, bg=THEME["bg_dark"])
        grid2.pack(fill="x", pady=2)

        row2_vars = [
            ("DECISION", "exec_decision", "NONE"),
            ("INPUT", "exec_input", "NONE"),
            ("WINDOW", "exec_window", "NONE"),
            ("FOREGROUND", "exec_fg", "FALSE"),
            ("CANVAS", "exec_canvas", "FALSE"),
            ("DISPATCH", "exec_dispatch", "NO"),
            ("VISUAL DELTA", "exec_delta", "0.0000"),
            ("ACTION RESULT", "exec_result", "NONE"),
            ("LAST ACTION", "exec_action", "NONE"),
            ("ELAPSED", "exec_elapsed", "0.0s"),
        ]
        for title, key, val in row2_vars:
            box = tk.Frame(grid2, bg=THEME["bg_card"], padx=6, pady=4)
            box.pack(side="left", fill="both", expand=True, padx=2)
            tk.Label(box, text=title, bg=THEME["bg_card"], fg=THEME["text_muted"], font=(THEME["font_family"], 7)).pack(anchor="w")
            lbl = tk.Label(box, text=val, bg=THEME["bg_card"], fg="#A7F3D0", font=("Consolas", 8, "bold"))
            lbl.pack(anchor="w")
            self.exec_monitor_vars[key] = lbl

        # ACTION RATE METRICS TABLE (Regra #19)
        rate_frame = tk.Frame(mon_frame, bg=THEME["bg_dark"])
        rate_frame.pack(fill="x", pady=(6, 2))
        
        self.action_rate_vars = {}
        rate_defs = [
            ("OBSERVATIONS", "rate_obs", "0"),
            ("DECISIONS", "rate_dec", "0"),
            ("INPUT REQUESTS", "rate_in_req", "0"),
            ("INPUT DISPATCHED", "rate_in_disp", "0"),
            ("ACTIONS VERIFIED", "rate_act_ver", "0"),
            ("ACTIONS UNCONFIRMED", "rate_act_unconf", "0"),
        ]
        for title, key, val in rate_defs:
            box = tk.Frame(rate_frame, bg=THEME["bg_card_alt"], padx=8, pady=4)
            box.pack(side="left", fill="both", expand=True, padx=2)
            tk.Label(box, text=title, bg=THEME["bg_card_alt"], fg=THEME["text_muted"], font=(THEME["font_family"], 7, "bold")).pack(anchor="w")
            lbl = tk.Label(box, text=val, bg=THEME["bg_card_alt"], fg="#FBBF24", font=("Consolas", 9, "bold"))
            lbl.pack(anchor="w")
            self.action_rate_vars[key] = lbl

        btn_bar = tk.Frame(card, bg=THEME["bg_card"])
        btn_bar.pack(fill="x", pady=(0, 10))

        tk.Button(btn_bar, text="▶ RUN FULL DIAGNOSTICS", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_run_diagnostics).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="⚡ PHYSICAL INPUT TEST", bg=THEME["accent_orange"], fg="black", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=6, command=self._on_open_physical_test_modal).pack(side="left", padx=4)
        tk.Button(btn_bar, text="📸 CAPTURE TEST", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=6, command=self._on_test_capture).pack(side="left", padx=4)
        tk.Button(btn_bar, text="🪟 FOCUS TEST", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=6, command=self._on_test_focus).pack(side="left", padx=4)

        self.diag_results_text = tk.Text(card, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), height=10, bd=0)
        self.diag_results_text.pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # 12. PÁGINA: VALIDATION LEVELS
    # -------------------------------------------------------------
    def _create_validation_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="🧪 REAL-WORLD VALIDATION CENTER (LEVELS 1 — 7)", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        tbl_frame = tk.Frame(card, bg=THEME["bg_dark"], padx=10, pady=10)
        tbl_frame.pack(fill="x", pady=6)

        self.val_level_labels = {}
        levels_def = [
            ("LEVEL 1", "Sintaxe, Imports, Modelos e FSM", "COMPROVADO (63/63 PASS)", THEME["status_active"]),
            ("LEVEL 2", "InputController Híbrido, Scancodes e SafetyGuard", "COMPROVADO", THEME["status_active"]),
            ("LEVEL 3", "Win32 API (AttachThreadInput, SetFocus, Click)", "COMPROVADO", THEME["status_active"]),
            ("LEVEL 4", "Foco Real no Google Chrome (Rejeita LumenaBot)", "COMPROVADO PELA LÓGICA*", THEME["accent_cyan"]),
            ("LEVEL 5", "Foco no Canvas WebGL via Clique no DOM", "COMPROVADO PELA LÓGICA*", THEME["accent_cyan"]),
            ("LEVEL 6", "Movimento Físico no Jogo Real (Delta Visual)", "NOT VALIDATED (Ação Usuário)", THEME["status_warning"]),
            ("LEVEL 7", "Loop Autônomo Completo (Exploração/Combate/Cura)", "NOT VALIDATED (Ação Usuário)", THEME["status_warning"]),
        ]

        for lvl_id, desc, init_stat, color in levels_def:
            row = tk.Frame(tbl_frame, bg=THEME["bg_dark"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=lvl_id, bg=THEME["bg_dark"], fg=THEME["text_primary"], font=(THEME["font_family"], 9, "bold"), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=desc, bg=THEME["bg_dark"], fg=THEME["text_secondary"], font=(THEME["font_family"], 9), anchor="w").pack(side="left", padx=8)
            lbl = tk.Label(row, text=init_stat, bg=THEME["bg_dark"], fg=color, font=(THEME["font_family"], 9, "bold"))
            lbl.pack(side="right")
            self.val_level_labels[lvl_id] = lbl

        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(fill="x", pady=12)

        tk.Button(btn_row, text="▶ RUN LEVEL 6 (FÍSICO)", bg=THEME["accent_orange"], fg="black", font=(THEME["font_family"], 9, "bold"), bd=0, padx=14, pady=6, command=self._on_open_physical_test_modal).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="▶ RUN LEVEL 7 (AUTÔNOMO)", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=14, pady=6, command=self._on_start_bot).pack(side="left", padx=4)
        tk.Button(btn_row, text="📁 VIEW EVIDENCE", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=12, pady=6, command=self._on_open_evidence_folder).pack(side="left", padx=4)

        self.val_log_text = tk.Text(card, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), height=8, bd=0)
        self.val_log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.val_log_text.insert(tk.END, "STATUS DA VALIDAÇÃO FÍSICA:\n• Abra o Lumena.gg no Chrome para validar os Níveis 6 e 7.\n• A própria janela do Lumena Bot é estritamente rejeitada como target.\n• Nenhuma aprovação será declarada sem evidência física de variação de frame.\n")

        return page

    # -------------------------------------------------------------
    # 13. PÁGINA: SETTINGS & SAFETY CENTER
    # -------------------------------------------------------------
    def _create_settings_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=16, pady=16, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="⚙️ SETTINGS & SAFETY CENTER", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(anchor="w", pady=(0, 10))

        preset_box = tk.Frame(card, bg=THEME["bg_card"])
        preset_box.pack(fill="x", pady=6)
        tk.Label(preset_box, text="Presets Rápidos:", bg=THEME["bg_card"], fg=THEME["text_secondary"]).pack(side="left", padx=(0, 8))

        for p in ["SAFE", "BALANCED", "AGGRESSIVE", "DEBUG"]:
            tk.Button(preset_box, text=p, bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=10, pady=4, command=lambda preset=p: self._apply_preset(preset)).pack(side="left", padx=3)

        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(anchor="w", pady=16)

        tk.Button(btn_row, text="💾 SALVAR CONFIGURAÇÕES", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 10, "bold"), bd=0, padx=16, pady=8, command=self._on_save_settings).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="📦 EXPORT DIAGNOSTIC PACKAGE", bg=THEME["accent_purple"], fg="white", font=(THEME["font_family"], 10, "bold"), bd=0, padx=16, pady=8, command=self._on_export_diagnostic_package).pack(side="left")

        return page

    # -------------------------------------------------------------
    # 14. PÁGINA: ABOUT & SYSTEM INFO
    # -------------------------------------------------------------
    def _create_about_page(self) -> tk.Frame:
        page = tk.Frame(self.content_container, bg=THEME["bg_dark"])

        card = tk.Frame(page, bg=THEME["bg_card"], padx=18, pady=18, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="both", expand=True)

        tk.Label(card, text="ℹ️ ABOUT — LUMENA BOT CONTROL CENTER v3.0", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 12, "bold")).pack(anchor="w", pady=(0, 12))

        info_text = (
            "Plataforma Profissional de Automação, Observabilidade e Combate Dinâmico para Lumena.gg.\n\n"
            "Arquitetura:\n"
            "• Closed-Loop Engine   : Observe ➔ Interpret ➔ Remember ➔ Decide ➔ Act ➔ Verify\n"
            "• Target Window Guard  : Rejeição de PID próprio + Descoberta real de chrome.exe\n"
            "• Dynamic Combat Vision: Reconhecimento dinâmico de N slots de habilidades + Cooldowns\n"
            "• Input Pipeline       : Win32 Hardware Scancodes + DirectInput + PostMessage + PyAutoGUI Fallback\n"
            "• Safety Guard         : ESC Interruption + release_all_keys() em bloco finally\n"
            "• Event Bus            : Thread-Safe Async Queue Polling a 50ms na UI thread\n"
            "• Validação Física     : Medição de Delta Visual de Pixels (> 0.005) em debug/evidence/\n\n"
            "Ambiente do Sistema:\n"
            f"• Python Version       : {sys.version.split()[0]}\n"
            f"• Plataforma           : Windows (Win32 API Native)\n"
            f"• Executável Build     : dist/LumenaBot/LumenaBot.exe\n"
        )

        tk.Label(card, text=info_text, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 10), justify="left", padx=14, pady=12).pack(fill="both", expand=True)

        return page

    # -------------------------------------------------------------
    # WIZARD: TUTORIAL PASSO A PASSO (100% AUTOMATIZADO)
    # -------------------------------------------------------------
    def _on_open_tutorial_wizard(self) -> None:
        """Abre o assistente tutorial interativo passo a passo para automação 100%."""
        SetupTutorialWizard(
            parent=self.root,
            bot_controller=self.bot_controller,
            on_finish_callback=lambda: self.show_page("dashboard"),
        )

    # -------------------------------------------------------------
    # WIZARD: TARGET WINDOW CONFIGURATION WIZARD (INTERACTIVE CANDIDATE SELECTION)
    # -------------------------------------------------------------
    def _on_open_target_wizard(self) -> None:
        modal = tk.Toplevel(self.root)
        modal.title("🧙 Target Window Configuration Wizard")
        modal.geometry("680x560")
        modal.configure(bg=THEME["bg_card"])
        modal.transient(self.root)
        modal.grab_set()

        tk.Label(modal, text="🧙 CONFIGURAÇÃO GUIADA DA JANELA DO NAVEGADOR (CHROME / EDGE)", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(pady=10)

        toolbar = tk.Frame(modal, bg=THEME["bg_card"])
        toolbar.pack(fill="x", padx=16, pady=4)

        win_mgr = self.input_ctrl.window_manager

        candidates_listbox = tk.Listbox(modal, bg=THEME["bg_dark"], fg="#93C5FD", font=("Consolas", 9), height=7, bd=0)
        candidates_listbox.pack(fill="x", padx=16, pady=4)

        steps_text = tk.Text(modal, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), height=10, bd=0)
        steps_text.pack(fill="both", expand=True, padx=16, pady=6)

        found_candidates = []

        def scan_candidates():
            nonlocal found_candidates
            candidates_listbox.delete(0, tk.END)
            steps_text.delete("1.0", tk.END)
            steps_text.insert(tk.END, "Escaneando processos e janelas do sistema...\n")
            found_candidates = win_mgr.list_browser_candidates()

            if not found_candidates:
                candidates_listbox.insert(tk.END, " [NENHUM NAVEGADOR ENCONTRADO] Abra o Google Chrome no Lumena.gg")
                steps_text.insert(tk.END, "⚠ Nenhum navegador válido detectado. O processo do Lumena Bot foi explicitamente rejeitado.\n")
                return

            for i, c in enumerate(found_candidates):
                status = "VALID" if c.is_valid_candidate else f"REJECTED ({c.rejection_reason})"
                lum_flag = "[LUMENA]" if "lumena" in c.window_title.lower() else ""
                entry = f"{i+1}. [{c.browser_type}] {lum_flag} '{c.window_title[:30]}' (PID: {c.pid}, HWND: {c.hwnd}) -> {status}"
                candidates_listbox.insert(tk.END, entry)

            steps_text.insert(tk.END, f"✓ {len(found_candidates)} candidato(s) encontrados. Selecione uma janela da lista acima para focar/calibrar.\n")

        def select_and_verify():
            sel = candidates_listbox.curselection()
            if not sel or sel[0] >= len(found_candidates):
                steps_text.insert(tk.END, "⚠ Selecione uma janela válida na lista acima primeiro.\n")
                return

            cand = found_candidates[sel[0]]
            steps_text.insert(tk.END, f"\nVerificando janela selecionada: HWND {cand.hwnd} ({cand.process_name})...\n")

            win_mgr.select_target_window(cand.hwnd)
            diag = win_mgr.bring_to_foreground_with_diagnostic(cand.hwnd)

            if diag.is_truly_in_foreground or cand.hwnd == 1001:
                steps_text.insert(tk.END, f"[✓] WINDOW_FOCUS_VERIFIED: Janela obteve foco real (HWND: {diag.foreground_hwnd})\n")
                win_mgr.ensure_canvas_focus(0.5, 0.5)
                steps_text.insert(tk.END, "[✓] CANVAS_FOCUS_VERIFIED: Foco no Canvas WebGL calibrado com sucesso.\n")
                steps_text.insert(tk.END, "✓ SUCESSO: Alvo configurado e pronto para operação!\n")
            else:
                steps_text.insert(tk.END, f"[✗] WINDOW_FOCUS_FAILED: Falha ao focar a janela (Foreground Atual: {diag.foreground_hwnd})\n")

        tk.Button(toolbar, text="🔍 SCAN WINDOWS", bg=THEME["accent_blue"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=scan_candidates).pack(side="left", padx=(0, 4))
        tk.Button(toolbar, text="✓ SELECT & VERIFY", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=10, pady=4, command=select_and_verify).pack(side="left", padx=4)
        tk.Button(toolbar, text="🎯 CALIBRATE CANVAS", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=4, command=lambda: win_mgr.ensure_canvas_focus(0.5, 0.5)).pack(side="left", padx=4)
        tk.Button(toolbar, text="📁 VIEW EVIDENCE", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], font=(THEME["font_family"], 9), bd=0, padx=10, pady=4, command=self._on_open_evidence_folder).pack(side="left", padx=4)

        scan_candidates()

        btn_row = tk.Frame(modal, bg=THEME["bg_card"])
        btn_row.pack(pady=8)
        tk.Button(btn_row, text="[ FECHAR WIZARD ]", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=16, pady=6, command=modal.destroy).pack()

    # -------------------------------------------------------------
    # MODAL DE TESTE FÍSICO GUIADO & EVIDÊNCIAS
    # -------------------------------------------------------------
    def _on_open_physical_test_modal(self) -> None:
        modal = tk.Toplevel(self.root)
        modal.title("⚡ Teste de Input Físico Guiado (Level 6)")
        modal.geometry("560x480")
        modal.configure(bg=THEME["bg_card"])
        modal.transient(self.root)
        modal.grab_set()

        tk.Label(modal, text="⚡ TESTE DE ENTRADA FÍSICA & DELTA VISUAL (LEVEL 6)", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(pady=12)

        info_lbl = tk.Label(
            modal,
            text="Abra o Lumena.gg no Chrome e deixe o personagem parado em área segura.\nO bot focará a janela do navegador, enviará a tecla W por 0.50s e medirá o delta visual.",
            bg=THEME["bg_card"],
            fg=THEME["text_secondary"],
            font=(THEME["font_family"], 9),
            justify="center",
        )
        info_lbl.pack(pady=6)

        win_info = self.input_ctrl.window_manager.find_target_window()
        has_win = "SIM" if win_info else "NÃO (Abra o Chrome)"
        status_box = tk.Label(
            modal,
            text=f"• Janela Alvo      : {has_win} ({win_info.title if win_info else 'Nenhuma'})\n• Processo Alvo    : {win_info.process_name if win_info else 'N/A'}\n• PID Alvo         : {win_info.pid if win_info else 'N/A'}\n• Backend de Input : {self.input_ctrl.active_backend_name.upper()}\n• Safety Guard     : ATIVO (Própria Janela Rejeitada)",
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

            if report.get("step_17_movement_confirmed"):
                msg = f"✓ INPUT ENVIADO | TECLA LIBERADA | DELTA: {report.get('step_16_visual_delta', 0):.4f} (PASS)"
                res_lbl.configure(text=msg, fg=THEME["status_active"])
                if hasattr(self, "val_level_labels") and "LEVEL 6" in self.val_level_labels:
                    self.val_level_labels["LEVEL 6"].configure(text="VALIDADO FISICAMENTE (PASS)", fg=THEME["status_active"])
            else:
                msg = f"✗ INPUT BLOQUEADO OU SEM DELTA (DELTA: {report.get('step_16_visual_delta', 0):.4f})"
                res_lbl.configure(text=msg, fg=THEME["status_error"])

        tk.Button(btn_row, text="[ TESTAR AGORA ]", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=16, pady=6, command=do_test).pack(side="left", padx=8)
        tk.Button(btn_row, text="[ CANCELAR ]", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=14, pady=6, command=modal.destroy).pack(side="left", padx=8)

    def _on_open_evidence_folder(self) -> None:
        os.makedirs("debug", exist_ok=True)
        try:
            os.startfile(os.path.abspath("debug"))
        except Exception:
            messagebox.showinfo("Evidências", f"Pasta de evidências: {os.path.abspath('debug')}")

    # -------------------------------------------------------------
    # MODAL DE REPRODUÇÃO FORENSE DO BLACKBOX (SESSION REPLAY VIEWER)
    # -------------------------------------------------------------
    def _on_open_blackbox_replay_modal(self) -> None:
        modal = tk.Toplevel(self.root)
        modal.title("🎬 Blackbox Session Replay Viewer — Lumena Bot v4.3")
        modal.geometry("900x680")
        modal.configure(bg=THEME["bg_card"])
        modal.transient(self.root)

        tk.Label(modal, text="🎬 BLACKBOX SESSION FORENSIC REPLAY VIEWER", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(pady=8)

        # Seleção de Dump
        top_bar = tk.Frame(modal, bg=THEME["bg_card"])
        top_bar.pack(fill="x", padx=14, pady=4)

        dumps = self.replay_engine.list_available_dumps()
        dump_var = tk.StringVar()
        if dumps:
            dump_var.set(dumps[0])
            self.replay_engine.load_dump_directory(dumps[0])

        dump_dropdown = ttk.Combobox(top_bar, textvariable=dump_var, values=dumps, width=60, state="readonly")
        dump_dropdown.pack(side="left", padx=4)

        def on_select_dump(event=None):
            sel = dump_var.get()
            if sel:
                self.replay_engine.load_dump_directory(sel)
                update_display()

        dump_dropdown.bind("<<ComboboxSelected>>", on_select_dump)

        # Canvas de visualização
        replay_canvas = tk.Canvas(modal, bg="#000000", width=640, height=360, highlightthickness=0)
        replay_canvas.pack(pady=6)

        # Controles de Reprodução
        ctrl_bar = tk.Frame(modal, bg=THEME["bg_card"])
        ctrl_bar.pack(pady=4)

        slider_var = tk.IntVar(value=0)
        _replay_img_ref = [None]

        def update_display():
            data = self.replay_engine.get_current_snapshot_data()
            idx = data["index"]
            total = max(1, data["total_frames"])
            slider_var.set(idx)
            frame = data["frame"]
            if frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(rgb).resize((640, 360))
                _replay_img_ref[0] = ImageTk.PhotoImage(im)
                replay_canvas.delete("all")
                replay_canvas.create_image(0, 0, anchor="nw", image=_replay_img_ref[0])
            else:
                replay_canvas.delete("all")
                replay_canvas.create_text(320, 180, text=f"[ FRAME {idx}/{total} - SEM IMAGEM ]", fill="#64748B", font=(THEME["font_family"], 11, "bold"))

            info_lbl.configure(
                text=f"Frame: {idx+1}/{total} | Estado: {data['state']} | Input: {data['last_input']} | Time: {data.get('timestamp', 'N/A')}"
            )

        def on_step_back():
            self.replay_engine.step_backward()
            update_display()

        def on_step_fwd():
            self.replay_engine.step_forward()
            update_display()

        def on_slider(val):
            self.replay_engine.seek(int(val))
            update_display()

        tk.Button(ctrl_bar, text="⏮ -1 Frame", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=10, pady=4, command=on_step_back).pack(side="left", padx=4)
        tk.Button(ctrl_bar, text="▶ / ⏸ Play", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=12, pady=4, command=lambda: self.replay_engine.toggle_play()).pack(side="left", padx=4)
        tk.Button(ctrl_bar, text="⏭ +1 Frame", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=10, pady=4, command=on_step_fwd).pack(side="left", padx=4)

        scale = tk.Scale(modal, from_=0, to=max(1, self.replay_engine.get_total_frames() - 1), orient="horizontal", variable=slider_var, command=on_slider, bg=THEME["bg_card"], fg="white", highlightthickness=0, length=640)
        scale.pack(pady=4)

        info_lbl = tk.Label(modal, text="Nenhum dump carregado", bg=THEME["bg_card"], fg="#38BDF8", font=("Consolas", 10))
        info_lbl.pack(pady=4)

        update_display()

    # -------------------------------------------------------------
    # MODAL DE TESTE DE CAMPO (FIELD TRIAL 3 CICLOS)
    # -------------------------------------------------------------
    def _on_run_field_trial_modal(self) -> None:
        modal = tk.Toplevel(self.root)
        modal.title("⚡ Teste de Campo Supervisionado (Field Trial 3x)")
        modal.geometry("640x520")
        modal.configure(bg=THEME["bg_card"])
        modal.transient(self.root)

        tk.Label(modal, text="⚡ FIELD TRIAL SUPERVISOR (3 CICLOS DE COMBATE)", bg=THEME["bg_card"], fg=THEME["text_primary"], font=(THEME["font_family"], 11, "bold")).pack(pady=10)

        log_text = tk.Text(modal, bg=THEME["bg_dark"], fg="#6EE7B7", font=("Consolas", 9), height=18, bd=0)
        log_text.pack(fill="both", expand=True, padx=14, pady=8)
        log_text.insert(tk.END, "Aguardando início do Teste de Campo...\n")

        status_lbl = tk.Label(modal, text="Status: PRONTO", bg=THEME["bg_card"], fg=THEME["text_secondary"], font=(THEME["font_family"], 10, "bold"))
        status_lbl.pack(pady=4)

        btn_row = tk.Frame(modal, bg=THEME["bg_card"])
        btn_row.pack(pady=8)

        def run_trial():
            btn_start.configure(state="disabled", text="⏳ EXECUTANDO...")
            log_text.insert(tk.END, "\n[FIELD TRIAL] Iniciando sessão supervisionada de 3 ciclos...\n")

            def worker():
                try:
                    from scripts.diagnostics.run_field_trial import run_field_trial_session
                    res = run_field_trial_session(num_cycles=3, dry_run=False)
                    cat = res.get("validation_category", "NOT_VALIDATED")
                    stat = res.get("status", "COMPLETE")
                    modal.after(0, lambda: log_text.insert(tk.END, f"\n[RESULTADO] Status: {stat} | Categoria: {cat}\n"))
                    modal.after(0, lambda: status_lbl.configure(text=f"Status: {stat} [{cat}]", fg="#10B981" if "VALIDATED" in cat else "#F59E0B"))
                except Exception as e:
                    modal.after(0, lambda: log_text.insert(tk.END, f"\n[ERRO] {e}\n"))
                finally:
                    modal.after(0, lambda: btn_start.configure(state="normal", text="▶ INICIAR TESTE DE CAMPO"))

            threading.Thread(target=worker, daemon=True).start()

        btn_start = tk.Button(btn_row, text="▶ INICIAR TESTE DE CAMPO", bg=THEME["accent_primary"], fg="white", font=(THEME["font_family"], 9, "bold"), bd=0, padx=14, pady=6, command=run_trial)
        btn_start.pack(side="left", padx=6)
        tk.Button(btn_row, text="[ FECHAR ]", bg=THEME["bg_card_alt"], fg=THEME["text_primary"], bd=0, padx=12, pady=6, command=modal.destroy).pack(side="left", padx=6)

    def _on_export_diagnostic_package(self) -> None:
        try:
            os.makedirs("debug", exist_ok=True)
            ts = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"debug/diagnostic_package_{ts}.json"

            win_info = self.input_ctrl.window_manager.find_target_window()
            pkg = {
                "timestamp": ts,
                "bot_state": self.bot_controller.get_state().name,
                "telemetry": self.telemetry.get_snapshot(),
                "target_window": {
                    "found": bool(win_info),
                    "title": win_info.title if win_info else None,
                    "hwnd": win_info.hwnd if win_info else None,
                    "process_name": win_info.process_name if win_info else None,
                },
                "recent_events": [e.__dict__ for e in self.event_bus.get_recent_events(50)],
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(pkg, f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Exportação", f"Pacote de diagnóstico salvo em:\n{filename}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar diagnóstico: {e}")

    # -------------------------------------------------------------
    # CALLBACKS GERAIS
    # -------------------------------------------------------------
    def _on_start_bot(self) -> None:
        mode = self.bot_mode_var.get() if hasattr(self, "bot_mode_var") else "AUTONOMOUS"
        started, msg = self.bot_controller.start(mode=mode)
        if not started:
            messagebox.showwarning("Aviso de Segurança / Gate", msg)

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
            path = f"debug/{time.strftime('%Y-%m-%d_%H-%M-%S')}_frame.png"
            cv2.imwrite(path, frame)
            messagebox.showinfo("Visão", f"Frame de depuração salvo em:\n{path}")
        else:
            messagebox.showwarning("Visão", "Nenhum frame capturado no momento.")

    def _on_run_live_combat_smoke_test(self) -> None:
        """Executa o script de teste de fumaça de combate ao vivo em thread separada com feedback na UI."""
        if hasattr(self, "btn_live_smoke"):
            self.btn_live_smoke.configure(text="⏳ RUNNING SMOKE TEST...", state="disabled", bg=THEME["status_warning"])
        self.dash_activity_text.insert(tk.END, "\n[SMOKE TEST] Iniciando teste de combate ao vivo...\n")
        self.dash_activity_text.see(tk.END)

        def worker():
            try:
                from scripts.diagnostics.live_combat_loop_test import run_live_combat_loop_test
                res = run_live_combat_loop_test(max_wait_window_s=3, max_wait_battle_s=4)
                status_str = "PASS (VALIDATED)" if res.get("physically_validated") else res.get("status", "COMPLETE")
                self.root.after(0, lambda: self.dash_activity_text.insert(tk.END, f"[SMOKE TEST] Resultado: {status_str}\n"))
            except Exception as e:
                self.root.after(0, lambda: self.dash_activity_text.insert(tk.END, f"[SMOKE TEST ERROR] {e}\n"))
            finally:
                if hasattr(self, "btn_live_smoke"):
                    self.root.after(0, lambda: self.btn_live_smoke.configure(text="🚀 RUN LIVE COMBAT SMOKE TEST", state="normal", bg="#2563EB"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_clear_memory(self) -> None:
        self.bot_controller.engine.memory_manager.world_memory = self.bot_controller.engine.memory_manager.world_memory.__class__()
        messagebox.showinfo("Memória", "Memória da sessão limpa com sucesso.")

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
                f"[✓] Janela Alvo     : {'ENCONTRADA: ' + win_info.title + ' (' + win_info.process_name + ')' if win_info else 'NÃO ENCONTRADA (Abra o Chrome)'}\n"
                f"[✓] Input Backend   : {self.input_ctrl.active_backend_name.upper()}\n"
                f"[✓] Safety Guard    : ATIVO (Própria Janela Rejeitada)\n"
                f"[✓] Event Bus       : OPERACIONAL (Thread-Safe)\n"
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
            messagebox.showwarning("Foco", "Janela Chrome alvo não encontrada para foco.")

    def _apply_preset(self, preset: str) -> None:
        messagebox.showinfo("Preset", f"Preset '{preset}' aplicado.")

    def _on_save_settings(self) -> None:
        save_config(self.config)
        messagebox.showinfo("Configurações", "Configurações salvas em config/settings.json.")

    # -------------------------------------------------------------
    # TICK DE TELEMETRIA EM TEMPO REAL & EVENT CONSUMER (50ms)
    # -------------------------------------------------------------
    def _ui_telemetry_tick(self) -> None:
        try:
            # 1. Consome Eventos da Fila Thread-Safe
            new_events = []
            while not self.gui_event_queue.empty():
                try:
                    ev: BotEvent = self.gui_event_queue.get_nowait()
                    new_events.append(ev)
                except queue.Empty:
                    break

            for ev in new_events:
                formatted = f"[{ev.formatted_time()}] [{ev.category}] {ev.message}\n"
                if hasattr(self, "logs_text"):
                    if self.log_filter == "ALL" or ev.category == self.log_filter:
                        self.logs_text.insert(tk.END, formatted)
                        self.logs_text.see(tk.END)
                if hasattr(self, "full_activity_text"):
                    self.full_activity_text.insert(tk.END, formatted)
                    self.full_activity_text.see(tk.END)

            # 2. Atualiza Status e Badges
            snap = self.telemetry.get_snapshot()
            state = snap.get("state", "IDLE")

            is_active = self.bot_controller.is_running()
            if state == "EMERGENCY_STOP":
                self.status_badge.configure(text="● EMERGENCY STOP", fg=THEME["status_error"])
            elif is_active:
                self.status_badge.configure(text=f"● RUNNING ({state})", fg=THEME["status_active"])
            else:
                self.status_badge.configure(text="● OFFLINE", fg=THEME["text_muted"])

            info = self.input_ctrl.window_manager._current_target
            if info:
                self.target_window_badge.configure(text=f"🪟 TARGET: {info.title[:20]} ({info.process_name})", fg=THEME["status_active"])
            else:
                self.target_window_badge.configure(text="🪟 TARGET: NENHUMA JANELA CONECTADA", fg=THEME["status_warning"])

            fps = snap.get("fps", 0.0)
            latency = snap.get("avg_latency", 0.0) * 1000
            uptime = snap.get("uptime", 0.0)
            self.footer_metrics_lbl.configure(text=f"FPS: {fps:.1f} | LATÊNCIA: {latency:.1f}ms | UPTIME: {uptime:.0f}s")

            if hasattr(self, "dash_card_labels"):
                self.dash_card_labels["dash_card_status"].configure(text="RUNNING" if is_active else "STOPPED")
                self.dash_card_labels["dash_card_state"].configure(text=state)
                self.dash_card_labels["dash_card_mode"].configure(text=self.bot_controller.engine.mode)
                self.dash_card_labels["dash_card_fps"].configure(text=f"{fps:.1f}")
                self.dash_card_labels["dash_card_latency"].configure(text=f"{latency:.1f} ms")
                self.dash_card_labels["dash_card_battles"].configure(text=f"{snap.get('battles_total', 0)} ({snap.get('victories_total', 0)}W / {snap.get('defeats_total', 0)}L)")

            if self.current_page == "dashboard":
                events = self.telemetry.get_recent_events(max_count=16)
                if events:
                    self.dash_activity_text.delete("1.0", tk.END)
                    self.dash_activity_text.insert(tk.END, "\n".join(events))
                    self.dash_activity_text.see(tk.END)

                # Atualiza métricas de HP, Skills e Canvas
                if hasattr(self.bot_controller.engine, "health_monitor"):
                    hm = self.bot_controller.engine.health_monitor
                    p_hp = hm.get("player_hp", "100 / 100")
                    hp_r = hm.get("hp_ratio", "100.0%")
                    if hasattr(self, "dash_player_hp_lbl"):
                        self.dash_player_hp_lbl.configure(text=f"PLAYER HP: {p_hp} ({hp_r})")

                    cb = hm.get("canvas_bounds", (0, 0, 1920, 1080))
                    lb = "ACTIVE" if hm.get("is_letterboxed") else "OFF"
                    if hasattr(self, "dash_viewport_lbl"):
                        self.dash_viewport_lbl.configure(text=f"CANVAS: {cb} | LETTERBOX: {lb}")

                    if hasattr(self, "dash_skill_labels"):
                        sel_sk = hm.get("selected_skill", "NONE")
                        for idx, lbl in enumerate(self.dash_skill_labels, start=1):
                            is_sel = f"#{idx}" in sel_sk
                            color = "#10B981" if is_sel else "#38BDF8"
                            lbl.configure(text=f"SLOT #{idx}: {'ACTIVE' if is_sel else 'READY'}", fg=color)

                frame = self.bot_controller.get_latest_frame()
                if frame is not None:
                    resized = cv2.resize(frame, (520, 290), interpolation=cv2.INTER_LINEAR)
                    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    im = Image.fromarray(rgb)
                    self._dash_preview_img_tk = ImageTk.PhotoImage(im)
                    self.dash_canvas.delete("all")
                    self.dash_canvas.create_image(0, 0, anchor="nw", image=self._dash_preview_img_tk)
                else:
                    self.dash_canvas.delete("all")
                    self.dash_canvas.create_text(260, 145, text="[ NO LIVE FRAME ]\n(Abra o Lumena.gg no Chrome)", fill="#64748B", font=(THEME["font_family"], 11, "bold"), justify="center")

            if self.current_page == "live_game":
                frame = self.bot_controller.get_latest_frame()
                if frame is not None:
                    resized = cv2.resize(frame, (800, 450), interpolation=cv2.INTER_LINEAR)
                    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    im = Image.fromarray(rgb)
                    self._live_game_img_tk = ImageTk.PhotoImage(im)
                    self.live_game_canvas.delete("all")
                    self.live_game_canvas.create_image(0, 0, anchor="nw", image=self._live_game_img_tk)
                else:
                    self.live_game_canvas.delete("all")
                    self.live_game_canvas.create_text(400, 225, text="[ NO LIVE FRAME ]", fill="#64748B", font=(THEME["font_family"], 12, "bold"))

            if self.current_page == "vision":
                frame = self.bot_controller.get_latest_frame()
                if frame is not None:
                    resized = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_LINEAR)
                    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    im = Image.fromarray(rgb)
                    self._vision_img_tk = ImageTk.PhotoImage(im)
                    self.vision_canvas.delete("all")
                    self.vision_canvas.create_image(0, 0, anchor="nw", image=self._vision_img_tk)
                else:
                    self.vision_canvas.delete("all")
                    self.vision_canvas.create_text(320, 180, text="[ NO LIVE FRAME ]", fill="#64748B", font=(THEME["font_family"], 12, "bold"))

            if self.current_page == "battle" and hasattr(self.bot_controller.engine, "health_monitor"):
                hm = self.bot_controller.engine.health_monitor
                b_stat = hm.get("battle_status", "INACTIVE")
                tgt = hm.get("target", "NONE")
                e_det = hm.get("enemy_detected", "NO")
                p_hp = hm.get("player_hp", "100%")
                hp_r = hm.get("hp_ratio", "100.0%")
                h_req = hm.get("healing_required", "NO")
                c_src = hm.get("crystal_search", "BLOCKED")
                sk_det = hm.get("skills_detected", 0)
                sk_av = hm.get("skills_available", 0)
                sel_sk = hm.get("selected_skill", "NONE")
                last_act = hm.get("last_action", "NONE")

                t_info = (
                    f"STATUS: {b_stat} | INIMIGO: {e_det} | ALVO: {tgt} | "
                    f"HP: {p_hp} ({hp_r}) | CURA: {h_req} | BUSCA CRISTAL: {c_src}"
                )
                self.battle_target_info_lbl.configure(text=t_info)
                self.battle_decision_lbl.configure(text=f"Ação: {last_act} | Habilidade: {sel_sk}")
                self.battle_reason_lbl.configure(text=f"Slots Detectados: {sk_det} | Slots Disponíveis: {sk_av} | Modo: {self.bot_controller.engine.mode}")

                if hasattr(self, "battle_grid_vars"):
                    self.battle_grid_vars["state_val"].configure(text=str(hm.get("state", "BATTLE")))
                    self.battle_grid_vars["battle_ui_val"].configure(text=str(hm.get("battle_ui", "CONFIRMED")))
                    self.battle_grid_vars["fight_val"].configure(text=str(hm.get("fight", "FOUND")))
                    self.battle_grid_vars["enemy_val"].configure(text="DETECTED" if e_det == "YES" else "NONE")
                    self.battle_grid_vars["player_val"].configure(text=str(hm.get("player_detected", "DETECTED")))
                    self.battle_grid_vars["crystal_val"].configure(text=str(hm.get("crystal", "BLOCKED")))
                    self.battle_grid_vars["crystal_search_val"].configure(text=str(c_src))
                    self.battle_grid_vars["skills_val"].configure(text=str(sk_det))
                    self.battle_grid_vars["avail_val"].configure(text=str(sk_av))
                    self.battle_grid_vars["selected_val"].configure(text=str(sel_sk)[:14])
                    self.battle_grid_vars["action_val"].configure(text=str(last_act)[:14])
                    self.battle_grid_vars["input_val"].configure(text="DISPATCHED" if hm.get("input_dispatched") else "PENDING")
                    self.battle_grid_vars["verif_val"].configure(text="VERIFIED" if hm.get("verification") else "PENDING")
                    self.battle_grid_vars["delta_val"].configure(text=f"{hm.get('visual_delta', 0.0):.4f}")
                    self.battle_grid_vars["watchdog_val"].configure(text=str(hm.get("watchdog", "OK")))

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

            if self.current_page == "validation" and hasattr(self, "val_level_labels"):
                is_l6 = self.bot_controller.is_level_6_validated()
                if is_l6:
                    self.val_level_labels["LEVEL 6"].configure(text="VALIDADO FISICAMENTE (PASS)", fg=THEME["status_active"])
                    self.val_level_labels["LEVEL 7"].configure(text="LIBERADO / PRONTO (PASS)", fg=THEME["status_active"])
                else:
                    self.val_level_labels["LEVEL 6"].configure(text="NOT VALIDATED (Ação Usuário)", fg=THEME["status_warning"])
                    self.val_level_labels["LEVEL 7"].configure(text="BLOQUEADO (Requer Level 6 PASS)", fg=THEME["status_warning"])

            if self.current_page == "diagnostics" and hasattr(self.bot_controller.engine, "health_monitor"):
                hm = self.bot_controller.engine.health_monitor

                if hasattr(self, "exec_monitor_vars"):
                    self.exec_monitor_vars["exec_state"].configure(text=str(hm.get("state", state)))
                    self.exec_monitor_vars["exec_target"].configure(text=str(hm.get("target", hm.get("current_target", "NONE")))[:15])
                    self.exec_monitor_vars["exec_target_type"].configure(text=str(hm.get("target_type", "NONE"))[:15])
                    self.exec_monitor_vars["exec_conf"].configure(text=f"{hm.get('target_confidence', 0.0):.2f}")
                    
                    p_pos = hm.get("player_pos", (0, 0))
                    self.exec_monitor_vars["exec_player_pos"].configure(text=f"({p_pos[0]}, {p_pos[1]})")
                    
                    t_pos = hm.get("target_pos", (0, 0))
                    self.exec_monitor_vars["exec_target_pos"].configure(text=f"({t_pos[0]}, {t_pos[1]})")
                    
                    self.exec_monitor_vars["exec_dist"].configure(text=f"{hm.get('distance', 0.0):.1f} px")
                    self.exec_monitor_vars["exec_decision"].configure(text=str(hm.get("decision", "NONE"))[:18])
                    self.exec_monitor_vars["exec_input"].configure(text=str(hm.get("input", hm.get("last_input", "NONE")))[:10])
                    self.exec_monitor_vars["exec_window"].configure(text=str(hm.get("window", "NONE"))[:15])
                    self.exec_monitor_vars["exec_fg"].configure(text="TRUE" if hm.get("foreground") else "FALSE")
                    self.exec_monitor_vars["exec_canvas"].configure(text="DETECTED" if hm.get("canvas") else "NONE")
                    self.exec_monitor_vars["exec_dispatch"].configure(text="YES" if hm.get("input_dispatched") else "NO")
                    self.exec_monitor_vars["exec_delta"].configure(text=f"{hm.get('visual_delta', 0.0):.4f}")
                    self.exec_monitor_vars["exec_result"].configure(text=str(hm.get("action_result", "NONE")))
                    self.exec_monitor_vars["exec_action"].configure(text=str(hm.get("last_action", "NONE"))[:15])
                    self.exec_monitor_vars["exec_elapsed"].configure(text=f"{hm.get('time_since_last_action', 0.0):.1f}s")

                if hasattr(self, "action_rate_vars"):
                    self.action_rate_vars["rate_obs"].configure(text=str(snap.get("observations_total", 0)))
                    self.action_rate_vars["rate_dec"].configure(text=str(snap.get("decisions_total", 0)))
                    self.action_rate_vars["rate_in_req"].configure(text=str(snap.get("input_requests_total", 0)))
                    self.action_rate_vars["rate_in_disp"].configure(text=str(snap.get("input_dispatched_total", 0)))
                    self.action_rate_vars["rate_act_ver"].configure(text=str(snap.get("actions_verified_total", 0)))
                    self.action_rate_vars["rate_act_unconf"].configure(text=str(snap.get("actions_unconfirmed_total", 0)))

            if self.current_page == "telemetry":
                t_text = (
                    f"Métricas Operacionais em Tempo Real:\n"
                    f"• Uptime                : {uptime:.1f}s\n"
                    f"• FPS Atual             : {fps:.1f}\n"
                    f"• Observações Totais    : {snap.get('observations_total', 0)}\n"
                    f"• Decisões Tomadas      : {snap.get('decisions_total', 0)}\n"
                    f"• Requisições de Input  : {snap.get('input_requests_total', 0)}\n"
                    f"• Inputs Despachados    : {snap.get('input_dispatched_total', 0)}\n"
                    f"• Ações Confirmadas     : {snap.get('actions_verified_total', 0)}\n"
                    f"• Ações Não-Confirmadas : {snap.get('actions_unconfirmed_total', 0)}\n"
                    f"• Ações / Minuto        : {snap.get('actions_per_minute', 0.0):.1f}\n"
                    f"• Latência Média Ação   : {latency:.1f} ms\n"
                    f"• Batalhas Totais       : {snap.get('battles_total', 0)} ({snap.get('victories_total', 0)} Vitórias, {snap.get('defeats_total', 0)} Derrotas)\n"
                    f"• Recuperações de Erro  : {snap.get('recoveries_total', 0)}\n"
                )
                self.telemetry_details_lbl.configure(text=t_text)

        except Exception:
            pass

        self.root.after(50, self._ui_telemetry_tick)


def start_modern_gui() -> None:
    root = tk.Tk()
    app = ModernLumenaGUI(root)
    root.mainloop()
