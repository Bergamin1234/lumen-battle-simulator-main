"""
LUMENA BOT v3.7 — DEBUG BATTLE UI
=================================
Script de diagnóstico visual dedicado à detecção de interface de combate.
Gera artefatos em debug/battle_ui/<timestamp>/ com anotações semânticas:
- VERDE: FIGHT
- AZUL: TEAM
- AMARELO: BAG
- VERMELHO: RUN
- MAGENTA: ENEMY HP
"""

import os
import sys
import time
import json
import numpy as np
import cv2

# Configura path raiz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.perception.screen_capture import ScreenCapture
from src.perception.battle_ui_detector import BattleUIDetector


def run_debug_battle_ui():
    print("=" * 70)
    print("   LUMENA BOT v3.7 — DEBUG BATTLE UI DIAGNOSTIC")
    print("=" * 70)

    ts_str = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.abspath(os.path.join("debug", "battle_ui", f"run_{ts_str}"))
    os.makedirs(out_dir, exist_ok=True)

    cap = ScreenCapture()
    frame, _ = cap.capture_frame()

    if frame is None or frame.size == 0:
        print("⚠️ Tela vazia ou monitor inativo. Gerando frame sintético de demonstração...")
        frame = np.full((720, 1280, 3), 30, dtype=np.uint8)
        # Desenha elementos de batalha simulados
        # FIGHT (Verde/Vermelho botão)
        cv2.rectangle(frame, (900, 520), (1100, 600), (40, 50, 200), -1)
        cv2.putText(frame, "FIGHT", (940, 565), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        # ENEMY HP
        cv2.rectangle(frame, (700, 80), (1050, 110), (40, 180, 40), -1)

    cv2.imwrite(os.path.join(out_dir, "frame.png"), frame)

    detector = BattleUIDetector()
    result = detector.analyze_battle_ui(frame)

    annotated = frame.copy()

    # Cores BGR
    COLOR_FIGHT = (0, 255, 0)      # GREEN
    COLOR_TEAM = (255, 100, 0)     # BLUE
    COLOR_BAG = (0, 220, 255)      # YELLOW
    COLOR_RUN = (0, 0, 255)        # RED
    COLOR_ENEMY_HP = (255, 0, 255) # MAGENTA

    color_map = {
        "FIGHT": COLOR_FIGHT,
        "TEAM": COLOR_TEAM,
        "BAG": COLOR_BAG,
        "RUN": COLOR_RUN,
        "ENEMY_HP": COLOR_ENEMY_HP,
    }

    detections_data = {
        "timestamp": result.timestamp,
        "battle_ui_confirmed": result.battle_ui_confirmed,
        "battle_ui_score": result.battle_ui_score,
        "skill_menu_open": result.skill_menu_open,
        "elements": {},
    }

    for name, elem in result.elements.items():
        detections_data["elements"][name] = {
            "present": elem.is_present,
            "bbox": list(elem.bbox),
            "center": list(elem.center),
            "confidence": round(elem.confidence, 3),
        }
        if elem.is_present and elem.bbox != (0, 0, 0, 0):
            col = color_map.get(name, (200, 200, 200))
            x, y, w, h = elem.bbox
            cv2.rectangle(annotated, (x, y), (x + w, y + h), col, 2)
            cv2.circle(annotated, elem.center, 4, col, -1)
            lbl = f"{name} ({elem.confidence:.2f})"
            cv2.putText(annotated, lbl, (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)

    # Info HUD superior
    cv2.rectangle(annotated, (10, 10), (450, 80), (0, 0, 0), -1)
    cv2.putText(annotated, f"BATTLE UI: {'CONFIRMED' if result.battle_ui_confirmed else 'INACTIVE'}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(annotated, f"SCORE: {result.battle_ui_score:.2f} | SKILLS OPEN: {result.skill_menu_open}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    cv2.imwrite(os.path.join(out_dir, "annotated.png"), annotated)

    with open(os.path.join(out_dir, "detections.json"), "w", encoding="utf-8") as f:
        json.dump(detections_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Diagnóstico Battle UI concluído com sucesso!")
    print(f"  - Battle UI Confirmada: {result.battle_ui_confirmed}")
    print(f"  - Score: {result.battle_ui_score}")
    print(f"  - Botão FIGHT Presente: {result.fight_button.is_present if result.fight_button else False}")
    print(f"📁 Artefatos salvos em: {out_dir}")

    return detections_data


if __name__ == "__main__":
    run_debug_battle_ui()
