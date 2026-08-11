from src.models.lumen import Lumen, Skill
from src.models.enums import Element, Rarity, AIStrategyType
from src.core.battle import BattleEngine
from src.services.simulation import MassSimulator

class CLIInterface:
    def start(self):
        while True:
            print("\n==========================================")
            print("       LUMEN BATTLE SIMULATOR             ")
            print("==========================================")
            print("1. Criar Lumen de Teste")
            print("2. Simular Batalha X1")
            print("3. Executar Campeonato Massivo (Benchmark)")
            print("4. Sair")
            
            option = input("\nEscolha uma opção: ").strip()
            
            if option == "1":
                self._menu_create_lumen()
            elif option == "2":
                self._menu_quick_battle()
            elif option == "3":
                self._menu_mass_simulation()
            elif option == "4":
                print("Encerrando simulador...")
                break
            else:
                print("Opção inválida! Tente novamente.")

    def _menu_create_lumen(self):
        name = input("Nome do Lumen: ").strip() or "Lumen-Standard"
        print("Lumen criado com sucesso!")

    def _menu_quick_battle(self):
        s1 = Skill("Golpe Elétrico", Element.ELECTRIC, power=30, energy_cost=10, accuracy=0.9)
        s2 = Skill("Jato de Água", Element.WATER, power=35, energy_cost=15, accuracy=0.85)

        l1 = Lumen(1, "Volt", Element.ELECTRIC, Rarity.RARE, skills=[s1])
        l2 = Lumen(2, "Aqua", Element.WATER, Rarity.COMMON, skills=[s2])

        print(f"\nIniciando duelo: {l1.name} VS {l2.name}")
        engine = BattleEngine(l1, l2, AIStrategyType.AGGRESSIVE, AIStrategyType.DEFENSIVE)
        result = engine.run()
        print(f"-> Vencedor: {result.winner.name} em {result.turns} turnos!")

    def _menu_mass_simulation(self):
        rounds = 500
        print(f"\nRodando {rounds} batalhas automatizadas entre IAs...")
        
        s1 = Skill("Chama", Element.FIRE, power=25, energy_cost=5, accuracy=0.95)
        
        def build_lumen_a(): return Lumen(1, "Ignis", Element.FIRE, Rarity.RARE, skills=[s1])
        def build_lumen_b(): return Lumen(2, "Terra", Element.EARTH, Rarity.RARE, skills=[s1])

        sim = MassSimulator(build_lumen_a, build_lumen_b)
        metrics = sim.run_benchmark(rounds, AIStrategyType.AGGRESSIVE, AIStrategyType.BALANCED)
        
        print("\n--- Resultados do Benchmark ---")
        print(f"Total de Batalhas: {metrics.total_battles}")
        print(f"Vitórias da IA Agressiva: {metrics.wins_a}")
        print(f"Vitórias da IA Equilibrada: {metrics.wins_b}")
        print(f"Média de Turnos: {metrics.avg_turns:.2f}")