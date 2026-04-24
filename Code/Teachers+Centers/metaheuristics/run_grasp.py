# Script de ejecución de GRASP --> carga una instancia, ejecuta el algoritmo GRASP y muestra/guarda el conjunto de Pareto + estadísticas

# cd C:\Code\VRAIN-practicas\Code\Teachers+Centers
# python -m metaheuristics.run_grasp

# --------------------------------------------------
# Librerías
# --------------------------------------------------

from metaheuristics.scripts.grasp import run_grasp
from tools.multiobjective_search import print_pareto_set, save_results_to_txt
from tools.evaluator import ObjectiveWeights
from tools.problem import load_instance


# --------------------------------------------------
# Ejecución principal
# --------------------------------------------------

def main():
    """
    Carga una instancias, ejecuta GRASP y muestra/guarda resultados
    """
    # Algoritmo empleado, pesos de los objetivos, instancia sobre la que se trabaja y carga del problema
    modelo = "grasp"

    weights = ObjectiveWeights(alpha=0.35, beta=0.35, gamma=0.20, delta=0.10)

    for i in [2]:
        for j in range(1,2):
            instance_path = f"inst_creator/output/problem_instance_ext_{i}00_{j}.txt"
            instance_name = instance_path.split("/")[-1]

            # Carga de la instancia
            problem = load_instance(instance_path)

            # Ejecución GRASP
            result = run_grasp(
                problem=problem,
                weights=weights,
                alpha_rcl=0.5,
                time_limit_seconds=300,
                max_iterations=None,
                max_pareto_size=None,
                base_seed=1234,
                normalize_student_dist=True,
                normalize_supervision_dist=True,
                constructive_max_attempts=50,
                verbose=True,
            )

            # Mostrar estadísticas
            print("\n=== STATS ===")
            for k, v in result["stats"].items():
                print(k, v)

            # Mostrar Pareto
            print_pareto_set(result["pareto_set"])

            # Guardar resultados en archivos separados
            statistics_file = f"results/statistics/statistics_{modelo}_{instance_name}"
            assignments_file = f"results/assignments/assignments_{modelo}_{instance_name}"

            save_results_to_txt(
                statistics_filepath=statistics_file,
                assignments_filepath=assignments_file,
                instance_name=instance_name,
                stats=result["stats"],
                pareto_set=result["pareto_set"],
                model=modelo
            )

            print(f"\nStatistics saved in: {statistics_file}")
            print(f"Assignments saved in: {assignments_file}")


if __name__ == "__main__":
    main()