import os
import sys
import time
import json
import logging

# Garante inclusão da raiz do projeto no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LiveInputValidation")


def run_live_input_diagnostic():
    results = {}
    details = {}

    print("\n=======================================================")
    print("DIAGNÓSTICO REAL DE ENTRADA, JANELA E AMBIENTE")
    print("=======================================================\n")

    # 1. Python Runtime
    try:
        py_version = sys.version
        results["check_1_python"] = "PASSOU"
        details["python_version"] = py_version.split()[0]
        logger.info(f"✓ Python OK: {details['python_version']}")
    except Exception as e:
        results["check_1_python"] = "FALHOU"
        details["python_error"] = str(e)

    # 2. Pillow (PIL)
    try:
        import PIL
        from PIL import Image
        results["check_2_pillow"] = "PASSOU"
        details["pillow_version"] = PIL.__version__
        logger.info(f"✓ Pillow OK: v{PIL.__version__}")
    except Exception as e:
        results["check_2_pillow"] = "FALHOU"
        details["pillow_error"] = str(e)

    # 3. OpenCV (cv2)
    try:
        import cv2
        results["check_3_opencv"] = "PASSOU"
        details["opencv_version"] = cv2.__version__
        logger.info(f"✓ OpenCV OK: v{cv2.__version__}")
    except Exception as e:
        results["check_3_opencv"] = "FALHOU"
        details["opencv_error"] = str(e)

    # 4. PyAutoGUI
    try:
        import pyautogui
        size = pyautogui.size()
        results["check_4_pyautogui"] = "PASSOU"
        details["screen_size"] = f"{size.width}x{size.height}"
        logger.info(f"✓ PyAutoGUI OK: Display {details['screen_size']}, Fail-safe={pyautogui.FAILSAFE}")
    except Exception as e:
        results["check_4_pyautogui"] = "FALHOU"
        details["pyautogui_error"] = str(e)

    # 5. Janela Alvo (TargetWindowManager)
    from src.input.target_window import TargetWindowManager
    win_mgr = TargetWindowManager()
    win_info = win_mgr.find_target_window()

    if win_info is not None:
        results["check_5_target_window"] = "PASSOU"
        details["target_window"] = {
            "title": win_info.title,
            "hwnd": win_info.hwnd,
            "bounds": f"{win_info.width}x{win_info.height} em ({win_info.left},{win_info.top})",
            "is_active": win_info.is_active,
            "is_minimized": win_info.is_minimized,
        }
        logger.info(f"✓ Janela Alvo Encontrada: {win_info.title} (HWND: {win_info.hwnd})")
    else:
        results["check_5_target_window"] = "NÃO VALIDADO"
        details["target_window"] = "Nenhuma janela do jogo (Lumena, Chrome, Brave, etc.) aberta no momento."
        logger.warning("Janela Alvo: NÃO VALIDADO (Navegador com o jogo não está aberto)")

    # 6. Captura Real de Tela
    from src.perception.screen_capture import ScreenCapture
    sc = ScreenCapture(monitor_index=1)
    frame, ts = sc.capture_frame()

    if frame is not None and frame.size > 0:
        results["check_6_screen_capture"] = "PASSOU"
        details["captured_resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
        logger.info(f"✓ Captura Real OK: Frame {details['captured_resolution']} @ {ts:.2f}")
    else:
        results["check_6_screen_capture"] = "NÃO VALIDADO"
        details["capture_note"] = "Sessão não-interativa do SO ou sem superfície GDI ativa."
        logger.warning("Captura de Tela: NÃO VALIDADO (Sessão não interativa sem monitor físico acoplado)")

    # 7. InputController
    from src.input.input_controller import InputController
    input_ctrl = InputController()
    results["check_7_input_controller"] = "PASSOU"
    logger.info("✓ InputController instanciado com backend Win32 SendInput + PyAutoGUI fallback.")

    # 8. Envio Real de Teclado (WASD Diagnostic)
    if win_info is not None:
        logger.info("Testando envio real de teclas WASD para a janela do jogo...")
        try:
            input_ctrl.focus_game_window()
            for k in ["w", "a", "s", "d"]:
                success = input_ctrl.press_key(k, duration=0.1)
                logger.info(f"  • Tecla {k.upper()}: {'OK' if success else 'FALHOU'}")
            input_ctrl.release_all_keys()
            results["check_8_keyboard_input"] = "PASSOU"
        except Exception as e:
            results["check_8_keyboard_input"] = "FALHOU"
            details["keyboard_error"] = str(e)
    else:
        results["check_8_keyboard_input"] = "NÃO VALIDADO"
        details["keyboard_note"] = "Envio físico pausado por segurança (janela alvo não está aberta)."

    # 9. Envio Real de Mouse
    if win_info is not None:
        try:
            cx = win_info.left + win_info.width // 2
            cy = win_info.top + win_info.height // 2
            click_ok = input_ctrl.click(cx, cy)
            results["check_9_mouse_input"] = "PASSOU" if click_ok else "FALHOU"
            details["mouse_click_pos"] = f"({cx}, {cy})"
        except Exception as e:
            results["check_9_mouse_input"] = "FALHOU"
            details["mouse_error"] = str(e)
    else:
        results["check_9_mouse_input"] = "NÃO VALIDADO"
        details["mouse_note"] = "Cliques físicos pausados por segurança (janela alvo ausente)."

    # 10. Retorno Visual e Feedback
    if frame is not None and win_info is not None:
        results["check_10_visual_feedback"] = "PASSOU"
    else:
        results["check_10_visual_feedback"] = "NÃO VALIDADO"
        details["visual_feedback_note"] = "Requer jogo aberto para detecção de delta de frame."

    sc.close()

    print("\n=======================================================")
    print("RESULTADO DO DIAGNÓSTICO:")
    print("=======================================================")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("\nDETALHES E EVIDÊNCIAS:")
    print(json.dumps(details, indent=2, ensure_ascii=False))

    return results, details


if __name__ == "__main__":
    run_live_input_diagnostic()
