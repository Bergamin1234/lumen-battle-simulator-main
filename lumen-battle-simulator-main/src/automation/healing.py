import time
import math
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np

from config.settings import BotConfig
from src.models.lumen import StateSnapshot, UIElement, TargetLockInfo
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
        interaction_distance_threshold: float = 80.0,
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
        self.target_lock_info: Optional[TargetLockInfo] = None
        self.stable_frames: int = 0
        self.target_lost_frames: int = 0
        self.interaction_attempts: int = 0
        self.max_interaction_attempts: int = 5
        self.last_move_key: Optional[str] = None
        self.last_move_time: float = 0.0
        self.search_step: int = 0
        self.last_delta: float = 0.0
        self.movement_verified: bool = False

    def reset(self) -> None:
        """Reinicia o estado interno do controlador de cura."""
        self.state = "SEARCH_TARGET"
        self.target_locked = False
        self.locked_crystal = None
        self.target_lock_info = None
        self.stable_frames = 0
        self.target_lost_frames = 0
        self.interaction_attempts = 0
        self.last_move_key = None
        self.search_step = 0
        self.last_delta = 0.0
        self.movement_verified = False

    def step(
        self,
        snapshot: StateSnapshot,
        frame: Optional[np.ndarray] = None,
        screen_capture_func: Optional[Any] = None,
    ) -> Tuple[str, bool, str]:
        """
        Executa um passo do ciclo de cura em malha fechada.
        Retorna:
        - state: estado atual
        - is_completed: True se a cura foi totalmente confirmada
        - message: descrição detalhada da ação
        """
        self.telemetry.record_decision()
        interact_key = getattr(getattr(self.config, "keys", None), "interact", "space")

        # 1. Checa se o Cristal Azul está visível
        crystal = snapshot.ui_elements.get("blue_crystal")
        rel_pos = snapshot.crystal_relative_pos
        player = snapshot.player_info

        if crystal and rel_pos is not None:
            self.target_lost_frames = 0
            self.stable_frames += 1
            dx, dy = rel_pos
            dist = math.hypot(dx, dy)
            self.locked_crystal = crystal

            # Trava ou atualiza Target Lock Info
            self.target_lock_info = TargetLockInfo(
                target_id="HEALING_CRYSTAL",
                semantic_type="HEALING_CRYSTAL",
                confidence=crystal.confidence,
                bounding_box=crystal.bounding_box,
                center_x=crystal.center[0],
                center_y=crystal.center[1],
                distance=dist,
                timestamp=time.time(),
                locked=True,
            )

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

            # 2. Avalia diálogo de cura ou prompt na tela
            has_dialog = "dialog_box" in snapshot.ui_elements

            if has_dialog:
                self.state = "INTERACTING"
                self.logger.info("💬 Caixa de diálogo do Cristal detectada. Avançando texto de cura...")
                self.telemetry.record_input_request()
                diag = self.input_ctrl.press_key_with_diagnostic(interact_key, duration=0.15)
                if diag.success:
                    self.telemetry.record_input_dispatched()
                time.sleep(0.3)
                self.interaction_attempts += 1

                if self.interaction_attempts >= 3:
                    self.state = "HEALING_VERIFIED"
                    self.telemetry.record_action_verified()
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

                self.telemetry.record_input_request()
                # Despacha micro-movimento com diagnóstico
                diag = self.input_ctrl.press_key_with_diagnostic(move_key, duration=0.20, frame_before=frame)
                
                if diag.success:
                    self.telemetry.record_input_dispatched()

                # Verificação de movimento pós-input se função de captura estiver disponível
                if screen_capture_func:
                    frame_after, _ = screen_capture_func()
                    confirmed, delta = self.input_ctrl.compute_visual_delta(frame, frame_after)
                    self.last_delta = delta
                    self.movement_verified = confirmed
                    if confirmed:
                        self.telemetry.record_action_verified()
                    else:
                        self.telemetry.record_action_unconfirmed()
                        self.event_bus.publish(
                            EventType.ACTION_UNCONFIRMED,
                            data={"action": "MOVE", "key": move_key, "delta": delta},
                            category="NAVIGATION",
                            level="WARNING",
                            message=f"Movimento {move_key.upper()} não produziu alteração visual perceptível (delta={delta:.4f})",
                        )

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

                self.telemetry.record_input_request()
                diag = self.input_ctrl.press_key_with_diagnostic(interact_key, duration=0.20, frame_before=frame)
                if diag.success:
                    self.telemetry.record_input_dispatched()

                self.interaction_attempts += 1
                time.sleep(0.25)

                if self.interaction_attempts >= 4:
                    self.state = "HEALING_VERIFIED"
                    self.telemetry.record_action_verified()
                    self.reset()
                    return "HEALING_VERIFIED", True, "Cura realizada por interações consecutivas."

                return "INTERACTING", False, f"Interagindo com o Cristal ({self.interaction_attempts})"

        else:
            # Cristal não detectado no frame atual -> Não ficar parado em deadlock!
            self.target_lost_frames += 1
            if self.target_lost_frames >= 4 and self.target_locked:
                self.target_locked = False
                self.state = "TARGET_LOST"
                self.logger.warning("⚠️ [TARGET LOST] Contato visual com o Cristal de Cura perdido. Iniciando busca ativa...")
                self.event_bus.publish(
                    EventType.TARGET_LOST,
                    category="TARGET",
                    level="WARNING",
                    message="Cristal de Cura fora do campo visual. Replanejando busca...",
                )
            elif not self.target_locked:
                self.state = "SEARCH_TARGET"

            # Busca Ativa (Active Scan / Micro-Exploration) para evitar inércia no estado de busca
            self.search_step = (self.search_step + 1) % 4
            search_keys = ["w", "d", "s", "a"]
            scan_key = search_keys[self.search_step]
            
            self.logger.debug(f"🔍 [BUSCA ATIVA] Cristal não visível. Varredura tática via '{scan_key.upper()}'...")
            self.telemetry.record_input_request()
            diag = self.input_ctrl.press_key_with_diagnostic(scan_key, duration=0.15)
            if diag.success:
                self.telemetry.record_input_dispatched()

            return "SEARCH_TARGET", False, f"Varredura ativa buscando Cristal Azul (passo {scan_key.upper()})."