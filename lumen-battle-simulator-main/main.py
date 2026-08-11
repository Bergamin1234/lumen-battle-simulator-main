import sys
from src.ui.cli import UnifiedCLI


def main() -> None:
    """Ponto de entrada principal da aplicação."""
    try:
        app = UnifiedCLI()
        app.run()
    except KeyboardInterrupt:
        print("\n\n[-] Aplicação interrompida pelo usuário.")
        sys.exit(0)


if __name__ == "__main__":
    main()