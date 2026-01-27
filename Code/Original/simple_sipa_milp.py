from ortools.linear_solver import pywraplp
from ortools.init.python import init
import time

def solve_simple_sipa_milp(problem, solver_name, mode=0, alpha=0.5, beta=0.5, time_limit=900):
    """
    Employs a MILP solver to build and solve the model proposed in the article
    Args:
        problem_data: A tuple that contains
            The list of students registers
            The list of placement registers
            The list of company registers
            The list of placement dependences
            A matrix of distances between students and placements
        solver_name: A string with the name of the solver to employ. Valid options right now are CBC, SCIP and Gurobi.
        mode: An integer whose values can be 0, 1 and 2. Overrides the information in alpha and beta. Values are:
            0 for using provided alpha and beta.
            1 for ignoring the second sum term in equation 3a
            2 for ignoring the first sum term in equation 3a
        alpha: The value for alpha in equation 3a
        beta: The value for beta in equation 3b
        time_limit: The maximum computation time for the solver expressed in seconds.
    Returns:
        A tuple with information 
            An integer with the finalization status for ORTools
            The utility for students without considering alpha
            The utility for businesses without considering beta
            The result of equation 3a
            The number of milliseconds to solve the model.
    """

    t1 = time.time()
    # Create the SCIP solver
    if solver_name == "GUROBI":
        init.CppBridge.load_gurobi_shared_library("/data/vicsana1@upvnet.upv.es/opt/gurobi1003/linux64/lib/libgurobi100.so")
    solver = pywraplp.Solver.CreateSolver(solver_name)

    
    # Define decision variables
    x = [[solver.BoolVar('y_%i_%i' % (i, j)) for j in range(problem.number_placements)] for i in range(problem.number_students)]

    delta = [solver.BoolVar('delta_%i' % i) for i in range(problem.number_placement_dependencies)]

    
    # add constraints
    # 3b
    for i in range(problem.number_students):
        c = solver.Constraint(1, 1)
        for j in range(problem.number_placements):
            c.SetCoefficient(x[i][j], 1)

    # 3c
    for j in range(problem.number_placements):
        c = solver.Constraint(0, 1)
        for i in range(problem.number_students):
            c.SetCoefficient(x[i][j], 1)

    for k in range(problem.number_companies):
        placement_list = problem.get_placements_for_company(k)
        M = problem.get_max_student_company(k)
        m = problem.get_min_student_company(k)
        c = solver.Constraint(m, M)
        for i in range(problem.number_students):
            for j in range(len(placement_list)):
                c.SetCoefficient(x[i][placement_list[j]], 1 )


    # 3f, 3g
    for k in range(problem.number_placement_dependencies):
        placement_list = problem.get_placement_dependencies(k)
        c1 = solver.Constraint(-solver.infinity(), 0)
        c1.SetCoefficient(delta[k], -len(placement_list))
        c2 = solver.Constraint(-solver.infinity(), 0)
        c2.SetCoefficient(delta[k], len(placement_list))
        for i in range(problem.number_students):
            for j in range(len(placement_list)):
                c1.SetCoefficient(x[i][placement_list[j]], 1)
                c2.SetCoefficient(x[i][placement_list[j]], -1)


    # Create the objective function
    o = solver.Objective()
    o.SetMaximization()
    for i in range(problem.number_students):
        for j in range(problem.number_placements):
            o.SetCoefficient(x[i][j], 1/problem.number_students * problem.get_utility_individual_assignment(i, j))


    if solver_name == "GUROBI":
        solver.SetSolverSpecificParametersAsString('Threads 1')
    else:
        solver.SetNumThreads(1)

    t2 = time.time()
    print("Time model construction", t2-t1, flush=True)
    time_left = round(max((time_limit - (t2-t1)), 0)*1000)
    print(time_left, flush=True)
    solver.set_time_limit(time_left)
    status = solver.Solve()

    utility_students = 0
    utility_businesses = 0 
    utility_solution = 0
    if status == solver.OPTIMAL or status == solver.FEASIBLE:

        assignments = [(i, j) for i in range(problem.number_students) for j in range(problem.number_placements) if x[i][j].solution_value()==1]

        chosen_students = [x[0] for x in assignments]
        chosen_placements = [x[1] for x in assignments]
        placements_per_business = {k: 0 for k in range(problem.number_companies)}
        for j in chosen_placements:
            k = problem.get_company_id(j)
            placements_per_business[k] = placements_per_business[k] + 1

        utility_students, utility_businesses = problem.get_unweighted_utility(assignments)
        utility_solution = problem.get_utility_solution(assignments)

        for k in range(problem.number_companies):
            d = placements_per_business[k]
            assert (d >= problem.get_min_student_company(k)) and (d <= problem.get_max_student_company(k))

        assert len(chosen_students) == problem.number_students

        for dep in problem.placement_dependencies_info:
            c = set(chosen_placements).intersection(dep)
            assert len(c) == len(dep) or len(c) == 0

    return status, utility_students, utility_businesses, utility_solution, solver.wall_time()
