from tools.problem import load_instance
from tools.random_feasible import generate_random_feasible

problem = load_instance("Code/Teachers+Centers/inst_creator/output/problem_instance_ext_600_0.txt")
sol = generate_random_feasible(problem, seed=123)

print("Complete:", sol.is_complete())
print("Total assigned students:", sum(1 for x in sol.student_to_placement if x != -1))
print("Company max ok:", all(sol.company_load[k] <= problem.company_max[k] for k in range(problem.n_companies)))
print("Professor cap ok:", all(sol.professor_load[t] <= problem.prof_capacity[t] for t in range(problem.n_professors)))
print("Company min ok:", all(sol.company_load[k] >= problem.company_min[k] for k in range(problem.n_companies)))