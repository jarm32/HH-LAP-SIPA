from tools.problem import load_instance
from tools.random_feasible_fixing import generate_random_feasible_fixing
from tools.evaluator import evaluate_solution, ObjectiveWeights


def main():
    instance_path = "Code/Teachers+Centers/inst_creator/output/problem_instance_ext_600_0.txt"
    problem = load_instance(instance_path)

    sol = generate_random_feasible_fixing(problem)

    print("Students:", problem.n_students)
    print("Companies:", problem.n_companies)
    print("Placements:", problem.n_placements)
    print("Solution valid:", sol.validate())

    weights = ObjectiveWeights(alpha=0.35, beta=0.35, gamma=0.20, delta=0.10)

    result = evaluate_solution(sol, weights)

    print("\n--- EVALUATION RESULT ---")
    print("Valid:", result["valid"])
    print("Objective value:", result["objective_value"])
    print("Components:")
    for k, v in result["components"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()