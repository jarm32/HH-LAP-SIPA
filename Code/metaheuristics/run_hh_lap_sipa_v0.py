# Script de ejecución de HH-LAP-SIPA --> carga una instancia, ejecuta la heurística híbrida con LAP y muestra/guarda el conjunto de Pareto + estadísticas.

# cd C:\Code\VRAIN-practicas\Code\Teachers+Centers
# python -m metaheuristics.run_hh_lap_sipa_v0

# --------------------------------------------------
# Librerías
# --------------------------------------------------

from metaheuristics.scripts.hh_lap_sipa_v0 import run_hh_lap_sipa
from tools.multiobjective_search import print_pareto_set, save_results_to_txt
from tools.evaluator import ObjectiveWeights
from tools.problem import load_instance


# --------------------------------------------------
# Ejecución principal
# --------------------------------------------------

def main():
    """
    Carga una instancia, ejecuta HH-LAP-SIPA y muestra/guarda resultados.
    """
    # Algoritmo empleado, instancia sobre la que se trabaja y carga del problema
    modelo = "hh_lap_sipa"

    for i in [5,20,40,60]:
        for j in range(4):
            instance_path = f"inst_creator/output/problem_instance_ext_{i}0_{j}.txt"
            instance_name = instance_path.split("/")[-1]
            problem = load_instance(instance_path)

            # Pesos para la evaluación auxiliar
            weights = ObjectiveWeights(alpha=0.35, beta=0.35, gamma=0.20, delta=0.10)

            # Ejecución HH-LAP-SIPA
            result = run_hh_lap_sipa(
                problem=problem,
                weights=weights,
                time_limit_seconds=300,
                max_iterations=None,
                max_pareto_size=None,
                base_seed=1234,
                placement_max_attempts=50,
                lap_solver="lapjv",
                normalize_student_dist=True,
                normalize_supervision_dist=True,
                professor_lbar_weight=1.0,
                professor_omega_weight=1.0,
                verbose=True,
            )

            # Mostrar estadísticas
            print("\n=== STATS ===")
            for k, v in result["stats"].items():
                print(k, v)

            # Mostrar Pareto
            print_pareto_set(result["pareto_set"])

            # Guardar resultados
            statistics_file = f"results/statistics/statistics_{modelo}_{instance_name}"
            assignments_file = f"results/assignments/assignments_{modelo}_{instance_name}"

            save_results_to_txt(
                statistics_filepath=statistics_file,
                assignments_filepath=assignments_file,
                instance_name=instance_name,
                stats=result["stats"],
                pareto_set=result["pareto_set"],
                model=modelo,
            )

            print(f"\nStatistics saved in: {statistics_file}")
            print(f"Assignments saved in: {assignments_file}")


if __name__ == "__main__":
    main()