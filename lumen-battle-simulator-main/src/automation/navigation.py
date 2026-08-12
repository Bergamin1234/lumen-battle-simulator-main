import json
import logging
import os
import time
from typing import List, Dict, Union
from config.settings import BotConfig
from src.input.input_controller import InputController


class NavigationController:
    """Controlador de rotas gravadas (WASD) e navegação autônoma em malha fechada."""

    def __init__(self, config: BotConfig, input_ctrl: InputController) -> None:
        self.config = config
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")
        self.route_file = "config/farm_to_heal_route.json"

    def save_route(self, route_data: List[Dict[str, Union[float, str]]]) -> None:
        """Salva a sequência gravada de passos e curvas em um arquivo JSON."""
        os.makedirs("config", exist_ok=True)
        with open(self.route_file, "w", encoding="utf-8") as f:
            json.dump(route_data, f, indent=2)
        self.logger.info("✓ Rota de navegação gravada e salva com sucesso em config/farm_to_heal_route.json!")

    def load_route(self) -> List[Dict[str, Union[float, str]]]:
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

        steps = list(reversed(route)) if reverse else list(route)
        action_type = "Volta para o Mato" if reverse else "Ida para o Cristal de Cura"
        self.logger.info(f"🧭 Executando Rota Autônoma ({action_type}) com {len(steps)} passos...")

        # Garante foco no navegador antes de iniciar o replay de teclas
        self.input_ctrl.focus_game_window()

        opposite_keys = {"w": "s", "s": "w", "a": "d", "d": "a"}

        try:
            for idx, step in enumerate(steps, 1):
                key = str(step["key"]).lower()
                duration = float(step["duration"])

                if reverse:
                    key = opposite_keys.get(key, key)

                self.logger.info(f"[REPLAY] Passo {idx}/{len(steps)}: {key.upper()} por {duration:.2f}s")
                self.input_ctrl.press_key(key, duration=duration)
                time.sleep(0.05)
        finally:
            self.input_ctrl.release_all_keys()
            self.logger.info(f"✓ Rota ({action_type}) concluída com sucesso.")

    def _fallback_walk(self, reverse: bool) -> None:
        """Movimento genérico de emergência caso não exista rota gravada."""
        self.input_ctrl.focus_game_window()
        up_key = getattr(self.config.keys, "up", "w")
        down_key = getattr(self.config.keys, "down", "s")
        left_key = getattr(self.config.keys, "left", "a")

        try:
            if not reverse:
                self.input_ctrl.press_key(down_key, duration=2.5)
                self.input_ctrl.press_key(left_key, duration=1.2)
            else:
                self.input_ctrl.press_key(up_key, duration=2.8)
                time.sleep(2.0)
                self.input_ctrl.press_key(left_key, duration=1.5)
        finally:
            self.input_ctrl.release_all_keys()

    def walk_to_heal_point(self) -> None:
        """Caminha do Mato até o Cristal Azul na Cidade seguindo a Rota Gravada."""
        self.execute_route(reverse=False)

    def return_to_farm_area(self) -> None:
        """Caminha do Cristal na Cidade até o Portal e de volta para o Mato seguindo a Rota Inversa."""
        self.execute_route(reverse=True)