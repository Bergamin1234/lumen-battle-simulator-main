import os
import time
import json
import logging
from typing import Optional, Dict, Any
import cv2
import numpy as np

logger = logging.getLogger("LumenaEvidence")


def save_evidence_package(
    evidence_dir: Optional[str] = None,
    tag: str = "action",
    frame_before: Optional[np.ndarray] = None,
    frame_after: Optional[np.ndarray] = None,
    target_crop: Optional[np.ndarray] = None,
    annotated_frame: Optional[np.ndarray] = None,
    input_data: Optional[Dict[str, Any]] = None,
    window_data: Optional[Dict[str, Any]] = None,
    telemetry_data: Optional[Dict[str, Any]] = None,
    decision_data: Optional[Dict[str, Any]] = None,
    events_data: Optional[list] = None,
    execution_trace: Optional[list] = None,
    visual_delta: float = 0.0,
    action_name: str = "",
    target_type: str = "UNKNOWN",
    target_confidence: float = 0.0,
    input_dispatched: bool = False,
    foreground_verified: bool = False,
    target_window_verified: bool = False,
    action_verified: bool = False,
    failure_reason: str = "",
) -> str:
    """Gera pacote padronizado de evidências físicas e diagnóstico em debug/evidence/<timestamp>/."""
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    if not evidence_dir:
        evidence_dir = os.path.join("debug", "evidence", f"{ts}_{tag}")

    os.makedirs(evidence_dir, exist_ok=True)

    # 1. Salva frames
    if frame_before is not None:
        cv2.imwrite(os.path.join(evidence_dir, "before.png"), frame_before)

    if frame_after is not None:
        cv2.imwrite(os.path.join(evidence_dir, "after.png"), frame_after)

    if frame_before is not None and frame_after is not None:
        try:
            diff = cv2.absdiff(frame_before, frame_after)
            cv2.imwrite(os.path.join(evidence_dir, "diff.png"), diff)
        except Exception:
            pass

    if target_crop is not None and target_crop.size > 0:
        cv2.imwrite(os.path.join(evidence_dir, "target.png"), target_crop)

    if annotated_frame is not None and annotated_frame.size > 0:
        cv2.imwrite(os.path.join(evidence_dir, "annotated.png"), annotated_frame)

    # 2. Salva metadados JSON
    with open(os.path.join(evidence_dir, "input.json"), "w", encoding="utf-8") as f:
        json.dump(input_data or {}, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "window.json"), "w", encoding="utf-8") as f:
        json.dump(window_data or {}, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "telemetry.json"), "w", encoding="utf-8") as f:
        json.dump(telemetry_data or {}, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "decision.json"), "w", encoding="utf-8") as f:
        json.dump(decision_data or {}, f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "events.json"), "w", encoding="utf-8") as f:
        json.dump(events_data or [], f, indent=2, ensure_ascii=False)

    with open(os.path.join(evidence_dir, "execution_trace.json"), "w", encoding="utf-8") as f:
        json.dump(execution_trace or [], f, indent=2, ensure_ascii=False)

    # 3. Salva result.json padronizado (Regra #22)
    visual_change = visual_delta >= 0.005
    physical_verified = bool(
        target_window_verified
        and foreground_verified
        and input_dispatched
        and visual_change
        and action_verified
    )

    result_payload = {
        "action_requested": True,
        "input_dispatched": bool(input_dispatched),
        "action_verified": bool(action_verified),
        "physically_validated": bool(physical_verified),
        "target_window_verified": bool(target_window_verified),
        "foreground_verified": bool(foreground_verified),
        "visual_change_detected": bool(visual_change),
        "visual_delta": round(float(visual_delta), 4),
        "physical_execution_verified": bool(physical_verified),
        "target_type": str(target_type),
        "target_confidence": round(float(target_confidence), 2),
        "action": str(action_name),
        "failure_reason": str(failure_reason) if not physical_verified else "",
        "timestamp": ts,
    }

    with open(os.path.join(evidence_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2, ensure_ascii=False)

    logger.debug(f"Pacote de evidência completo salvo em: {evidence_dir}")
    return evidence_dir
