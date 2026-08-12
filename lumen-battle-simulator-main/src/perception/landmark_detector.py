import logging
from typing import Optional, Tuple, Dict, List
import cv2
import numpy as np
from src.models.lumen import UIElement


class LandmarkDetector:
    """Detector de marcos visuais no mapa (Cristal Azul de Cura, Portais, Postes, Entradas)."""

    def __init__(
        self,
        crystal_hsv_lower: Optional[np.ndarray] = None,
        crystal_hsv_upper: Optional[np.ndarray] = None,
        templates: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        # Intervalo HSV para o Cristal Azul Luminoso (Ciano/Azul elétrico)
        self.crystal_lower = crystal_hsv_lower if crystal_hsv_lower is not None else np.array([85, 80, 120])
        self.crystal_upper = crystal_hsv_upper if crystal_hsv_upper is not None else np.array([135, 255, 255])
        self.templates = templates or {}

    def detect_crystal(
        self,
        frame: Optional[np.ndarray],
    ) -> Tuple[bool, Optional[Tuple[int, int]], Optional[UIElement]]:
        """
        Detecta o Cristal Azul de Cura no cenário.
        Retorna:
        - crystal_detected: bool
        - relative_vector: (dx, dy) relativo ao centro da tela (onde dx > 0 = direita, dy > 0 = abaixo)
        - ui_element: UIElement com bounding box e confiança
        """
        if frame is None or frame.size == 0:
            return False, None, None

        try:
            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2

            # 1. Busca por template se disponível
            if "blue_crystal.png" in self.templates:
                tmpl = self.templates["blue_crystal.png"]
                th, tw = tmpl.shape[:2]
                if th <= h and tw <= w:
                    res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= 0.70:
                        bx, by = max_loc
                        cx = bx + tw // 2
                        cy = by + th // 2
                        elem = UIElement(
                            name="blue_crystal",
                            bounding_box=(bx, by, tw, th),
                            confidence=float(max_val),
                            center=(cx, cy),
                        )
                        return True, (cx - center_x, cy - center_y), elem

            # 2. Segmentação HSV do Cristal Azul Luminoso
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.crystal_lower, self.crystal_upper)

            # Limpeza morfológica
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = 50
            max_area = (w * h) * 0.15  # Cristal não ocupa mais que 15% da tela

            valid_crystals: List[Tuple[float, Tuple[int, int, int, int], Tuple[int, int]]] = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect_ratio = bh / max(1, bw)
                    # Cristais costumam ser ligeiramente verticais ou quadrados
                    if 0.5 <= aspect_ratio <= 3.0:
                        cx = x + bw // 2
                        cy = y + bh // 2
                        confidence = min(1.0, 0.60 + (area / 1000.0) * 0.35)
                        valid_crystals.append((confidence, (x, y, bw, bh), (cx, cy)))

            if valid_crystals:
                # Escolhe o cristal com maior confiança
                best_conf, best_bbox, best_center = max(valid_crystals, key=lambda item: item[0])
                elem = UIElement(
                    name="blue_crystal",
                    bounding_box=best_bbox,
                    confidence=best_conf,
                    center=best_center,
                )
                dx = best_center[0] - center_x
                dy = best_center[1] - center_y
                return True, (dx, dy), elem

        except Exception as e:
            self.logger.debug(f"Erro tolerado em LandmarkDetector: {e}")

        return False, None, None

    def detect_portal(self, frame: Optional[np.ndarray]) -> Optional[UIElement]:
        """Detecta portais de transição de mapa entre a cidade e a rota selvagem."""
        if frame is None or frame.size == 0:
            return None

        try:
            h, w = frame.shape[:2]
            # Portais/portas costumam ter aspecto retangular escuro/luminoso no topo do mapa
            roi = frame[0:int(h * 0.4), :]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            # Roxo / Magenta de portais
            mask = cv2.inRange(hsv, np.array([130, 80, 80]), np.array([165, 255, 255]))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 200 < area < (w * h * 0.1):
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    return UIElement(
                        name="portal",
                        bounding_box=(x, y, bw, bh),
                        confidence=0.75,
                        center=(x + bw // 2, y + bh // 2),
                    )
        except Exception:
            pass
        return None
