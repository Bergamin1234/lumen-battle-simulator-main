import logging
from typing import Optional, Tuple, Dict, List
import cv2
import numpy as np
from src.models.lumen import UIElement


class LandmarkDetector:
    """Detector de marcos visuais no mapa (Cristal Azul de Cura, Portais, Postes, Entradas)."""

    # Máscara HSV exclusiva para o Cristal Azul Luminoso de Cura (Ciano/Azul elétrico de alta pureza)
    CRYSTAL_HSV_LOWER = np.array([95, 160, 180], dtype=np.uint8)
    CRYSTAL_HSV_UPPER = np.array([115, 255, 255], dtype=np.uint8)

    def __init__(
        self,
        crystal_hsv_lower: Optional[np.ndarray] = None,
        crystal_hsv_upper: Optional[np.ndarray] = None,
        templates: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaPerception")
        self.crystal_lower = crystal_hsv_lower if crystal_hsv_lower is not None else self.CRYSTAL_HSV_LOWER
        self.crystal_upper = crystal_hsv_upper if crystal_hsv_upper is not None else self.CRYSTAL_HSV_UPPER
        self.templates = templates or {}

    def detect_player(
        self,
        frame: Optional[np.ndarray],
        in_battle: bool = False,
    ) -> Tuple[bool, Tuple[int, int, int, int], Tuple[int, int], float]:
        """Detecta o personagem do jogador no mapa respeitando o contexto (WORLD_PLAYER vs BATTLE_PLAYER)."""
        if in_battle:
            return self.detect_battle_player(frame)
        return self.detect_world_player(frame)

    def detect_world_player(
        self,
        frame: Optional[np.ndarray],
    ) -> Tuple[bool, Tuple[int, int, int, int], Tuple[int, int], float]:
        """Detecta o sprite do jogador no Overworld (WORLD_PLAYER) centrado na tela de navegação."""
        if frame is None or frame.size == 0:
            return False, (0, 0, 0, 0), (0, 0), 0.0

        try:
            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2

            # 1. Template matching se disponível
            if "player.png" in self.templates:
                tmpl = self.templates["player.png"]
                th, tw = tmpl.shape[:2]
                if th <= h and tw <= w:
                    res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= 0.65:
                        bx, by = max_loc
                        cx = bx + tw // 2
                        cy = by + th // 2
                        return True, (bx, by, tw, th), (cx, cy), float(max_val)

            # 2. Heurística visual: busca por entidade no quadrante central
            roi_top = max(0, int(h * 0.35))
            roi_bottom = min(h, int(h * 0.68))
            roi_left = max(0, int(w * 0.35))
            roi_right = min(w, int(w * 0.68))

            roi = frame[roi_top:roi_bottom, roi_left:roi_right]
            if roi.size > 0:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 40, 140)
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                valid_player_candidates = []
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if 60 <= area <= 6000:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        aspect = bh / max(1, bw)
                        if 0.6 <= aspect <= 3.0:
                            abs_x = roi_left + x
                            abs_y = roi_top + y
                            cx = abs_x + bw // 2
                            cy = abs_y + bh // 2
                            dist_center = np.hypot(cx - center_x, cy - center_y)
                            score = 1.0 / (1.0 + dist_center * 0.05)
                            valid_player_candidates.append((score, (abs_x, abs_y, bw, bh), (cx, cy)))

                if valid_player_candidates:
                    best_score, best_bbox, best_center = max(valid_player_candidates, key=lambda item: item[0])
                    conf = min(0.98, max(0.70, best_score))
                    return True, best_bbox, best_center, conf

            # 3. Fallback estável: centro da viewport com dimensões padrão de sprite
            sprite_w, sprite_h = 36, 52
            bbox = (center_x - sprite_w // 2, center_y - sprite_h // 2, sprite_w, sprite_h)
            return True, bbox, (center_x, center_y), 0.80

        except Exception as e:
            self.logger.debug(f"Erro tolerado em detect_world_player: {e}")
            h, w = (frame.shape[:2]) if frame is not None else (1080, 1920)
            center_x, center_y = w // 2, h // 2
            sprite_w, sprite_h = 36, 52
            bbox = (center_x - sprite_w // 2, center_y - sprite_h // 2, sprite_w, sprite_h)
            return True, bbox, (center_x, center_y), 0.80

    def detect_battle_player(
        self,
        frame: Optional[np.ndarray],
    ) -> Tuple[bool, Tuple[int, int, int, int], Tuple[int, int], float]:
        """Detecta a posição do sprite do jogador no layout de combate (canto inferior esquerdo)."""
        if frame is None or frame.size == 0:
            return False, (0, 0, 0, 0), (0, 0), 0.0

        h, w = frame.shape[:2]
        px, py, pw, ph = int(w * 0.28), int(h * 0.52), int(w * 0.14), int(h * 0.20)
        return True, (px, py, pw, ph), (px + pw // 2, py + ph // 2), 0.80

    def detect_crystal(
        self,
        frame: Optional[np.ndarray],
        player_pos: Optional[Tuple[int, int]] = None,
        in_battle: bool = False,
        player_hp_pct: Optional[float] = None,
    ) -> Tuple[bool, Optional[Tuple[int, int]], Optional[UIElement]]:
        """
        Detecta o Grande Cristal Azul de Cura no cenário de forma semântica e restritiva.
        Guard Clause O(1): Se in_battle == True ou player_hp_pct > 0.40, retorna (False, None, None) imediatamente.
        """
        # 1. Guard Clauses em O(1)
        if in_battle:
            return False, None, None
        if player_hp_pct is not None and player_hp_pct > 0.40:
            return False, None, None

        if frame is None or frame.size == 0:
            return False, None, None

        try:
            h, w = frame.shape[:2]
            if player_pos is None:
                _, _, p_center, _ = self.detect_player(frame)
                ref_x, ref_y = p_center
            else:
                ref_x, ref_y = player_pos

            # 2. Template Matching Estrito (Threshold >= 0.88)
            if "blue_crystal.png" in self.templates:
                tmpl = self.templates["blue_crystal.png"]
                th, tw = tmpl.shape[:2]
                if th <= h and tw <= w:
                    res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= 0.88:
                        bx, by = max_loc
                        cx = bx + tw // 2
                        cy = by + th // 2
                        elem = UIElement(
                            name="blue_crystal",
                            bounding_box=(bx, by, tw, th),
                            confidence=float(max_val),
                            center=(cx, cy),
                            semantic_type="HEALING_CRYSTAL",
                        )
                        return True, (cx - ref_x, cy - ref_y), elem

            # 3. Segmentação HSV Exclusiva do Cristal Azul/Ciano Brilhante
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.crystal_lower, self.crystal_upper)

            # Limpeza morfológica
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = 100
            max_area = (w * h) * 0.35

            valid_crystals: List[Tuple[float, Tuple[int, int, int, int], Tuple[int, int]]] = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect_ratio = bh / max(1, bw)
                    if 0.5 <= aspect_ratio <= 3.0:
                        # Verifica densidade de pixels azuis brilhantes na ROI
                        roi_mask = mask[y:y + bh, x:x + bw]
                        blue_density = np.count_nonzero(roi_mask) / float(bw * bh)
                        if blue_density >= 0.25:
                            cx = x + bw // 2
                            cy = y + bh // 2
                            confidence = min(0.99, max(0.88, 0.88 + blue_density * 0.10))
                            valid_crystals.append((confidence, (x, y, bw, bh), (cx, cy)))

            if valid_crystals:
                best_conf, best_bbox, best_center = max(valid_crystals, key=lambda item: item[0])
                elem = UIElement(
                    name="blue_crystal",
                    bounding_box=best_bbox,
                    confidence=best_conf,
                    center=best_center,
                    semantic_type="HEALING_CRYSTAL",
                )
                return True, (best_center[0] - ref_x, best_center[1] - ref_y), elem

            return False, None, None

        except Exception as e:
            self.logger.debug(f"Erro em detect_crystal: {e}")
            return False, None, None

    def detect_interaction_prompt(
        self,
        frame: Optional[np.ndarray],
    ) -> Tuple[bool, str, Optional[Tuple[int, int, int, int]], float]:
        """
        Detecta prompts de interação do jogo (ex: 'Press Space to Interact', '[SPACE]', 'Talk').
        Retorna (prompt_detected, prompt_text, bounding_box, confidence).
        """
        if frame is None or frame.size == 0:
            return False, "", None, 0.0

        try:
            h, w = frame.shape[:2]
            # Prompt de interação costuma aparecer no terço inferior central ou acima do objeto
            roi = frame[int(h * 0.4):int(h * 0.9), int(w * 0.2):int(w * 0.8)]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Detecta caixas de texto com alto contraste (texto branco/amarelo em fundo escuro)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                x, y, bw, bh = cv2.boundingRect(cnt)
                # Aspecto retangular de banner/botão de interação
                if bw > 60 and 15 < bh < 80:
                    aspect = bw / float(bh)
                    if 2.0 <= aspect <= 10.0:
                        global_x = int(w * 0.2) + x
                        global_y = int(h * 0.4) + y
                        return True, "PRESS_SPACE_TO_INTERACT", (global_x, global_y, bw, bh), 0.85
        except Exception:
            pass

        return False, "", None, 0.0

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
