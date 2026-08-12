import time
import math
import logging
from collections import deque
from typing import Dict, List, Optional, Set, Tuple, Any

from src.models.enums import AgentState, MoveDirection
from src.models.lumen import StateSnapshot, AtomicAction


class WorldMemory:
    """Modelo topológico e memória de sessão em memória do agente (posição, heading, heatmap, landmarks e histórico)."""

    def __init__(
        self,
        grid_cell_size: float = 1.0,
        max_snapshots: int = 10,
        max_actions: int = 20,
    ) -> None:
        self.logger = logging.getLogger("LumenaMemory")
        self.grid_cell_size = grid_cell_size

        # Estimativa de posição contínua e vetor de orientação (dx, dy)
        self.estimated_position: Tuple[float, float] = (0.0, 0.0)
        self.heading_vector: Tuple[float, float] = (0.0, 1.0)  # Padrão: apontando para baixo (+Y / Sul)

        # Heatmap de visitas: (gx, gy) -> int (quantidade de visitas)
        self.exploration_heatmap: Dict[Tuple[int, int], int] = {}

        # Mapa de obstáculos: {(gx, gy)}
        self.obstacle_map: Set[Tuple[int, int]] = set()

        # Marcos conhecidos: name -> dict(x, y, confidence, last_seen, data)
        self.known_landmarks: Dict[str, Dict[str, Any]] = {}

        # Watchdog e contadores de ação
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.last_safe_state: Optional[AgentState] = None
        self.last_safe_position: Tuple[float, float] = (0.0, 0.0)

        # Buffers limitados (sem vazamento de memória)
        self.recent_snapshots: deque[StateSnapshot] = deque(maxlen=max_snapshots)
        self.recent_actions: deque[Tuple[AtomicAction, bool]] = deque(maxlen=max_actions)

    # -------------------------------------------------------------
    # Posição e Orientação (Heading)
    # -------------------------------------------------------------
    def set_position(self, x: float, y: float) -> None:
        """Define a posição absoluta estimada."""
        self.estimated_position = (float(x), float(y))

    def update_position(self, dx: float, dy: float, scale: float = 1.0) -> Tuple[float, float]:
        """Aplica deslocamento relativo à posição estimada."""
        curr_x, curr_y = self.estimated_position
        new_x = curr_x + (dx * scale)
        new_y = curr_y + (dy * scale)
        self.estimated_position = (new_x, new_y)
        return self.estimated_position

    def set_heading(self, dx: float, dy: float) -> None:
        """Atualiza o vetor de direção/orientação do personagem."""
        norm = math.hypot(dx, dy)
        if norm > 0:
            self.heading_vector = (dx / norm, dy / norm)
        else:
            self.heading_vector = (0.0, 0.0)

    def set_heading_from_direction(self, direction: str) -> None:
        """Converte direção ('w', 'a', 's', 'd') em vetor de heading."""
        d = direction.lower().strip()
        dir_map = {
            "w": (0.0, -1.0),
            "s": (0.0, 1.0),
            "a": (-1.0, 0.0),
            "d": (1.0, 0.0),
            "up": (0.0, -1.0),
            "down": (0.0, 1.0),
            "left": (-1.0, 0.0),
            "right": (1.0, 0.0),
        }
        vec = dir_map.get(d, (0.0, 0.0))
        self.set_heading(vec[0], vec[1])

    # -------------------------------------------------------------
    # Heatmap e Células Visitadas
    # -------------------------------------------------------------
    def world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Converte coordenadas contínuas de mundo em coordenadas discretas de grid."""
        gx = int(math.floor(x / self.grid_cell_size))
        gy = int(math.floor(y / self.grid_cell_size))
        return gx, gy

    def record_visit(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Incrementa a contagem de visitas na célula atual ou especificada."""
        px, py = self.estimated_position if (x is None or y is None) else (x, y)
        cell = self.world_to_grid(px, py)
        self.exploration_heatmap[cell] = self.exploration_heatmap.get(cell, 0) + 1
        return cell

    def get_visit_cost(self, gx: int, gy: int) -> int:
        """Retorna o custo/contagem de visitas de uma célula."""
        return self.exploration_heatmap.get((gx, gy), 0)

    def get_least_visited_neighbor(
        self,
        gx: Optional[int] = None,
        gy: Optional[int] = None,
        radius: int = 1,
    ) -> Tuple[int, int]:
        """Localiza a célula vizinha com menor número de visitas (exploração inteligente)."""
        if gx is None or gy is None:
            gx, gy = self.world_to_grid(self.estimated_position[0], self.estimated_position[1])

        best_cell = (gx, gy)
        min_visits = float("inf")

        # Prioriza ordem cardinal: Norte, Leste, Sul, Oeste
        candidates = [
            (gx, gy - radius),
            (gx + radius, gy),
            (gx, gy + radius),
            (gx - radius, gy),
        ]

        for cx, cy in candidates:
            if (cx, cy) in self.obstacle_map:
                continue
            visits = self.get_visit_cost(cx, cy)
            if visits < min_visits:
                min_visits = visits
                best_cell = (cx, cy)

        return best_cell

    # -------------------------------------------------------------
    # Obstáculos
    # -------------------------------------------------------------
    def register_obstacle(self, gx: int, gy: int) -> None:
        """Registra uma célula como intransponível/bloqueada."""
        self.obstacle_map.add((gx, gy))

    def is_obstacle(self, gx: int, gy: int) -> bool:
        """Verifica se a célula é um obstáculo conhecido."""
        return (gx, gy) in self.obstacle_map

    def clear_obstacle(self, gx: int, gy: int) -> None:
        self.obstacle_map.discard((gx, gy))

    # -------------------------------------------------------------
    # Marcos (Landmarks) & Recalibração de Posição
    # -------------------------------------------------------------
    def register_landmark(
        self,
        name: str,
        rel_pos: Tuple[int, int],
        confidence: float = 1.0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Registra ou atualiza um landmark conhecido associando à posição estimada de mundo.
        rel_pos: (dx, dy) em pixels na tela em relação ao centro da tela.
        """
        curr_x, curr_y = self.estimated_position
        # Converte pixels de tela para estimativa espacial relativa em unidades de mundo
        pixel_to_world_scale = 0.01  # escala normalizada de calibração
        landmark_world_x = curr_x + (rel_pos[0] * pixel_to_world_scale)
        landmark_world_y = curr_y + (rel_pos[1] * pixel_to_world_scale)

        self.known_landmarks[name] = {
            "name": name,
            "world_x": landmark_world_x,
            "world_y": landmark_world_y,
            "screen_rel_pos": rel_pos,
            "confidence": confidence,
            "last_seen_ts": time.time(),
            "data": data or {},
        }

    def get_landmark(self, name: str) -> Optional[Dict[str, Any]]:
        """Retorna os dados de um marco identificado."""
        return self.known_landmarks.get(name)

    def recalibrate_position_from_landmark(
        self,
        landmark_name: str,
        known_anchor_pos: Tuple[float, float],
        current_rel_pos: Tuple[int, int],
    ) -> bool:
        """
        Corrige drift de posição contínua usando um landmark fixo como âncora topológica.
        """
        if landmark_name not in self.known_landmarks:
            return False

        pixel_to_world_scale = 0.01
        # Posição corrigida = posição da âncora menos o deslocamento do vetor relativo
        corrected_x = known_anchor_pos[0] - (current_rel_pos[0] * pixel_to_world_scale)
        corrected_y = known_anchor_pos[1] - (current_rel_pos[1] * pixel_to_world_scale)

        self.set_position(corrected_x, corrected_y)
        self.logger.info(f"📍 Posição recalibrada via âncora '{landmark_name}' para ({corrected_x:.2f}, {corrected_y:.2f})")
        return True

    # -------------------------------------------------------------
    # Watchdog de Ações e Estado Seguro
    # -------------------------------------------------------------
    def record_success(self) -> None:
        """Registra ação bem-sucedida (reinicia falhas)."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Registra ação malsucedida/sem feedback (reinicia sucessos)."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0

    def reset_watchdog(self) -> None:
        """Reseta contadores de falhas e sucessos."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0

    def save_safe_state(self, state: AgentState) -> None:
        """Salva o último estado seguro conhecido e posição associada."""
        self.last_safe_state = state
        self.last_safe_position = self.estimated_position

    def get_last_safe_state(self) -> Optional[AgentState]:
        return self.last_safe_state

    def get_last_safe_position(self) -> Tuple[float, float]:
        return self.last_safe_position

    # -------------------------------------------------------------
    # Buffers Históricos
    # -------------------------------------------------------------
    def add_snapshot(self, snapshot: StateSnapshot) -> None:
        """Adiciona snapshot ao buffer circular com limite máximo de tamanho."""
        if snapshot is not None:
            self.recent_snapshots.append(snapshot)

    def add_action(self, action: AtomicAction, success: bool = True) -> None:
        """Adiciona ação ao histórico recente."""
        if action is not None:
            self.recent_actions.append((action, success))
