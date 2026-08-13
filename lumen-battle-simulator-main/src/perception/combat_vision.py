import logging
import time
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import cv2

from src.models.enums import Element
from src.models.combat_vision import SkillSlot, EnemyTarget, PositionInfo, CombatSnapshot

logger = logging.getLogger("LumenaCombatVision")


class CombatVisionAnalyzer:
    """Analisador visual de combate dinâmico (Vision-First / SkillScanner):

    Detecta barra de habilidades com N slots arbitrários (1, 2, 4, 6, 8, 10+),
    analisa cooldowns visuais, posições relativas de jogador e alvos, distância euclidiana,
    alvos inimigos e realiza transformações DPI-aware.
    """

    def __init__(self, templates: Optional[Dict[str, np.ndarray]] = None) -> None:
        self.logger = logging.getLogger("LumenaCombatVision")
        self.templates: Dict[str, np.ndarray] = templates or {}
        self._dpi_scale: float = 1.0
        self._custom_hotkey_map: Dict[int, str] = {
            1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "0"
        }

    def set_dpi_scale(self, scale: float) -> None:
        self._dpi_scale = max(0.5, scale)

    def set_hotkey_mapping(self, mapping: Dict[int, str]) -> None:
        """Permite mapeamento configurável de teclas por slot."""
        self._custom_hotkey_map.update(mapping)

    def screen_to_client(self, point: Tuple[int, int], window_origin: Tuple[int, int]) -> Tuple[int, int]:
        """Converte coordenadas da tela para coordenadas de cliente da janela."""
        return (int(point[0] - window_origin[0]), int(point[1] - window_origin[1]))

    def client_to_screen(self, point: Tuple[int, int], window_origin: Tuple[int, int]) -> Tuple[int, int]:
        """Converte coordenadas de cliente para coordenadas globais de tela com DPI scaling."""
        return (int((point[0] + window_origin[0]) * self._dpi_scale), int((point[1] + window_origin[1]) * self._dpi_scale))

    def analyze_frame(self, frame: Optional[np.ndarray], timestamp: Optional[float] = None) -> CombatSnapshot:
        """Executa a análise visual completa de combate no frame recebido."""
        ts = timestamp or time.time()
        if frame is None or frame.size == 0:
            return CombatSnapshot(timestamp=ts, in_battle=False)

        h, w = frame.shape[:2]

        # 1. Detecção do Botão FIGHT / HUD
        fight_pos, fight_conf = self.detect_fight_button(frame)
        in_battle = fight_pos is not None or fight_conf >= 0.65

        # 2. Detecção de HP do Inimigo e Jogador
        enemy_hp = self.detect_enemy_hp_percentage(frame)
        player_hp = self.detect_player_hp_percentage(frame)

        if not in_battle and (enemy_hp is not None and player_hp is not None):
            in_battle = True

        # 3. Detecção Dinâmica de Slots de Habilidades (N slots)
        detected_skills = self.detect_skill_slots(frame, in_battle, fight_pos)

        # 4. Detecção de Alvos Inimigos na Arena
        detected_enemies = self.detect_enemy_targets(frame)
        target_enemy = detected_enemies[0] if detected_enemies else None

        # 5. Posição e Distância de Combate
        player_pos, target_pos, distance, pos_info = self.estimate_combat_positions(frame, target_enemy)

        # 6. Detecção de Vitória ou Derrota
        victory = False
        defeat = False
        if in_battle:
            if enemy_hp is not None and enemy_hp <= 0.02:
                victory = True
            if player_hp is not None and player_hp <= 0.0:
                defeat = True

        return CombatSnapshot(
            timestamp=ts,
            player_hp=player_hp if player_hp is not None else 1.0,
            player_resource=100.0,
            player_position=player_pos,
            target_enemy=target_enemy,
            detected_enemies=detected_enemies,
            available_skills=detected_skills,
            combat_state="BATTLE" if in_battle else "IDLE",
            position_info=pos_info,
            dialog_active=False,
            in_battle=in_battle,
            victory_detected=victory,
            defeat_detected=defeat,
            fight_button_pos=fight_pos,
        )

    def estimate_combat_positions(
        self,
        frame: np.ndarray,
        target_enemy: Optional[EnemyTarget] = None,
    ) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]], float, PositionInfo]:
        """Estima a posição do jogador, posição do alvo e distância tática euclidiana."""
        h, w = frame.shape[:2]
        # Posição do jogador no centro/metade inferior esquerda da tela
        player_pos = (int(w * 0.35), int(h * 0.65))

        target_pos = target_enemy.center if target_enemy else (int(w * 0.70), int(h * 0.35))
        distance = float(np.sqrt((target_pos[0] - player_pos[0]) ** 2 + (target_pos[1] - player_pos[1]) ** 2)) if target_enemy else 0.0

        required_range = 180.0
        pos_state = "ATTACK_POSITION_READY"
        if target_enemy:
            if distance > 320.0:
                pos_state = "APPROACH_TARGET"
            elif distance < 80.0:
                pos_state = "MAINTAIN_DISTANCE"
            else:
                pos_state = "ATTACK_POSITION_READY"

        pos_info = PositionInfo(
            player_pos=player_pos,
            target_pos=target_pos,
            distance=distance,
            required_range=required_range,
            positioning_state=pos_state,
            movement_confirmed=True,
        )

        return player_pos, target_pos, distance, pos_info

    def detect_fight_button(self, frame: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """Localiza o botão FIGHT na interface via cor/formato ou template."""
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
                    cx = int(w * 0.3 + x + bw // 2)
                    cy = int(h * 0.5 + y + bh // 2)
                    return (cx, cy), 0.85

        return None, 0.0

    def detect_skill_slots(
        self,
        frame: np.ndarray,
        in_battle: bool,
        fight_pos: Optional[Tuple[int, int]] = None,
    ) -> List[SkillSlot]:
        """Detecta dinamicamente a barra de habilidades (SkillScanner) e analisa cada slot quanto à disponibilidade e cooldown."""
        h, w = frame.shape[:2]
        skills: List[SkillSlot] = []

        # Região de interesse (HUD inferior onde as habilidades são renderizadas)
        roi_top = int(h * 0.65)
        roi_bottom = int(h * 0.96)
        roi_left = int(w * 0.15)
        roi_right = int(w * 0.85)

        roi = frame[roi_top:roi_bottom, roi_left:roi_right]
        if roi.size == 0:
            return self._generate_fallback_skills(w, h)

        # 1. Procura contornos de botões na barra de habilidades
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detected_boxes = []

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Filtra botões de tamanho coerente com slots de habilidades (ex: 30x30 a 200x120)
            if 30 <= bw <= 200 and 30 <= bh <= 120:
                aspect = bw / max(1, bh)
                if 0.6 <= aspect <= 3.0:
                    detected_boxes.append((x, y, bw, bh))

        # Ordena caixas da esquerda para a direita
        detected_boxes.sort(key=lambda b: (b[0]))

        # Se detectou caixas válidas, constrói os slots dinâmicos
        if len(detected_boxes) >= 2:
            slot_idx = 1
            for bx, by, bw, bh in detected_boxes:
                gx = roi_left + bx
                gy = roi_top + by
                cx = gx + bw // 2
                cy = gy + bh // 2

                # Analisa cooldown visual (região escura ou dessaturada = cooldown)
                slot_crop = frame[gy:gy + bh, gx:gx + bw]
                is_available, cd_val, cd_ratio = self._evaluate_cooldown_detailed(slot_crop)

                hotkey = self._custom_hotkey_map.get(slot_idx, str(slot_idx) if slot_idx <= 9 else None)

                skills.append(
                    SkillSlot(
                        id=f"skill_slot_{slot_idx}",
                        index=slot_idx,
                        slot_index=slot_idx,
                        screen_x=gx,
                        screen_y=gy,
                        width=bw,
                        height=bh,
                        center_x=cx,
                        center_y=cy,
                        icon_detected=True,
                        cooldown=cd_val,
                        cooldown_ratio=cd_ratio,
                        cooldown_remaining=cd_val,
                        available=is_available,
                        disabled=not is_available,
                        confidence=0.92,
                        hotkey=hotkey,
                        skill_name=f"Skill #{slot_idx}",
                        element=Element.NORMAL,
                        power=40 + (slot_idx * 10),
                        range_type="RANGED" if slot_idx % 2 == 1 else "MELEE",
                        last_seen=time.time(),
                    )
                )
                slot_idx += 1

        # Se a visão não encontrou contornos nítidos, fornece grade visual estimada
        if not skills:
            skills = self._generate_fallback_skills(w, h)

        return skills

    def _evaluate_cooldown_detailed(self, slot_crop: np.ndarray) -> Tuple[bool, float, float]:
        """Avalia detalhadamente se a habilidade está em cooldown com base na luminosidade média e histograma."""
        if slot_crop.size == 0:
            return True, 0.0, 0.0

        gray = cv2.cvtColor(slot_crop, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))

        # Se muito escuro (máscara de cooldown escura típica do WebGL), calcula tempo e ratio estimado
        if mean_brightness < 45.0:
            cd_time = max(0.5, (45.0 - mean_brightness) / 10.0)
            cd_ratio = max(0.1, min(1.0, (45.0 - mean_brightness) / 45.0))
            return False, cd_time, cd_ratio

        return True, 0.0, 0.0

    def analyze_slot_cooldown(self, slot_crop: np.ndarray) -> bool:
        """Retorna True se o slot estiver em cooldown (escurecido/desativado)."""
        is_available, _, _ = self._evaluate_cooldown_detailed(slot_crop)
        return not is_available

    def _evaluate_cooldown(self, slot_crop: np.ndarray) -> Tuple[bool, float]:
        avail, cd, _ = self._evaluate_cooldown_detailed(slot_crop)
        return avail, cd

    def _generate_fallback_skills(self, w: int, h: int) -> List[SkillSlot]:
        """Gera grade proporcional de habilidades caso o HUD esteja em baixa resolução."""
        skills = []
        base_names = [
            ("WaterPulse", Element.WATER, 60, "RANGED"),
            ("FlameBurst", Element.FIRE, 75, "RANGED"),
            ("LeafBlade", Element.GRASS, 55, "MELEE"),
            ("ThunderShock", Element.ELECTRIC, 50, "RANGED"),
            ("Tackle", Element.NORMAL, 40, "MELEE"),
            ("QuickAttack", Element.NORMAL, 35, "MELEE"),
        ]

        slot_w = int(w * 0.08)
        slot_h = int(h * 0.06)
        start_x = int(w * 0.25)
        y = int(h * 0.78)

        for i, (name, elem, power, rtype) in enumerate(base_names, 1):
            x = start_x + (i - 1) * int(slot_w * 1.3)
            skills.append(
                SkillSlot(
                    id=f"skill_slot_{i}",
                    index=i,
                    slot_index=i,
                    screen_x=x,
                    screen_y=y,
                    width=slot_w,
                    height=slot_h,
                    center_x=x + slot_w // 2,
                    center_y=y + slot_h // 2,
                    icon_detected=True,
                    available=True,
                    cooldown=0.0,
                    cooldown_ratio=0.0,
                    cooldown_remaining=0.0,
                    disabled=False,
                    confidence=0.88,
                    hotkey=str(i),
                    skill_name=name,
                    element=elem,
                    power=power,
                    range_type=rtype,
                    last_seen=time.time(),
                )
            )

        return skills

    def detect_enemy_targets(self, frame: np.ndarray) -> List[EnemyTarget]:
        """Detecta alvos inimigos presentes na tela através de contornos e posições da metade superior."""
        h, w = frame.shape[:2]
        enemies: List[EnemyTarget] = []

        # Região superior direita/central onde os inimigos ficam posicionados no combate
        roi = frame[int(h * 0.15):int(h * 0.60), int(w * 0.45):int(w * 0.90)]
        if roi.size == 0:
            return enemies

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 30, 100)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        target_id = 1

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if (w * h * 0.005) < area < (w * h * 0.10):
                x, y, bw, bh = cv2.boundingRect(cnt)
                gx = int(w * 0.45) + x
                gy = int(h * 0.15) + y
                cx = gx + bw // 2
                cy = gy + bh // 2

                enemies.append(
                    EnemyTarget(
                        target_id=target_id,
                        bbox=(gx, gy, bw, bh),
                        center=(cx, cy),
                        confidence=0.89,
                        hp_estimate=1.0,
                        distance=float(np.sqrt((cx - int(w * 0.35)) ** 2 + (cy - int(h * 0.65)) ** 2)),
                        state="IDLE",
                        element=Element.FIRE,
                        weakness=Element.WATER,
                        priority=100.0,
                        name=f"Enemy #{target_id}",
                    )
                )
                target_id += 1

        # Fallback se não encontrou contorno nítido mas há frame de combate
        if not enemies:
            cx = int(w * 0.70)
            cy = int(h * 0.35)
            enemies.append(
                EnemyTarget(
                    target_id=1,
                    bbox=(int(w * 0.62), int(h * 0.25), int(w * 0.16), int(h * 0.20)),
                    center=(cx, cy),
                    confidence=0.75,
                    hp_estimate=1.0,
                    distance=float(np.sqrt((cx - int(w * 0.35)) ** 2 + (cy - int(h * 0.65)) ** 2)),
                    state="IDLE",
                    element=Element.FIRE,
                    weakness=Element.WATER,
                    priority=100.0,
                    name="Target Enemy",
                )
            )

        return enemies

    def detect_enemy_hp_percentage(self, frame: np.ndarray) -> Optional[float]:
        """Detecta a barra de vida do oponente."""
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.05):int(h * 0.35), int(w * 0.45):int(w * 0.95)]
        if roi.size == 0:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask_green = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        mask_red1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([165, 100, 100]), np.array([180, 255, 255]))
        mask_hp = cv2.bitwise_or(mask_green, cv2.bitwise_or(mask_red1, mask_red2))

        contours, _ = cv2.findContours(mask_hp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw > 30 and 4 <= bh <= 25 and (bw / max(1, bh)) > 3.0:
                crop = mask_hp[y:y + bh, x:x + bw]
                filled = np.count_nonzero(crop)
                pct = filled / max(1, bw * bh)
                return max(0.0, min(1.0, float(pct)))

        return None

    def detect_player_hp_percentage(self, frame: np.ndarray) -> Optional[float]:
        """Detecta a barra de vida do jogador."""
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.45):int(h * 0.85), int(w * 0.05):int(w * 0.55)]
        if roi.size == 0:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask_green = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        mask_red1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([165, 100, 100]), np.array([180, 255, 255]))
        mask_hp = cv2.bitwise_or(mask_green, cv2.bitwise_or(mask_red1, mask_red2))

        contours, _ = cv2.findContours(mask_hp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw > 30 and 4 <= bh <= 25 and (bw / max(1, bh)) > 3.0:
                crop = mask_hp[y:y + bh, x:x + bw]
                filled = np.count_nonzero(crop)
                pct = filled / max(1, bw * bh)
                return max(0.0, min(1.0, float(pct)))

        return None
