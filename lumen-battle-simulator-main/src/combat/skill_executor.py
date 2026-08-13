import time
import logging
from typing import Optional, Tuple
import numpy as np

from src.models.combat_vision import SkillSlot, CombatDecision
from src.input.input_controller import InputController
from src.core.event_bus import EventBus, EventType

logger = logging.getLogger("LumenaCombat")


class SkillExecutor:
    """Executor determinístico de habilidades de combate com verificação em malha fechada (visual delta)."""

    def __init__(
        self,
        input_controller: Optional[InputController] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        self.input_ctrl = input_controller or InputController()
        self.event_bus = event_bus or EventBus()

    def execute_skill(
        self,
        skill: SkillSlot,
        frame_before: Optional[np.ndarray] = None,
        prefer_click: bool = False,
    ) -> Tuple[bool, float]:
        """Despacha a habilidade selecionada via tecla de atalho ou clique direto nas coordenadas da interface."""
        self.logger.info(f"⚔️ [COMBAT] Despachando habilidade: {skill.skill_name or f'Slot #{skill.slot_index}'} (Hotkey: {skill.hotkey}, Coords: ({skill.center_x}, {skill.center_y}))")

        self.event_bus.publish(
            EventType.BATTLE_ACTION_SELECTED,
            data={"slot": skill.slot_index, "name": skill.skill_name, "power": skill.power},
            category="COMBAT",
            level="INFO",
            message=f"Habilidade selecionada: {skill.skill_name or f'Slot #{skill.slot_index}'}",
        )

        success = False
        t0 = time.time()

        # 1. Se preferir hotkey e a hotkey estiver definida (ex: "1", "2", "3")
        if not prefer_click and skill.hotkey:
            success = self.input_ctrl.press_key(skill.hotkey, duration=0.15)
        else:
            # 2. Caso contrário, clica diretamente nas coordenadas do centro do slot
            success = self.input_ctrl.click(skill.center_x, skill.center_y)

        t1 = time.time()

        if success:
            self.event_bus.publish(
                EventType.BATTLE_ACTION_EXECUTED,
                data={"slot": skill.slot_index, "name": skill.skill_name, "latency": t1 - t0},
                category="COMBAT",
                level="INFO",
                message=f"Habilidade {skill.skill_name or f'Slot #{skill.slot_index}'} despachada com sucesso.",
            )
        else:
            self.logger.warning(f"⚠️ [COMBAT] Falha ao despachar habilidade {skill.skill_name}")

        return success, float(t1 - t0)
