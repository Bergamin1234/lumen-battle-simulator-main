import re
import logging
from typing import Optional, Tuple
import cv2
import numpy as np


class OCREngine:
    """Motor de OCR desacoplado otimizado exclusivamente para regiões de interesse (ROI) com pré-processamento adaptativo."""

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self._tesseract_available = False
        self._pytesseract = None

        try:
            import pytesseract
            self._pytesseract = pytesseract
            if tesseract_cmd:
                self._pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self._tesseract_available = True
        except ImportError:
            self.logger.debug("pytesseract não instalado. OCREngine operará em modo de fallback visual.")
        except Exception as e:
            self.logger.debug(f"Aviso ao inicializar pytesseract: {e}")

    @property
    def is_available(self) -> bool:
        return self._tesseract_available

    def preprocess_roi(self, roi: Optional[np.ndarray], mode: str = "digits") -> Optional[np.ndarray]:
        """
        Aplica pipeline de melhoria de contraste e binarização em ROI.
        Modos: 'digits' (Otsu com alto contraste) ou 'text' (Adaptive Threshold).
        """
        if roi is None or roi.size == 0:
            return None

        try:
            # 1. Grayscale
            if len(roi.shape) == 3:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi.copy()

            # 2. Redimensionamento 2x (aumenta densidade dos caracteres pequenos)
            scaled = cv2.resize(gray, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

            # 3. Redução de ruído com filtro Gaussiano leve
            blurred = cv2.GaussianBlur(scaled, (3, 3), 0)

            # 4. Binarização
            if mode == "digits":
                # Otsu Thresholding
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                # Adaptive Gaussian Thresholding
                thresh = cv2.adaptiveThreshold(
                    blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )

            return thresh
        except Exception as e:
            self.logger.debug(f"Erro no pré-processamento de ROI: {e}")
            return None

    def read_text(self, roi: Optional[np.ndarray]) -> str:
        """Executa OCR em uma ROI de texto geral."""
        if roi is None or roi.size == 0:
            return ""

        if not self._tesseract_available or self._pytesseract is None:
            return ""

        try:
            processed = self.preprocess_roi(roi, mode="text")
            if processed is None:
                return ""

            config = "--psm 6"
            text = self._pytesseract.image_to_string(processed, config=config)
            return text.strip()
        except Exception as e:
            self.logger.debug(f"Erro na extração de texto por OCR: {e}")
            return ""

    def parse_hp(self, roi: Optional[np.ndarray]) -> Tuple[Optional[int], Optional[int], float]:
        """
        Lê e extrai valores numéricos de HP formato '85/100' ou '85 / 100'.
        Retorna (current_hp, max_hp, percentage: 0.0 a 1.0).
        """
        if roi is None or roi.size == 0:
            return None, None, 1.0

        raw_text = ""
        if self._tesseract_available and self._pytesseract is not None:
            try:
                processed = self.preprocess_roi(roi, mode="digits")
                if processed is not None:
                    config = "--psm 7 -c tessedit_char_whitelist=0123456789/"
                    raw_text = self._pytesseract.image_to_string(processed, config=config).strip()
            except Exception:
                pass

        # Parsing via Regex do padrão "X/Y"
        match = re.search(r"(\d+)\s*/\s*(\d+)", raw_text)
        if match:
            try:
                curr = int(match.group(1))
                max_v = int(match.group(2))
                pct = min(1.0, max(0.0, curr / max(1, max_v)))
                return curr, max_v, pct
            except Exception:
                pass

        # Se falhar ou OCR indisponível, retorna valor default neutro seguro
        return None, None, 1.0

    def parse_pp(self, roi: Optional[np.ndarray]) -> Tuple[Optional[int], Optional[int], bool]:
        """
        Lê e extrai valores numéricos de PP formato '12/15'.
        Retorna (current_pp, max_pp, is_available: bool).
        """
        if roi is None or roi.size == 0:
            return None, None, True

        raw_text = ""
        if self._tesseract_available and self._pytesseract is not None:
            try:
                processed = self.preprocess_roi(roi, mode="digits")
                if processed is not None:
                    config = "--psm 7 -c tessedit_char_whitelist=0123456789/"
                    raw_text = self._pytesseract.image_to_string(processed, config=config).strip()
            except Exception:
                pass

        match = re.search(r"(\d+)\s*/\s*(\d+)", raw_text)
        if match:
            try:
                curr = int(match.group(1))
                max_v = int(match.group(2))
                return curr, max_v, curr > 0
            except Exception:
                pass

        return None, None, True
