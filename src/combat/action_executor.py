import time
import logging
from typing import Optional, Tuple, Dict, Any

from src.models.lumen import ActionPlan, AtomicAction, BattleTelemetry
from src.input.input_controller import InputController
from src.memory.memory_manager import MemoryManager


class ActionExecutor:
    """Camada de execução física responsável por transformar ActionPlan em comandos de entrada via InputController com auditoria na memória."""

    def __init__(
        self,
        input_controller: Optional[InputController] = None,
        memory_manager: Optional[MemoryManager] = None,
    ) -> None:
        self.logger = logging.getLogger("LumenaCombat")
        self.input_ctrl = input_controller or InputController()
        self.memory_manager = memory_manager

    def execute_plan(
        self,
        plan: Optional[ActionPlan],
        telemetry: Optional[BattleTelemetry] = None,
        timeout: float = 5.0,
        max_retries: int = 2,
    ) -> bool:
        """
        Executa sequencialmente todas as ações atômicas contidas no ActionPlan.
        Retorna True se todas as ações foram despachadas com sucesso.
        """
        if plan is None or not plan.actions:
            return False

        start_time = time.time()
        for idx, action in enumerate(plan.actions):
            if (time.time() - start_time) > timeout:
                self.logger.warning(f"⏰ Timeout na execução do ActionPlan após {timeout:.1f}s.")
                if self.memory_manager:
                    self.memory_manager.record_action_result(action, verified_success=False)
                return False

            success = False
            for attempt in range(max_retries):
                try:
                    success = self._dispatch_atomic_action(action, telemetry)
                    if success:
                        break
                    time.sleep(0.05)
                except Exception as e:
                    self.logger.error(f"Erro ao despachar ação '{action.action_type}': {e}")
                    success = False

            if self.memory_manager:
                self.memory_manager.record_action_result(action, verified_success=success)

            if not success:
                self.logger.warning(f"⚠️ Falha ao executar ação {idx + 1}/{len(plan.actions)}: {action.action_type}")
                return False

        return True

    def _dispatch_atomic_action(
        self,
        action: AtomicAction,
        telemetry: Optional[BattleTelemetry],
    ) -> bool:
        """Traduz ação atômica abstrata em chamadas seguras para o InputController."""
        act_type = action.action_type.upper()
        target = str(action.target).lower()

        # 1. Espera / Delay
        if act_type == "WAIT":
            time.sleep(max(0.01, action.duration))
            return True

        # 2. Clique no Centro da Tela (Avançar Diálogos / Telas)
        if act_type == "CLICK_CENTER":
            cx, cy = self.input_ctrl.get_screen_center()
            return self.input_ctrl.click(cx, cy)

        # 3. Clique no Botão FIGHT
        if act_type == "CLICK_FIGHT":
            if telemetry and telemetry.fight_button_pos is not None:
                fx, fy = telemetry.fight_button_pos
                return self.input_ctrl.click(fx, fy)
            else:
                # Fallback: clica no centro inferior direito
                cx, cy = self.input_ctrl.get_screen_center()
                return self.input_ctrl.click(cx + 100, cy + 100)

        # 4. Clique em Slot de Golpe
        if act_type == "CLICK_MOVE":
            if telemetry and telemetry.available_moves and telemetry.fight_button_pos is not None:
                fx, fy = telemetry.fight_button_pos
                # Extrai slot index
                slot_idx = 0
                if "slot_" in target:
                    try:
                        slot_idx = int(target.replace("slot_", ""))
                    except ValueError:
                        slot_idx = 0

                # Busca o slot nas moves disponíveis
                for move_info in telemetry.available_moves:
                    if move_info.slot_index == slot_idx:
                        rx, ry, rw, rh = move_info.button_rect
                        if rw > 0 and rh > 0:
                            return self.input_ctrl.click(rx + rw // 2, ry + rh // 2)

                # Fallback de offset geométrico caso button_rect não esteja preenchido
                offsets = [(-220, -35), (-220, 35), (-70, -35), (-70, 35)]
                dx, dy = offsets[min(slot_idx, 3)]
                return self.input_ctrl.click(fx + dx, fy + dy)
            else:
                cx, cy = self.input_ctrl.get_screen_center()
                return self.input_ctrl.click(cx, cy)

        # 5. Clique em Botão de Troca (SWITCH)
        if act_type == "CLICK_SWITCH":
            if telemetry and telemetry.switch_button_pos is not None:
                sx, sy = telemetry.switch_button_pos
                return self.input_ctrl.click(sx, sy)
            elif telemetry and telemetry.fight_button_pos is not None:
                fx, fy = telemetry.fight_button_pos
                # SWITCH costuma ficar abaixo/ao lado do FIGHT
                return self.input_ctrl.click(fx, fy + 70)
            else:
                cx, cy = self.input_ctrl.get_screen_center()
                return self.input_ctrl.click(cx + 150, cy + 120)

        # 6. Clique em Slot de Criatura da Equipe
        if act_type == "CLICK_SLOT":
            slot_idx = 0
            if "slot_" in target:
                try:
                    slot_idx = int(target.replace("slot_", "").replace("team_", ""))
                except ValueError:
                    slot_idx = 0
            cx, cy = self.input_ctrl.get_screen_center()
            # Estimativa de slots da equipe verticalmente
            return self.input_ctrl.click(cx - 100, cy - 100 + (slot_idx * 50))

        # 7. Pressionamento de Tecla
        if act_type == "KEY_PRESS":
            return self.input_ctrl.press_key(target, duration=action.duration)

        # 8. Segurar Teclas
        if act_type == "KEY_HOLD":
            keys = target.split("+")
            return self.input_ctrl.hold_keys(keys, duration=action.duration)

        # Ação genérica desconhecida
        self.logger.warning(f"Tipo de ação atômica não reconhecido: {act_type}")
        return False
