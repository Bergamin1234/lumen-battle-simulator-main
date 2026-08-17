"""
LUMENA BOT v5.0 — INTELLIGENT GRASS PATROL & ANTI-STUCK ENGINE
==============================================================
Motor de patrulha oscilatória no mato alto (Grass Wiggle) com:
- Oscilação A/D contínua (450ms A -> 35ms -> 450ms D -> 35ms)
- Ancoragem no mato (Grass Anchoring) via máscara HSV de vegetação [35..75, 80..255, 40..160]
- Proteção contra colisão e travamento em paredes (Optical Flow Collision Guard)
- Interrupção instantânea de teclas W, A, S, D na transição para combate
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np
import cv2

from src.core.event_bus import EventBus, EventType
from src.input.input_controller import InputController


class GrassPatrolEngine:
    """Motor de patrulha oscilatória com ancoragem de vegetação e proteção anti-stuck."""

    GRASS_HSV_LOWER = np.array([35, 80, 40], dtype=np.uint8)
    GRASS_HSV_UPPER = np.array([75, 255, 160], dtype=np.uint8)

    def __init__(
        self,
        input_controller: Optional[InputController] = None,
        event_bus: Optional[EventBus] = None,
        step_duration: float = 0.45,
        pause_duration: float = 0.035,
    ) -> None:
        self.logger = logging.getLogger("LumenaGrassPatrol")
        self.input_ctrl = input_controller or InputController()
        self.event_bus = event_bus or EventBus()
        self.step_duration = step_duration
        self.pause_duration = pause_duration

        self.current_direction: str = "a"
        self.cycle_count: int = 0
        self._last_key_press_time: float = 0.0
        self._last_frame_center: Optional[np.ndarray] = None
        self._is_active: bool = False
        self._collision_count: int = 0

    def compute_grass_density(self, frame: Optional[np.ndarray]) -> float:
        """Calcula o percentual de pixels de grama sob e ao redor do avatar (ROI central 30%)."""
        if frame is None or frame.size == 0:
            return 1.0
        h, w = frame.shape[:2]
        cy_min, cy_max = int(h * 0.35), int(h * 0.65)
        cx_min, cx_max = int(w * 0.35), int(w * 0.65)
        center_roi = frame[cy_min:cy_max, cx_min:cx_max]

        if center_roi.size == 0:
            return 1.0

        hsv = cv2.cvtColor(center_roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.GRASS_HSV_LOWER, self.GRASS_HSV_UPPER)
        total_pixels = center_roi.shape[0] * center_roi.shape[1]
        grass_pixels = int(np.count_nonzero(mask))
        return float(grass_pixels) / float(max(1, total_pixels))

    def detect_optical_flow_displacement(
        self,
        prev_frame: Optional[np.ndarray],
        curr_frame: Optional[np.ndarray],
    ) -> float:
        """Estima o deslocamento médio de pixels no centro da tela via fluxo óptico / diff."""
        if prev_frame is None or curr_frame is None or prev_frame.shape != curr_frame.shape:
            return 5.0
        h, w = prev_frame.shape[:2]
        roi_prev = prev_frame[int(h * 0.25):int(h * 0.75), int(w * 0.25):int(w * 0.75)]
        roi_curr = curr_frame[int(h * 0.25):int(h * 0.75), int(w * 0.25):int(w * 0.75)]

        gray_prev = cv2.cvtColor(roi_prev, cv2.COLOR_BGR2GRAY)
        gray_curr = cv2.cvtColor(roi_curr, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(gray_prev, gray_curr)
        mean_delta = float(np.mean(diff))
        return mean_delta

    def execute_patrol_step(
        self,
        current_frame: Optional[np.ndarray] = None,
        prev_frame: Optional[np.ndarray] = None,
    ) -> Tuple[str, bool]:
        """
        Executa um ciclo da patrulha oscilatória no mato.
        Retorna (tecla_executada, anti_stuck_acionado).
        """
        # 1. Ancoragem de Vegetação (Grass Anchoring)
        if current_frame is not None:
            density = self.compute_grass_density(current_frame)
            if density < 0.35:
                # Avatar saiu do mato -> Aplica pulso corretivo na direção oposta
                corrective_key = "d" if self.current_direction == "a" else "a"
                self.logger.warning(f"🌿 [GRASS ANCHOR] Densidade de grama baixa ({density:.2f}). Corrigindo com '{corrective_key.upper()}'.")
                self.input_ctrl.press_key(corrective_key, duration=0.30)
                self.current_direction = corrective_key
                return corrective_key, False

        # 2. Detecção de Colisão / Optical Flow Anti-Stuck
        if prev_frame is not None and current_frame is not None:
            displacement = self.detect_optical_flow_displacement(prev_frame, current_frame)
            if displacement < 2.0:
                self._collision_count += 1
                if self._collision_count >= 2:
                    self.logger.warning(f"🛑 [ANTI-STUCK] Colisão detectada (deslocamento={displacement:.2f}px). Executando desengate.")
                    self.event_bus.publish(
                        EventType.COLLISION_STUCK_DETECTED,
                        data={"displacement": displacement, "direction": self.current_direction},
                        category="NAVIGATION",
                        level="WARNING",
                        message="COLLISION_STUCK_DETECTED: Avatar colidindo com obstáculo.",
                    )
                    self.disengage_collision()
                    self._collision_count = 0
                    return "DISENGAGE", True
            else:
                self._collision_count = 0

        # 3. Oscilação A/D contínua
        key = self.current_direction
        self.input_ctrl.press_key(key, duration=self.step_duration)
        time.sleep(self.pause_duration)

        # Alterna direção para o próximo passo
        self.current_direction = "d" if self.current_direction == "a" else "a"
        self.cycle_count += 1

        # A cada 4 ciclos A/D, aplica micro-pulso vertical (W ou S) para permanecer no centro do mato
        if self.cycle_count % 4 == 0:
            vert_key = "w" if (self.cycle_count // 4) % 2 == 0 else "s"
            self.input_ctrl.press_key(vert_key, duration=0.15)
            time.sleep(0.02)

        return key, False

    def disengage_collision(self) -> None:
        """Rotina de desengate: recuo oposto 350ms -> pulso perpendicular 250ms."""
        self.release_all_movement_keys()
        opposite_key = "d" if self.current_direction == "a" else "a"
        self.input_ctrl.press_key(opposite_key, duration=0.35)
        time.sleep(0.04)
        vert_key = "w" if (self.cycle_count % 2 == 0) else "s"
        self.input_ctrl.press_key(vert_key, duration=0.25)
        time.sleep(0.04)
        self.current_direction = opposite_key

    def release_all_movement_keys(self) -> None:
        """Solta imediatamente todas as teclas de movimentação (W, A, S, D)."""
        backend = getattr(self.input_ctrl, "backend", None)
        if backend and hasattr(backend, "key_up"):
            for k in ("w", "a", "s", "d"):
                backend.key_up(k)
        elif hasattr(self.input_ctrl, "release_key"):
            for k in ("w", "a", "s", "d"):
                self.input_ctrl.release_key(k)


class MovementController(GrassPatrolEngine):
    """Classe de compatibilidade com nomes legados."""
    pass
