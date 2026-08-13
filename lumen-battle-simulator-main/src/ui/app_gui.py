from src.ui.modern_gui import ModernLumenaGUI, start_modern_gui

LumenaAppGUI = ModernLumenaGUI


def launch_gui() -> None:
    """Inicia a interface moderna de alta fidelidade do Lumena Bot."""
    start_modern_gui()


if __name__ == "__main__":
    launch_gui()