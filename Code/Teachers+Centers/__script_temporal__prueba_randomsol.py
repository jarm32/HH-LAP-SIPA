from tools.problem import load_instance
from tools.random_feasible import generate_random_feasible
from tools.solution_export import export_solution_xlsx

a = [200, 400, 600]
b = [0, 1, 2]

for elem in a:
    for elem2 in b:
        instance = f"problem_instance_ext_{elem}_{elem2}"
        problem = load_instance(f"Code/Teachers+Centers/inst_creator/output/{instance}.txt")
        sol = generate_random_feasible(problem)

        print("Complete:", sol.is_complete())
        print("Total assigned students:", sum(1 for x in sol.student_to_placement if x != -1))
        print("Company max ok:", all(sol.company_load[k] <= problem.company_max[k] for k in range(problem.n_companies)))
        print("Professor cap ok:", all(sol.professor_load[t] <= problem.prof_capacity[t] for t in range(problem.n_professors)))
        print("Company min ok:", all(sol.company_load[k] >= problem.company_min[k] for k in range(problem.n_companies)))
        print("Dependencies ok:", sol.dependencies_ok())

        export_solution_xlsx(sol, f"Code/Teachers+Centers/obsolete/outputs/random_feasible_solution_{instance}.xlsx")
        print("Exported to outputs/random_feasible_solution.xlsx")