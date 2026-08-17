"""
LUMENA BOT CONTROL CENTER v4.3 — REAL-TIME CANVAS INSPECTOR & CALIBRATION OVERLAY
================================================================================
Renderizador visual de calibração em tempo real que projeta todas as ROIs dinâmicas,
limites de Canvas WebGL, barras de HP, botões de combate e trajetórias Bézier
sobre o feed capturado da janela do Chrome.
"""

from typing import Tuple, List, Dict, Any, Optional
import cv2
import numpy as np


class CanvasInspectorOverlay:
    """Projetor visual de calibração em tempo real para inspeção de ROIs e trajetórias."""

    # Cores BGR para as ROIs
    COLOR_CANVAS = (50, 220, 50)       # Verde Claro: Área útil sem letterbox
    COLOR_FIGHT = (235, 130, 40)       # Azul: Botão de Combate FIGHT
    COLOR_SKILLS = (30, 215, 255)      # Amarelo: Slots de Habilidades
    COLOR_PLAYER_HP = (220, 200, 30)   # Ciano: Barra de Vida do Jogador
    COLOR_ENEMY_HP = (30, 140, 255)    # Laranja: Barra de Vida do Inimigo
    COLOR_MODAL = (200, 50, 220)       # Magenta: Área de Modais / Diálogos
    COLOR_BEZIER = (0, 0, 255)         # Vermelho: Curva Bézier
    COLOR_BEZIER_NODE = (0, 255, 0)    # Verde: Nós de controle P0, P1, P2, P3

    def __init__(self) -> None:
        self.fine_tuning_params: Dict[str, float] = {
            "match_threshold": 0.70,
            "hsv_tolerance": 20.0,
            "letterbox_thresh": 15.0,
            "hp_temporal_history": 3.0,
        }

    def update_param(self, key: str, value: float) -> None:
        """Atualiza dinamicamente parâmetros de calibração em tempo de execução."""
        if key in self.fine_tuning_params:
            self.fine_tuning_params[key] = float(value)

    def get_param(self, key: str, default: float = 0.0) -> float:
        return self.fine_tuning_params.get(key, default)

    def project_rois_to_frame(
        self,
        frame: np.ndarray,
        canvas_bounds: Optional[Tuple[int, int, int, int]] = None,
        is_letterboxed: bool = False,
        fight_bbox: Optional[Tuple[int, int, int, int]] = None,
        skill_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
        player_hp_bbox: Optional[Tuple[int, int, int, int]] = None,
        enemy_hp_bbox: Optional[Tuple[int, int, int, int]] = None,
        modal_bbox: Optional[Tuple[int, int, int, int]] = None,
        bezier_points: Optional[List[Tuple[int, int]]] = None,
    ) -> np.ndarray:
        """Renderiza todas as caixas delimitadoras e vetores de movimento sobre uma cópia do frame."""
        if frame is None or frame.size == 0:
            return np.zeros((720, 1280, 3), dtype=np.uint8)

        annotated = frame.copy()
        h, w = annotated.shape[:2]
        cb = canvas_bounds if canvas_bounds else (0, 0, w, h)
        cx, cy, cw, ch = cb

        # 1. Desenha Borda do Canvas WebGL Útil
        cv2.rectangle(annotated, (cx, cy), (cx + cw, cy + ch), self.COLOR_CANVAS, 2)
        lb_tag = "LETTERBOX: ON" if is_letterboxed else "LETTERBOX: OFF"
        cv2.putText(annotated, f"CANVAS [{cw}x{ch}] - {lb_tag}", (cx + 8, cy + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.COLOR_CANVAS, 2)

        # 2. Desenha ROI do Botão FIGHT
        if fight_bbox:
            fx, fy, fw, fh = fight_bbox
            cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), self.COLOR_FIGHT, 2)
            cv2.putText(annotated, "[FIGHT]", (fx, fy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_FIGHT, 2)

        # 3. Desenha Slots de Habilidades
        if skill_bboxes:
            for idx, (sx, sy, sw, sh) in enumerate(skill_bboxes, start=1):
                cv2.rectangle(annotated, (sx, sy), (sx + sw, sy + sh), self.COLOR_SKILLS, 2)
                cv2.putText(annotated, f"[SKILL #{idx}]", (sx, sy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_SKILLS, 1)

        # 4. Desenha Barras de HP
        if player_hp_bbox:
            px, py, pw, ph = player_hp_bbox
            cv2.rectangle(annotated, (px, py), (px + pw, py + ph), self.COLOR_PLAYER_HP, 2)
            cv2.putText(annotated, "[PLAYER HP]", (px, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_PLAYER_HP, 1)

        if enemy_hp_bbox:
            ex, ey, ew, eh = enemy_hp_bbox
            cv2.rectangle(annotated, (ex, ey), (ex + ew, ey + eh), self.COLOR_ENEMY_HP, 2)
            cv2.putText(annotated, "[ENEMY HP]", (ex, ey - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_ENEMY_HP, 1)

        # 5. Desenha Modal Detection ROI
        if modal_bbox:
            mx, my, mw, mh = modal_bbox
            cv2.rectangle(annotated, (mx, my), (mx + mw, my + mh), self.COLOR_MODAL, 2)
            cv2.putText(annotated, "[POST-BATTLE MODAL]", (mx, my - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_MODAL, 1)

        # 6. Renderiza Trajetória Bézier Cúbica e Nós
        if bezier_points and len(bezier_points) >= 2:
            for i in range(len(bezier_points) - 1):
                p_start = bezier_points[i]
                p_end = bezier_points[i + 1]
                cv2.line(annotated, p_start, p_end, self.COLOR_BEZIER, 2)

            # Nós P0 e P3
            cv2.circle(annotated, bezier_points[0], 5, self.COLOR_BEZIER_NODE, -1)
            cv2.circle(annotated, bezier_points[-1], 5, self.COLOR_BEZIER_NODE, -1)

        return annotated
