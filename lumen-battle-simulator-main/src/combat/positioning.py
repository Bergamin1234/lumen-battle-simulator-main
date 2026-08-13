import logging
import math
from typing import Optional, Tuple, Dict, Any
from src.core.event_bus import EventBus, EventType
from src.models.combat_vision import PositionInfo, SkillSlot, EnemyTarget

logger = logging.getLogger("LumenaCombatPositioning")


class CombatPositioningController:
    """Controlador de posicionamento tático de combate em malha fechada.

    Responsável por gerenciar distância do alvo, alcance de habilidades, aproximação,
    afastamento e confirmação visual de movimento antes da execução de ataques.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaCombatPositioning")
        self.event_bus = EventBus()
        self.default_melee_range = 120.0
        self.default_ranged_range = 350.0
        self.min_safe_distance = 60.0

    def get_skill_effective_range(self, skill: Optional[SkillSlot]) -> float:
        """Determina o alcance efetivo em pixels de uma habilidade."""
        if not skill:
            return self.default_melee_range

        rtype = (skill.range_type or "MELEE").upper()
        if rtype == "RANGED":
            return self.default_ranged_range
        elif rtype == "MELEE":
            return self.default_melee_range
        elif rtype in ("HEAL", "BUFF", "UTILITY"):
            return 9999.0  # Habilidades de suporte não exigem aproximação do inimigo

        return self.default_melee_range

    def evaluate_positioning(
        self,
        player_pos: Tuple[int, int],
        target_pos: Optional[Tuple[int, int]],
        skill: Optional[SkillSlot] = None,
    ) -> Tuple[str, Optional[str], float]:
        """Avalia a posição atual em relação ao alvo e à habilidade selecionada.

        Retorna:
            (positioning_state, recommended_move_key, current_distance)
        """
        if not target_pos:
            return "NO_TARGET", None, 0.0

        dx = target_pos[0] - player_pos[0]
        dy = target_pos[1] - player_pos[1]
        distance = float(math.sqrt(dx * dx + dy * dy))

        required_range = self.get_skill_effective_range(skill)

        # Se for habilidade de suporte ou se já estiver dentro do alcance
        if required_range >= 9000.0:
            return "ATTACK_POSITION_READY", None, distance

        if distance > required_range:
            # Precisa aproximar do alvo
            move_key = self._get_direction_key(dx, dy, approach=True)
            self.logger.debug(f"[POSITIONING] Inimigo fora de alcance ({distance:.1f}px > {required_range:.1f}px). Aproximando via '{move_key}'.")
            return "APPROACH_TARGET", move_key, distance
        elif distance < self.min_safe_distance and skill and skill.range_type == "RANGED":
            # Muito perto para ataque ranged -> afasta
            move_key = self._get_direction_key(dx, dy, approach=False)
            self.logger.debug(f"[POSITIONING] Muito próximo para ranged ({distance:.1f}px < {self.min_safe_distance:.1f}px). Recuando via '{move_key}'.")
            return "MAINTAIN_DISTANCE", move_key, distance
        else:
            # Posição ideal para desferir o ataque
            return "ATTACK_POSITION_READY", None, distance

    def _get_direction_key(self, dx: float, dy: float, approach: bool = True) -> str:
        """Calcula a tecla direcional prioritária (W, S, A, D) em direção ao alvo ou para recuo."""
        factor = 1.0 if approach else -1.0
        target_dx = dx * factor
        target_dy = dy * factor

        if abs(target_dx) >= abs(target_dy):
            return "d" if target_dx > 0 else "a"
        else:
            return "s" if target_dy > 0 else "w"

    def verify_position_delta(self, before_distance: float, after_distance: float, approach: bool = True) -> bool:
        """Verifica se o movimento resultou em alteração esperada da distância em relação ao alvo."""
        delta = before_distance - after_distance
        if approach:
            success = delta > 3.0  # Ficou mais próximo
        else:
            success = delta < -3.0  # Ficou mais distante

        if success:
            self.event_bus.publish(
                EventType.MOVEMENT_VERIFIED,
                data={"before": before_distance, "after": after_distance, "delta": delta},
                category="NAVIGATION",
                level="DEBUG",
                message=f"Posicionamento tático verificado (Delta distância: {delta:+.1f}px)",
            )
        else:
            self.event_bus.publish(
                EventType.MOVEMENT_FAILED,
                data={"before": before_distance, "after": after_distance, "delta": delta},
                category="NAVIGATION",
                level="WARNING",
                message=f"Posicionamento não produziu delta de distância suficiente ({delta:+.1f}px)",
            )

        return success
