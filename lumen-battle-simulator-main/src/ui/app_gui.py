import logging
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from PIL import Image, ImageTk

from config.settings import BotConfig
from src.automation.bot_engine import LumenaBotEngine
from src.automation.navigation import NavigationController
from src.input.input_controller import InputController


class TextHandler(logging.Handler):
    """Handler customizado que encaminha os registros de log para a fila da interface gráfica."""
    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.log_queue.put(msg)


class RouteRecorderWindow(tk.Toplevel):
    """Janela nativa que captura WASD para criar a rota de navegação sem dependências externas."""
    def __init__(self, parent: tk.Tk, on_complete_callback=None) -> None:
        super().__init__(parent)
        self.title("Gravador de Rota (WASD)")
        self.geometry("520x380")
        self.configure(bg="#18132b")
        self.on_complete_callback = on_complete_callback

        self.is_recording = False
        self.recorded_steps = []
        self.active_keys = {}

        self._build_ui()
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)

    def _build_ui(self) -> None:
        lbl_title = tk.Label(self, text="GRAVADOR DE ROTA DE NAVEGAÇÃO", font=("Segoe UI", 12, "bold"), fg="#00f0ff", bg="#18132b")
        lbl_title.pack(pady=10)

        info_text = (
            "Instruções:\n"
            "1. Clique em 'Iniciar Gravação'.\n"
            "2. Mantenha esta janela em foco (ou clique nela) e pressione WASD.\n"
            "3. Faça o trajeto do MATO DE FARM até o CRISTAL DE CURA.\n"
            "4. Clique em 'Salvar Rota'."
        )
        lbl_info = tk.Label(self, text=info_text, font=("Segoe UI", 9), fg="#e2e8f0", bg="#18132b", justify=tk.LEFT)
        lbl_info.pack(padx=20, pady=5)

        self.lbl_status = tk.Label(self, text="Status: Aguardando...", font=("Segoe UI", 10, "bold"), fg="#f59e0b", bg="#18132b")
        self.lbl_status.pack(pady=10)

        self.lbl_count = tk.Label(self, text="Passos gravados: 0", font=("Segoe UI", 9), fg="#94a3b8", bg="#18132b")
        self.lbl_count.pack(pady=2)

        btn_frame = tk.Frame(self, bg="#18132b")
        btn_frame.pack(pady=15)

        self.btn_start = ttk.Button(btn_frame, text="🔴 Iniciar Gravação", command=self.start_recording)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(btn_frame, text="💾 Salvar Rota", command=self.stop_recording, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

    def start_recording(self) -> None:
        self.is_recording = True
        self.recorded_steps = []
        self.active_keys = {}
        self.lbl_status.configure(text="Status: 🔴 GRAVANDO... Pressione W, A, S, D aqui nesta janela!", fg="#ef4444")
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.focus_set()

    def on_key_press(self, event) -> None:
        if not self.is_recording:
            return
        k = event.keysym.lower()
        if k in ['w', 'a', 's', 'd'] and k not in self.active_keys:
            self.active_keys[k] = time.time()

    def on_key_release(self, event) -> None:
        if not self.is_recording:
            return
        k = event.keysym.lower()
        if k in self.active_keys:
            start_t = self.active_keys.pop(k)
            duration = round(time.time() - start_t, 2)
            if duration >= 0.05:
                self.recorded_steps.append({"key": k, "duration": duration})
                self.lbl_count.configure(text=f"Passos gravados: {len(self.recorded_steps)}")

    def stop_recording(self) -> None:
        self.is_recording = False
        nav = NavigationController(BotConfig.load_from_json(), InputController())
        nav.save_route(self.recorded_steps)

        messagebox.showinfo("Sucesso", f"Rota salva com {len(self.recorded_steps)} passos!")
        if self.on_complete_callback:
            self.on_complete_callback()
        self.destroy()


class LumenaAppGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Lumena.gg - Bot Autônomo v3.1")
        self.root.geometry("920x720")
        self.root.minsize(800, 600)

        self.config = BotConfig.load_from_json()
        self.engine: LumenaBotEngine | None = None
        self.bot_thread: threading.Thread | None = None
        self.is_running = False

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.logo_image: ImageTk.PhotoImage | None = None

        self._setup_theme()
        self._build_header()
        self._build_tabs()
        self._setup_logging()
        self.root.after(100, self._poll_log_queue)

    def _setup_theme(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        self.bg_color = "#100c1e"
        self.card_bg = "#18132b"
        self.accent_cyan = "#00f0ff"
        self.text_main = "#e2e8f0"
        self.text_muted = "#94a3b8"

        self.root.configure(bg=self.bg_color)

        style.configure(".", background=self.bg_color, foreground=self.text_main, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.bg_color)
        style.configure("Card.TFrame", background=self.card_bg)

        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e1838", foreground=self.text_muted, padding=[15, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.card_bg)], foreground=[("selected", self.accent_cyan)])

        style.configure("TLabelframe", background=self.card_bg, foreground=self.accent_cyan, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=self.card_bg, foreground=self.accent_cyan, font=("Segoe UI", 10, "bold"))

        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background="#10b981", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#059669")])

        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background="#ef4444", foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#dc2626")])

        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), background="#3b82f6", foreground="#ffffff")
        style.map("Action.TButton", background=[("active", "#2563eb")])

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=self.card_bg, height=80, highlightthickness=1, highlightbackground="#2e2552")
        header_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(10, 5))

        title_box = tk.Frame(header_frame, bg=self.card_bg)
        title_box.pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=15)

        lbl_title = tk.Label(title_box, text="LUMENA.GG AUTOMATION BOT", font=("Segoe UI", 15, "bold"), fg=self.accent_cyan, bg=self.card_bg)
        lbl_title.pack(anchor=tk.W)

        lbl_sub = tk.Label(title_box, text="Sistema Autônomo em Malha Fechada com Combate Inteligente", font=("Segoe UI", 9), fg=self.text_muted, bg=self.card_bg)
        lbl_sub.pack(anchor=tk.W)

        self.status_badge = tk.Label(header_frame, text="● PARADO", font=("Segoe UI", 10, "bold"), fg="#f59e0b", bg=self.card_bg, padx=15)
        self.status_badge.pack(side=tk.RIGHT, padx=15)

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tab_main = ttk.Frame(notebook)
        notebook.add(tab_main, text="🎮 Painel de Controle")
        self._build_tab_main(tab_main)

        tab_route = ttk.Frame(notebook)
        notebook.add(tab_route, text="🗺️ Gravar Rota com Curvas")
        self._build_tab_route(tab_route)

        tab_config = ttk.Frame(notebook)
        notebook.add(tab_config, text="⚙️ Configurações")
        self._build_tab_config(tab_config)

    def _build_tab_main(self, parent: ttk.Frame) -> None:
        top_frame = tk.Frame(parent, bg=self.bg_color)
        top_frame.pack(fill=tk.X, pady=5)

        ctrl_box = ttk.LabelFrame(top_frame, text=" Comandos Principais ", padding="10")
        ctrl_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.btn_start = ttk.Button(ctrl_box, text="▶ Iniciar Bot Autônomo", style="Primary.TButton", command=self.toggle_bot)
        self.btn_start.pack(fill=tk.X, pady=4)

        self.btn_test = ttk.Button(ctrl_box, text="🔍 Testar Reconhecimento de Tela", style="Action.TButton", command=self.test_vision)
        self.btn_test.pack(fill=tk.X, pady=4)

        log_box = ttk.LabelFrame(parent, text=" Terminal de Execução em Tempo Real ", padding="10")
        log_box.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(log_box, bg="#090710", fg="#a7f3d0", font=("Consolas", 9), wrap=tk.WORD, borderwidth=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_tab_route(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=" Criador de Rota Personalizada (Curvas + Portal + Cristal) ", padding="15")
        box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        desc = (
            "Para que o bot consiga fazer as curvas no seu mapa, atravessar o portal e ir curar:\n\n"
            "1. Clique no botão abaixo para abrir a janela de gravação.\n"
            "2. Pressione WASD na janela de gravação simulando o caminho do Mato até o Cristal.\n"
            "3. O bot salvará os passos para repetir a rota de ida e volta sozinho no navegador!"
        )
        tk.Label(box, text=desc, bg=self.card_bg, fg=self.text_main, justify=tk.LEFT, font=("Segoe UI", 10)).pack(anchor=tk.W, pady=10)

        btn_open_rec = ttk.Button(box, text="🔴 Abrir Gravador de Rota", style="Action.TButton", command=self.open_route_recorder)
        btn_open_rec.pack(pady=15)

    def open_route_recorder(self) -> None:
        RouteRecorderWindow(self.root, None)

    def _build_tab_config(self, parent: ttk.Frame) -> None:
        cfg_card = ttk.LabelFrame(parent, text=" Parâmetros de Movimento e Visão ", padding="15")
        cfg_card.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(cfg_card, text="Padrão de Movimento:", bg=self.card_bg, fg=self.text_main).grid(row=0, column=0, sticky=tk.W, pady=8)
        self.combo_pattern = ttk.Combobox(cfg_card, values=["zigzag", "square", "left_right", "random"], state="readonly", width=18)
        self.combo_pattern.set(self.config.movement_pattern)
        self.combo_pattern.grid(row=0, column=1, sticky=tk.W, pady=8, padx=10)

        tk.Label(cfg_card, text="Batalhas antes da Cura:", bg=self.card_bg, fg=self.text_main).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.entry_heal_battles = ttk.Entry(cfg_card, width=20)
        self.entry_heal_battles.insert(0, str(self.config.battles_before_heal_check))
        self.entry_heal_battles.grid(row=1, column=1, sticky=tk.W, pady=8, padx=10)

        btn_save = ttk.Button(cfg_card, text="💾 Salvar Alterações", style="Primary.TButton", command=self.save_settings)
        btn_save.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(15, 0))

    def _setup_logging(self) -> None:
        """Configura encaminhamento global de logs de todos os subsistemas para o terminal da GUI."""
        handler = TextHandler(self.log_queue)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
        handler.setFormatter(formatter)

        # Registra o handler nos loggers de todos os módulos
        loggers_to_attach = [
            "LumenaMacro",
            "LumenaCombat",
            "LumenaPerception",
            "LumenaMemory",
            "LumenaInput",
            "LumenaWindow",
            "RealIntegrationValidation",
        ]
        for name in loggers_to_attach:
            l = logging.getLogger(name)
            l.setLevel(logging.INFO)
            l.addHandler(handler)

        # Adiciona também no root logger para capturar logs não categorizados
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def _poll_log_queue(self) -> None:
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        self.root.after(100, self._poll_log_queue)

    def save_settings(self) -> None:
        try:
            self.config.battles_before_heal_check = int(self.entry_heal_battles.get())
            self.config.save_to_json()
            messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
        except ValueError:
            messagebox.showerror("Erro", "Insira valores numéricos válidos.")

    def toggle_bot(self) -> None:
        if not self.is_running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self) -> None:
        if self.is_running:
            return

        self.is_running = True
        self.btn_start.configure(text="⏹ Parar Bot", style="Danger.TButton")
        self.status_badge.configure(text="● INICIANDO...", fg="#3b82f6")

        self.engine = LumenaBotEngine(self.config)
        self.bot_thread = threading.Thread(target=self._run_bot_loop, daemon=True)
        self.bot_thread.start()

        # Atualiza badge para ATIVO após início
        self.root.after(500, lambda: self.status_badge.configure(text="● ATIVO", fg="#10b981") if self.is_running else None)

    def _run_bot_loop(self) -> None:
        try:
            if self.engine:
                self.engine.start()
        except Exception as e:
            logging.getLogger("LumenaMacro").error(f"Erro fatal na thread do bot: {e}", exc_info=True)
            self.status_badge.configure(text="● ERRO", fg="#ef4444")
            self.stop_bot()

    def stop_bot(self) -> None:
        self.is_running = False
        self.status_badge.configure(text="● PARANDO...", fg="#eab308")
        if self.engine:
            self.engine.stop()
        self.btn_start.configure(text="▶ Iniciar Bot Autônomo", style="Primary.TButton")
        self.status_badge.configure(text="● PARADO", fg="#f59e0b")

    def test_vision(self) -> None:
        threading.Thread(target=self._run_vision_test, daemon=True).start()

    def _run_vision_test(self) -> None:
        engine = LumenaBotEngine(self.config)
        results = engine.test_vision_system()
        msg = "\n".join([f"• {name}: {'PASSOU' if found else 'NÃO DETECTADO'}" for name, found in results.items()])
        messagebox.showinfo("Resultado da Visão Computacional", msg)


def launch_gui() -> None:
    root = tk.Tk()
    app = LumenaAppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()