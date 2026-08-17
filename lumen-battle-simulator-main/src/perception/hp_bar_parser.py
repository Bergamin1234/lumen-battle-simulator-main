"""
LUMENA BOT v4.2 — ROBUST MULTI-CHANNEL HP BAR PARSER
=====================================================
Segmentador híbrido multi-canal de barras de HP para combate WebGL:
- Segmentação por canais HSV (Verde / Amarelo / Vermelho)
- Segmentação de contorno e fundo escuro do container da barra
- Filtro temporal de mediana móvel (janela de 3 frames) contra ruído de dano piscante (flashing damage)
- Extração estável de ratio de HP (0.0 a 1.0) para Player e Inimigo
"""

import collections
import logging
from typing import Optional, Tuple, Deque
import numpy as np
import cv2


class HPBarParser:
    """Parser multi-canal robusto para barras de vida em interfaces WebGL com filtro anti-ruído."""

    def __init__(self, history_len: int = 3) -> None:
        self.logger = logging.getLogger("LumenaHPBarParser")
        self.history_len = history_len
        self._player_hp_history: Deque[float] = collections.deque(maxlen=history_len)
        self._enemy_hp_history: Deque[float] = collections.deque(maxlen=history_len)

        # Faixas HSV para cores de preenchimento de HP
        # Verde (HP Alto >= 50%)
        self.green_lower = np.array([35, 60, 60], dtype=np.uint8)
        self.green_upper = np.array([85, 255, 255], dtype=np.uint8)

        # Amarelo/Laranja (HP Médio 20% a 50%)
        self.yellow_lower = np.array([15, 70, 70], dtype=np.uint8)
        self.yellow_upper = np.array([35, 255, 255], dtype=np.uint8)

        # Vermelho (HP Baixo < 20%) - Dois intervalos no espaço HSV
        self.red_lower1 = np.array([0, 70, 70], dtype=np.uint8)
        self.red_upper1 = np.array([14, 255, 255], dtype=np.uint8)
        self.red_lower2 = np.array([170, 70, 70], dtype=np.uint8)
        self.red_upper2 = np.array([180, 255, 255], dtype=np.uint8)

        # Background escuro do container de HP (preto/cinza escuro da vida perdida)
        self.dark_bg_lower = np.array([0, 0, 10], dtype=np.uint8)
        self.dark_bg_upper = np.array([180, 70, 90], dtype=np.uint8)

    def reset_history(self) -> None:
        """Limpa o histórico temporal de leituras."""
        self._player_hp_history.clear()
        self._enemy_hp_history.clear()

    def parse_hp_bar(
        self,
        roi_img: np.ndarray,
        is_player: bool = True,
        apply_temporal_filter: bool = True,
    ) -> float:
        """
        Analisa uma imagem de ROI contendo uma barra de HP e retorna o ratio de vida (0.0 a 1.0).
        Utiliza segmentação híbrida e filtro de mediana temporal.
        """
        if roi_img is None or roi_img.size == 0:
            return 1.0

        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)

        # 1. Máscaras de cores de preenchimento de HP
        mask_g = cv2.inRange(hsv, self.green_lower, self.green_upper)
        mask_y = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        mask_r1 = cv2.inRange(hsv, self.red_lower1, self.red_upper1)
        mask_r2 = cv2.inRange(hsv, self.red_lower2, self.red_upper2)
        mask_fill = cv2.bitwise_or(mask_g, mask_y)
        mask_fill = cv2.bitwise_or(mask_fill, cv2.bitwise_or(mask_r1, mask_r2))

        # 2. Máscara de container de fundo (área escura da barra)
        mask_bg = cv2.inRange(hsv, self.dark_bg_lower, self.dark_bg_upper)

        # União de preenchimento + fundo escuro forma o container total da barra
        total_bar_mask = cv2.bitwise_or(mask_fill, mask_bg)

        # Projeta no eixo X (colunas)
        fill_cols = np.sum(mask_fill > 0, axis=0)
        total_cols = np.sum(total_bar_mask > 0, axis=0)

        # Colunas ativas com pixels preenchidos
        active_fill_cols = np.count_nonzero(fill_cols > 2)
        active_total_cols = np.count_nonzero(total_cols > 2)

        if active_total_cols > 10:
            raw_ratio = float(active_fill_cols) / float(active_total_cols)
        else:
            # Fallback por densidade direta de pixels na ROI
            total_pixels = roi_img.shape[0] * roi_img.shape[1]
            fill_pixels = int(np.count_nonzero(mask_fill))
            raw_ratio = float(fill_pixels) / float(max(1, total_pixels * 0.45))

        raw_ratio = max(0.0, min(1.0, raw_ratio))

        if not apply_temporal_filter:
            return raw_ratio

        # 3. Filtro temporal de mediana móvel (Anti-flashing damage)
        history = self._player_hp_history if is_player else self._enemy_hp_history
        history.append(raw_ratio)

        # Calcula mediana dos últimos frames para eliminar picos de dano piscante
        filtered_ratio = float(np.median(list(history)))
        return filtered_ratio

    def parse_player_and_enemy_hp(
        self,
        player_roi: Optional[np.ndarray],
        enemy_roi: Optional[np.ndarray],
    ) -> Tuple[float, float]:
        """Lê ambos os ratios de HP de jogador e inimigo de forma sincronizada."""
        p_hp = self.parse_hp_bar(player_roi, is_player=True) if player_roi is not None else 1.0
        e_hp = self.parse_hp_bar(enemy_roi, is_player=False) if enemy_roi is not None else 1.0
        return p_hp, e_hp
