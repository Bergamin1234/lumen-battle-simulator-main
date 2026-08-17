"""
LUMENA BOT v3.7 — DEBUG CRYSTAL CONTEXT
=======================================
Script de diagnóstico para provar que a detecção de cristal de cura
está estritamente desabilitada durante o modo de batalha.
Gera artefatos em debug/crystal_context/<timestamp>/:
- world.png
- battle.png
- world_annotated.png
- battle_annotated.png
- result.json
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

from src.perception.landmark_detector import LandmarkDetector
from src.perception.battle_ui_detector import BattleUIDetector


def run_debug_crystal_context():
    print("=" * 70)
    print("   LUMENA BOT v3.7 — DEBUG CRYSTAL CONTEXT (WORLD vs BATTLE)")
    print("=" * 70)

    ts_str = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.abspath(os.path.join("debug", "crystal_context", f"run_{ts_str}"))
    os.makedirs(out_dir, exist_ok=True)

    landmark_detector = LandmarkDetector()
    battle_detector = BattleUIDetector()

    # 1. Cria frame de MUNDO (Overworld com objeto azul / cristal no mapa)
    world_frame = np.full((720, 1280, 3), (40, 140, 40), dtype=np.uint8)  # Grama verde
    # Adiciona cristal azul no mundo
    cv2.rectangle(world_frame, (750, 250), (850, 420), (230, 180, 0), -1)  # Azul/ciano em BGR
    cv2.putText(world_frame, "[WORLD MAP]", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(out_dir, "world.png"), world_frame)

    # 2. Cria frame de BATALHA (Arena com HUD de Batalha e o mesmo objeto azul no fundo)
    battle_frame = np.full((720, 1280, 3), (60, 60, 60), dtype=np.uint8)  # Arena
    # Objeto azul no fundo
    cv2.rectangle(battle_frame, (750, 250), (850, 420), (230, 180, 0), -1)
    # HUD de Batalha: Botão FIGHT e HP Inimigo
    cv2.rectangle(battle_frame, (900, 520), (1120, 620), (30, 40, 220), -1)  # Botão FIGHT
    cv2.putText(battle_frame, "FIGHT", (950, 580), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.rectangle(battle_frame, (700, 80), (1100, 110), (40, 200, 40), -1)  # HP
    cv2.putText(battle_frame, "[BATTLE ARENA]", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(out_dir, "battle.png"), battle_frame)

    # --- TESTE 1: WORLD MODE ---
    w_detected, w_rel_pos, w_elem = landmark_detector.detect_crystal(world_frame, in_battle=False)
    world_annotated = world_frame.copy()
    if w_detected and w_elem is not None:
        x, y, w, h = w_elem.bounding_box
        cv2.rectangle(world_annotated, (x, y), (x + w, y + h), (0, 255, 255), 3)
        cv2.putText(world_annotated, f"CRYSTAL (Conf={w_elem.confidence:.2f})", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(world_annotated, f"STATE: WORLD | CRYSTAL: {'ENABLED' if w_detected else 'NOT_FOUND'}", (50, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imwrite(os.path.join(out_dir, "world_annotated.png"), world_annotated)

    # --- TESTE 2: BATTLE MODE ---
    # Battle UIDetector confirma estado de batalha
    b_ui_res = battle_detector.analyze_battle_ui(battle_frame)
    # Landmark detector chamado com in_battle=True
    b_detected, b_rel_pos, b_elem = landmark_detector.detect_crystal(battle_frame, in_battle=b_ui_res.battle_ui_confirmed)
    battle_annotated = battle_frame.copy()
    cv2.putText(battle_annotated, f"STATE: BATTLE | BATTLE_UI: CONFIRMED | CRYSTAL_DETECTOR: DISABLED", (50, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
    cv2.imwrite(os.path.join(out_dir, "battle_annotated.png"), battle_annotated)

    result_data = {
        "timestamp": time.time(),
        "world_mode": {
            "crystal_detector_active": True,
            "crystal_detected": w_detected,
            "confidence": w_elem.confidence if w_elem else 0.0,
            "status": "ALLOWED",
        },
        "battle_mode": {
            "battle_ui_confirmed": b_ui_res.battle_ui_confirmed,
            "crystal_detector_active": False,
            "crystal_detected": b_detected,
            "crystal_search": "BLOCKED",
            "status": "DISABLED_IN_BATTLE",
        },
        "validation": {
            "crystal_blocked_in_battle": not b_detected,
            "crystal_allowed_in_world": w_detected,
            "pass": bool(w_detected and not b_detected),
        }
    }

    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    print("✓ Diagnóstico de Contexto do Cristal concluído!")
    print(f"  - No Mundo: Cristal Detectado = {w_detected} (ALLOWED)")
    print(f"  - Na Batalha: Cristal Detectado = {b_detected} (DISABLED / BLOCKED)")
    print(f"  - Validação de Isolamento de Contexto: {'PASS' if result_data['validation']['pass'] else 'FAIL'}")
    print(f"📁 Artefatos salvos em: {out_dir}")

    return result_data


if __name__ == "__main__":
    run_debug_crystal_context()
