import json
import logging
import os
import time
from config.settings import BotConfig
from src.automation.input_controller import InputController


class NavigationController:
    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")
        self.route_file = "config/farm_to_heal_route.json"

    def save_route(self, route_data: list[dict[str, float | str]]) -> None:
        """Salva a sequência gravada de passos e curvas em um arquivo JSON."""
        os.makedirs("config", exist_ok=True)
        with open(self.route_file, "w", encoding="utf-8") as f:
            json.dump(route_data, f, indent=2)
        self.logger.info("✓ Rota de navegação gravada e salva com sucesso em config/farm_to_heal_route.json!")

    def load_route(self) -> list[dict[str, float | str]]:
        """Carrega os passos da rota gravada."""
        if os.path.exists(self.route_file):
            try:
                with open(self.route_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Erro ao carregar arquivo de rota: {e}")
        return []

    def execute_route(self, reverse: bool = False) -> None:
        """
        Executa a rota gravada passo a passo (com todas as curvas e mudanças de mapa).
        Se reverse=True, executa a rota no sentido inverso (do Cristal de volta para o Mato).
        """
        route = self.load_route()
        if not route:
            self.logger.warning("Nenhuma rota gravada encontrada em config/farm_to_heal_route.json!")
            self.logger.warning("Usando navegação padrão genérica...")
            self._fallback_walk(reverse)
            return

        steps = reversed(route) if reverse else route
        action_type = "Volta para o Mato" if reverse else "Ida para o Cristal de Cura"
        self.logger.info(f"🧭 Executando Rota Autônoma ({action_type})...")

        opposite_keys = {"w": "s", "s": "w", "a": "d", "d": "a"}

        for step in steps:
            key = str(step["key"])
            duration = float(step["duration"])

            # Se for a rota inversa de volta, inverte a tecla da curva
            if reverse:
                key = opposite_keys.get(key, key)

            self.logger.debug(f"Passo: {key.upper()} por {duration:.2f}s")
            self.input_ctrl.press_key(key, duration=duration)
            time.sleep(0.1)

    def _fallback_walk(self, reverse: bool) -> None:
        """Movimento genérico caso não exista rota gravada."""
        up_key = getattr(self.config.keys, "up", "w")
        down_key = getattr(self.config.keys, "down", "s")
        left_key = getattr(self.config.keys, "left", "a")

        if not reverse:
            self.input_ctrl.press_key(down_key, duration=2.5)
            self.input_ctrl.press_key(left_key, duration=1.2)
        else:
            self.input_ctrl.press_key(up_key, duration=2.8)
            time.sleep(2.0)  # Portal
            self.input_ctrl.press_key(left_key, duration=1.5)

    def walk_to_heal_point(self) -> None:
        """Caminha do Mato até o Cristal Azul na Cidade seguindo a Rota Gravada."""
        self.execute_route(reverse=False)

    def return_to_farm_area(self) -> None:
        """Caminha do Cristal na Cidade até o Portal e de volta para o Mato seguindo a Rota Inversa."""
        self.execute_route(reverse=True)