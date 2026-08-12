import time
import cv2
import os
from src.automation.bot_engine import LumenaBotEngine


class UnifiedCLI:
    def __init__(self) -> None:
        self.bot = LumenaBotEngine()

    def capture_template(self) -> None:
        print("\n--- CAPTURA DE TEMPLATES ---")
        filename = input("Nome do template (ex: fight_button.png, dialog_box.png): ").strip()
        if not filename.endswith((".png", ".jpg")):
            filename += ".png"

        print("Alterne para o jogo em 3 segundos...")
        time.sleep(3)
        screenshot = self.bot.vision.get_screenshot()
        save_path = os.path.join(self.bot.config.templates_dir, filename)
        cv2.imwrite(save_path, screenshot)
        self.bot.vision.load_templates()
        print(f"[+] Print salvo em '{save_path}'. Recorte a imagem para isolar o botão.")

    def test_vision(self) -> None:
        print("\n--- TESTE DE VISÃO COMPUTACIONAL ---")
        screenshot = self.bot.vision.get_screenshot()
        for name in self.bot.vision.templates.keys():
            match = self.bot.vision.find_template(name, screenshot=screenshot)
            if match:
                print(f"[OK] Template '{name}' detectado em: {match}")
            else:
                print(f"[X] Template '{name}' não encontrado.")

    def run(self) -> None:
        while True:
            status = "EXECUTANDO" if self.bot.is_running else "PARADO"
            print("\n==============================================")
            print(f"   LUMENA BATTLE SIMULATOR & BOT [{status}]")
            print("==============================================")
            print("1 - Iniciar / Parar Automação Visual (Macro)")
            print("2 - Capturar Novo Template de Tela")
            print("3 - Testar Reconhecimento Visão")
            print("4 - Executar Teste Manual da Rota + Cura")
            print("5 - Sair")

            choice = input("Opção: ").strip()

            if choice == "1":
                if self.bot.is_running:
                    self.bot.stop()
                else:
                    self.bot.start()
            elif choice == "2":
                self.capture_template()
            elif choice == "3":
                self.test_vision()
            elif choice == "4":
                print("\nIniciando rota até a Estrutura Azul e Cura em 3s...")
                time.sleep(3)
                self.bot.full_heal_routine()
            elif choice == "5":
                self.bot.stop()
                print("Encerrando...")
                break
            else:
                print("Opção inválida.")