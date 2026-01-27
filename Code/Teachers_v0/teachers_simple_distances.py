from ortools.linear_solver import pywraplp
from ortools.init.python import init
import time

def solve_simple_sipa_milp(problem, solver_name, mode=0, alpha=0.5, beta=0.5, gamma=0.2, time_limit=900):


    t1 = time.time()
    # Create the SCIP solver
    if solver_name == "GUROBI":
        init.CppBridge.load_gurobi_shared_library("/data/vicsana1@upvnet.upv.es/opt/gurobi1003/linux64/lib/libgurobi100.so")
    solver = pywraplp.Solver.CreateSolver(solver_name)

    # Define decision variables
    x = [[[solver.BoolVar(f'x_{i}_{j}_{t}') for t in range(problem.number_teachers)] for j in range(problem.number_placements)] for i in range(problem.number_students)]
    
    delta = [solver.BoolVar('delta_%i' % i) for i in range(problem.number_placement_dependencies)]

    # add constraints
    # 3b
    for i in range(problem.number_students):
        c = solver.Constraint(1, 1)
        for j in range(problem.number_placements):
            for t in range(problem.number_teachers):
                c.SetCoefficient(x[i][j][t], 1)
    
    #3c
    for j in range(problem.number_placements):
        c = solver.Constraint(0, 1)
        for i in range(problem.number_students):
            for t in range(problem.number_teachers):
                c.SetCoefficient(x[i][j][t], 1)

    #3d, 3e
    for b in range(problem.number_companies):
        placement_list = problem.get_placements_for_company(b)
        M = problem.get_max_student_company(b)
        m = problem.get_min_student_company(b)
        c = solver.Constraint(m, M)
        for i in range(problem.number_students):
            for t in range(problem.number_teachers):
                for j in placement_list:
                    c.SetCoefficient(x[i][j][t], 1)
    
    #3f, 3g
    for k in range(problem.number_placement_dependencies):
        placement_list = problem.get_placement_dependencies(k)
        c1 = solver.Constraint(-solver.infinity(), 0)
        c2 = solver.Constraint(-solver.infinity(), 0)
        c1.SetCoefficient(delta[k], -len(placement_list))
        c2.SetCoefficient(delta[k], len(placement_list))
        for i in range(problem.number_students):
            for t in range(problem.number_teachers):
                for j in placement_list:
                    c1.SetCoefficient(x[i][j][t], 1)
                    c2.SetCoefficient(x[i][j][t], -1)

    #3h
    for t in range(problem.number_teachers):
        c = solver.Constraint(0, problem.get_teacher_capacity(t))
        for i in range(problem.number_students):
            for j in range(problem.number_placements):
                c.SetCoefficient(x[i][j][t], 1)

    # Create the objective function
    o = solver.Objective()
    o.SetMaximization()

    for i in range(problem.number_students):
        for j in range(problem.number_placements):
            for t in range(problem.number_teachers):
                utility = (
                    alpha * problem.get_student_utility(i, j) +
                    beta  * problem.get_business_utility(i, j) +
                    gamma * problem.get_teacher_utility(j, t)
                )
                o.SetCoefficient(x[i][j][t], utility / problem.number_students)

    return