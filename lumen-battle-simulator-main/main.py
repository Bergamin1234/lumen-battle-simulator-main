"""
LUMENA BOT CONTROL CENTER v4.4 — MAIN ENTRYPOINT
===============================================
Ponto de entrada unificado para execução gráfica (GUI) ou linha de comando (CLI/Field Trial).
"""

import sys
import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="LumenaBot",
        description="Lumena Bot Control Center v5.0 — Autonomous Industrial Master Suite",
    )
    parser.add_argument("--version", action="store_true", help="Exibe a versão atual do sistema e encerra")
    parser.add_argument("--cli", action="store_true", help="Executa o motor central em modo linha de comando (sem GUI)")
    parser.add_argument("--field-trial", action="store_true", help="Executa o protocolo de Teste de Campo (Field Trial)")
    parser.add_argument("--cycles", type=int, default=3, help="Número de ciclos para o Field Trial (padrão: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Executa o Field Trial em modo simulado sem Chrome")
    parser.add_argument("--output", type=str, default=None, help="Caminho de saída para result.json")

    args, unknown = parser.parse_known_args()

    if args.version:
        print("Lumena Bot Control Center v4.4 / v5.0 Master Industrial — Autonomous Industrial Master Suite")
        print("Build: v5.0 Master Industrial | Python 3.12 | Win32 API WebGL Engine")
        sys.exit(0)

    if args.field_trial:
        from scripts.diagnostics.run_field_trial import run_field_trial_session
        res = run_field_trial_session(
            num_cycles=args.cycles,
            dry_run=args.dry_run,
            output_path=args.output,
        )
        sys.exit(0 if res.get("status") in ("PASS", "NO_TARGET_WINDOW_DETECTED", "PASS_SYNTHETIC") else 1)

    if args.cli:
        from src.automation.bot_controller import BotController
        print("Iniciando Lumena Bot em modo CLI autônomo...")
        controller = BotController()
        controller.start()
        try:
            while True:
                import time
                time.sleep(1.0)
        except KeyboardInterrupt:
            controller.stop()
            sys.exit(0)

    # Modo padrão: Inicialização da Interface Gráfica
    try:
        from src.ui.app_gui import launch_gui
        launch_gui()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()