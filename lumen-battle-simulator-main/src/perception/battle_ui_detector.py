"""
LUMENA BOT v3.7 — BATTLE UI DETECTOR
====================================
Módulo de percepção dedicado exclusivamente à detecção da interface de combate.
Template-first + ROI-first + Heurística semântica.
Evita falsos positivos do cenário ao isolar o contexto de batalha da exploração de mundo.
"""

import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaBattleUIDetector")


@dataclass
class BattleUIElement:
    name: str
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, width, height)
    center: Tuple[int, int] = (0, 0)                # (center_x, center_y)
    confidence: float = 0.0
    is_present: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def center_x(self) -> int:
        return self.center[0]

    @property
    def center_y(self) -> int:
        return self.center[1]


@dataclass
class BattleUIDetectionResult:
    timestamp: float = 0.0
    in_battle: bool = False
    battle_ui_confirmed: bool = False
    battle_ui_score: float = 0.0
    fight_button: Optional[BattleUIElement] = None
    run_button: Optional[BattleUIElement] = None
    team_button: Optional[BattleUIElement] = None
    bag_button: Optional[BattleUIElement] = None
    enemy_hp_bar: Optional[BattleUIElement] = None
    skill_menu_open: bool = False
    modal_detected: bool = False
    modal_type: str = "NONE"
    modal_confirm_button: Optional[BattleUIElement] = None
    elements: Dict[str, BattleUIElement] = field(default_factory=dict)
    roi_used: Optional[Tuple[int, int, int, int]] = None


