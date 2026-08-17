"""
LUMENA BOT v4.0 — HUMANIZED INPUT DISPATCHER & CUBIC BÉZIER ENGINE
===================================================================
Despachador físico de entradas com curvas de Bézier cúbicas, micro-jitter estocástico,
distribuição gaussiana de duração de cliques e perfil de velocidade senoidal.
"""

import time
import math
import random
import logging
from typing import List, Tuple, Optional, Callable, Any

logger = logging.getLogger("LumenaInputDispatcher")


def generate_cubic_bezier_trajectory(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    steps: int = 25,
    jitter_magnitude: float = 1.5,
) -> List[Tuple[int, int]]:
    """Gera uma trajetória contínua suave via Curva de Bézier Cúbica com micro-jitter estocástico."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)

    if dist < 5:
        return [(x0, y0), (x1, y1)]

    # Ângulo e vetor perpendicular
    angle = math.atan2(dy, dx)
    perp_angle = angle + math.pi / 2

    # Desvio proporcional dos pontos de controle (10% a 30% da distância)
    dev1 = (random.random() * 0.4 - 0.2) * dist
    dev2 = (random.random() * 0.4 - 0.2) * dist

    # Ponto de controle 1 (1/3 do caminho + desvio perpendicular)
    ctrl1_dist = dist * (0.25 + random.random() * 0.15)
    cx1 = x0 + math.cos(angle) * ctrl1_dist + math.cos(perp_angle) * dev1
    cy1 = y0 + math.sin(angle) * ctrl1_dist + math.sin(perp_angle) * dev1

    # Ponto de controle 2 (2/3 do caminho + desvio perpendicular)
    ctrl2_dist = dist * (0.60 + random.random() * 0.15)
    cx2 = x0 + math.cos(angle) * ctrl2_dist + math.cos(perp_angle) * dev2
    cy2 = y0 + math.sin(angle) * ctrl2_dist + math.sin(perp_angle) * dev2

    num_steps = max(5, min(60, steps))
    points: List[Tuple[int, int]] = []

    for i in range(num_steps + 1):
        # Perfil de velocidade senoidal (Ease-in-out)
        raw_t = i / float(num_steps)
        t = 0.5 * (1.0 - math.cos(raw_t * math.pi))

        # Equação de Bézier Cúbica: B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
        u = 1.0 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t

        px = uuu * x0 + 3 * uu * t * cx1 + 3 * u * tt * cx2 + ttt * x1
        py = uuu * y0 + 3 * uu * t * cy1 + 3 * u * tt * cy2 + ttt * y1

        # Micro-jitter estocástico (exceto no início e no final)
        if 0 < i < num_steps:
            jx = (random.random() * 2 - 1) * jitter_magnitude
            jy = (random.random() * 2 - 1) * jitter_magnitude
            px += jx
            py += jy

        points.append((int(round(px)), int(round(py))))

    # Garante início e fim exatos
    points[0] = (x0, y0)
    points[-1] = (x1, y1)

    return points


class HumanizedInputDispatcher:
    """Despachador de input com temporização realista e guarda de limites."""

    def __init__(self, input_backend: Optional[Any] = None) -> None:
        self.logger = logging.getLogger("LumenaInputDispatcher")
        self.backend = input_backend
        self._current_mouse_pos: Tuple[int, int] = (960, 540)

    def move_to(self, x: int, y: int, bounds: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """Move o cursor até (x, y) seguindo trajetória Bézier cúbica."""
        x0, y0 = self._current_mouse_pos
        points = generate_cubic_bezier_trajectory(x0, y0, x, y)

        for px, py in points:
            if bounds:
                bx, by, bw, bh = bounds
                px = max(bx, min(bx + bw - 1, px))
                py = max(by, min(by + bh - 1, py))

            if self.backend and hasattr(self.backend, "mouse_move"):
                self.backend.mouse_move(px, py)
            time.sleep(0.002)

        self._current_mouse_pos = (x, y)
        return True

    def humanized_click(
        self,
        x: int,
        y: int,
        bounds: Optional[Tuple[int, int, int, int]] = None,
        reaction_delay: bool = True,
    ) -> bool:
        """Executa clique humanizado com reação realista e duração gaussiana de clique."""
        if bounds:
            bx, by, bw, bh = bounds
            if not (bx <= x <= bx + bw and by <= y <= by + bh):
                self.logger.warning(f"🛑 [INPUT GUARD] Clique em ({x}, {y}) rejeitado fora dos limites {bounds}")
                return False

        if reaction_delay:
            # Intervalo de reação: 120ms a 280ms
            delay = random.uniform(0.12, 0.28)
            time.sleep(delay)

        self.move_to(x, y, bounds=bounds)

        # Duração gaussiana do clique (45ms a 85ms)
        press_duration = max(0.045, min(0.095, random.gauss(0.065, 0.012)))

        if self.backend and hasattr(self.backend, "mouse_down"):
            self.backend.mouse_down()
            time.sleep(press_duration)
            self.backend.mouse_up()
        elif self.backend and hasattr(self.backend, "click"):
            self.backend.click(x, y)
            time.sleep(press_duration)

        return True

    def humanized_press_key(self, key: str, duration: Optional[float] = None) -> bool:
        """Pressiona uma tecla com duração humanizada."""
        dur = duration if duration is not None else max(0.045, min(0.12, random.gauss(0.075, 0.015)))
        if self.backend and hasattr(self.backend, "press_key"):
            return bool(self.backend.press_key(key, duration=dur))
        return False
