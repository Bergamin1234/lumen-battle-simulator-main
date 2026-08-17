import os
import time
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import cv2

from src.models.combat_vision import SkillSlot
from src.perception.screen_capture import ScreenCapture
from src.perception.combat_vision import CombatVisionAnalyzer

logger = logging.getLogger("LumenaSkillScanner")


def run_debug_skill_scan(
    frame: Optional[np.ndarray] = None,
    output_dir: Optional[str] = None,
    in_battle: bool = True,
) -> Dict[str, Any]:
    """Captura ou recebe o frame atual, detecta N slots de habilidades visualmente,

    anota as caixas/centros/cooldowns e salva o pacote completo em debug/skill_scanner/<timestamp>/.
    """
    ts_str = time.strftime("%Y-%m-%d_%H-%M-%S")
    target_dir = output_dir or os.path.join("debug", "skill_scanner", ts_str)
    os.makedirs(target_dir, exist_ok=True)

    analyzer = CombatVisionAnalyzer()

    if frame is None:
        sc = ScreenCapture(monitor_index=1)
        captured_frame, _ = sc.capture_frame()
        sc.close()
    else:
        captured_frame = frame

    if captured_frame is None or captured_frame.size == 0:
        # Cria frame sintético se não houver display ativo
        captured_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # 1. Salva screenshot original
    raw_path = os.path.join(target_dir, "screenshot.png")
    cv2.imwrite(raw_path, captured_frame)

    # 2. Executa a detecção visual de N slots estritamente em combate
    detected_skills: List[SkillSlot] = analyzer.detect_skill_slots(captured_frame, in_battle=in_battle)

    # 3. Cria a imagem anotada com overlays visuais
    annotated = captured_frame.copy()
    h, w = annotated.shape[:2]

    # Região de interesse analisada
    roi_top = int(h * 0.65)
    roi_bottom = int(h * 0.96)
    roi_left = int(w * 0.15)
    roi_right = int(w * 0.85)
    cv2.rectangle(annotated, (roi_left, roi_top), (roi_right, roi_bottom), (100, 100, 255), 2)
    cv2.putText(annotated, "ANALYZED SKILL BAR ROI", (roi_left + 10, roi_top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

    skills_json_list = []

    for s in detected_skills:
        # Bounding box
        color = (0, 255, 0) if s.available else (0, 165, 255)
        cv2.rectangle(annotated, (s.screen_x, s.screen_y), (s.screen_x + s.width, s.screen_y + s.height), color, 2)
        # Centro
        cv2.circle(annotated, (s.center_x, s.center_y), 4, (0, 0, 255), -1)

        # Labels
        status_text = f"#{s.index} [{s.hotkey or '?'}] {'READY' if s.available else f'CD {s.cooldown:.1f}s'}"
        cv2.putText(annotated, status_text, (s.screen_x, s.screen_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        skills_json_list.append({
            "index": s.index,
            "slot_id": s.id,
            "hotkey": s.hotkey,
            "available": s.available,
            "disabled": s.disabled,
            "cooldown": s.cooldown,
            "cooldown_ratio": s.cooldown_ratio,
            "cooldown_remaining": s.cooldown_remaining,
            "element": s.element.name if s.element else "NORMAL",
            "power": s.power,
            "range_type": s.range_type,
            "confidence": s.confidence,
            "position": {
                "screen_x": s.screen_x,
                "screen_y": s.screen_y,
                "width": s.width,
                "height": s.height,
                "center_x": s.center_x,
                "center_y": s.center_y,
            }
        })

    annotated_path = os.path.join(target_dir, "annotated.png")
    cv2.imwrite(annotated_path, annotated)

    skills_doc = {
        "timestamp": ts_str,
        "detected_slots": len(detected_skills),
        "roi": {"left": roi_left, "top": roi_top, "width": roi_right - roi_left, "height": roi_bottom - roi_top},
        "skills": skills_json_list,
    }

    json_path = os.path.join(target_dir, "skills.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(skills_doc, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ [SKILL SCANNER] Escaneamento concluído: {len(detected_skills)} slots detectados. Evidências salvas em: {target_dir}")
    return {
        "output_dir": target_dir,
        "screenshot_path": raw_path,
        "annotated_path": annotated_path,
        "json_path": json_path,
        "detected_slots": len(detected_skills),
        "skills": skills_doc,
    }
