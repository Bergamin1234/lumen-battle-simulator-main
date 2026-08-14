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
        now = time.time()
        action_id = f"act_{int(now * 1000)}_{skill.slot_index}"
        target_info = self.input_ctrl.window_manager._current_target
        target_hwnd = target_info.hwnd if target_info else 0
        target_pid = getattr(target_info, "pid", 0) if target_info else 0
        input_type = "HOTKEY" if (not prefer_click and skill.hotkey) else "CLICK"

        self.logger.info(f"⚔️ [COMBAT] Despachando habilidade: {skill.skill_name or f'Slot #{skill.slot_index}'} (Hotkey: {skill.hotkey}, Coords: ({skill.center_x}, {skill.center_y}))")

        # 1. Emite ACTION_REQUESTED
        action_data = {
            "timestamp": now,
            "action_id": action_id,
            "target_hwnd": target_hwnd,
            "target_pid": target_pid,
            "state": "BATTLE",
            "skill_id": skill.id,
            "skill_position": (skill.center_x, skill.center_y),
            "input_type": input_type,
            "hotkey": skill.hotkey,
        }

        self.event_bus.publish(
            EventType.ACTION_REQUESTED,
            data=action_data,
            category="COMBAT",
            level="INFO",
            message=f"ACTION_REQUESTED: {skill.skill_name or f'Slot #{skill.slot_index}'} [{input_type}]",
        )

        self.event_bus.publish(
            EventType.BATTLE_ACTION_SELECTED,
            data={"slot": skill.slot_index, "name": skill.skill_name, "power": skill.power, "action_id": action_id},
            category="COMBAT",
            level="INFO",
            message=f"Habilidade selecionada: {skill.skill_name or f'Slot #{skill.slot_index}'}",
        )

        success = False
        t0 = time.time()

        # 2. Despacha entrada física
        if not prefer_click and skill.hotkey:
            success = self.input_ctrl.press_key(skill.hotkey, duration=0.15)
        else:
            success = self.input_ctrl.click(skill.center_x, skill.center_y)

        t1 = time.time()
        elapsed = float(t1 - t0)

        if success:
            action_data["duration"] = elapsed
            self.event_bus.publish(
                EventType.ACTION_DISPATCHED,
                data=action_data,
                category="COMBAT",
                level="INFO",
                message=f"ACTION_DISPATCHED: {skill.skill_name or f'Slot #{skill.slot_index}'} despachada via {input_type}.",
            )
            self.event_bus.publish(
                EventType.BATTLE_ACTION_EXECUTED,
                data={"slot": skill.slot_index, "name": skill.skill_name, "latency": elapsed, "action_id": action_id},
                category="COMBAT",
                level="INFO",
                message=f"Habilidade {skill.skill_name or f'Slot #{skill.slot_index}'} executada fisicamente.",
            )
        else:
            action_data["reason"] = "Falha no despacho de entrada ou janela alvo inacessível"
            self.logger.warning(f"⚠️ [COMBAT] Falha ao despachar habilidade {skill.skill_name}")
            self.event_bus.publish(
                EventType.INPUT_BLOCKED,
                data=action_data,
                category="SAFETY",
                level="WARNING",
                message=f"INPUT_BLOCKED: Ataque '{skill.skill_name}' bloqueado por segurança ou janela sem foco.",
            )

        return success, elapsed
