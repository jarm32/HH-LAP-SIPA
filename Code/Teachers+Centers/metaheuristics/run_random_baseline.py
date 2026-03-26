from scripts.random_feasible_fixing import generate_random_feasible_fixing
from tools.multiobjective_search import random_search_pareto, print_pareto_set, save_results_to_txt
from tools.evaluator import ObjectiveWeights
from tools.problem import load_instance


def main():
    modelo = "random"

    instance_path = "inst_creator/output/problem_instance_ext_400_1.txt"
    instance_name = instance_path.split("/")[-1]

    problem = load_instance(instance_path)

    weights = ObjectiveWeights(
        alpha=0.35,
        beta=0.35,
        gamma=0.20,
        delta=0.10,
    )

    result = random_search_pareto(
        problem=problem,
        generator_fn=generate_random_feasible_fixing,
        weights=weights, # Pesos usados solo para el objective_value escalar auxiliar (desempate en poda), no para la dominancia Pareto
        time_limit_seconds=60,
        max_pareto_size=50,
        base_seed=1234,
        verbose=True
    )

    print("\n=== STATS ===")
    for k, v in result["stats"].items():
        print(k, v)

    print_pareto_set(result["pareto_set"])

    output_file = f"results/results_{modelo}_{instance_name}"

    save_results_to_txt(
        filepath=output_file,
        instance_name=instance_name,
        stats=result["stats"],
        pareto_set=result["pareto_set"]
    )

    print(f"\nResults saved in: {output_file}")


if __name__ == "__main__":
    main()