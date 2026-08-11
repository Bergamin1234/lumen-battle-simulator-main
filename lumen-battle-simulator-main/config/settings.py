import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class KeyBindings:
    up: str = "w"
    down: str = "s"
    left: str = "a"
    right: str = "d"
    interact: str = "e"


@dataclass
class RouteStep:
    direction: str
    duration: float


@dataclass
class BotConfig:
    window_title: str = "Lumena.gg"
    confidence: float = 0.8
    templates_dir: str = "templates"
    logs_dir: str = "logs"
    movement_pattern: str = "zigzag"
    step_duration: float = 0.35
    battle_timeout: float = 35.0
    attack_delay: float = 0.8
    monitor: int = 1
    battles_before_heal_check: int = 5
    keys: KeyBindings = field(default_factory=KeyBindings)
    route_to_heal: List[RouteStep] = field(default_factory=list)
    route_to_farm: List[RouteStep] = field(default_factory=list)

    @classmethod
    def load_from_json(cls, filepath: str = "settings.json") -> "BotConfig":
        if not os.path.exists(filepath):
            config = cls()
            config.save_to_json(filepath)
            return config

        with open(filepath, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)

        keys_data = data.pop("keys", {})
        keys = KeyBindings(**keys_data)

        raw_route_heal = data.pop("route_to_heal", [])
        route_to_heal = [RouteStep(**step) for step in raw_route_heal]

        raw_route_farm = data.pop("route_to_farm", [])
        route_to_farm = [RouteStep(**step) for step in raw_route_farm]

        return cls(
            keys=keys,
            route_to_heal=route_to_heal,
            route_to_farm=route_to_farm,
            **data
        )

    def save_to_json(self, filepath: str = "settings.json") -> None:
        data = {
            "window_title": self.window_title,
            "confidence": self.confidence,
            "templates_dir": self.templates_dir,
            "logs_dir": self.logs_dir,
            "movement_pattern": self.movement_pattern,
            "step_duration": self.step_duration,
            "battle_timeout": self.battle_timeout,
            "attack_delay": self.attack_delay,
            "monitor": self.monitor,
            "battles_before_heal_check": self.battles_before_heal_check,
            "keys": {
                "up": self.keys.up,
                "down": self.keys.down,
                "left": self.keys.left,
                "right": self.keys.right,
                "interact": self.keys.interact
            },
            "route_to_heal": [{"direction": s.direction, "duration": s.duration} for s in self.route_to_heal],
            "route_to_farm": [{"direction": s.direction, "duration": s.duration} for s in self.route_to_farm]
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)