import time
import logging
import cv2
import numpy as np
import mss
from config.settings import BotConfig
from src.automation.vision import VisionSystem
from src.input.input_controller import InputController


class LegacyBattleMacro:
    def __init__(self, config: BotConfig, vision: VisionSystem, input_ctrl: InputController) -> None:
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl
        self.logger = logging.getLogger("LumenaMacro")
        self.current_attack = 0

    def in_battle(self) -> bool:
        """Verifica se o botão FIGHT vermelho ou a interface de batalha está visível."""
        return self.vision.template_exists("fight_button.png")

    def check_enemy_hp_zero(self) -> bool:
        """
        Analisa a barra de vida do oponente no canto superior direito por Cor (RGB).
        Retorna True se não houver mais cor verde (HP 0%).
        """
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[self.config.monitor]
                screenshot = np.array(sct.grab(monitor))

                # Região aproximada do canto superior direito (onde fica a barra de HP do inimigo)
                h, w, _ = screenshot.shape
                hp_region = screenshot[int(h * 0.02):int(h * 0.12), int(w * 0.70):int(w * 0.98)]

                # Converter para HSV para detectar a cor verde da barra de vida
                hsv = cv2.cvtColor(hp_region, cv2.COLOR_BGRA2BGR)
                hsv = cv2.cvtColor(hsv, cv2.COLOR_BGR2HSV)

                # Intervalo da cor verde no HSV
                lower_green = np.array([35, 50, 50])
                upper_green = np.array([85, 255, 255])

                mask = cv2.inRange(hsv, lower_green, upper_green)
                green_pixels = cv2.countNonZero(mask)

                # Se houver pouquíssimos pixels verdes, o HP do oponente acabou
                return green_pixels < 50
        except Exception as e:
            self.logger.debug(f"Erro ao checar HP por cor: {e}")
            return False

    def execute_turn(self) -> None:
        """Executa a jogada encontrando o FIGHT e usando coordenadas offset para os ataques da esquerda."""
        fight_pos = self.vision.find_template("fight_button.png")

        if fight_pos:
            fx, fy = self.vision.get_center_coords(fight_pos)

            # 1. Clica no Botão FIGHT
            self.input_ctrl.click(fx, fy)
            time.sleep(0.5)

            # 2. As caixas dos 2 ataques da esquerda ficam posicionadas à esquerda do FIGHT
            # Cálculo de offset baseado na interface do Lumena:
            attack_x = fx - 220  # Move para a coluna da esquerda

            if self.current_attack == 0:
                attack_y = fy - 35  # Ataque 1 (Superior Esquerdo)
                self.logger.info("⚡ Atacando com o 1º Golpe da Esquerda!")
                self.current_attack = 1
            else:
                attack_y = fy + 35  # Ataque 2 (Inferior Esquerdo)
                self.logger.info("🔥 Atacando com o 2º Golpe da Esquerda!")
                self.current_attack = 0

            self.input_ctrl.click(attack_x, attack_y)
            time.sleep(1.0)
        else:
            # Se não viu o FIGHT, clica no centro para avançar animação/diálogo
            cx, cy = self.input_ctrl.get_screen_center()
            self.input_ctrl.click(cx, cy)

    def run_battle_sequence(self) -> None:
        """Loop autônomo de batalha."""
        self.logger.info("⚔️ Entrou em batalha! Iniciando rotina de ataques...")
        turns = 0

        while turns < 30:
            # Checa se o HP do inimigo zera por análise de cor
            if self.check_enemy_hp_zero():
                self.logger.info("HP do oponente zerou (Barra sem cor verde)! Finalizando batalha...")
                cx, cy = self.input_ctrl.get_screen_center()
                for _ in range(6):
                    self.input_ctrl.click(cx, cy)
                    time.sleep(0.3)
                break

            # Se saiu da batalha
            if not self.in_battle() and turns > 1:
                self.logger.info("Interface de batalha fechada. Batalha vencida!")
                break

            self.execute_turn()
            time.sleep(1.2)
            turns += 1

        self.logger.info("✓ Combate encerrado. Retornando ao loop de navegação.")
