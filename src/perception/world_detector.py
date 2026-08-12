import logging
from typing import Optional, Tuple, Dict
import cv2
import numpy as np


class WorldDetector:
    """Detector de ambiente, vegetação (mato/grama alta), caminhos e densidade espacial."""

    def __init__(
        self,
        grass_hsv_lower: Optional[np.ndarray] = None,
        grass_hsv_upper: Optional[np.ndarray] = None,
        path_hsv_lower: Optional[np.ndarray] = None,
        path_hsv_upper: Optional[np.ndarray] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        # Intervalo HSV de grama/vegetação padrão
        self.grass_lower = grass_hsv_lower if grass_hsv_lower is not None else np.array([28, 40, 40])
        self.grass_upper = grass_hsv_upper if grass_hsv_upper is not None else np.array([85, 255, 255])

        # Intervalo HSV de caminho de terra/estrada padrão
        self.path_lower = path_hsv_lower if path_hsv_lower is not None else np.array([10, 20, 50])
        self.path_upper = path_hsv_upper if path_hsv_upper is not None else np.array([25, 180, 200])

    def detect_world_features(self, frame: Optional[np.ndarray]) -> Dict[str, any]:
        """Extrai todas as características espaciais do mundo aberto."""
        if frame is None or frame.size == 0:
            return {
                "grass_density": 0.0,
                "has_grass": False,
                "grass_mask": None,
                "path_density": 0.0,
                "walkable_mask": None,
            }

        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            h, w = frame.shape[:2]
            total_pixels = h * w

            # 1. Segmentação da Grama
            grass_mask = cv2.inRange(hsv, self.grass_lower, self.grass_upper)
            # Limpeza morfológica para remover ruído
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            grass_clean = cv2.morphologyEx(grass_mask, cv2.MORPH_OPEN, kernel)
            grass_pixels = cv2.countNonZero(grass_clean)
            grass_density = float(grass_pixels / max(1, total_pixels))

            # 2. Segmentação de Caminhos
            path_mask = cv2.inRange(hsv, self.path_lower, self.path_upper)
            path_clean = cv2.morphologyEx(path_mask, cv2.MORPH_OPEN, kernel)
            path_pixels = cv2.countNonZero(path_clean)
            path_density = float(path_pixels / max(1, total_pixels))

            # 3. Máscara de navegabilidade (caminhos + áreas livres)
            walkable_mask = cv2.bitwise_or(grass_clean, path_clean)

            return {
                "grass_density": min(1.0, max(0.0, grass_density)),
                "has_grass": grass_density > 0.08,
                "grass_mask": grass_clean,
                "path_density": min(1.0, max(0.0, path_density)),
                "walkable_mask": walkable_mask,
            }
        except Exception as e:
            self.logger.debug(f"Erro tolerado em WorldDetector: {e}")
            return {
                "grass_density": 0.0,
                "has_grass": False,
                "grass_mask": None,
                "path_density": 0.0,
                "walkable_mask": None,
            }

    def compute_grass_density(self, frame: Optional[np.ndarray]) -> float:
        """Helper leve para obter exclusivamente a densidade de grama (0.0 a 1.0)."""
        features = self.detect_world_features(frame)
        return features["grass_density"]
