# Script de ejecución de la baseline de búsqueda aleatoria --> carga una instancia, lanza la búsqueda multiobjetivo y muestra/guarda el conjunto de Pareto + estadísticas

# cd C:\Code\VRAIN-practicas\Code\Teachers+Centers
# python -m metaheuristics.run_random_baseline

# --------------------------------------------------
# Librerías
# --------------------------------------------------

from metaheuristics.scripts.random_feasible_fixing import generate_random_feasible_fixing
from tools.multiobjective_search import random_search_pareto, print_pareto_set, save_results_to_txt
from tools.evaluator import ObjectiveWeights
from tools.problem import load_instance


# --------------------------------------------------
# Ejecución principal
# --------------------------------------------------

def main():
    """
    Carga una instancia, ejecuta la búsqueda multiobjetivo con la heurística aleatoria y muestra/guarda resultados
    """
    # Algoritmo empleado
    modelo = "RS_baseline"

    for i in [2,4,6]:
        # Instancia escogida + carga
        instance_path = f"inst_creator/output/problem_instance_ext_{i}00_2.txt"
        instance_name = instance_path.split("/")[-1]
        problem = load_instance(instance_path)

        # Pesos de las componentes de la f.o.
        weights = ObjectiveWeights(
            alpha=0.35,
            beta=0.35,
            gamma=0.20,
            delta=0.10,
        )

        # Ejecución del algoritmo
        result = random_search_pareto(
            problem=problem,
            generator_fn=generate_random_feasible_fixing,
            weights=weights, # Pesos usados solo para el objective_value escalar auxiliar (desempate en poda), no para la dominancia Pareto
            time_limit_seconds=300,
            max_pareto_size=None,
            base_seed=1234,
            verbose=True
        )

        # Imprimir estadísticas
        print("\n=== STATS ===")
        for k, v in result["stats"].items():
            print(k, v)

        # Imprimir Pareto
        print_pareto_set(result["pareto_set"])

        # Archivo salida
        output_file = f"results/results_{modelo}_{instance_name}"
        
        save_results_to_txt(
            filepath=output_file,
            instance_name=instance_name,
            stats=result["stats"],
            pareto_set=result["pareto_set"],
            model=modelo
        )

        print(f"\nResults saved in: {output_file}")


if __name__ == "__main__":
    main()