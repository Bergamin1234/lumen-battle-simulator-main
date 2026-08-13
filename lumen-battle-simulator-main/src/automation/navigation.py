import json
import logging
import os
import time
from typing import List, Dict, Union, Optional, Callable
from config.settings import BotConfig
from src.input.input_controller import InputController
from src.telemetry.telemetry_manager import TelemetryManager

logger = logging.getLogger("LumenaNavigation")


class RouteManager:
    """Gerenciador completo de rotas gravadas em disco com suporte a gravação, edição e reversão."""

    def __init__(self, routes_dir: str = "config/routes") -> None:
        self.logger = logging.getLogger("LumenaNavigation")
        self.routes_dir = routes_dir
        os.makedirs(self.routes_dir, exist_ok=True)

        # Estado de gravação
        self.is_recording = False
        self.is_paused = False
        self.active_recording_steps: List[Dict[str, Union[str, float]]] = []
        self._step_start_time = 0.0
        self._current_recording_key: Optional[str] = None

    def list_routes(self) -> List[str]:
        """Lista os nomes de todas as rotas salvas."""
        routes = []
        if os.path.exists(self.routes_dir):
            for file in os.listdir(self.routes_dir):
                if file.endswith(".json"):
                    routes.append(file[:-5])
        # Suporte para rota padrão legada
        if os.path.exists("config/farm_to_heal_route.json") and "farm_to_heal_route" not in routes:
            routes.append("farm_to_heal_route")
        return sorted(routes)

    def load_route(self, route_name: str) -> List[Dict[str, Union[str, float]]]:
        """Carrega passos da rota especificada."""
        path = os.path.join(self.routes_dir, f"{route_name}.json")
        if not os.path.exists(path) and route_name == "farm_to_heal_route":
            path = "config/farm_to_heal_route.json"

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Erro ao carregar rota '{route_name}': {e}")
        return []

    def save_route(self, route_name: str, steps: List[Dict[str, Union[str, float]]]) -> bool:
        """Salva a rota no diretório padrão."""
        clean_name = route_name.strip().replace(" ", "_").lower()
        if not clean_name:
            clean_name = f"route_{int(time.time())}"
        path = os.path.join(self.routes_dir, f"{clean_name}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(steps, f, indent=2)
            self.logger.info(f"✓ Rota '{clean_name}' salva com sucesso com {len(steps)} passos.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar rota '{clean_name}': {e}")
            return False

    def delete_route(self, route_name: str) -> bool:
        path = os.path.join(self.routes_dir, f"{route_name}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
                self.logger.info(f"✓ Rota '{route_name}' excluída.")
                return True
            except Exception as e:
                self.logger.error(f"Erro ao excluir rota '{route_name}': {e}")
        return False

    def reverse_route(self, steps: List[Dict[str, Union[str, float]]]) -> List[Dict[str, Union[str, float]]]:
        """Inverte uma rota de navegação mapeando direções opostas."""
        opposite_keys = {"w": "s", "s": "w", "a": "d", "d": "a"}
        reversed_steps = []
        for step in reversed(steps):
            k = str(step["key"]).lower()
            dur = float(step["duration"])
            reversed_steps.append({"key": opposite_keys.get(k, k), "duration": dur})
        return reversed_steps

    def start_recording(self) -> None:
        self.is_recording = True
        self.is_paused = False
        self.active_recording_steps = []
        self._current_recording_key = None
        self.logger.info("🎙️ Gravação de rota iniciada.")

    def pause_recording(self) -> None:
        if self.is_recording:
            self.is_paused = True
            self.logger.info("⏸️ Gravação de rota pausada.")

    def resume_recording(self) -> None:
        if self.is_recording:
            self.is_paused = False
            self.logger.info("▶️ Gravação de rota retomada.")

    def add_recording_step(self, key: str, duration: float) -> None:
        if self.is_recording and not self.is_paused:
            self.active_recording_steps.append({"key": key.lower().strip(), "duration": round(duration, 3)})
            self.logger.info(f"📝 [REC] Passo gravado: {key.upper()} por {duration:.2f}s")

    def stop_recording(self, route_name: str = "nova_rota") -> List[Dict[str, Union[str, float]]]:
        self.is_recording = False
        self.is_paused = False
        steps = list(self.active_recording_steps)
        if steps:
            self.save_route(route_name, steps)
        self.logger.info(f"⏹️ Gravação de rota finalizada com {len(steps)} passos.")
        return steps


class NavigationController:
    """Controlador de navegação autônoma em malha fechada e replay de rotas."""

    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaNavigation")
        self.route_manager = RouteManager()
        self.telemetry = TelemetryManager()
        self.route_file = "config/farm_to_heal_route.json"

        self.current_route_name = ""
        self.current_step_index = 0
        self.total_steps = 0
        self.is_navigating = False

    def save_route(self, route_data: List[Dict[str, Union[float, str]]]) -> None:
        self.route_manager.save_route("farm_to_heal_route", route_data)

    def load_route(self) -> List[Dict[str, Union[float, str]]]:
        return self.route_manager.load_route("farm_to_heal_route")

    def execute_route(
        self,
        route_name: Optional[str] = None,
        reverse: bool = False,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Executa a rota passo a passo com telemetria e checagem de parada de emergência."""
        target_name = route_name or "farm_to_heal_route"
        steps = self.route_manager.load_route(target_name)

        if not steps:
            self.logger.warning(f"Nenhuma rota gravada encontrada para '{target_name}'.")
            return False

        if reverse:
            steps = self.route_manager.reverse_route(steps)

        action_type = "Volta / Sentido Inverso" if reverse else "Ida / Sentido Normal"
        self.logger.info(f"🧭 [NAV] Executando rota '{target_name}' ({action_type}) com {len(steps)} passos...")

        self.is_navigating = True
        self.current_route_name = target_name
        self.total_steps = len(steps)
        self.input_ctrl.focus_game_window()

        try:
            for idx, step in enumerate(steps, 1):
                if stop_check and stop_check():
                    self.logger.warning("🛑 [NAV] Execução de rota interrompida.")
                    return False

                self.current_step_index = idx
                key = str(step["key"]).lower()
                dur = float(step["duration"])

                progress_pct = round((idx / len(steps)) * 100, 1)
                self.logger.info(f"[REPLAY] Passo {idx}/{len(steps)} ({progress_pct}%): {key.upper()} por {dur:.2f}s")
                self.telemetry.update_agent_status(
                    objective=f"Navegando: {target_name} ({idx}/{len(steps)})",
                    decision=f"Pressionar {key.upper()}",
                    reason=f"Passo de Rota ({dur:.2f}s)",
                )

                t0 = time.time()
                success = self.input_ctrl.press_key(key, duration=dur)
                t1 = time.time()
                self.telemetry.record_action(success, latency=t1 - t0, action_type="NAV_STEP")

                time.sleep(0.05)
            return True
        finally:
            self.input_ctrl.release_all_keys()
            self.is_navigating = False
            self.current_step_index = 0
            self.logger.info(f"✓ [NAV] Rota '{target_name}' ({action_type}) concluída com sucesso.")

    def walk_to_heal_point(self, stop_check: Optional[Callable[[], bool]] = None) -> None:
        self.execute_route("farm_to_heal_route", reverse=False, stop_check=stop_check)

    def return_to_farm_area(self, stop_check: Optional[Callable[[], bool]] = None) -> None:
        self.execute_route("farm_to_heal_route", reverse=True, stop_check=stop_check)