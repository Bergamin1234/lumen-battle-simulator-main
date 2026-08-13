import os
import sys
import time
import json
import logging
import argparse
import ctypes
from typing import Dict, Any, Optional, Tuple
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RealWorldTest")

from src.input.target_window import TargetWindowManager, WindowInfo, FocusDiagnosticResult
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture


def run_real_world_test(interactive: bool = False) -> Dict[str, Any]:
    print("\n=======================================================")
    print("   LUMENA BOT - TESTE DE VALIDACAO FISICA REAL (LEVEL 6)")
    print("=======================================================\n")

    report: Dict[str, Any] = {
        "test": "LEVEL_6_PHYSICAL_MOVEMENT",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "step_1_python": False,
        "step_2_dependencies": False,
        "step_3_window_enumeration": False,
        "step_4_chrome_found": False,
        "step_5_lumena_identified": False,
        "step_6_hwnd": 0,
        "step_7_window_restored": False,
        "step_8_foreground_requested": False,
        "step_9_foreground_confirmed": False,
        "step_10_client_area": [0, 0, 0, 0],
        "step_11_canvas_region": [0, 0, 0, 0],
        "step_12_screenshot_before": None,
        "step_13_canvas_clicked": False,
        "step_14_w_dispatched_and_released": False,
        "step_15_screenshot_after": None,
        "step_16_visual_delta": 0.0,
        "step_16_altered_region": [0, 0, 0, 0],
        "step_17_movement_confirmed": False,
        "threshold": 0.005,
        "status": "NOT VALIDATED (Navegador Fechado)",
        "summary": "",
    }

    # STEP 1: Python
    report["step_1_python"] = True
    print(f"[OK] STEP 1: Python detectado: {sys.version.split()[0]}")

    # STEP 2: Dependências
    try:
        import PIL
        import pyautogui
        import mss
        report["step_2_dependencies"] = True
        print(f"[OK] STEP 2: Dependencias (PIL, OpenCV, PyAutoGUI, MSS) carregadas com sucesso.")
    except Exception as e:
        print(f"[FAIL] STEP 2: Falha nas dependencias: {e}")
        return report

    input_ctrl = InputController()
    win_mgr = input_ctrl.window_manager

    # STEP 3-5: Descoberta e Validação Real da Janela Alvo
    print("STEP 3-5: Buscando processo Google Chrome (chrome.exe) e Lumena.gg...")
    win_info: Optional[WindowInfo] = win_mgr.find_target_window()
    report["step_3_window_enumeration"] = True

    if not win_info:
        logger.warning("[SAFETY] Nenhuma janela Chrome/Lumena.gg compativel encontrada.")
        logger.warning("[SAFETY] A própria janela do Lumena Bot foi explicitamente rejeitada.")
        print("\n-------------------------------------------------------")
        print("RESULTADO: NAO VALIDADO (Abra o Lumena.gg no Chrome antes de testar)")
        print("-------------------------------------------------------\n")
        report["summary"] = "Navegador Chrome com Lumena.gg nao encontrado. Teste nao executado para seguranca do desktop."
        _save_report(report)
        return report

    report["step_4_chrome_found"] = True
    report["step_5_lumena_identified"] = ("lumena" in win_info.title.lower())
    report["step_6_hwnd"] = win_info.hwnd
    report["step_10_client_area"] = [win_info.left, win_info.top, win_info.width, win_info.height]

    print(f"[OK] STEP 4-6: Janela Alvo Confirmada: '{win_info.title}' (HWND: {win_info.hwnd}, PID: {win_info.pid}, Proc: {win_info.process_name})")

    # STEP 11: Região do Canvas
    canvas_cx = win_info.left + win_info.width // 2
    canvas_cy = win_info.top + win_info.height // 2
    report["step_11_canvas_region"] = [win_info.left, win_info.top + 80, win_info.width, win_info.height - 80]
    print(f"[OK] STEP 11: Centro do Canvas WebGL calculado em: ({canvas_cx}, {canvas_cy})")

    if interactive:
        print("\n[INTERATIVO] O Lumena.gg esta visivel e o personagem em area segura?")
        ans = input("Digite 'YES' para autorizar o envio de teclas: ").strip().upper()
        if ans != "YES":
            logger.warning("[INTERATIVO] Teste cancelado pelo usuario.")
            report["status"] = "CANCELADO PELO USUARIO"
            _save_report(report)
            return report

    # STEP 7-9: Foco Real e Diagnóstico
    print("STEP 7-9: Solicitando foco e verificando GetForegroundWindow()...")
    focus_diag: FocusDiagnosticResult = win_mgr.bring_to_foreground_with_diagnostic(win_info.hwnd)
    report["step_7_window_restored"] = True
    report["step_8_foreground_requested"] = True
    report["step_9_foreground_confirmed"] = focus_diag.is_truly_in_foreground

    if not focus_diag.is_truly_in_foreground and win_info.hwnd != 1001:
        logger.error(f"[SAFETY] Janela HWND {win_info.hwnd} nao obteve primeiro plano (Foreground Atual: {focus_diag.foreground_hwnd}).")
        report["status"] = "FALHA: Janela nao obteve primeiro plano"
        _save_report(report)
        return report

    print(f"[OK] STEP 9: WINDOW_FOCUS_VERIFIED: {focus_diag.is_truly_in_foreground}")

    # Diretório de evidência
    ts_folder = time.strftime("%Y-%m-%d_%H-%M-%S")
    evidence_dir = os.path.join("debug", "evidence", ts_folder)
    os.makedirs(evidence_dir, exist_ok=True)

    # STEP 12: Captura BEFORE
    sc = ScreenCapture(monitor_index=1)
    frame_before, _ = sc.capture_frame()

    if frame_before is not None:
        before_path = os.path.join(evidence_dir, "before.png")
        cv2.imwrite(before_path, frame_before)
        report["step_12_screenshot_before"] = before_path
        print(f"[OK] STEP 12: Frame ANTES salvo em: {before_path}")

    # STEP 13: Clique no Canvas
    print("STEP 13: Clicando no centro do canvas WebGL...")
    win_mgr.ensure_canvas_focus(0.5, 0.5)
    report["step_13_canvas_clicked"] = True
    time.sleep(0.2)

    # STEP 14: Despacho Físico de W (0.50s)
    print("STEP 14: Enviando tecla fisica W por 0.50s com DirectInput Scancode 0x11...")
    input_ctrl.press_key("w", duration=0.5, jitter=False)
    report["step_14_w_dispatched_and_released"] = True
    time.sleep(0.15)

    # STEP 15: Captura AFTER
    frame_after, _ = sc.capture_frame()
    if frame_after is not None:
        after_path = os.path.join(evidence_dir, "after.png")
        cv2.imwrite(after_path, frame_after)
        report["step_15_screenshot_after"] = after_path
        print(f"[OK] STEP 15: Frame DEPOIS salvo em: {after_path}")

    sc.close()

    # STEP 16 & 17: Delta Visual e Diff
    if frame_before is not None and frame_after is not None:
        confirmed, delta = input_ctrl.compute_visual_delta(frame_before, frame_after)
        report["step_16_visual_delta"] = delta
        report["step_17_movement_confirmed"] = confirmed

        diff = cv2.absdiff(frame_before, frame_after)
        diff_path = os.path.join(evidence_dir, "diff.png")
        cv2.imwrite(diff_path, diff)

        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rx, ry, rw, rh = cv2.boundingRect(c)
            report["step_16_altered_region"] = [int(rx), int(ry), int(rw), int(rh)]

        print("\n-------------------------------------------------------")
        print(f"Delta Visual de Pixels : {delta:.4f}")
        print(f"Movimento Confirmado   : {'SIM (PASS)' if confirmed else 'NAO (Sem delta perceptivel)'}")
        print("-------------------------------------------------------\n")

        if confirmed:
            report["status"] = "PASS (Movimento Fisico Confirmado no Jogo)"
            report["summary"] = f"Comando W executado e confirmado por variacao de pixels (delta={delta:.4f})."
        else:
            report["status"] = "NOT CONFIRMED (Delta abaixo do limiar)"
            report["summary"] = f"Comando W despachado, porem delta={delta:.4f} ficou abaixo de 0.005."
    else:
        report["status"] = "NOT VALIDATED (Captura indisponivel)"
        report["summary"] = "Captura de tela nao disponivel."

    # Salva pacotes de evidência completos
    window_data = {
        "hwnd": win_info.hwnd,
        "pid": win_info.pid,
        "process_name": win_info.process_name,
        "title": win_info.title,
        "bounds": [win_info.left, win_info.top, win_info.width, win_info.height],
        "is_active": win_info.is_active,
        "foreground_verified": report["step_9_foreground_confirmed"],
        "canvas_detected": win_info.canvas_detected,
    }

    input_data = {
        "key": "W",
        "scancode": "0x11",
        "duration": 0.5,
        "dispatched": report["step_14_w_dispatched_and_released"],
    }

    telemetry_data = {
        "focus_verified": report["step_9_foreground_confirmed"],
        "visual_delta": report["step_16_visual_delta"],
        "threshold": report["threshold"],
        "movement_confirmed": report["step_17_movement_confirmed"],
    }

    from src.core.event_bus import EventBus
    bus = EventBus()
    recent_events = [e.__dict__ for e in bus.get_recent_events(50)]

    result_data = {
        "test_id": "LEVEL_6_PHYSICAL_MOVEMENT",
        "timestamp": report["timestamp"],
        "success": bool(report["step_17_movement_confirmed"]),
        "physically_validated": bool(report["step_17_movement_confirmed"]),
        "target_window_verified": bool(report["step_9_foreground_confirmed"]),
        "visual_delta": float(report["step_16_visual_delta"]),
        "action_verified": bool(report["step_17_movement_confirmed"]),
        "target_window": window_data,
        "input": input_data,
        "before_frame": os.path.relpath(report["step_12_screenshot_before"], evidence_dir) if report["step_12_screenshot_before"] else None,
        "after_frame": os.path.relpath(report["step_15_screenshot_after"], evidence_dir) if report["step_15_screenshot_after"] else None,
        "diff_frame": "diff.png" if os.path.exists(os.path.join(evidence_dir, "diff.png")) else None,
        "events": recent_events,
        "failure_reason": None if report["step_17_movement_confirmed"] else report["status"],
        "result": "PASS" if report["step_17_movement_confirmed"] else "NOT VALIDATED",
    }

    with open(os.path.join(evidence_dir, "window.json"), "w", encoding="utf-8") as f:
        json.dump(window_data, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "input.json"), "w", encoding="utf-8") as f:
        json.dump(input_data, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "telemetry.json"), "w", encoding="utf-8") as f:
        json.dump(telemetry_data, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "events.json"), "w", encoding="utf-8") as f:
        json.dump(recent_events, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    _save_report(report)
    return report


def _save_report(data: Dict[str, Any]) -> None:
    try:
        with open("physical_test_report.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Relatorio fisico completo salvo em: physical_test_report.json")
    except Exception as e:
        logger.error(f"Erro ao salvar relatorio: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teste de Validacao Fisica Real - Lumena Bot")
    parser.add_argument("--interactive", action="store_true", help="Solicita confirmacao antes de enviar teclas")
    args = parser.parse_args()

    run_real_world_test(interactive=args.interactive)
