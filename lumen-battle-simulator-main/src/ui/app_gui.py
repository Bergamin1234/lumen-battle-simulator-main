import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from PIL import Image, ImageTk

from config.settings import BotConfig
from src.automation.bot_engine import LumenaBotEngine


class TextHandler(logging.Handler):
    """Redireciona logs em tempo real para a caixa de texto da interface."""
    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.log_queue.put(msg)


class LumenaAppGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Lumena.gg - Bot de Automação Visual v2.5")
        self.root.geometry("900x680")
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

        # Paleta inspirada na Logo (Cosmic Dark / Neon Cyan & Purple)
        self.bg_color = "#100c1e"
        self.card_bg = "#18132b"
        self.accent_cyan = "#00f0ff"
        self.accent_purple = "#8a5cf6"
        self.text_main = "#e2e8f0"
        self.text_muted = "#94a3b8"

        self.root.configure(bg=self.bg_color)

        style.configure(".", background=self.bg_color, foreground=self.text_main, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.bg_color)
        style.configure("Card.TFrame", background=self.card_bg)

        # Abas (Notebook)
        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e1838", foreground=self.text_muted, padding=[15, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.card_bg)], foreground=[("selected", self.accent_cyan)])

        # Caixas de Agrupamento
        style.configure("TLabelframe", background=self.card_bg, foreground=self.accent_cyan, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=self.card_bg, foreground=self.accent_cyan, font=("Segoe UI", 10, "bold"))

        # Botões
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background="#10b981", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#059669")])

        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background="#ef4444", foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#dc2626")])

        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), background="#3b82f6", foreground="#ffffff")
        style.map("Action.TButton", background=[("active", "#2563eb")])

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=self.card_bg, height=80, highlightthickness=1, highlightbackground="#2e2552")
        header_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(10, 5))

        # Carregar Logo do Anexo
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path).resize((64, 64), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(pil_img)
                logo_label = tk.Label(header_frame, image=self.logo_image, bg=self.card_bg)
                logo_label.pack(side=tk.LEFT, padx=12, pady=8)
            except Exception:
                pass

        # Título e Subtítulo
        title_box = tk.Frame(header_frame, bg=self.card_bg)
        title_box.pack(side=tk.LEFT, fill=tk.Y, pady=12)

        lbl_title = tk.Label(title_box, text="LUMENA.GG AUTOMATION BOT", font=("Segoe UI", 15, "bold"), fg=self.accent_cyan, bg=self.card_bg)
        lbl_title.pack(anchor=tk.W)

        lbl_sub = tk.Label(title_box, text="Sistema de Visão Computacional e Combate Autônomo", font=("Segoe UI", 9), fg=self.text_muted, bg=self.card_bg)
        lbl_sub.pack(anchor=tk.W)

        # Status
        self.status_badge = tk.Label(header_frame, text="● PARADO", font=("Segoe UI", 10, "bold"), fg="#f59e0b", bg=self.card_bg, padx=15)
        self.status_badge.pack(side=tk.RIGHT, padx=15)

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Aba 1: Controle
        tab_main = ttk.Frame(notebook)
        notebook.add(tab_main, text="🎮 Painel de Controle")
        self._build_tab_main(tab_main)

        # Aba 2: Configurações
        tab_config = ttk.Frame(notebook)
        notebook.add(tab_config, text="⚙️ Configurações")
        self._build_tab_config(tab_config)

        # Aba 3: Tutorial
        tab_tutorial = ttk.Frame(notebook)
        notebook.add(tab_tutorial, text="📖 Guia & Tutorial")
        self._build_tab_tutorial(tab_tutorial)

    def _build_tab_main(self, parent: ttk.Frame) -> None:
        top_frame = tk.Frame(parent, bg=self.bg_color)
        top_frame.pack(fill=tk.X, pady=5)

        # Botões de Ação
        ctrl_box = ttk.LabelFrame(top_frame, text=" Comandos Principais ", padding="10")
        ctrl_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.btn_start = ttk.Button(ctrl_box, text="▶ Iniciar Bot", style="Primary.TButton", command=self.toggle_bot)
        self.btn_start.pack(fill=tk.X, pady=4)

        self.btn_test = ttk.Button(ctrl_box, text="🔍 Testar Reconhecimento de Tela", style="Action.TButton", command=self.test_vision)
        self.btn_test.pack(fill=tk.X, pady=4)

        self.btn_heal_test = ttk.Button(ctrl_box, text="🧪 Testar Ciclo de Cura", style="Action.TButton", command=self.test_heal_route)
        self.btn_heal_test.pack(fill=tk.X, pady=4)

        # Resumo de Status
        info_box = ttk.LabelFrame(top_frame, text=" Monitoramento ", padding="10")
        info_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.lbl_info_pattern = tk.Label(info_box, text=f"Padrão: {self.config.movement_pattern.upper()}", bg=self.card_bg, fg=self.text_main)
        self.lbl_info_pattern.pack(anchor=tk.W, pady=2)

        self.lbl_info_monitor = tk.Label(info_box, text=f"Monitor Alvo: #{self.config.monitor}", bg=self.card_bg, fg=self.text_main)
        self.lbl_info_monitor.pack(anchor=tk.W, pady=2)

        self.lbl_info_speed = tk.Label(info_box, text=f"Passo: {self.config.step_duration}s", bg=self.card_bg, fg=self.text_main)
        self.lbl_info_speed.pack(anchor=tk.W, pady=2)

        # Console de Logs
        log_box = ttk.LabelFrame(parent, text=" Terminal de Execução ", padding="10")
        log_box.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_box,
            bg="#090710",
            fg="#a7f3d0",
            insertbackground="white",
            font=("Consolas", 9),
            wrap=tk.WORD,
            borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_tab_config(self, parent: ttk.Frame) -> None:
        cfg_card = ttk.LabelFrame(parent, text=" Parâmetros de Movimento e Visão ", padding="15")
        cfg_card.pack(fill=tk.X, padx=10, pady=10)

        # Grid de entradas
        tk.Label(cfg_card, text="Padrão de Movimento:", bg=self.card_bg, fg=self.text_main).grid(row=0, column=0, sticky=tk.W, pady=8)
        self.combo_pattern = ttk.Combobox(cfg_card, values=["zigzag", "square", "left_right", "random"], state="readonly", width=18)
        self.combo_pattern.set(self.config.movement_pattern)
        self.combo_pattern.grid(row=0, column=1, sticky=tk.W, pady=8, padx=10)

        tk.Label(cfg_card, text="Duração do Passo (segundos):", bg=self.card_bg, fg=self.text_main).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.entry_step = ttk.Entry(cfg_card, width=20)
        self.entry_step.insert(0, str(self.config.step_duration))
        self.entry_step.grid(row=1, column=1, sticky=tk.W, pady=8, padx=10)

        tk.Label(cfg_card, text="Índice do Monitor (1, 2...):", bg=self.card_bg, fg=self.text_main).grid(row=2, column=0, sticky=tk.W, pady=8)
        self.entry_monitor = ttk.Entry(cfg_card, width=20)
        self.entry_monitor.insert(0, str(self.config.monitor))
        self.entry_monitor.grid(row=2, column=1, sticky=tk.W, pady=8, padx=10)

        tk.Label(cfg_card, text="Batalhas antes da Cura:", bg=self.card_bg, fg=self.text_main).grid(row=3, column=0, sticky=tk.W, pady=8)
        self.entry_heal_battles = ttk.Entry(cfg_card, width=20)
        self.entry_heal_battles.insert(0, str(self.config.battles_before_heal_check))
        self.entry_heal_battles.grid(row=3, column=1, sticky=tk.W, pady=8, padx=10)

        btn_save = ttk.Button(cfg_card, text="💾 Salvar Alterações", style="Primary.TButton", command=self.save_settings)
        btn_save.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=(15, 0))

    def _build_tab_tutorial(self, parent: ttk.Frame) -> None:
        tut_card = ttk.LabelFrame(parent, text=" Passo a Passo para Operação do Bot ", padding="15")
        tut_card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tut_text = scrolledtext.ScrolledText(
            tut_card,
            bg=self.card_bg,
            fg=self.text_main,
            font=("Segoe UI", 9.5),
            wrap=tk.WORD,
            borderwidth=0
        )
        tut_text.pack(fill=tk.BOTH, expand=True)

        guide_content = """📌 NOTA DE TUTORIAL E INSTRUÇÕES DE USO

1. CAPTURA DOS TEMPLATES (IMAGENS):
   Para o bot reconhecer os botões do jogo na sua resolução de tela, salve recortes de print (.png) na pasta 'templates/':
   • fight_button.png   -> Botão 'Fight' ou entrar na batalha.
   • first_move.png     -> Ícone do primeiro ataque do seu Lumena.
   • dialog_box.png     -> A caixa de diálogo da Estrutura Azul de cura.
   • heal_yes_btn.png   -> Botão 'Sim' para confirmar a restauração.

2. POSICIONAMENTO DA JANELA:
   • Deixe a janela do Lumena.gg totalmente visível no monitor selecionado nas configurações.
   • Evite sobrepor janelas por cima do jogo durante o farm autônomo.

3. TESTANDO ANTES DE LIGAR:
   • Vá até a aba '🎮 Painel de Controle' e clique em '🔍 Testar Reconhecimento de Tela'.
   • O terminal mostrará quais elementos visuais foram identificados com sucesso.

4. ROTAS E INTERVALOS:
   • Para ajustar o tempo de caminhada até o ponto de cura ou trocar o padrão de andando em zigzag, altere os parâmetros na aba '⚙️ Configurações' ou diretamente no arquivo 'settings.json'."""

        tut_text.insert(tk.END, guide_content)
        tut_text.configure(state="disabled")

    def _setup_logging(self) -> None:
        logger = logging.getLogger("LumenaMacro")
        logger.setLevel(logging.INFO)
        handler = TextHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)

    def _poll_log_queue(self) -> None:
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        self.root.after(100, self._poll_log_queue)

    def save_settings(self) -> None:
        try:
            self.config.movement_pattern = self.combo_pattern.get()
            self.config.step_duration = float(self.entry_step.get())
            self.config.monitor = int(self.entry_monitor.get())
            self.config.battles_before_heal_check = int(self.entry_heal_battles.get())
            self.config.save_to_json()

            self.lbl_info_pattern.configure(text=f"Padrão: {self.config.movement_pattern.upper()}")
            self.lbl_info_monitor.configure(text=f"Monitor Alvo: #{self.config.monitor}")
            self.lbl_info_speed.configure(text=f"Passo: {self.config.step_duration}s")

            messagebox.showinfo("Sucesso", "Configurações salvas e aplicadas!")
        except ValueError:
            messagebox.showerror("Erro", "Insira apenas números válidos nos campos.")

    def toggle_bot(self) -> None:
        if not self.is_running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self) -> None:
        self.is_running = True
        self.btn_start.configure(text="⏹ Parar Bot", style="Danger.TButton")
        self.status_badge.configure(text="● EM EXECUÇÃO", fg="#10b981")

        self.engine = LumenaBotEngine(self.config)
        self.bot_thread = threading.Thread(target=self._run_bot_loop, daemon=True)
        self.bot_thread.start()

    def _run_bot_loop(self) -> None:
        if self.engine:
            self.engine.start()

    def stop_bot(self) -> None:
        self.is_running = False
        if self.engine:
            self.engine.stop()
        self.btn_start.configure(text="▶ Iniciar Bot", style="Primary.TButton")
        self.status_badge.configure(text="● PARADO", fg="#f59e0b")

    def test_vision(self) -> None:
        threading.Thread(target=self._run_vision_test, daemon=True).start()

    def _run_vision_test(self) -> None:
        engine = LumenaBotEngine(self.config)
        results = engine.test_vision_system()
        msg = "\n".join([f"• {name}: {'ENCONTRADO' if found else 'NÃO ENCONTRADO'}" for name, found in results.items()])
        messagebox.showinfo("Resultado da Visão Computacional", msg)

    def test_heal_route(self) -> None:
        if messagebox.askyesno("Confirmar", "Iniciar teste da rota de cura com o jogo visível?"):
            threading.Thread(target=self._run_heal_test, daemon=True).start()

    def _run_heal_test(self) -> None:
        engine = LumenaBotEngine(self.config)
        engine.healing_ctrl.perform_heal()


def launch_gui() -> None:
    root = tk.Tk()
    app = LumenaAppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()