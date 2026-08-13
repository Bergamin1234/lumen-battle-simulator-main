import logging
from typing import Optional, Dict, Any, Tuple

from src.models.enums import AgentState
from src.models.lumen import StateSnapshot, AtomicAction
from src.memory.world_memory import WorldMemory
from src.memory.experience_store import ExperienceStore


class MemoryManager:
    """Gerenciador central de memória que unifica a memória de sessão em tempo real (WorldMemory) e a persistência em disco (ExperienceStore)."""

    def __init__(
        self,
        world_memory: Optional[WorldMemory] = None,
        experience_store: Optional[ExperienceStore] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaMemory")
        self.world_memory = world_memory or WorldMemory()
        self.experience_store = experience_store or ExperienceStore()

        self._last_battle_state_logged: Optional[bool] = None

    def update_from_snapshot(self, snapshot: Optional[StateSnapshot]) -> None:
        """Alias para ingest_snapshot para integração unificada."""
        self.ingest_snapshot(snapshot)

    def ingest_snapshot(self, snapshot: Optional[StateSnapshot]) -> None:
        """
        Ingere a observação de estado produzida pela camada de percepção (Fase 2).
        Atualiza o modelo de mundo, heatmap, landmarks e histórico seguro.
        """
        if snapshot is None:
            return

        try:
            # 1. Adiciona ao buffer circular dos últimos snapshots
            self.world_memory.add_snapshot(snapshot)

            # 2. Registra e persiste marco do Cristal Azul quando avistado
            if snapshot.crystal_detected and snapshot.crystal_relative_pos is not None:
                self.world_memory.register_landmark(
                    name="blue_crystal",
                    rel_pos=snapshot.crystal_relative_pos,
                    confidence=0.85,
                )
                landmark_data = self.world_memory.get_landmark("blue_crystal")
                if landmark_data:
                    self.experience_store.save_landmark(
                        name="blue_crystal",
                        world_x=landmark_data["world_x"],
                        world_y=landmark_data["world_y"],
                        confidence=landmark_data["confidence"],
                    )

            # 3. Salva último estado seguro em exploração/caminho
            if snapshot.screen_state in (AgentState.EXPLORING, AgentState.SEARCHING_FARM):
                self.world_memory.save_safe_state(snapshot.screen_state)
                # Incrementa visita no heatmap na posição estimada atual
                gx, gy = self.world_memory.record_visit()
                visits = self.world_memory.get_visit_cost(gx, gy)
                self.experience_store.save_exploration_cell(gx, gy, visits, is_obstacle=False)

            # 4. Registra métricas de batalha e cura
            if snapshot.battle_telemetry and snapshot.battle_telemetry.in_battle:
                if snapshot.battle_telemetry.victory_detected and self._last_battle_state_logged != "victory":
                    self.experience_store.update_session_metrics(battles_won_delta=1)
                    self._last_battle_state_logged = "victory"
                elif snapshot.battle_telemetry.defeat_detected and self._last_battle_state_logged != "defeat":
                    self.experience_store.update_session_metrics(battles_lost_delta=1)
                    self._last_battle_state_logged = "defeat"
            else:
                self._last_battle_state_logged = None

            if snapshot.screen_state == AgentState.HEALING:
                self.experience_store.update_session_metrics(heals_delta=1)

        except Exception as e:
            self.logger.debug(f"Erro tolerado ao ingerir StateSnapshot no MemoryManager: {e}")

    def record_action_result(
        self,
        action: AtomicAction,
        verified_success: bool,
        step_delta_distance: float = 1.0,
    ) -> None:
        """
        Registra a execução de uma ação atômica e seu resultado verificado em malha fechada.
        Atualiza posição estimada, contadores de watchdog, obstáculos e logs de experiência.
        """
        if action is None:
            return

        try:
            # 1. Registra no histórico em memória
            self.world_memory.add_action(action, verified_success)

            # 2. Atualiza heading e estimativa de posição se for ação de movimento
            target_key = str(action.target).lower().strip()
            if target_key in ("w", "a", "s", "d", "up", "down", "left", "right"):
                self.world_memory.set_heading_from_direction(target_key)

                if verified_success:
                    # Aplica deslocamento relativo na direção do heading
                    hx, hy = self.world_memory.heading_vector
                    dist = step_delta_distance * max(0.5, action.duration / 0.15)
                    self.world_memory.update_position(hx * dist, hy * dist)
                    self.world_memory.record_success()
                    self.experience_store.update_session_metrics(steps_delta=1)
                else:
                    self.world_memory.record_failure()
                    # Se falhar 3 vezes consecutivas na mesma direção, infere colisão com obstáculo
                    if self.world_memory.consecutive_failures >= 3:
                        hx, hy = self.world_memory.heading_vector
                        curr_x, curr_y = self.world_memory.estimated_position
                        obs_gx, obs_gy = self.world_memory.world_to_grid(curr_x + hx, curr_y + hy)
                        self.world_memory.register_obstacle(obs_gx, obs_gy)
                        self.experience_store.save_exploration_cell(obs_gx, obs_gy, visits=1, is_obstacle=True)
                        self.experience_store.record_stuck_event(curr_x, curr_y, target_key)
                        self.logger.warning(f"⚠️ Obstáculo/Colisão registrada em ({obs_gx}, {obs_gy}) após {self.world_memory.consecutive_failures} falhas.")
            else:
                if verified_success:
                    self.world_memory.record_success()
                else:
                    self.world_memory.record_failure()

            # 3. Registra resultado da ação no banco persistente
            self.experience_store.record_action_outcome(
                action_type=action.action_type,
                target=str(action.target),
                success=verified_success,
            )

        except Exception as e:
            self.logger.debug(f"Erro tolerado ao registrar ação no MemoryManager: {e}")

    def is_stuck(self, failure_threshold: int = 3) -> bool:
        """Indica se o personagem está travado com base nas falhas consecutivas de movimento."""
        return self.world_memory.consecutive_failures >= failure_threshold

    def get_world_summary(self) -> Dict[str, Any]:
        """Retorna resumo do estado de mundo e métricas para consumo do planejador e decisões cognitivas."""
        pos_x, pos_y = self.world_memory.estimated_position
        gx, gy = self.world_memory.world_to_grid(pos_x, pos_y)
        session_stats = self.experience_store.get_session_summary()

        return {
            "estimated_position": (pos_x, pos_y),
            "current_grid": (gx, gy),
            "heading": self.world_memory.heading_vector,
            "consecutive_failures": self.world_memory.consecutive_failures,
            "consecutive_successes": self.world_memory.consecutive_successes,
            "is_stuck": self.is_stuck(),
            "total_obstacles": len(self.world_memory.obstacle_map),
            "known_landmarks": list(self.world_memory.known_landmarks.keys()),
            "total_visited_cells": len(self.world_memory.exploration_heatmap),
            "last_safe_state": self.world_memory.last_safe_state.name if self.world_memory.last_safe_state else None,
            "session_metrics": session_stats,
        }

    def restore_from_disk(self) -> None:
        """Recupera marcos conhecidos e mapa de calor do banco persistente."""
        try:
            # 1. Restaura landmarks
            landmarks = self.experience_store.load_landmarks()
            for lm in landmarks:
                self.world_memory.known_landmarks[lm["name"]] = {
                    "name": lm["name"],
                    "world_x": lm["world_x"],
                    "world_y": lm["world_y"],
                    "screen_rel_pos": (0, 0),
                    "confidence": lm["confidence"],
                    "last_seen_ts": lm["last_seen_ts"],
                    "data": {},
                }

            # 2. Restaura heatmap e obstáculos
            persisted_grid = self.experience_store.load_exploration_grid()
            self.world_memory.exploration_heatmap.update(persisted_grid)

            persisted_obstacles = self.experience_store.load_obstacles()
            self.world_memory.obstacle_map.update(persisted_obstacles)

            self.logger.info(f"💾 Memória restaurada: {len(landmarks)} landmarks, {len(persisted_grid)} células, {len(persisted_obstacles)} obstáculos.")
        except Exception as e:
            self.logger.debug(f"Aviso ao restaurar memória do disco: {e}")
