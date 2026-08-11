import time
import logging
from config.settings import BotConfig
from src.automation.vision import VisionSystem
from src.automation.input_controller import InputController


class BattleController:
    def __init__(self, config: BotConfig, vision: VisionSystem, input_ctrl: InputController) -> None:
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")
        self.total_battles_fought = 0

    def in_battle(self) -> bool:
        return (
            self.vision.template_exists("fight_button.png") or 
            self.vision.template_exists("battle_hud.png")
        )

    def needs_healing(self) -> bool:
        if self.vision.template_exists("low_hp_warning.png") or self.vision.template_exists("fainted_lumen.png"):
            self.logger.warning("HP Baixo ou Lumen Desmaiado detectado.")
            return True

        if self.total_battles_fought >= self.config.battles_before_heal_check:
            self.logger.info(f"Limite de {self.config.battles_before_heal_check} batalhas atingido. Indo curar.")
            return True

        return False

    def reset_battle_counter(self) -> None:
        self.total_battles_fought = 0

    def handle_battle(self) -> bool:
        self.logger.info("Batalha iniciada.")
        start_time = time.time()

        while time.time() - start_time < self.config.battle_timeout:
            fight_loc = self.vision.wait_template("fight_button.png", timeout=3.0)
            if fight_loc:
                cx, cy = self.vision.get_center_coords(fight_loc)
                self.input_ctrl.click(cx, cy)
                time.sleep(0.5)

                move_loc = self.vision.wait_template("first_move.png", timeout=2.0)
                if move_loc:
                    mx, my = self.vision.get_center_coords(move_loc)
                    self.input_ctrl.click(mx, my)
                    self.logger.info("Primeiro golpe ativado.")
                else:
                    self.input_ctrl.click(cx, cy)

            xp_loc = self.vision.find_template("xp_screen.png")
            if xp_loc:
                cx, cy = self.vision.get_center_coords(xp_loc)
                self.input_ctrl.click(cx, cy)
                self.logger.info("Tela de XP fechada.")
                time.sleep(0.5)

            close_loc = self.vision.find_template("close_battle.png")
            if close_loc:
                cx, cy = self.vision.get_center_coords(close_loc)
                self.input_ctrl.click(cx, cy)

            if not self.in_battle() and not self.vision.template_exists("xp_screen.png"):
                self.total_battles_fought += 1
                self.logger.info(f"Vitória confirmada. Lutas na sessão: {self.total_battles_fought}")
                return True

            time.sleep(self.config.attack_delay)

        self.logger.error("Timeout de batalha.")
        return False