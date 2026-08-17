import logging
from typing import Optional, Tuple, List, Dict
import cv2
import numpy as np
from src.models.lumen import BattleTelemetry, MoveSlotInfo, UIElement
from src.models.enums import Element


class BattleDetector:
    """Detector especializado em telemetria, interface e estado de combate."""

    def __init__(self, templates: Optional[Dict[str, np.ndarray]] = None) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self.templates: Dict[str, np.ndarray] = templates or {}

    def detect_battle_state(self, frame: Optional[np.ndarray]) -> BattleTelemetry:
        """Processa o frame e sintetiza a telemetria de combate completa."""
        if frame is None or frame.size == 0:
            return BattleTelemetry(in_battle=False)

        try:
            h, w = frame.shape[:2]

            # 1. Detecção do botão FIGHT e botões principais
            fight_pos, fight_conf = self.detect_fight_button(frame)
            switch_pos, _ = self.detect_switch_button(frame)

            in_battle = fight_pos is not None or fight_conf >= 0.65

            # 2. Leitura de barras de HP (Enemy & Player)
            enemy_hp_pct = self.detect_enemy_hp_percentage(frame)
            player_hp_pct = self.detect_player_hp_percentage(frame)

            # Se detectar barras de HP típicas de combate, confirma in_battle
            if not in_battle and (enemy_hp_pct is not None and player_hp_pct is not None):
                in_battle = True

            # 3. Detecção de Slots de Golpes
            moves = []
            if in_battle and fight_pos is not None:
                moves = self.estimate_move_slots(frame, fight_pos)

            # 4. Detecção de Vitória ou Derrota
            victory = False
            defeat = False
            if in_battle:
                if enemy_hp_pct is not None and enemy_hp_pct <= 0.02:
                    victory = True
                if player_hp_pct is not None and player_hp_pct <= 0.0:
                    defeat = True

            return BattleTelemetry(
                in_battle=in_battle,
                player_hp_pct=player_hp_pct if player_hp_pct is not None else 1.0,
                enemy_hp_pct=enemy_hp_pct if enemy_hp_pct is not None else 1.0,
                player_lumen_name=None,
                enemy_lumen_name=None,
                available_moves=moves,
                fight_button_pos=fight_pos,
                switch_button_pos=switch_pos,
                dialog_active=False,
                victory_detected=victory,
                defeat_detected=defeat,
            )
        except Exception as e:
            self.logger.debug(f"Erro tolerado em BattleDetector: {e}")
            return BattleTelemetry(in_battle=False)

    def detect_fight_button(self, frame: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """Localiza o botão FIGHT via template matching ou por assinatura de cor vermelha/formato."""
        if "fight_button.png" in self.templates:
            tmpl = self.templates["fight_button.png"]
            th, tw = tmpl.shape[:2]
            fh, fw = frame.shape[:2]
            if th <= fh and tw <= fw:
                res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= 0.70:
                    bx, by = max_loc
                    return (bx + tw // 2, by + th // 2), float(max_val)

        # Fallback heurístico: detecção por cor vermelha na metade inferior
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.5):int(h * 0.95), int(w * 0.3):int(w * 0.9)]
        if roi.size == 0:
            return None, 0.0

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # Vermelho em HSV (dois intervalos)
        mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([165, 100, 100]), np.array([180, 255, 255]))
        mask = cv2.bitwise_or(mask1, mask2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 400 < area < (w * h * 0.05):
                x, y, bw, bh = cv2.boundingRect(cnt)
                ratio = bw / max(1, bh)
                if 1.5 <= ratio <= 4.0:
                    center_x = int(w * 0.3) + x + bw // 2
                    center_y = int(h * 0.5) + y + bh // 2
                    return (center_x, center_y), 0.70

        return None, 0.0

    def detect_switch_button(self, frame: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """Localiza botão de troca de criatura (SWITCH/POKEMON/TEAM)."""
        if "switch_button.png" in self.templates:
            tmpl = self.templates["switch_button.png"]
            th, tw = tmpl.shape[:2]
            fh, fw = frame.shape[:2]
            if th <= fh and tw <= fw:
                res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= 0.70:
                    bx, by = max_loc
                    return (bx + tw // 2, by + th // 2), float(max_val)
        return None, 0.0

    def detect_enemy_hp_percentage(self, frame: np.ndarray) -> Optional[float]:
        """Analisa a barra de HP do oponente no canto superior direito via segmentação HSV."""
        h, w = frame.shape[:2]
        # Região normalizada típica do HUD inimigo
        roi = frame[int(h * 0.02):int(h * 0.20), int(w * 0.60):int(w * 0.98)]
        return self._extract_bar_fill_ratio(roi)

    def detect_player_hp_percentage(self, frame: np.ndarray) -> Optional[float]:
        """Analisa a barra de HP do jogador na região inferior/lateral via segmentação HSV."""
        h, w = frame.shape[:2]
        # Região normalizada típica do HUD do jogador
        roi = frame[int(h * 0.50):int(h * 0.85), int(w * 0.45):int(w * 0.98)]
        return self._extract_bar_fill_ratio(roi)

    @staticmethod
    def _extract_bar_fill_ratio(roi: np.ndarray) -> Optional[float]:
        """Calcula o percentual preenchido de uma barra de vida (Verde/Amarelo/Vermelho)."""
        if roi is None or roi.size == 0:
            return None

        # Se a ROI for completamente preta (ex: tela preta/loading), não é uma barra de HP
        if float(np.mean(roi)) < 6.0:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Verde (HP alto)
        mask_green = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([85, 255, 255]))
        # Amarelo/Laranja (HP médio)
        mask_yellow = cv2.inRange(hsv, np.array([15, 70, 70]), np.array([34, 255, 255]))
        # Vermelho (HP baixo)
        mask_red1 = cv2.inRange(hsv, np.array([0, 70, 70]), np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([170, 70, 70]), np.array([180, 255, 255]))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        combined_hp_mask = cv2.bitwise_or(mask_green, cv2.bitwise_or(mask_yellow, mask_red))
        hp_pixels = cv2.countNonZero(combined_hp_mask)

        # Fundo escuro da barra (para medir a largura total da barra)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(combined_hp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_area = roi.shape[0] * roi.shape[1]

        if not contours:
            return 0.0 if hp_pixels == 0 and cv2.countNonZero(dark_mask) > 100 else None

        # Se a cor ocupar quase toda a ROI (> 40%), é cenário/mato, não uma barra de HP
        if hp_pixels > (roi_area * 0.40):
            return None

        # Pega o maior contorno de barra de vida
        best_cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(best_cnt)
        bx, by, bw, bh = cv2.boundingRect(best_cnt)
        ratio = bw / max(1, bh)

        # Barra de vida deve ter formato horizontal e dimensões contidas
        if bw < 25 or bh < 3 or bh > 35 or ratio < 2.5:
            return None

        # Proporção preenchida
        return min(1.0, max(0.0, float(hp_pixels / max(1, bw * bh))))


    def estimate_move_slots(
        self,
        frame: np.ndarray,
        fight_button_center: Tuple[int, int],
    ) -> List[MoveSlotInfo]:
        """Calcula dinamicamente a geometria dos 4 slots de ataque relativos à interface."""
        fx, fy = fight_button_center
        h, w = frame.shape[:2]

        slots: List[MoveSlotInfo] = []
        # Estimativas de layout relativas ao centro do menu de batalha
        offsets = [
            (-220, -35, 0),  # Slot 1: Superior Esquerdo
            (-220, 35, 1),   # Slot 2: Inferior Esquerdo
            (-70, -35, 2),   # Slot 3: Superior Direito
            (-70, 35, 3),    # Slot 4: Inferior Direito
        ]

        for dx, dy, idx in offsets:
            cx = max(0, min(w - 1, fx + dx))
            cy = max(0, min(h - 1, fy + dy))
            bw, bh = 130, 40
            rect = (max(0, cx - bw // 2), max(0, cy - bh // 2), bw, bh)

            slots.append(
                MoveSlotInfo(
                    slot_index=idx,
                    name=f"Move_{idx + 1}",
                    current_pp=15,
                    max_pp=15,
                    element=Element.NORMAL,
                    is_available=True,
                    power=40,
                    button_rect=rect,
                )
            )

        return slots
