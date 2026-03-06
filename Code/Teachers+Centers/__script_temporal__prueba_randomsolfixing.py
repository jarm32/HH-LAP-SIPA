from tools.problem import load_instance
from tools.random_feasible_fixing import generate_random_feasible_fixing
from tools.solution_export import export_solution_xlsx

a = [200, 400, 600]
b = [0, 1, 2]

for elem in a:
    for elem2 in b:
        instance = f"problem_instance_ext_{elem}_{elem2}"
        problem = load_instance(f"Code/Teachers+Centers/inst_creator/output/{instance}.txt")
        try:
            sol = generate_random_feasible_fixing(problem)
        except ValueError as e:
            print(f"[{instance}] FAILED: {e}")
            continue

        print(f"\n--- {instance} ---")
        print("Complete:", sol.is_complete())
        print("Total assigned students:", sum(1 for x in sol.student_to_placement if x != -1))
        print("Company max ok:", all(sol.company_load[k] <= problem.company_max[k] for k in range(problem.n_companies)))
        print("Professor cap ok:", all(sol.professor_load[t] <= problem.prof_capacity[t] for t in range(problem.n_professors)))
        print("Company min ok:", all(sol.company_load[k] >= problem.company_min[k] for k in range(problem.n_companies)))
        print("Dependencies ok:", sol.dependencies_ok())
        print("Validate:", sol.validate())

        out_path = f"Code/Teachers+Centers/obsolete/outputs/random_feasible_fixing_solution_{instance}.xlsx"
        export_solution_xlsx(sol, out_path)
        print(f"Exported to {out_path}")