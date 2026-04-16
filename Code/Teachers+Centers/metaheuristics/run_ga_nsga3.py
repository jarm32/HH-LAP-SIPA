# Script de ejecución de NSGA-III --> carga una instancia, ejecuta el algoritmo genético multiobjetivo y muestra/guarda el conjunto de Pareto + estadísticas

# cd C:\Code\VRAIN-practicas\Code\Teachers+Centers
# python -m metaheuristics.run_ga_nsga3_v1

# --------------------------------------------------
# Librerías
# --------------------------------------------------

from metaheuristics.scripts.ga_nsga3 import run_nsga3
from tools.multiobjective_search import print_pareto_set, save_results_to_txt
from tools.evaluator import ObjectiveWeights
from tools.problem import load_instance

# --------------------------------------------------
# Ejecución principal
# --------------------------------------------------

def main():
    """
    Carga una instancia, ejecuta NSGA-III y muestra/guarda resultados
    """
    # Algoritmo empleado, instancia sobre la que se trabaja y carga del problema
    modelo = "nsga3"

    for i in [2,4,6]:
        instance_path = f"inst_creator/output/problem_instance_ext_{i}00_2.txt"
        instance_name = instance_path.split("/")[-1]
        problem = load_instance(instance_path)

        # Pesos para la evaluación auxiliar
        weights = ObjectiveWeights(alpha=0.35, beta=0.35, gamma=0.20, delta=0.10)

        # Ejecución NSGA-III
        result = run_nsga3(
            problem=problem,
            weights=weights,
            population_size=50,
            offspring_size=50,
            cx_prob=0.8,
            mut_prob=0.2,
            time_limit_seconds=300,
            max_generations=None,
            max_pareto_size=None,
            base_seed=1234,
            normalize_student_dist=True,
            normalize_supervision_dist=True,
            ref_points_p=5,
            verbose=True
        )

        # Mostrar estadísticas
        print("\n=== STATS ===")
        for k, v in result["stats"].items():
            print(k, v)

        # Mostrar Pareto
        print_pareto_set(result["pareto_set"])

        # Guardar resultados
        output_file = f"results/results_{modelo}_{instance_name}"
        save_results_to_txt(filepath=output_file, instance_name=instance_name, stats=result["stats"], pareto_set=result["pareto_set"], model=modelo)
        print(f"\nResults saved in: {output_file}")


if __name__ == "__main__":
    main()