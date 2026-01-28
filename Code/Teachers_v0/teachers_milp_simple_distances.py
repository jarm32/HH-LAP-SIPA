from ortools.linear_solver import pywraplp
from ortools.init.python import init
import time


def solve_simple_sipa_milp(problem, solver_name, mode=0, alpha=0.4, beta=0.4, gamma=0.2, time_limit=900):
    """
    Extended MILP version of SIPA including teachers (supervisors).

    Decision variable:
        x[i][j][t] = 1 if student i is assigned to placement j supervised by teacher t

    Keeps original SIPA constraints:
        - Each student assigned exactly once
        - Each placement assigned to at most one student
        - Company min/max quotas
        - Placement dependencies via delta variables

    Adds teacher constraint:
        - Teacher capacity (max number of supervised students)

    Objective:
        Maximize average utility:
            alpha * student_utility(i,j) +
            beta  * business_utility(i,j) +
            gamma * teacher_utility(j,t)

    mode:
        0: use alpha and beta as provided
        1: ignore business term (beta term)
        2: ignore student term (alpha term)

    Returns:
        (status, utility_students, utility_businesses, joint_utility, wall_time_ms)

        utility_students/businesses are the unweighted (no alpha/beta) averages as in the original code.
        joint_utility is the objective value achieved (already averaged by number_students).
    """

    t1 = time.time()

    # Load Gurobi shared library if needed (kept from original)
    if solver_name == "GUROBI":
        init.CppBridge.load_gurobi_shared_library(
            "/data/vicsana1@upvnet.upv.es/opt/gurobi1003/linux64/lib/libgurobi100.so"
        )

    solver = pywraplp.Solver.CreateSolver(solver_name)
    if solver is None:
        raise RuntimeError(f"Could not create solver '{solver_name}'. Is it installed/available in OR-Tools?")

    n_students = problem.number_students
    n_placements = problem.number_placements
    n_companies = problem.number_companies
    n_deps = problem.number_placement_dependencies
    n_teachers = getattr(problem, "number_teachers", None)

    # Define decision variables
    x = [[[solver.BoolVar(f'x_{i}_{j}_{t}') for t in range(problem.number_teachers)] for j in range(problem.number_placements)] for i in range(problem.number_students)]

    delta = [solver.BoolVar(f"delta_{k}") for k in range(n_deps)]

    # add constraints
    # 3b
    for i in range(n_students):
        c = solver.Constraint(1, 1)
        for j in range(n_placements):
            for t in range(n_teachers):
                c.SetCoefficient(x[i][j][t], 1)

    #3c
    for j in range(n_placements):
        c = solver.Constraint(0, 1)
        for i in range(n_students):
            for t in range(n_teachers):
                c.SetCoefficient(x[i][j][t], 1)

    #3d, 3e
    for k in range(n_companies):
        placement_list = problem.get_placements_for_company(k)
        M = problem.get_max_student_company(k)
        m = problem.get_min_student_company(k)
        c = solver.Constraint(m, M)
        for i in range(n_students):
            for j in placement_list:
                for t in range(n_teachers):
                    c.SetCoefficient(x[i][j][t], 1)

    #3f, 3g
    for k in range(n_deps):
        placement_list = problem.get_placement_dependencies(k)

        c1 = solver.Constraint(-solver.infinity(), 0)
        c1.SetCoefficient(delta[k], -len(placement_list))

        c2 = solver.Constraint(-solver.infinity(), 0)
        c2.SetCoefficient(delta[k], len(placement_list))

        for i in range(n_students):
            for j in placement_list:
                for t in range(n_teachers):
                    c1.SetCoefficient(x[i][j][t], 1)
                    c2.SetCoefficient(x[i][j][t], -1)

    #3h
    for t in range(n_teachers):
        cap_t = problem.get_teacher_capacity(t)
        c = solver.Constraint(0, cap_t)
        for i in range(n_students):
            for j in range(n_placements):
                c.SetCoefficient(x[i][j][t], 1)

    # Create the objective function
    if mode == 1:
        beta_eff = 0.0
        alpha_eff = alpha
    elif mode == 2:
        alpha_eff = 0.0
        beta_eff = beta
    else:
        alpha_eff = alpha
        beta_eff = beta

    o = solver.Objective()
    o.SetMaximization()

    for i in range(n_students):
        for j in range(n_placements):
            u_s = problem.get_utility_student_placement(i, j)
            u_b = problem.get_utility_placement_student(j, i)
            for t in range(n_teachers):
                u_t = problem.get_teacher_utility(j, t)
                total_u = alpha_eff * u_s + beta_eff * u_b + gamma * u_t
                o.SetCoefficient(x[i][j][t], (total_u / n_students))

    if solver_name == "GUROBI":
        solver.SetSolverSpecificParametersAsString("Threads 1")
    else:
        solver.SetNumThreads(1)

    t2 = time.time()
    print("Time model construction", t2 - t1, flush=True)
    time_left_ms = round(max((time_limit - (t2 - t1)), 0) * 1000)
    print(time_left_ms, flush=True)
    solver.set_time_limit(time_left_ms)
    status = solver.Solve()


    # Extract solution & utilities
    utility_students = 0
    utility_businesses = 0
    utility_teachers = 0
    utility_solution = 0

    if status == solver.OPTIMAL or status == solver.FEASIBLE:
        assignments_ijt = []
        for i in range(n_students):
            for j in range(n_placements):
                for t in range(n_teachers):
                    if x[i][j][t].solution_value() == 1:
                        assignments_ijt.append((i, j, t))


        # A PARTIR DE AQUÍ MALLLLLLLLLLLLLLL


        

        # Reduce to (i, j) for original utility functions
        assignments_ij = [(i, j) for (i, j, _) in assignments_ijt]

        # -------------------------
        # Utilities
        # -------------------------

        # Student & business utilities (same meaning as original model)
        utility_students, utility_businesses = problem.get_unweighted_utility(assignments_ij)

        # Teacher utility (NEW)
        for (i, j, t) in assignments_ijt:
            utility_teachers += problem.get_teacher_utility(j, t)
        utility_teachers /= n_students

        # Joint utility (explicit)
        utility_solution = (
            alpha_eff * utility_students +
            beta_eff  * utility_businesses +
            gamma     * utility_teachers
        )

        # -------------------------
        # Validity checks (adapted from original)
        # -------------------------

        # Each student assigned exactly once
        chosen_students = [i for (i, _, _) in assignments_ijt]
        assert len(chosen_students) == n_students
        assert len(set(chosen_students)) == n_students

        # Each placement assigned at most once
        chosen_placements = [j for (_, j, _) in assignments_ijt]
        assert len(set(chosen_placements)) == len(chosen_placements)

        # Company quotas
        placements_per_business = {k: 0 for k in range(n_companies)}
        for j in chosen_placements:
            k = problem.get_company_id(j)
            placements_per_business[k] += 1

        for k in range(n_companies):
            assert problem.get_min_student_company(k) <= placements_per_business[k] <= problem.get_max_student_company(k)

        # Placement dependencies
        for dep in problem.placement_dependencies_info:
            chosen = set(chosen_placements).intersection(dep)
            assert len(chosen) == 0 or len(chosen) == len(dep)

        # Teacher capacity
        load_per_teacher = {t: 0 for t in range(n_teachers)}
        for (_, _, t) in assignments_ijt:
            load_per_teacher[t] += 1

        for t in range(n_teachers):
            assert load_per_teacher[t] <= problem.get_teacher_capacity(t)

    # -------------------------
    # Return
    # -------------------------
    return (
        status,
        utility_students,
        utility_businesses,
        utility_teachers,
        utility_solution,
        solver.wall_time()
    )