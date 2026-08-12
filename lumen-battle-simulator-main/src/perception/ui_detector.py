import logging
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from src.models.lumen import UIElement


class UIDetector:
    """Detector multimodal de componentes da interface gráfica (modais, botões, caixas de diálogo, transições)."""

    def __init__(self, templates: Optional[Dict[str, np.ndarray]] = None) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self.templates: Dict[str, np.ndarray] = templates or {}

    def add_template(self, name: str, template_img: np.ndarray) -> None:
        if template_img is not None and len(template_img.shape) >= 2:
            self.templates[name] = template_img

    def detect_all(self, frame: Optional[np.ndarray]) -> Dict[str, UIElement]:
        """Executa a detecção combinada de elementos de UI e retorna dicionário de UIElements."""
        elements: Dict[str, UIElement] = {}
        if frame is None or frame.size == 0:
            return elements

        try:
            # 1. Checa transição de tela preta / loading
            black_transition = self.detect_black_screen(frame)
            if black_transition is not None:
                elements["black_screen"] = black_transition

            # 2. Detecta caixa de diálogo
            dialog_box = self.detect_dialog_box(frame)
            if dialog_box is not None:
                elements["dialog_box"] = dialog_box

            # 3. Detecta botões por template matching
            for name, tmpl in self.templates.items():
                match_elem = self.match_template_element(frame, name, tmpl)
                if match_elem is not None:
                    elements[name] = match_elem

            # 4. Detecta botões por contornos geométricos salientes
            detected_buttons = self.detect_button_contours(frame)
            for idx, btn in enumerate(detected_buttons):
                elements[f"button_contour_{idx}"] = btn

        except Exception as e:
            self.logger.debug(f"Erro tolerado em UIDetector: {e}")

        return elements

    def detect_black_screen(self, frame: np.ndarray, threshold: float = 12.0) -> Optional[UIElement]:
        """Detecta tela preta ou transição escura de loading."""
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        mean_val = float(np.mean(frame))
        if mean_val <= threshold:
            confidence = max(0.0, min(1.0, 1.0 - (mean_val / threshold)))
            return UIElement(
                name="black_screen",
                bounding_box=(0, 0, w, h),
                confidence=confidence,
                center=(w // 2, h // 2),
            )
        return None

    def detect_dialog_box(self, frame: np.ndarray) -> Optional[UIElement]:
        """Detecta presença de caixa de diálogo na região inferior da tela."""
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        # Região de interesse: 60% a 98% da altura
        roi_top = int(h * 0.60)
        roi_bottom = int(h * 0.98)
        roi_left = int(w * 0.05)
        roi_right = int(w * 0.95)

        roi = frame[roi_top:roi_bottom, roi_left:roi_right]
        if roi.size == 0:
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Busca retângulo escuro típico de caixa de diálogo (intensidade < 45)
        _, thresh = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_area = (roi_right - roi_left) * (roi_bottom - roi_top)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (roi_area * 0.25):  # Ocupa pelo menos 25% da ROI
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect_ratio = bw / max(1, bh)
                if aspect_ratio >= 2.0:  # Caixa larga horizontal
                    abs_x = roi_left + x
                    abs_y = roi_top + y
                    return UIElement(
                        name="dialog_box",
                        bounding_box=(abs_x, abs_y, bw, bh),
                        confidence=0.85,
                        center=(abs_x + bw // 2, abs_y + bh // 2),
                    )
        return None


    def detect_button_contours(self, frame: np.ndarray) -> List[UIElement]:
        """Detecta caixas retangulares que correspondem a botões interativos na tela."""
        buttons: List[UIElement] = []
        if frame is None or frame.size == 0:
            return buttons

        try:
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)

            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            min_area = (w * h) * 0.001  # Pelo menos 0.1% da tela
            max_area = (w * h) * 0.08   # No máximo 8% da tela

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area < area < max_area:
                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
                    if len(approx) == 4:  # Quadrilátero
                        bx, by, bw, bh = cv2.boundingRect(approx)
                        ratio = bw / max(1, bh)
                        if 1.5 <= ratio <= 6.0:  # Proporção típica de botão
                            buttons.append(
                                UIElement(
                                    name="button_contour",
                                    bounding_box=(bx, by, bw, bh),
                                    confidence=0.75,
                                    center=(bx + bw // 2, by + bh // 2),
                                )
                            )
        except Exception:
            pass
        return buttons

    def match_template_element(
        self,
        frame: np.ndarray,
        name: str,
        template: np.ndarray,
        threshold: float = 0.75,
    ) -> Optional[UIElement]:
        """Localiza template específico com normalização de escala e limites."""
        if frame is None or template is None:
            return None

        fh, fw = frame.shape[:2]
        th, tw = template.shape[:2]
        if th > fh or tw > fw or th == 0 or tw == 0:
            return None

        try:
            res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                bx, by = max_loc
                return UIElement(
                    name=name,
                    bounding_box=(bx, by, tw, th),
                    confidence=float(max_val),
                    center=(bx + tw // 2, by + th // 2),
                )
        except Exception as e:
            self.logger.debug(f"Erro em match_template_element ({name}): {e}")
        return None
