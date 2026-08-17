"""
LUMENA BOT v4.0 — MULTI-TURN SKILL ROTATION STRATEGY ENGINE
============================================================
Motor determinístico de rotação de habilidades para combates prolongados de múltiplos turnos.
Gerencia prioridades de ataque, cache de cooldowns internos e detecção visual de disponibilidade.
"""

import time
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from src.models.combat_vision import SkillSlot
from src.models.enums import Element

logger = logging.getLogger("LumenaSkillStrategy")


@dataclass
class SkillUsageRecord:
    slot_index: int
    turn_used: int
    timestamp: float = field(default_factory=time.time)
    cooldown_duration_turns: int = 2


class SkillStrategyEngine:
    """Motor de seleção e rotação de habilidades multi-turno."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("LumenaSkillStrategy")
        self.current_turn: int = 1
        self.usage_history: List[SkillUsageRecord] = []
        self._cooldown_cache: Dict[int, int] = {}  # slot_index -> last_turn_used
        # Prioridade padrão por índice de slot (Slot 1 como ataque primário padrão)
        self.priority_order: List[int] = [1, 2, 3, 4]

    def reset_battle(self) -> None:
        """Reinicia o estado para uma nova batalha."""
        self.current_turn = 1
        self.usage_history.clear()
        self._cooldown_cache.clear()
        self.logger.debug("⚔️ [SKILL STRATEGY] Estratégia de habilidades reiniciada para nova batalha.")

    def advance_turn(self) -> None:
        """Avança o contador de turno de combate."""
        self.current_turn += 1
        self.logger.debug(f"⚔️ [SKILL STRATEGY] Avançando para o Turno {self.current_turn}")

    def register_skill_use(self, slot_index: int, cooldown_turns: int = 2) -> None:
        """Registra o uso de uma habilidade no turno atual."""
        self._cooldown_cache[slot_index] = self.current_turn
        rec = SkillUsageRecord(
            slot_index=slot_index,
            turn_used=self.current_turn,
            timestamp=time.time(),
            cooldown_duration_turns=cooldown_turns,
        )
        self.usage_history.append(rec)
        self.logger.info(f"⚔️ [SKILL STRATEGY] Skill #{slot_index} registrada no Turno {self.current_turn} (Cooldown: {cooldown_turns} turnos).")

    def is_skill_on_cooldown(self, slot_index: int, cooldown_turns: int = 2) -> bool:
        """Verifica se a habilidade está em cooldown interno estimado."""
        last_used = self._cooldown_cache.get(slot_index)
        if last_used is None:
            return False
        turns_elapsed = self.current_turn - last_used
        return turns_elapsed < cooldown_turns

    def evaluate_skills(
        self,
        available_skills: List[SkillSlot],
        cooldown_turns_map: Optional[Dict[int, int]] = None,
    ) -> Optional[SkillSlot]:
        """
        Avalia e seleciona a melhor habilidade disponível seguindo a política multi-turno:
        1. Prioridade 1: Maior prioridade configurada que não esteja em cooldown visual nem em cache interno.
        2. Prioridade 2: Primeira habilidade disponível sem restrições.
        3. Prioridade 3 (Fallback seguro): Habilidade básica (Slot 1 ou primeiro elemento).
        """
        if not available_skills:
            return None

        cd_map = cooldown_turns_map or {1: 1, 2: 2, 3: 3, 4: 2}

        # Cria mapa slot_index -> SkillSlot
        skills_by_slot: Dict[int, SkillSlot] = {s.slot_index: s for s in available_skills}

        # 1. Tenta habilidades na ordem de prioridade configurada
        for slot_idx in self.priority_order:
            skill = skills_by_slot.get(slot_idx)
            if skill and skill.available:
                cd_dur = cd_map.get(slot_idx, 2)
                if not self.is_skill_on_cooldown(slot_idx, cooldown_turns=cd_dur):
                    self.logger.info(f"⚔️ [SKILL STRATEGY] Selecionada Habilidade #{slot_idx} ({skill.skill_name}) por prioridade estratégica.")
                    return skill

        # 2. Fallback: Qualquer slot detectado como disponível
        for skill in available_skills:
            cd_dur = cd_map.get(skill.slot_index, 2)
            if skill.available and not self.is_skill_on_cooldown(skill.slot_index, cooldown_turns=cd_dur):
                self.logger.info(f"⚔️ [SKILL STRATEGY] Selecionada Habilidade #{skill.slot_index} como fallback disponível.")
                return skill

        # 3. Fallback absoluto: Retorna o primeiro slot da lista (ataque básico padrão)
        fallback = available_skills[0]
        self.logger.warning(f"⚠️ [SKILL STRATEGY] Todas as habilidades em cooldown/restritas. Usando fallback básico: Slot #{fallback.slot_index}.")
        return fallback
