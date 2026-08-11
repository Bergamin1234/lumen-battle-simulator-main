import sys
from src.models.lumen import Lumen, Skill, LumenSpecies
from src.models.enums import Element, AIStrategyType, MoveCategory, CodeTraitGrade
from src.core.battle import BattleEngine
from src.services.simulation import MassSimulator
from src.core.codex import load_default_codex
from src.services.evolution import CODEX_REGISTRY, EvolutionService
from src.models.lumen import Lumen
from src.models.enums import CodeTraitGrade

def main():
    # 1. Carrega o Códice na memória RAM
    load_default_codex()
    print(f"Códice carregado com {len(CODEX_REGISTRY)} espécies!")

    # 2. Exemplo de teste rápido com o ID #1 (Leafy)
    meu_lumen = Lumen(
        id=101,
        nickname="Verdinho",
        species=CODEX_REGISTRY[1],  # Busca o ID #1 cadastrado no Códice
        level=15,
        code_trait=CodeTraitGrade.A
    )

    print(f"Lumen Criado: {meu_lumen.nickname} ({meu_lumen.species.species_name}) - Nível {meu_lumen.level}")
    
    # 3. Dá XP para subir ao Nível 16 e disparar evolução automática para o ID #2
    resultado = EvolutionService.add_experience(meu_lumen, 500)
    print(f"Nova Espécie após XP: {meu_lumen.species.species_name} (ID #{meu_lumen.species.codex_number})")

if __name__ == "__main__":
    main()

def create_sample_lumen(name: str, element: Element) -> Lumen:
    species = LumenSpecies(
        codex_number=1,
        species_name=name,
        primary_type=element,
        base_hp=60,
        base_attack=55,
        base_defense=50,
        base_sp_attack=65,
        base_sp_defense=50,
        base_speed=60
    )
    
    skill_strike = Skill(
        name="Golpe Direto", 
        element=element, 
        category=MoveCategory.PHYSICAL, 
        power=30, 
        accuracy=0.95, 
        max_pp=20, 
        current_pp=20
    )
    skill_burst = Skill(
        name="Explosão Elemental", 
        element=element, 
        category=MoveCategory.SPECIAL, 
        power=55, 
        accuracy=0.85, 
        max_pp=10, 
        current_pp=10
    )
    
    return Lumen(
        id=None,
        nickname=name,
        species=species,
        code_trait=CodeTraitGrade.A,
        skills=[skill_strike, skill_burst]
    )

def main():
    while True:
        print("\n==============================================")
        print("  LUMEN BATTLE SIMULATOR (100% IN-MEMORY)     ")
        print("==============================================")
        print("1. Batalha Rápida 1v1")
        print("2. Simulação Massiva (Benchmark de IAs)")
        print("3. Sair")
        
        choice = input("\nSelecione uma opção: ").strip()

        if choice == "1":
            lumen_1 = create_sample_lumen("Ignis", Element.FIRE)
            lumen_2 = create_sample_lumen("Aqua", Element.WATER)
            
            print(f"\nIniciando Batalha: {lumen_1.nickname} VS {lumen_2.nickname}")
            engine = BattleEngine(lumen_1, lumen_2, AIStrategyType.AGGRESSIVE, AIStrategyType.BALANCED)
            result = engine.run()
            print(f"-> Vencedor: {result.winner.nickname} em {result.turns} turnos!")

        elif choice == "2":
            rounds = 1000
            print(f"\nRodando Simulação Massiva ({rounds} Partidas)...")
            simulator = MassSimulator(
                lumen_a_factory=lambda: create_sample_lumen("Pyros", Element.FIRE),
                lumen_b_factory=lambda: create_sample_lumen("Hydro", Element.WATER)
            )
            metrics = simulator.run_benchmark(rounds, AIStrategyType.AGGRESSIVE, AIStrategyType.DEFENSIVE)
            
            print(f"\n--- Resultado do Benchmark ---")
            print(f"Vitórias IA Agressiva: {metrics.wins_a}")
            print(f"Vitórias IA Defensiva: {metrics.wins_b}")
            print(f"Média de Turnos: {metrics.avg_turns:.2f}")
            print(f"Taxa de Vitória Agressiva: {metrics.win_rate_a:.2f}%")
            
        elif choice == "3":
            print("Saindo do simulador...")
            sys.exit(0)
from src.ui.cli import UnifiedCLI

if __name__ == "__main__":
    app = UnifiedCLI()
    app.run()
if __name__ == "__main__":
    main()