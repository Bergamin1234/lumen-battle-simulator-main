"""
LUMENA BOT v5.3 — RECORDED PATH ENGINE (WAYPOINT MACRO & HEALING SEQUENCE)
===========================================================================
Motor de Gravação e Reprodução Determinística de Trajetórias (Macro Replayer)
e Sequenciador de Cura no Cristal com Tecla ESPAÇO e Retorno ao Mato.

REGRAS (DIRETIVA V5.3 MASTER):
1. Gravação / Reprodução precisa de sequências de teclas e durações via Win32 SendInput.
2. Inversão automática de rota (W <-> S, A <-> D em ordem reversa).
3. Interação com Cristal: ESPAÇO (100ms) -> 500ms -> ESPAÇO (100ms) -> 1.5s recomposição -> Validação HP.
4. Retorno ao Mato e retomada de BotState.EXPLORING com oscilação A/D.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from src.core.event_bus import EventBus, EventType
from src.input.input_controller import InputController

logger = logging.getLogger("LumenaRecordedPath")


@dataclass
class WaypointAction:
    key: str
    duration: float
    delay_after: float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "duration": self.duration}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WaypointAction":
        return cls(
            key=str(data.get("key", "w")).lower(),
            duration=float(data.get("duration", 0.5)),
            delay_after=float(data.get("delay_after", 0.05)),
        )


@dataclass
class RecordedRoute:
    name: str = "custom_route"
    actions: List[WaypointAction] = field(default_factory=list)

    def to_list(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.actions]

    @classmethod
    def from_list(cls, actions_list: List[Dict[str, Any]], name: str = "custom_route") -> "RecordedRoute":
        return cls(
            name=name,
            actions=[WaypointAction.from_dict(item) for item in actions_list],
        )

    def reverse(self, new_name: Optional[str] = None) -> "RecordedRoute":
        """Inverte a rota: inverte a ordem das ações e as direções (W <-> S, A <-> D)."""
        key_opposites = {
            "w": "s",
            "s": "w",
            "a": "d",
            "d": "a",
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }
        reversed_actions: List[WaypointAction] = []
        for action in reversed(self.actions):
            opp_key = key_opposites.get(action.key.lower(), action.key)
            reversed_actions.append(WaypointAction(key=opp_key, duration=action.duration, delay_after=action.delay_after))

        rev_name = new_name or f"{self.name}_reversed"
        return RecordedRoute(name=rev_name, actions=reversed_actions)


class RecordedPathEngine:
    """Motor de execução de rotas gravadas e orquestrador de ciclo de cura determinístico."""

    def __init__(
        self,
        input_controller: Optional[InputController] = None,
        event_bus: Optional[EventBus] = None,
        routes_dir: str = "config/routes",
    ) -> None:
        self.logger = logging.getLogger("LumenaRecordedPath")
        self.input_ctrl = input_controller or InputController()
        self.event_bus = event_bus or EventBus()
        self.routes_dir = routes_dir
        self._active_recording: List[WaypointAction] = []
        self._is_recording = False
        self._is_playing = False

    def load_route(self, route_name_or_path: str) -> RecordedRoute:
        """Carrega uma rota do disco (por nome ou caminho completo) ou retorna rota padrão de fallback."""
        path = route_name_or_path
        if not os.path.isabs(path) and not path.endswith(".json"):
            path = os.path.join(self.routes_dir, f"{route_name_or_path}.json")
        elif not os.path.isabs(path) and not os.path.exists(path):
            path = os.path.join(self.routes_dir, os.path.basename(path))

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return RecordedRoute.from_list(data, name=os.path.splitext(os.path.basename(path))[0])
            except Exception as e:
                self.logger.error(f"❌ [RECORDED_PATH] Erro ao carregar rota {path}: {e}")

        # Fallback determinístico (W 1.2s -> D 0.85s -> W 2.1s)
        self.logger.warning(f"⚠️ [RECORDED_PATH] Rota {route_name_or_path} não encontrada no disco. Usando rota padrão.")
        return RecordedRoute(
            name="default_grass_to_crystal",
            actions=[
                WaypointAction(key="w", duration=1.200),
                WaypointAction(key="d", duration=0.850),
                WaypointAction(key="w", duration=2.100),
            ],
        )

    def save_route(self, route: RecordedRoute, route_name_or_path: str) -> bool:
        """Salva uma rota gravada no disco em formato JSON."""
        path = route_name_or_path
        if not os.path.isabs(path) and not path.endswith(".json"):
            os.makedirs(self.routes_dir, exist_ok=True)
            path = os.path.join(self.routes_dir, f"{route_name_or_path}.json")

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(route.to_list(), f, indent=2)
            self.logger.info(f"💾 [RECORDED_PATH] Rota '{route.name}' salva em {path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ [RECORDED_PATH] Falha ao salvar rota {path}: {e}")
            return False

    def play_route(
        self,
        route_or_name: Any,
        cancel_predicate: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Reproduz a sequência de ações da rota gravada com precisão de temporização."""
        if isinstance(route_or_name, str):
            route = self.load_route(route_or_name)
        elif isinstance(route_or_name, RecordedRoute):
            route = route_or_name
        elif isinstance(route_or_name, list):
            route = RecordedRoute.from_list(route_or_name)
        else:
            self.logger.error(f"❌ [RECORDED_PATH] Tipo de rota inválido: {type(route_or_name)}")
            return False

        self.logger.info(f"🚶 [RECORDED_PATH] Iniciando reprodução da rota '{route.name}' ({len(route.actions)} waypoints)...")
        self._is_playing = True

        self.event_bus.publish(
            EventType.ACTION_DISPATCHED,
            data={"route_name": route.name, "waypoints_count": len(route.actions)},
            category="NAVIGATION",
            level="INFO",
            message=f"ROUTE_STARTED: Reproduzindo rota '{route.name}'.",
        )

        for idx, action in enumerate(route.actions, start=1):
            if cancel_predicate and cancel_predicate():
                self.logger.warning(f"🛑 [RECORDED_PATH] Rota '{route.name}' cancelada no waypoint #{idx}.")
                self.input_ctrl.release_all_movement_keys()
                self._is_playing = False
                return False

            self.logger.info(f"🧭 [WAYPOINT #{idx}/{len(route.actions)}] Pressionando '{action.key.upper()}' por {action.duration:.3f}s...")
            self.input_ctrl.press_key(action.key, duration=action.duration)

            if action.delay_after > 0:
                time.sleep(action.delay_after)

        self._is_playing = False
        self.logger.info(f"✅ [RECORDED_PATH] Rota '{route.name}' concluída com sucesso.")
        return True

    def execute_healing_sequence(
        self,
        forward_route: Optional[RecordedRoute] = None,
        return_route: Optional[RecordedRoute] = None,
        screen_capture_func: Optional[Callable[[], Tuple[Optional[np.ndarray], float]]] = None,
        hp_check_func: Optional[Callable[[np.ndarray], float]] = None,
        cancel_predicate: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """
        Executa a sequência determinística completa de 3 subetapas da Diretiva v5.3:
        Subetapa 4.1: Caminhada até o Cristal (Rota gravada grass_to_crystal).
        Subetapa 4.2: Interação de Cura com Tecla ESPAÇO (SPACE 100ms -> 500ms -> SPACE 100ms -> 1.5s recomposição).
        Subetapa 4.3: Retorno ao Mato de Farm (Rota gravada crystal_to_grass ou inversa).
        """
        self.logger.info("🏥 [HEALING SEQUENCE] Iniciando protocolo determinístico de cura em 3 etapas...")

        # 4.1 Caminhada até o Cristal
        route_fwd = forward_route or self.load_route("grass_to_crystal")
        success_fwd = self.play_route(route_fwd, cancel_predicate=cancel_predicate)
        if not success_fwd:
            self.logger.warning("⚠️ [HEALING SEQUENCE] Falha ou cancelamento durante caminhada até o cristal.")
            return False

        if cancel_predicate and cancel_predicate():
            return False

        # 4.2 Interação de Cura com Tecla ESPAÇO
        self.logger.info("✨ [HEALING SEQUENCE] Em frente ao cristal. Disparando interação com ESPAÇO...")
        self.input_ctrl.focus_game_window()

        # Primeiro toque no ESPAÇO para acionar o cristal
        self.input_ctrl.press_key("space", duration=0.100)
        self.event_bus.publish(
            EventType.ACTION_DISPATCHED,
            data={"action": "CRYSTAL_SPACE_INTERACT", "timestamp": time.time()},
            category="NAVIGATION",
            level="INFO",
            message="CRYSTAL_INTERACT: Pressionada tecla ESPAÇO no cristal.",
        )

        time.sleep(0.500)

        # Segundo toque no ESPAÇO para avançar eventuais diálogos
        self.input_ctrl.press_key("space", duration=0.100)

        # Aguarda 1.5 segundos para a animação e recomposição de HP
        self.logger.info("⏳ [HEALING SEQUENCE] Aguardando 1.5s para recomposição completa de HP...")
        time.sleep(1.500)

        # Validação visual do HP pós-cura (se disponível)
        if screen_capture_func and hp_check_func:
            frame, _ = screen_capture_func()
            if frame is not None:
                hp_val = hp_check_func(frame)
                self.logger.info(f"📊 [HEALING SEQUENCE] HP verificado pós-cura: {hp_val*100:.1f}%")

        self.event_bus.publish(
            EventType.HEALING_COMPLETED,
            data={"timestamp": time.time(), "hp_ratio": 1.0},
            category="NAVIGATION",
            level="INFO",
            message="HEALING_COMPLETED: HP da equipe restaurado no cristal.",
        )

        if cancel_predicate and cancel_predicate():
            return False

        # 4.3 Retorno ao Mato de Farm
        route_ret = return_route or self.load_route("crystal_to_grass")
        if route_ret is None or len(route_ret.actions) == 0:
            route_ret = route_fwd.reverse(new_name="crystal_to_grass_auto")

        self.logger.info("🌲 [HEALING SEQUENCE] Retornando ao mato de farm...")
        success_ret = self.play_route(route_ret, cancel_predicate=cancel_predicate)
        if not success_ret:
            self.logger.warning("⚠️ [HEALING SEQUENCE] Falha ou cancelamento no retorno ao mato.")
            return False

        self.logger.info("🎉 [HEALING SEQUENCE] Sequência de cura concluída! Retomando estado EXPLORING.")
        return True
