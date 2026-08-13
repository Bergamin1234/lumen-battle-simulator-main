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

# Configura codificação de saída para UTF-8 de forma segura
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RealWorldTest")

from src.input.target_window import TargetWindowManager, WindowInfo, FocusDiagnosticResult
from src.input.input_controller import InputController
from src.perception.screen_capture import ScreenCapture


def run_real_world_test(interactive: bool = False) -> Dict[str, Any]:
    print("\n=======================================================")
    print("   LUMENA BOT - TESTE DE VALIDACAO FISICA REAL (17 ETAPAS)")
    print("=======================================================\n")

    report: Dict[str, Any] = {
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

    # STEP 3 & 4 & 5: Enumeração e Localização de Janela
    print("STEP 3-5: Enumerando janelas do sistema e buscando Chrome / Lumena.gg...")
    win_info: Optional[WindowInfo] = win_mgr.find_target_window()
    report["step_3_window_enumeration"] = True

    if not win_info:
        logger.warning("[SAFETY] Nenhuma janela compativel com 'Lumena.gg' ou 'Chrome' foi encontrada.")
        logger.warning("[SAFETY] Teste fisico pausado para seguranca do desktop.")
        print("\n-------------------------------------------------------")
        print("RESULTADO: NAO VALIDADO (Abra o Lumena.gg no Chrome antes de testar)")
        print("-------------------------------------------------------\n")
        report["summary"] = "Navegador com o jogo nao esta aberto. Teste nao executado para evitar injecao incorreta."
        _save_report(report)
        return report

    report["step_4_chrome_found"] = True
    report["step_5_lumena_identified"] = ("lumena" in win_info.title.lower())
    report["step_6_hwnd"] = win_info.hwnd
    report["step_10_client_area"] = [win_info.left, win_info.top, win_info.width, win_info.height]

    print(f"[OK] STEP 4-6: Janela Alvo Encontrada: '{win_info.title}' (HWND: {win_info.hwnd}, PID: {win_info.pid})")
    print(f"               Area Util: {win_info.width}x{win_info.height} na posicao ({win_info.left}, {win_info.top})")

    # STEP 11: Região do Canvas (estimativa central padrão WebGL)
    canvas_cx = win_info.left + win_info.width // 2
    canvas_cy = win_info.top + win_info.height // 2
    report["step_11_canvas_region"] = [win_info.left, win_info.top + 80, win_info.width, win_info.height - 80]
    print(f"[OK] STEP 11: Centro do Canvas WebGL calculado em: ({canvas_cx}, {canvas_cy})")

    # Prompt no modo interativo
    if interactive:
        print("\n[INTERATIVO] O Lumena.gg esta visivel na tela e o personagem em area segura?")
        ans = input("Digite 'YES' para autorizar o teste fisico ou qualquer outra tecla para cancelar: ").strip().upper()
        if ans != "YES":
            logger.warning("[INTERATIVO] Teste cancelado pelo usuario.")
            report["status"] = "CANCELADO PELO USUARIO"
            _save_report(report)
            return report

    # STEP 7 & 8 & 9: Restauração, Primeiro Plano e Confirmação
    print("STEP 7-9: Restaurando janela e trazendo para primeiro plano...")
    focus_diag: FocusDiagnosticResult = win_mgr.bring_to_foreground_with_diagnostic(win_info.hwnd)
    report["step_7_window_restored"] = True
    report["step_8_foreground_requested"] = True
    report["step_9_foreground_confirmed"] = focus_diag.is_truly_in_foreground

    if not focus_diag.is_truly_in_foreground:
        logger.error(f"[SAFETY] Janela HWND {win_info.hwnd} nao pode obter primeiro plano.")
        report["status"] = "FALHA: Janela nao obteve primeiro plano"
        _save_report(report)
        return report

    print(f"[OK] STEP 9: Primeiro Plano Confirmado: {focus_diag.is_truly_in_foreground}")

    # STEP 12: Captura de Tela BEFORE
    os.makedirs("debug", exist_ok=True)
    sc = ScreenCapture(monitor_index=1)
    frame_before, _ = sc.capture_frame()

    if frame_before is not None:
        before_path = f"debug/{time.strftime('%Y-%m-%d_%H-%M-%S')}_before.png"
        cv2.imwrite(before_path, frame_before)
        report["step_12_screenshot_before"] = before_path
        print(f"[OK] STEP 12: Frame ANTES salvo em: {before_path}")

    # STEP 13: Foco no Canvas via Clique
    print("STEP 13: Clicando cuidadosamente no centro do canvas...")
    win_mgr.ensure_canvas_focus(0.5, 0.5)
    report["step_13_canvas_clicked"] = True
    time.sleep(0.2)

    # STEP 14: Envio Físico de W (0.5s) e Liberação
    print("STEP 14: Enviando comando fisico W por 0.50s com Win32 Scancode 0x11...")
    input_ctrl.press_key("w", duration=0.5, jitter=False)
    report["step_14_w_dispatched_and_released"] = True
    time.sleep(0.15)

    # STEP 15: Captura de Tela AFTER
    frame_after, _ = sc.capture_frame()
    if frame_after is not None:
        after_path = f"debug/{time.strftime('%Y-%m-%d_%H-%M-%S')}_after.png"
        cv2.imwrite(after_path, frame_after)
        report["step_15_screenshot_after"] = after_path
        print(f"[OK] STEP 15: Frame DEPOIS salvo em: {after_path}")

    sc.close()

    # STEP 16 & 17: Comparação e Cálculo de Delta Visual
    if frame_before is not None and frame_after is not None:
        confirmed, delta = input_ctrl.compute_visual_delta(frame_before, frame_after)
        report["step_16_visual_delta"] = delta
        report["step_17_movement_confirmed"] = confirmed

        # Calcula bounding box da região alterada
        diff = cv2.absdiff(frame_before, frame_after)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rx, ry, rw, rh = cv2.boundingRect(c)
            report["step_16_altered_region"] = [int(rx), int(ry), int(rw), int(rh)]

        print("\n-------------------------------------------------------")
        print(f"Delta Visual de Pixels Calculado : {delta:.4f}")
        print(f"Movimento Fisico Confirmado      : {'SIM (PASS)' if confirmed else 'NAO (Sem alteracao no frame)'}")
        print("-------------------------------------------------------\n")

        if confirmed:
            report["status"] = "PASS (Movimento Fisico Confirmado no Jogo)"
            report["summary"] = f"Comando W executado e confirmado por alteracao visual (delta={delta:.4f})."
        else:
            report["status"] = "NOT CONFIRMED (Sem delta visual perceptivel)"
            report["summary"] = f"Comando W despachado, porem o delta de pixels ({delta:.4f}) ficou abaixo do limiar (0.005)."
    else:
        report["status"] = "NOT VALIDATED (Captura de tela indisponivel)"
        report["summary"] = "Captura de tela nao pode ser obtida na sessao atual."

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
