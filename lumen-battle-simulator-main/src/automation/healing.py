import time
import math
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np

from config.settings import BotConfig
from src.models.lumen import StateSnapshot, UIElement
from src.input.input_controller import InputController
from src.core.event_bus import EventBus, EventType
from src.telemetry.telemetry_manager import TelemetryManager

logger = logging.getLogger("LumenaMacro")


class HealingController:
    """Controlador inteligente em malha fechada (Closed Loop) para localização,
    travamento de alvo, aproximação tática, interação e verificação visual do Cristal de Cura."""

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        input_ctrl: Optional[InputController] = None,
        interaction_distance_threshold: float = 90.0,
    ) -> None:
        self.logger = logging.getLogger("LumenaMacro")
        self.config = config or BotConfig()
        self.input_ctrl = input_ctrl or InputController()
        self.event_bus = EventBus()
        self.telemetry = TelemetryManager()
        self.interaction_threshold = interaction_distance_threshold

        # Estados de Cura:
        # SEARCH_TARGET -> TARGET_LOCKED -> APPROACH_TARGET -> ALIGN_TARGET -> INTERACT_READY -> INTERACTING -> VERIFYING -> HEALING_VERIFIED
        self.state: str = "SEARCH_TARGET"
        self.target_locked: bool = False
        self.locked_crystal: Optional[UIElement] = None
        self.stable_frames: int = 0
        self.target_lost_frames: int = 0
        self.interaction_attempts: int = 0
        self.max_interaction_attempts: int = 5
        self.last_move_key: Optional[str] = None
        self.last_move_time: float = 0.0

    def reset(self) -> None:
        """Reinicia o estado interno do controlador de cura."""
        self.state = "SEARCH_TARGET"
        self.target_locked = False
        self.locked_crystal = None
        self.stable_frames = 0
        self.target_lost_frames = 0
        self.interaction_attempts = 0
        self.last_move_key = None

    def step(
        self,
        snapshot: StateSnapshot,
        frame: Optional[np.ndarray] = None,
    ) -> Tuple[str, bool, str]:
        """
        Executa um passo do ciclo de cura.
        Retorna:
        - state: estado atual (SEARCH_TARGET, TARGET_LOCKED, APPROACH_TARGET, INTERACTING, HEALING_VERIFIED, etc.)
        - is_completed: True se a cura foi totalmente confirmada
        - message: descrição detalhada da ação
        """
        interact_key = getattr(getattr(self.config, "keys", None), "interact", "space")

        # 1. Checa se o Cristal Azul está visível
        crystal = snapshot.ui_elements.get("blue_crystal")
        rel_pos = snapshot.crystal_relative_pos

        if crystal and rel_pos is not None:
            self.target_lost_frames = 0
            self.stable_frames += 1
            dx, dy = rel_pos
            dist = math.hypot(dx, dy)
            self.locked_crystal = crystal

            if not self.target_locked and self.stable_frames >= 1:
                self.target_locked = True
                self.state = "TARGET_LOCKED"
                self.event_bus.publish(
                    EventType.TARGET_LOCKED,
                    data={"target": "HEALING_CRYSTAL", "bbox": crystal.bounding_box, "confidence": crystal.confidence, "distance": dist},
                    category="TARGET",
                    level="INFO",
                    message=f"🎯 [TARGET LOCK] Grande Cristal Azul travado (Distância: {dist:.1f}px, Confiança: {crystal.confidence:.2f})",
                )

            # 2. Avalia distância de interação
            has_dialog = "dialog_box" in snapshot.ui_elements

            if has_dialog:
                # Caixa de diálogo de cura já aberta -> Avança até curar
                self.state = "INTERACTING"
                self.logger.info("💬 Caixa de diálogo do Cristal detectada. Avançando texto de cura...")
                self.input_ctrl.press_key(interact_key, duration=0.15)
                time.sleep(0.4)
                self.interaction_attempts += 1

                if self.interaction_attempts >= 3:
                    self.state = "HEALING_VERIFIED"
                    self.event_bus.publish(
                        EventType.HEALING_SUCCESS,
                        category="NAVIGATION",
                        level="INFO",
                        message="✓ Cura da equipe totalmente confirmada no Cristal Azul.",
                    )
                    self.reset()
                    return "HEALING_VERIFIED", True, "Cura finalizada com sucesso."
                return "INTERACTING", False, f"Avançando diálogo ({self.interaction_attempts}/3)"

            if dist > self.interaction_threshold:
                # 3. Fora de alcance -> APROXIMAÇÃO TÁTICA (WASD Micro-movements)
                self.state = "APPROACH_TARGET"
                
                # Seleciona eixo primário de movimento
                if abs(dx) > abs(dy) * 0.8:
                    move_key = "d" if dx > 0 else "a"
                else:
                    move_key = "s" if dy > 0 else "w"

                self.last_move_key = move_key
                self.last_move_time = time.time()

                self.logger.info(
                    f"🚶 [APROXIMAÇÃO] Navegando até o Cristal: dx={dx}px, dy={dy}px (Distância: {dist:.1f}px) -> Tecla: {move_key.upper()}"
                )
                self.event_bus.publish(
                    EventType.POSITIONING_STARTED,
                    data={"target": "HEALING_CRYSTAL", "direction": move_key, "distance": dist},
                    category="NAVIGATION",
                    level="DEBUG",
                    message=f"Movimento em direção ao cristal: {move_key.upper()} ({dist:.1f}px)",
                )

                # Despacha micro-movimento
                self.input_ctrl.press_key_with_diagnostic(move_key, duration=0.20)
                return "APPROACH_TARGET", False, f"Aproximando do cristal ({dist:.1f}px via {move_key.upper()})"

            else:
                # 4. Dentro do alcance de interação -> INTERAGIR
                self.state = "INTERACT_READY"
                self.logger.info(f"✨ [ALCANCE ATINGIDO] Em distância de interação ({dist:.1f}px). Pressionando '{interact_key.upper()}'...")
                
                self.event_bus.publish(
                    EventType.ACTION_STARTED,
                    data={"action": "INTERACT", "target": "HEALING_CRYSTAL", "key": interact_key},
                    category="NAVIGATION",
                    level="INFO",
                    message=f"Interagindo com Cristal de Cura via {interact_key.upper()}",
                )

                self.input_ctrl.press_key(interact_key, duration=0.20)
                self.interaction_attempts += 1
                time.sleep(0.3)

                if self.interaction_attempts >= 4:
                    self.state = "HEALING_VERIFIED"
                    self.reset()
                    return "HEALING_VERIFIED", True, "Cura realizada por interações consecutivas."

                return "INTERACTING", False, f"Interagindo com o Cristal ({self.interaction_attempts})"

        else:
            # Cristal não detectado no frame atual
            self.target_lost_frames += 1
            if self.target_lost_frames >= 4 and self.target_locked:
                self.target_locked = False
                self.state = "TARGET_LOST"
                self.logger.warning("⚠️ [TARGET LOST] Contato visual com o Cristal de Cura perdido. Re-escaneando...")
                self.event_bus.publish(
                    EventType.TARGET_LOST,
                    category="TARGET",
                    level="WARNING",
                    message="Cristal de Cura fora do campo visual.",
                )
            elif not self.target_locked:
                self.state = "SEARCH_TARGET"

            return self.state, False, "Buscando Grande Cristal Azul no cenário."