import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RealInputDiagnostic")

from src.input.target_window import TargetWindowManager
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture
from src.telemetry.evidence_package import save_evidence_package
from src.core.event_bus import EventBus


def run_real_input_diagnostic() -> Dict[str, Any]:
    print("\n=======================================================")
    print("   LUMENA BOT v3.4 — CONTROLLED REAL INPUT DIAGNOSTIC")
    print("=======================================================\n")

    win_mgr = TargetWindowManager()
    input_ctrl = InputController()
    screen_cap = ScreenCapture()
    event_bus = EventBus()

    target_info = win_mgr.find_target_window()
    if not target_info or not target_info.hwnd or target_info.is_self_process:
        logger.warning("[SAFETY] Nenhuma janela de navegador aberta para teste controlado.")
        report = {
            "status": "NOT VALIDATED",
            "message": "Navegador Chrome/Edge/Firefox/Brave não encontrado ou em primeiro plano.",
            "actions_tested": [],
        }
        with open("real_input_diagnostic_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("Resultado: NOT VALIDATED (Abra o navegador com o jogo Lumena.gg antes de executar)\n")
        return report

    # Foco na janela
    win_mgr.focus_target_window(target_info.hwnd)
    win_mgr.focus_canvas(target_info.hwnd)

    actions = [("W", "w", 0.5), ("S", "s", 0.5), ("A", "a", 0.5), ("D", "d", 0.5)]
    results = []

    for label, key, duration in actions:
        logger.info(f"[DIAGNOSTIC] Testando ação controlada: {label} por {duration}s...")
        frame_before, _ = screen_cap.capture_frame()

        diag = input_ctrl.press_key_with_diagnostic(key, duration=duration)
        time.sleep(0.1)

        frame_after, _ = screen_cap.capture_frame()
        confirmed, delta = input_ctrl.compute_visual_delta(frame_before, frame_after)

        pkg_path = save_evidence_package(
            target_window_verified=target_info.is_valid_candidate,
            foreground_verified=win_mgr.verify_foreground(target_info.hwnd),
            input_dispatched=diag.success,
            visual_change_detected=confirmed,
            visual_delta=delta,
            action_verified=confirmed,
            physical_execution_verified=confirmed,
            target_type="PLAYER_OVERWORLD",
            target_confidence=1.0,
            action=f"CONTROLLED_MOVE_{label}",
            failure_reason="" if confirmed else "Visual delta abaixo do threshold",
            frame_before=frame_before,
            frame_after=frame_after,
            input_data={"key": key, "duration": duration, "scan_code": diag.scan_code, "latency": diag.latency},
            window_data=target_info.__dict__,
            events_data=[e.__dict__ for e in event_bus.get_recent_events(20)],
        )

        results.append({
            "action": label,
            "duration": duration,
            "dispatched": diag.success,
            "visual_delta": delta,
            "verified": confirmed,
            "evidence_package": pkg_path,
        })

    report = {
        "status": "COMPLETED",
        "target_hwnd": target_info.hwnd,
        "actions_tested": results,
    }
    with open("real_input_diagnostic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nDiagnóstico finalizado. Pacotes salvos em debug/evidence/.\n")
    return report


if __name__ == "__main__":
    run_real_input_diagnostic()
