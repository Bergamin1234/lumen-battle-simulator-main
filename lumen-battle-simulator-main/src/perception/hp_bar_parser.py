"""
LUMENA BOT v5.1 — SCALE & LEVEL INVARIANT DYNAMIC HP BAR PARSER
================================================================
Motor de percepção contínua e dinâmica de HP:
- 100% agnóstico a valores absolutos (zero números fixos como 113, 100, 50).
- Leitura geométrica contínua por proporção de preenchimento (Bar Ratio Engine): hp_pct ∈ [0.0, 1.0].
- Parser de texto numérico "{current}/{max}" via Regex r"(\\d+)\\s*/\\s*(\\d+)".
- Filtro temporal de mediana móvel (3 frames) para estabilização contra animações de dano (flashing damage).
"""

import re
import collections
import logging
from typing import Optional, Tuple, Deque
import numpy as np
import cv2


class HPBarParser:
    """Parser dinâmico e multi-canal para barras de vida em interfaces WebGL."""

    def __init__(self, history_len: int = 3) -> None:
        self.logger = logging.getLogger("LumenaHPBarParser")
        self.history_len = history_len
        self._player_hp_history: Deque[float] = collections.deque(maxlen=history_len)
        self._enemy_hp_history: Deque[float] = collections.deque(maxlen=history_len)

        # Faixas HSV para cores de preenchimento de HP
        # Verde (HP Alto >= 50%)
        self.green_lower = np.array([35, 50, 50], dtype=np.uint8)
        self.green_upper = np.array([85, 255, 255], dtype=np.uint8)

        # Amarelo/Laranja (HP Médio 20% a 50%)
        self.yellow_lower = np.array([15, 60, 60], dtype=np.uint8)
        self.yellow_upper = np.array([35, 255, 255], dtype=np.uint8)

        # Vermelho (HP Baixo < 20%) - Dois intervalos no espaço HSV
        self.red_lower1 = np.array([0, 60, 60], dtype=np.uint8)
        self.red_upper1 = np.array([14, 255, 255], dtype=np.uint8)
        self.red_lower2 = np.array([170, 60, 60], dtype=np.uint8)
        self.red_upper2 = np.array([180, 255, 255], dtype=np.uint8)

        # Background escuro do container de HP (borda escura ou fundo da vida perdida)
        self.dark_bg_lower = np.array([0, 0, 10], dtype=np.uint8)
        self.dark_bg_upper = np.array([180, 80, 100], dtype=np.uint8)

    def reset_history(self) -> None:
        """Limpa o histórico temporal de leituras."""
        self._player_hp_history.clear()
        self._enemy_hp_history.clear()

    @staticmethod
    def parse_hp_from_text(text: str) -> Optional[float]:
        """
        Extrai o percentual de HP a partir de uma string no formato '{current}/{max}'.
        Exemplo: '113 / 113' -> 1.0, '45 / 90' -> 0.50, '350 / 1200' -> 0.2917.
        """
        if not text:
            return None
        match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if match:
            try:
                curr = float(match.group(1))
                max_val = float(match.group(2))
                if max_val > 0:
                    return max(0.0, min(1.0, curr / max_val))
            except Exception:
                return None
        return None

    def parse_hp_bar(
        self,
        roi_img: Optional[np.ndarray],
        is_player: bool = True,
        apply_temporal_filter: bool = True,
        ocr_text: Optional[str] = None,
    ) -> float:
        """
        Analisa uma imagem de ROI contendo uma barra de HP e retorna o ratio de vida (0.0 a 1.0).
        Utiliza Bar Ratio Engine geométrico e OCR text fallback.
        """
        # 1. Tenta OCR se texto foi fornecido
        if ocr_text:
            text_ratio = self.parse_hp_from_text(ocr_text)
            if text_ratio is not None:
                if apply_temporal_filter:
                    hist = self._player_hp_history if is_player else self._enemy_hp_history
                    hist.append(text_ratio)
                    return float(np.median(list(hist)))
                return text_ratio

        if roi_img is None or roi_img.size == 0:
            return 1.0

        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)

        # 2. Segmentação de preenchimento (Verde, Amarelo, Vermelho)
        mask_g = cv2.inRange(hsv, self.green_lower, self.green_upper)
        mask_y = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        mask_r1 = cv2.inRange(hsv, self.red_lower1, self.red_upper1)
        mask_r2 = cv2.inRange(hsv, self.red_lower2, self.red_upper2)
        mask_fill = cv2.bitwise_or(mask_g, mask_y)
        mask_fill = cv2.bitwise_or(mask_fill, cv2.bitwise_or(mask_r1, mask_r2))

        # 3. Segmentação do container/fundo escuro da barra
        mask_bg = cv2.inRange(hsv, self.dark_bg_lower, self.dark_bg_upper)
        total_bar_mask = cv2.bitwise_or(mask_fill, mask_bg)

        # 4. Projeção nas colunas horizontais (Bar Ratio)
        fill_cols = np.sum(mask_fill > 0, axis=0)
        total_cols = np.sum(total_bar_mask > 0, axis=0)

        active_fill_cols = int(np.count_nonzero(fill_cols > 2))
        active_total_cols = int(np.count_nonzero(total_cols > 2))

        if active_total_cols > 8:
            raw_ratio = float(active_fill_cols) / float(active_total_cols)
        else:
            total_pixels = roi_img.shape[0] * roi_img.shape[1]
            fill_pixels = int(np.count_nonzero(mask_fill))
            raw_ratio = float(fill_pixels) / float(max(1, total_pixels * 0.45))

        raw_ratio = max(0.0, min(1.0, raw_ratio))

        # 5. Filtro temporal de mediana móvel
        if not apply_temporal_filter:
            return raw_ratio

        hist = self._player_hp_history if is_player else self._enemy_hp_history
        hist.append(raw_ratio)
        return float(np.median(list(hist)))

    def parse_hp_ratio(self, roi_img: Optional[np.ndarray]) -> float:
        """Alias para parse_hp_bar sem filtro temporal estocástico."""
        return self.parse_hp_bar(roi_img, apply_temporal_filter=False)

    def filter_hp(self, val: float, is_player: bool = True) -> float:
        """Aplica filtro temporal de mediana móvel a um valor escalar de HP."""
        hist = self._player_hp_history if is_player else self._enemy_hp_history
        hist.append(val)
        return float(np.median(list(hist)))

    @property
    def history(self) -> Deque[float]:
        """Acesso ao histórico de medições do jogador."""
        return self._player_hp_history

    def parse_player_and_enemy_hp(
        self,
        player_roi: Optional[np.ndarray],
        enemy_roi: Optional[np.ndarray],
        apply_temporal_filter: bool = True,
    ) -> Tuple[float, float]:
        """Extrai e retorna a tupla (player_hp_ratio, enemy_hp_ratio)."""
        p_ratio = self.parse_hp_bar(player_roi, is_player=True, apply_temporal_filter=apply_temporal_filter)
        e_ratio = self.parse_hp_bar(enemy_roi, is_player=False, apply_temporal_filter=apply_temporal_filter)
        return p_ratio, e_ratio
