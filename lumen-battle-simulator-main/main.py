import sys
from src.ui.app_gui import launch_gui


def main() -> None:
    try:
        launch_gui()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()