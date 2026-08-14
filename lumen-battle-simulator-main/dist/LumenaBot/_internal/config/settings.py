from dataclasses import dataclass, field
import json
import os
from typing import List, Dict, Any, Optional


CRITICAL_HP_RATIO: float = 0.20
HEALING_HP_RATIO: float = 0.40
COMBAT_ACTION_TIMEOUT: float = 5.0


@dataclass
class KeyBindings:
    up: str = "w"
    down: str = "s"
    left: str = "a"
    right: str = "d"
    interact: str = "e"
    space: str = "space"
    enter: str = "enter"
    escape: str = "esc"


@dataclass
class MonitorConfig:
    monitor_index: int = 1
    fps_limit: int = 30
    width: int = 1920
    height: int = 1080


@dataclass
class BattleConfig:
    battle_timeout: float = 35.0
    attack_delay: float = 0.8
    max_battle_turns: int = 30
    max_action_retries: int = 3
    critical_hp_ratio: float = 0.20
    healing_hp_ratio: float = 0.40
    combat_action_timeout: float = 5.0


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
    critical_hp_ratio: float = 0.20
    healing_hp_ratio: float = 0.40
    combat_action_timeout: float = 5.0
    keys: KeyBindings = field(default_factory=KeyBindings)
    monitor_cfg: MonitorConfig = field(default_factory=MonitorConfig)
    battle_cfg: BattleConfig = field(default_factory=BattleConfig)
    route_to_heal: List[RouteStep] = field(default_factory=list)
    route_to_farm: List[RouteStep] = field(default_factory=list)

    @classmethod
    def load_from_json(cls, filepath: str = "settings.json") -> "BotConfig":
        if not os.path.exists(filepath) and os.path.exists("config/settings.json"):
            filepath = "config/settings.json"

        if not os.path.exists(filepath):
            config = cls()
            config.save_to_json(filepath)
            return config

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            keys_data = data.pop("keys", {})
            keys = KeyBindings(**keys_data) if isinstance(keys_data, dict) else KeyBindings()

            raw_route_heal = data.pop("route_to_heal", [])
            route_to_heal = [RouteStep(**step) for step in raw_route_heal] if isinstance(raw_route_heal, list) else []

            raw_route_farm = data.pop("route_to_farm", [])
            route_to_farm = [RouteStep(**step) for step in raw_route_farm] if isinstance(raw_route_farm, list) else []

            monitor_val = data.get("monitor", 1)

            return cls(
                keys=keys,
                route_to_heal=route_to_heal,
                route_to_farm=route_to_farm,
                **{k: v for k, v in data.items() if k in cls.__annotations__}
            )
        except Exception:
            return cls()

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
                "interact": self.keys.interact,
            },
            "route_to_heal": [{"direction": s.direction, "duration": s.duration} for s in self.route_to_heal],
            "route_to_farm": [{"direction": s.direction, "duration": s.duration} for s in self.route_to_farm],
        }
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def load_config(filepath: str = "config/settings.json") -> BotConfig:
    return BotConfig.load_from_json(filepath)


def save_config(config: BotConfig, filepath: str = "config/settings.json") -> None:
    config.save_to_json(filepath)