class BattleUIDetector:
    """Detector especializado em interface de combate via Template Matching e Análise de ROI."""

    ROI_BATTLE_ACTIONS: Tuple[float, float, float, float] = (0.50, 0.55, 0.48, 0.42)
    ROI_ENEMY_STATUS: Tuple[float, float, float, float] = (0.35, 0.05, 0.60, 0.30)
    ROI_PLAYER_STATUS: Tuple[float, float, float, float] = (0.02, 0.65, 0.35, 0.32)
    ROI_MODALS: Tuple[float, float, float, float] = (0.20, 0.20, 0.60, 0.60)

    def __init__(
        self,
        template_dir: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaBattleUIDetector")
        self.event_bus = event_bus or EventBus()
        self.template_dir = template_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates", "battle"))
        self.templates: Dict[str, np.ndarray] = {}
        self._load_templates()

        # ROI Padrão para Controles de Batalha (Canto inferior direito: 50% a 100% largura, 55% a 100% altura)
        self.hud_roi_norm = self.ROI_BATTLE_ACTIONS

    def _load_templates(self) -> None:
        """Carrega templates PNG da pasta de templates de batalha."""
        if not os.path.exists(self.template_dir):
            try:
                os.makedirs(self.template_dir, exist_ok=True)
            except Exception as e:
                self.logger.warning(f"Não foi possível criar diretório de templates: {e}")

        if os.path.exists(self.template_dir):
            for fname in os.listdir(self.template_dir):
                if fname.lower().endswith((".png", ".jpg", ".bmp")):
                    path = os.path.join(self.template_dir, fname)
                    img = cv2.imread(path)
                    if img is not None:
                        key = os.path.splitext(fname)[0].lower()
                        self.templates[key] = img
                        self.logger.debug(f"[BattleUI] Template carregado: {key} ({img.shape})")

    def match_template_in_image(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: float = 0.65,
    ) -> Tuple[bool, Tuple[int, int, int, int], Tuple[int, int], float]:
        """Executa matchTemplate com normalização de histograma (CLAHE) e retorna (found, (x, y, w, h), (cx, cy), max_val)."""
        ih, iw = image.shape[:2]
        th, tw = template.shape[:2]

        if th > ih or tw > iw or th == 0 or tw == 0:
            return False, (0, 0, 0, 0), (0, 0), 0.0

        try:
            # Converte para escala de cinza e equaliza iluminação via CLAHE
            img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
            tmpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template.copy()

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_norm = clahe.apply(img_gray)
            tmpl_norm = clahe.apply(tmpl_gray)

            res = cv2.matchTemplate(img_norm, tmpl_norm, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold:
                x, y = max_loc
                cx = x + tw // 2
                cy = y + th // 2
                return True, (x, y, tw, th), (cx, cy), float(max_val)
            return False, (0, 0, 0, 0), (0, 0), float(max(0.0, max_val))
        except Exception:
            return False, (0, 0, 0, 0), (0, 0), 0.0

    def detect_fight_button(
        self,
        frame: np.ndarray,
        roi_rect: Optional[Tuple[int, int, int, int]] = None,
    ) -> BattleUIElement:
        """Localiza o botão FIGHT na interface (Template -> OCR/Cor -> ROI -> Fullscreen)."""
        h, w = frame.shape[:2]
        
        # 1. Template Matching se disponível
        if "fight_button" in self.templates or "fight" in self.templates:
            tmpl = self.templates.get("fight_button") if "fight_button" in self.templates else self.templates.get("fight")
            
            # Busca em ROI primeiro
            if roi_rect:
                rx, ry, rw, rh = roi_rect
                roi = frame[ry:ry + rh, rx:rx + rw]
                found, bbox, center, conf = self.match_template_in_image(roi, tmpl, threshold=0.60)
                if found:
                    gx = rx + bbox[0]
                    gy = ry + bbox[1]
                    return BattleUIElement(
                        name="FIGHT",
                        bbox=(gx, gy, bbox[2], bbox[3]),
                        center=(rx + center[0], ry + center[1]),
                        confidence=conf,
                        is_present=True,
                        details={"source": "template_roi"},
                    )

            # Fallback Full Screen
            found, bbox, center, conf = self.match_template_in_image(frame, tmpl, threshold=0.60)
            if found:
                return BattleUIElement(
                    name="FIGHT",
                    bbox=bbox,
                    center=center,
                    confidence=conf,
                    is_present=True,
                    details={"source": "template_fullscreen"},
                )

        # 2. Heurística Visual Robusta de Botão de Batalha (Retângulo contrastante / Vermelho-Laranja / Acentuado)
        # Região provável do botão FIGHT no HUD inferior direito
        bx, by = int(w * 0.65), int(h * 0.70)
        bw, bh = int(w * 0.28), int(h * 0.22)
        roi = frame[by:by + bh, bx:bx + bw]
        if roi.size > 0:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            # Máscaras de cores vibrantes típicas do botão FIGHT (vermelho/laranja/dourado)
            m1 = cv2.inRange(hsv, np.array([0, 90, 90]), np.array([20, 255, 255]))
            m2 = cv2.inRange(hsv, np.array([160, 90, 90]), np.array([180, 255, 255]))
            mask = cv2.bitwise_or(m1, m2)
            active_pixels = int(np.count_nonzero(mask))
            total_pixels = int(roi.shape[0] * roi.shape[1])
            ratio = active_pixels / max(1, total_pixels)

            if ratio > 0.04:
                # Contornos do botão
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    best_cnt = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(best_cnt) > 250:
                        cx_l, cy_l, cw_l, ch_l = cv2.boundingRect(best_cnt)
                        gx = bx + cx_l
                        gy = by + cy_l
                        return BattleUIElement(
                            name="FIGHT",
                            bbox=(gx, gy, cw_l, ch_l),
                            center=(gx + cw_l // 2, gy + ch_l // 2),
                            confidence=min(0.95, 0.65 + ratio * 2.0),
                            is_present=True,
                            details={"source": "color_contour_roi"},
                        )

            # Detecção de contorno retangular saliente
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if (bw * bh * 0.05) < area < (bw * bh * 0.70):
                    cx_l, cy_l, cw_l, ch_l = cv2.boundingRect(cnt)
                    aspect = cw_l / max(1, ch_l)
                    if 1.2 <= aspect <= 4.0:
                        gx = bx + cx_l
                        gy = by + cy_l
                        return BattleUIElement(
                            name="FIGHT",
                            bbox=(gx, gy, cw_l, ch_l),
                            center=(gx + cw_l // 2, gy + ch_l // 2),
                            confidence=0.75,
                            is_present=True,
                            details={"source": "edge_contour_roi"},
                        )

        # Retorna elemento ausente com coordenadas estimadas de fallback
        default_cx = int(w * 0.78)
        default_cy = int(h * 0.80)
        return BattleUIElement(
            name="FIGHT",
            bbox=(int(w * 0.70), int(h * 0.75), int(w * 0.16), int(h * 0.10)),
            center=(default_cx, default_cy),
            confidence=0.0,
            is_present=False,
            details={"source": "none"},
        )

    def detect_run_button(self, frame: np.ndarray, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> BattleUIElement:
        """Detecta botão RUN / FUGIR."""
        if "run_button" in self.templates or "run" in self.templates:
            tmpl = self.templates.get("run_button") if "run_button" in self.templates else self.templates.get("run")
            found, bbox, center, conf = self.match_template_in_image(frame, tmpl, threshold=0.60)
            if found:
                return BattleUIElement(name="RUN", bbox=bbox, center=center, confidence=conf, is_present=True)
        
        h, w = frame.shape[:2]
        return BattleUIElement(name="RUN", center=(int(w * 0.88), int(h * 0.90)), confidence=0.0, is_present=False)

    def detect_team_button(self, frame: np.ndarray, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> BattleUIElement:
        """Detecta botão TEAM / POKEMON."""
        if "team_button" in self.templates or "team" in self.templates:
            tmpl = self.templates.get("team_button") if "team_button" in self.templates else self.templates.get("team")
            found, bbox, center, conf = self.match_template_in_image(frame, tmpl, threshold=0.60)
            if found:
                return BattleUIElement(name="TEAM", bbox=bbox, center=center, confidence=conf, is_present=True)
        
        h, w = frame.shape[:2]
        return BattleUIElement(name="TEAM", center=(int(w * 0.70), int(h * 0.90)), confidence=0.0, is_present=False)

    def detect_bag_button(self, frame: np.ndarray, roi_rect: Optional[Tuple[int, int, int, int]] = None) -> BattleUIElement:
        """Detecta botão BAG / BOLSA."""
        if "bag_button" in self.templates or "bag" in self.templates:
            tmpl = self.templates.get("bag_button") if "bag_button" in self.templates else self.templates.get("bag")
            found, bbox, center, conf = self.match_template_in_image(frame, tmpl, threshold=0.60)
            if found:
                return BattleUIElement(name="BAG", bbox=bbox, center=center, confidence=conf, is_present=True)
        
        h, w = frame.shape[:2]
        return BattleUIElement(name="BAG", center=(int(w * 0.88), int(h * 0.75)), confidence=0.0, is_present=False)

    def detect_enemy_hp_bar(self, frame: np.ndarray) -> BattleUIElement:
        """Detecta a barra de vida do adversário no quadrante superior direito ou centro-superior."""
        h, w = frame.shape[:2]
        # Região típica do HP inimigo
        hx, hy = int(w * 0.50), int(h * 0.05)
        hw, hh = int(w * 0.45), int(h * 0.30)
        roi = frame[hy:hy + hh, hx:hx + hw]

        if roi.size > 0:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            # Verde de HP
            mask_green = cv2.inRange(hsv, np.array([35, 70, 70]), np.array([85, 255, 255]))
            # Vermelho de HP baixo
            m1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([15, 255, 255]))
            m2 = cv2.inRange(hsv, np.array([165, 80, 80]), np.array([180, 255, 255]))
            mask_red = cv2.bitwise_or(m1, m2)
            mask_hp = cv2.bitwise_or(mask_green, mask_red)

            contours, _ = cv2.findContours(mask_hp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                cx_l, cy_l, cw_l, ch_l = cv2.boundingRect(cnt)
                aspect = cw_l / max(1, ch_l)
                if aspect >= 2.5 and cw_l >= 30:
                    gx = hx + cx_l
                    gy = hy + cy_l
                    return BattleUIElement(
                        name="ENEMY_HP",
                        bbox=(gx, gy, cw_l, ch_l),
                        center=(gx + cw_l // 2, gy + ch_l // 2),
                        confidence=0.88,
                        is_present=True,
                    )

        return BattleUIElement(name="ENEMY_HP", confidence=0.0, is_present=False)

    def detect_skill_menu(self, frame: np.ndarray) -> Tuple[bool, List[BattleUIElement]]:
        """Detecta se o menu de habilidades abriu (substituindo o botão FIGHT por N botões de ataque)."""
        h, w = frame.shape[:2]
        bx, by = int(w * 0.20), int(h * 0.65)
        bw, bh = int(w * 0.75), int(h * 0.32)
        roi = frame[by:by + bh, bx:bx + bw]

        skills: List[BattleUIElement] = []
        if roi.size == 0:
            return False, skills

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if (bw * bh * 0.015) < area < (bw * bh * 0.40):
                cx_l, cy_l, cw_l, ch_l = cv2.boundingRect(cnt)
                aspect = cw_l / max(1, ch_l)
                if 1.0 <= aspect <= 4.5 and cw_l >= 35 and ch_l >= 25:
                    gx = bx + cx_l
                    gy = by + cy_l
                    skills.append(BattleUIElement(
                        name=f"SKILL_{len(skills) + 1}",
                        bbox=(gx, gy, cw_l, ch_l),
                        center=(gx + cw_l // 2, gy + ch_l // 2),
                        confidence=0.85,
                        is_present=True,
                        details={"slot_index": len(skills) + 1},
                    ))

        # Ordena horizontalmente
        skills.sort(key=lambda s: (s.bbox[1] // 40, s.bbox[0]))
        menu_open = len(skills) >= 2
        return menu_open, skills

    def detect_post_battle_modal(self, frame: np.ndarray) -> Tuple[bool, str, Optional[BattleUIElement]]:
        """Detecta telas modais intermediárias pós-batalha (VICTORY, DEFEAT, REWARD, LEVEL_UP, CLAIM, CONTINUE)."""
        h, w = frame.shape[:2]
        cx_min, cx_max = int(w * 0.20), int(w * 0.80)
        cy_min, cy_max = int(h * 0.20), int(h * 0.80)
        roi = frame[cy_min:cy_max, cx_min:cx_max]

        if roi.size == 0:
            return False, "NONE", None

        # 1. Template matching se disponível
        for modal_key in ["victory", "victory_screen", "reward", "level_up", "defeat", "ok_button", "continue_button"]:
            if modal_key in self.templates:
                tmpl = self.templates[modal_key]
                found, bbox, center, conf = self.match_template_in_image(roi, tmpl, threshold=0.65)
                if found:
                    gx = cx_min + bbox[0]
                    gy = cy_min + bbox[1]
                    elem = BattleUIElement(
                        name="MODAL_CONFIRM",
                        bbox=(gx, gy, bbox[2], bbox[3]),
                        center=(cx_min + center[0], cy_min + center[1]),
                        confidence=conf,
                        is_present=True,
                    )
                    m_type = "VICTORY_MODAL" if "victory" in modal_key else ("DEFEAT_MODAL" if "defeat" in modal_key else "REWARD_MODAL")
                    return True, m_type, elem

        # 2. Heurística visual de modal central contrastante
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_w = cx_max - cx_min
        roi_h = cy_max - cy_min

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if (roi_w * roi_h * 0.04) < area < (roi_w * roi_h * 0.85):
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bw / max(1, bh)
                if 1.2 <= aspect <= 5.0 and bw >= 80 and bh >= 30:
                    gx = cx_min + bx
                    gy = cy_min + by
                    elem = BattleUIElement(
                        name="MODAL_CONFIRM",
                        bbox=(gx, gy, bw, bh),
                        center=(gx + bw // 2, gy + bh // 2),
                        confidence=0.78,
                        is_present=True,
                    )
                    return True, "GENERIC_MODAL", elem

        return False, "NONE", None

    def analyze_battle_ui(self, frame: Optional[np.ndarray]) -> BattleUIDetectionResult:
        """Executa a análise completa da interface de batalha e computa a pontuação de confirmação."""
        now = time.time()
        if frame is None or frame.size == 0:
            return BattleUIDetectionResult(timestamp=now)

        h, w = frame.shape[:2]
        roi_rect = (
            int(w * self.hud_roi_norm[0]),
            int(h * self.hud_roi_norm[1]),
            int(w * self.hud_roi_norm[2]),
            int(h * self.hud_roi_norm[3]),
        )

        fight_elem = self.detect_fight_button(frame, roi_rect=roi_rect)
        run_elem = self.detect_run_button(frame, roi_rect=roi_rect)
        team_elem = self.detect_team_button(frame, roi_rect=roi_rect)
        bag_elem = self.detect_bag_button(frame, roi_rect=roi_rect)
        enemy_hp_elem = self.detect_enemy_hp_bar(frame)
        skill_menu_open, skill_elements = self.detect_skill_menu(frame)
        modal_detected, modal_type, modal_confirm_elem = self.detect_post_battle_modal(frame)

        # Computa battle_ui_score ponderado
        fight_score = fight_elem.confidence * 0.45 if fight_elem.is_present else 0.0
        enemy_hp_score = enemy_hp_elem.confidence * 0.30 if enemy_hp_elem.is_present else 0.0
        run_score = run_elem.confidence * 0.10 if run_elem.is_present else 0.0
        team_score = team_elem.confidence * 0.10 if team_elem.is_present else 0.0
        bag_score = bag_elem.confidence * 0.05 if bag_elem.is_present else 0.0
        skill_menu_score = 0.40 if skill_menu_open else 0.0

        total_score = fight_score + enemy_hp_score + run_score + team_score + bag_score + skill_menu_score
        battle_ui_confirmed = bool(total_score >= 0.35 or fight_elem.is_present or skill_menu_open or enemy_hp_elem.is_present or modal_detected)

        elements = {
            "FIGHT": fight_elem,
            "RUN": run_elem,
            "TEAM": team_elem,
            "BAG": bag_elem,
            "ENEMY_HP": enemy_hp_elem,
        }
        for s in skill_elements:
            elements[s.name] = s
        if modal_confirm_elem:
            elements["MODAL_CONFIRM"] = modal_confirm_elem

        result = BattleUIDetectionResult(
            timestamp=now,
            in_battle=battle_ui_confirmed,
            battle_ui_confirmed=battle_ui_confirmed,
            battle_ui_score=round(float(total_score), 3),
            fight_button=fight_elem,
            run_button=run_elem,
            team_button=team_elem,
            bag_button=bag_elem,
            enemy_hp_bar=enemy_hp_elem,
            skill_menu_open=skill_menu_open,
            modal_detected=modal_detected,
            modal_type=modal_type,
            modal_confirm_button=modal_confirm_elem,
            elements=elements,
            roi_used=roi_rect,
        )

        if modal_detected:
            self.event_bus.publish(
                EventType.MODAL_DETECTED,
                data={"modal_type": modal_type, "confirm_coords": modal_confirm_elem.center if modal_confirm_elem else None},
                category="COMBAT",
                level="INFO",
                message=f"MODAL_DETECTED: Modal pós-combate detectado ({modal_type}).",
            )

        if battle_ui_confirmed:
            self.event_bus.publish(
                EventType.BATTLE_UI_DETECTED,
                data={
                    "timestamp": now,
                    "score": result.battle_ui_score,
                    "fight_present": fight_elem.is_present,
                    "skill_menu_open": skill_menu_open,
                    "enemy_hp_present": enemy_hp_elem.is_present,
                },
                category="PERCEPTION",
                level="INFO",
                message=f"BATTLE_UI_DETECTED: Confiança={result.battle_ui_score:.2f} (Fight={fight_elem.is_present}, Skills={skill_menu_open})",
            )
            self.event_bus.publish(
                EventType.BATTLE_UI_CONFIRMED,
                data={"score": result.battle_ui_score},
                category="COMBAT",
                level="INFO",
                message=f"BATTLE_UI_CONFIRMED: Interface de Batalha Ativa (Score={result.battle_ui_score:.2f})",
            )
            # Bloqueio estrito de cristal
            self.event_bus.publish(
                EventType.CRYSTAL_SEARCH_BLOCKED,
                data={"reason": "BATTLE_UI_CONFIRMED"},
                category="SAFETY",
                level="DEBUG",
                message="CRYSTAL_SEARCH_BLOCKED: Busca por cristal desabilitada no modo de batalha.",
            )
            self.event_bus.publish(
                EventType.CRYSTAL_DETECTION_DISABLED_IN_BATTLE,
                data={"reason": "IN_BATTLE_UI"},
                category="PERCEPTION",
                level="DEBUG",
                message="CRYSTAL_DETECTION_DISABLED_IN_BATTLE: Detector de cristal desativado.",
            )

        return result
