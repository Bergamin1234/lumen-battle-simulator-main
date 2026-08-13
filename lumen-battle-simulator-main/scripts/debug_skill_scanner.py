import os
import sys
import argparse
import logging

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from src.perception.debug_skill_scanner import run_debug_skill_scan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug Skill Scanner — Lumena Bot")
    parser.add_argument("--output", type=str, default=None, help="Diretório de saída personalizado")
    args = parser.parse_args()

    print("\n=======================================================")
    print("      LUMENA BOT — DEBUG SKILL SCANNER (N SLOTS)")
    print("=======================================================\n")

    res = run_debug_skill_scan(output_dir=args.output)
    print(f"[OK] Slots Detectados : {res['detected_slots']}")
    print(f"[OK] Screenshot       : {res['screenshot_path']}")
    print(f"[OK] Anotado          : {res['annotated_path']}")
    print(f"[OK] JSON             : {res['json_path']}")
    print("\nResumo das Habilidades:")
    for s in res["skills"]["skills"]:
        stat = "READY" if s["available"] else f"CD {s['cooldown']:.1f}s"
        hk = str(s["hotkey"]) if s["hotkey"] is not None else "?"
        cx = s["position"]["center_x"]
        cy = s["position"]["center_y"]
        print(f"  • #{s['index']:<2} | Hotkey: {hk:<2} | Status: {stat:<10} | Tipo: {s['range_type']} | Elemento: {s['element']} | Coords: ({cx}, {cy})")
    print("\n=======================================================\n")
