# Algoritmo genético multiobjetivo (NSGA-III) que genera y evoluciona soluciones factibles del problema, aplicando
# cruce, mutación y repair, y evaluándolas según los objetivos del modelo

# ----------------------------
# Imports
# ----------------------------
import copy
import random
import time
from typing import List, Optional
from deap import base, creator, tools

from metaheuristics.scripts.random_feasible_fixing import generate_random_feasible_fixing, _assign_professors_with_repair
from tools.evaluator import ObjectiveWeights, evaluate_solution_multi
from tools.multiobjective_search import register_solution_in_pareto
from tools.solution import Solution


# ----------------------------
# Configuración DEAP
# ----------------------------

def _ensure_deap_types():
    """
    DEAP necesita que se le especifique cómo es una solución (individuo) 
    y cómo se mide su calidad (fitness). Esta función comprueba si estos 
    tipos ya existen y los crea en caso contrario
    """
    # Creación del tipo de fitness multiobjetivo
    if not hasattr(creator, "FitnessSIPAMulti"):
        creator.create(
            "FitnessSIPAMulti",               # nombre del tipo de fitness
            base.Fitness,                     # clase base de DEAP que gestiona la evaluación
            weights=(1.0, 1.0, -1.0, -1.0)    # max tau, max eta, min lbar, min sigma
        )

    # Creación del tipo de individuo --> lista con el fitness definido arriba
    if not hasattr(creator, "IndividualSIPA"):
        creator.create(
            "IndividualSIPA",                 # nombre del nuevo tipo de individuo       
            list,                             # estructura del individuo (lista de genes)
            fitness=creator.FitnessSIPAMulti  # tipo de fitness asociado a cada individuo
        )


# --------------------------------------------------------
# Utilidades básicas Solution <-> Individual
# --------------------------------------------------------

def solution_to_individual(sol: Solution):
    """
    Convierte una Solution a individuo DEAP.
    """
    ind = creator.IndividualSIPA(list(sol.student_to_placement))
    ind.cached_solution = _copy_solution(sol)
    ind.cached_multi_eval = None
    return ind


def _copy_solution(sol: Solution) -> Solution:
    """
    Copia ligera y segura de un objeto Solution.
    """
    new_sol = Solution(sol.problem)
    new_sol.student_to_placement = list(sol.student_to_placement)
    new_sol.placement_to_professor = list(sol.placement_to_professor)
    new_sol.company_load = list(sol.company_load)
    new_sol.professor_load = list(sol.professor_load)
    new_sol.placement_filled = list(sol.placement_filled)
    return new_sol


def _reset_professor_assignment(sol: Solution):
    """
    Borra la capa plaza -> profesor para reconstruirla.
    """
    sol.placement_to_professor = [-1] * sol.problem.n_placements
    sol.professor_load = [0] * sol.problem.n_professors


def _build_solution_from_assignment_vector(problem, assignments: List[int], rng: random.Random) -> Optional[Solution]:
    """
    Construye una Solution a partir de un vector student_to_placement ya completo.

    Esta función asume que:
    - hay una plaza por estudiante,
    - no hay plazas repetidas,
    - las plazas son válidas.

    Después reconstruye la capa plaza -> profesor.
    """
    if len(assignments) != problem.n_students:
        return None

    if any(j < 0 or j >= problem.n_placements for j in assignments):
        return None

    if len(set(assignments)) != len(assignments):
        return None

    sol = Solution(problem)

    for i, j in enumerate(assignments):
        sol.student_to_placement[i] = j
        sol.placement_filled[j] = True
        k = problem.placement_company[j]
        sol.company_load[k] += 1

    # Validación básica de la capa estudiante -> plaza
    for k in range(problem.n_companies):
        if sol.company_load[k] < problem.company_min[k]:
            return None
        if sol.company_load[k] > problem.company_max[k]:
            return None

    if not sol.dependencies_ok():
        return None

    # Reconstrucción de profesores
    _reset_professor_assignment(sol)

    ok = _assign_professors_with_repair(problem, sol, rng)
    if not ok:
        return None

    if not sol.validate():
        return None

    return sol



#############################################################


# ============================================================
# Utilidades para repair
# ============================================================

def _dependency_placement_set(problem):
    dep_set = set()
    for block in problem.dependencies:
        for j in block:
            dep_set.add(j)
    return dep_set


def _placement_owner(assignments: List[int]):
    """
    Devuelve un diccionario placement -> student.
    """
    return {j: i for i, j in enumerate(assignments)}


def _try_align_assignments_with_template(problem, desired: List[int], template_sol: Solution, rng: random.Random) -> List[int]:
    """
    Parte de una solución factible base y trata de incorporar información del individuo
    sin romper factibilidad estructural.

    Estrategia simple y robusta:
    - si la plaza deseada ya está en la solución base, intercambia estudiantes;
    - si no está en la solución base, solo permite sustituciones seguras:
      plaza actual y plaza deseada deben pertenecer a la misma empresa y no estar
      en dependencias.
    """
    assignments = list(template_sol.student_to_placement)
    owner = _placement_owner(assignments)
    dep_set = _dependency_placement_set(problem)

    order = list(range(problem.n_students))
    rng.shuffle(order)

    for i in order:
        j_des = desired[i]

        if not isinstance(j_des, int):
            continue
        if j_des < 0 or j_des >= problem.n_placements:
            continue

        j_cur = assignments[i]
        if j_des == j_cur:
            continue

        # Caso 1: la plaza deseada ya forma parte del conjunto actual -> swap
        if j_des in owner:
            other = owner[j_des]
            if other == i:
                continue

            assignments[i], assignments[other] = assignments[other], assignments[i]
            owner[assignments[i]] = i
            owner[assignments[other]] = other
            continue

        # Caso 2: sustitución segura dentro de misma empresa y fuera de dependencias
        same_company = problem.placement_company[j_cur] == problem.placement_company[j_des]
        both_nondep = (j_cur not in dep_set) and (j_des not in dep_set)

        if same_company and both_nondep:
            del owner[j_cur]
            assignments[i] = j_des
            owner[j_des] = i

    return assignments


def repair_individual(problem, individual, rng: random.Random, template_sol: Optional[Solution] = None, seed: Optional[int] = None) -> Solution:
    """
    Repair robusto y simple.

    Idea:
    1. parte de una solución factible base;
    2. intenta incorporar la información del individuo;
    3. reconstruye profesores;
    4. si falla, cae a una solución factible generada de nuevo.
    """
    desired = []
    for x in individual:
        try:
            desired.append(int(x))
        except Exception:
            desired.append(-1)

    candidate_templates = []

    if template_sol is not None:
        candidate_templates.append(_copy_solution(template_sol))

    # Añadimos algunas soluciones factibles auxiliares
    for extra in range(3):
        local_seed = None if seed is None else seed + 1000 + extra
        base_sol = generate_random_feasible_fixing(problem, seed=local_seed)
        candidate_templates.append(base_sol)

    for base_sol in candidate_templates:
        assignments = _try_align_assignments_with_template(problem, desired, base_sol, rng)
        repaired = _build_solution_from_assignment_vector(problem, assignments, rng)
        if repaired is not None and repaired.validate():
            return repaired

    # Último recurso: devolver una solución factible nueva
    fallback_seed = None if seed is None else seed + 999999
    return generate_random_feasible_fixing(problem, seed=fallback_seed)


# ============================================================
# Inicialización
# ============================================================

def _init_individual(problem, seed=None):
    """
    Genera un individuo factible inicial a partir del generador existente.
    """
    sol = generate_random_feasible_fixing(problem, seed=seed)
    return solution_to_individual(sol)


def _init_population(problem, population_size: int, base_seed: Optional[int] = None):
    """
    Genera la población inicial factible.
    """
    population = []
    for i in range(population_size):
        seed = None if base_seed is None else base_seed + i
        population.append(_init_individual(problem, seed=seed))
    return population


# ============================================================
# Operadores genéticos
# ============================================================

def crossover_simple(ind1, ind2, problem, rng: random.Random, seed: Optional[int] = None):
    """
    Cruce simple por máscara aleatoria de estudiantes.
    Después repara ambos descendientes.
    """
    parent1_sol = getattr(ind1, "cached_solution", None)
    parent2_sol = getattr(ind2, "cached_solution", None)

    child1_genes = list(ind1)
    child2_genes = list(ind2)

    for i in range(len(child1_genes)):
        if rng.random() < 0.5:
            child1_genes[i], child2_genes[i] = child2_genes[i], child1_genes[i]

    child1_sol = repair_individual(
        problem=problem,
        individual=child1_genes,
        rng=rng,
        template_sol=parent1_sol,
        seed=seed,
    )
    child2_sol = repair_individual(
        problem=problem,
        individual=child2_genes,
        rng=rng,
        template_sol=parent2_sol,
        seed=None if seed is None else seed + 1,
    )

    ind1[:] = list(child1_sol.student_to_placement)
    ind2[:] = list(child2_sol.student_to_placement)

    ind1.cached_solution = child1_sol
    ind2.cached_solution = child2_sol
    ind1.cached_multi_eval = None
    ind2.cached_multi_eval = None

    if ind1.fitness.valid:
        del ind1.fitness.values
    if ind2.fitness.valid:
        del ind2.fitness.values

    return ind1, ind2


def mutate_simple(individual, problem, rng: random.Random, seed: Optional[int] = None):
    """
    Mutación simple:
    - o bien intercambia dos estudiantes,
    - o bien cambia la plaza deseada de un estudiante por una plaza aleatoria.

    Después aplica repair.
    """
    mutated = list(individual)

    if len(mutated) >= 2 and rng.random() < 0.5:
        i, j = rng.sample(range(len(mutated)), 2)
        mutated[i], mutated[j] = mutated[j], mutated[i]
    else:
        i = rng.randrange(len(mutated))
        mutated[i] = rng.randrange(problem.n_placements)

    template_sol = getattr(individual, "cached_solution", None)

    repaired_sol = repair_individual(
        problem=problem,
        individual=mutated,
        rng=rng,
        template_sol=template_sol,
        seed=seed,
    )

    individual[:] = list(repaired_sol.student_to_placement)
    individual.cached_solution = repaired_sol
    individual.cached_multi_eval = None

    if individual.fitness.valid:
        del individual.fitness.values

    return (individual,)


# ============================================================
# Evaluación y Pareto externo
# ============================================================

def _evaluate_individual(individual, normalize_student_dist=True, normalize_supervision_dist=True):
    """
    Evalúa el individuo a partir de su Solution cacheada.
    """
    sol = getattr(individual, "cached_solution", None)
    if sol is None:
        raise ValueError("Individual has no cached_solution. Repair/init should build it first.")

    multi_eval = evaluate_solution_multi(
        sol,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )

    if not multi_eval.get("valid", False):
        # Penalización extrema; en principio no debería ocurrir si repair funciona
        individual.cached_multi_eval = multi_eval
        return (-1e18, -1e18, 1e18, 1e18)

    c = multi_eval["components"]
    values = (
        float(c["tau_sum"]),
        float(c["eta_sum"]),
        float(c["lbar_sum"]),
        float(c["sigma_sum"]),
    )
    individual.cached_multi_eval = multi_eval
    return values


def _register_individual_in_global_pareto(
    individual,
    pareto_set,
    iteration,
    seed,
    weights,
    max_pareto_size,
    normalize_student_dist,
    normalize_supervision_dist,
):
    """
    Registra el individuo ya evaluado en el Pareto global externo.
    """
    sol = individual.cached_solution
    multi_eval = getattr(individual, "cached_multi_eval", None)

    reg = register_solution_in_pareto(
        sol=sol,
        pareto_set=pareto_set,
        iteration=iteration,
        seed=seed,
        weights=weights,
        max_pareto_size=max_pareto_size,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
        precomputed_multi_eval=multi_eval,
        precomputed_scalar_eval=None,
    )

    return reg


# ============================================================
# Selección de padres
# ============================================================

def _select_parents(population, k, rng: random.Random):
    """
    Selección de padres mediante torneo binario basado en frentes no dominados.

    Criterio:
    - mejor frente -> gana
    - empate en frente -> desempate aleatorio

    Devuelve k copias de individuos seleccionados para reproducirse.
    """
    if not population:
        return []

    # Construir ranking por frentes
    fronts = tools.sortNondominated(population, len(population), first_front_only=False)

    rank = {}
    for r, front in enumerate(fronts):
        for ind in front:
            rank[id(ind)] = r

    selected = []

    for _ in range(k):
        if len(population) == 1:
            winner = population[0]
        else:
            a, b = rng.sample(population, 2)

            ra = rank[id(a)]
            rb = rank[id(b)]

            if ra < rb:
                winner = a
            elif rb < ra:
                winner = b
            else:
                winner = a if rng.random() < 0.5 else b

        selected.append(copy.deepcopy(winner))

    return selected


# ============================================================
# Toolbox DEAP
# ============================================================

def build_deap_toolbox(
    problem,
    rng: random.Random,
    normalize_student_dist=True,
    normalize_supervision_dist=True,
    ref_points_p=5,
):
    """
    Construye y devuelve el toolbox de DEAP.
    """
    _ensure_deap_types()

    toolbox = base.Toolbox()

    ref_points = tools.uniform_reference_points(nobj=4, p=ref_points_p)

    toolbox.register(
        "evaluate",
        _evaluate_individual,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )

    toolbox.register(
        "mate",
        crossover_simple,
        problem=problem,
        rng=rng,
    )

    toolbox.register(
        "mutate",
        mutate_simple,
        problem=problem,
        rng=rng,
    )

    toolbox.register(
        "select_survivors",
        tools.selNSGA3,
        ref_points=ref_points,
    )

    return toolbox, ref_points


# ============================================================
# Bucle principal NSGA-III
# ============================================================

def run_nsga3(
    problem,
    weights: ObjectiveWeights,
    population_size=50,
    offspring_size=50,
    cx_prob=0.8,
    mut_prob=0.2,
    time_limit_seconds=60,
    max_generations=None,
    max_pareto_size=None,
    base_seed=None,
    normalize_student_dist=True,
    normalize_supervision_dist=True,
    ref_points_p=5,
    verbose=True,
):
    """
    Ejecuta el algoritmo NSGA-III sobre el problema dado.

    Devuelve:
    - pareto_set externo
    - stats
    - population final
    """
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")
    if population_size <= 0:
        raise ValueError("population_size must be > 0")
    if offspring_size <= 0:
        raise ValueError("offspring_size must be > 0")

    weights.validate()

    rng = random.Random(base_seed)

    toolbox, ref_points = build_deap_toolbox(
        problem=problem,
        rng=rng,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
        ref_points_p=ref_points_p,
    )

    start = time.time()

    pareto_set = []
    population = _init_population(problem, population_size, base_seed=base_seed)

    generations = 0
    generated = 0
    feasible = 0
    failures = 0
    inserted = 0

    # Evaluación inicial + Pareto externo
    for idx, ind in enumerate(population):
        values = toolbox.evaluate(ind)
        if values[0] <= -1e17:
            failures += 1
            continue

        ind.fitness.values = values
        generated += 1
        feasible += 1

        reg = _register_individual_in_global_pareto(
            individual=ind,
            pareto_set=pareto_set,
            iteration=0,
            seed=None if base_seed is None else base_seed + idx,
            weights=weights,
            max_pareto_size=max_pareto_size,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )

        pareto_set = reg["pareto_set"]
        if reg["was_inserted"]:
            inserted += 1

    while True:
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break
        if max_generations is not None and generations >= max_generations:
            break

        generations += 1

        # Selección de padres
        parents = _select_parents(population, offspring_size, rng)

        # Variación
        offspring = parents

        for i in range(0, len(offspring) - 1, 2):
            if rng.random() < cx_prob:
                seed = None if base_seed is None else base_seed + generations * 100000 + i
                toolbox.mate(offspring[i], offspring[i + 1], seed=seed)

        for i in range(len(offspring)):
            if rng.random() < mut_prob:
                seed = None if base_seed is None else base_seed + generations * 200000 + i
                toolbox.mutate(offspring[i], seed=seed)

        # Evaluación de descendencia + Pareto externo
        for i, ind in enumerate(offspring):
            if not ind.fitness.valid:
                values = toolbox.evaluate(ind)

                if values[0] <= -1e17:
                    failures += 1
                    continue

                ind.fitness.values = values
                generated += 1
                feasible += 1

                reg = _register_individual_in_global_pareto(
                    individual=ind,
                    pareto_set=pareto_set,
                    iteration=generations,
                    seed=None if base_seed is None else base_seed + generations * 1000 + i,
                    weights=weights,
                    max_pareto_size=max_pareto_size,
                    normalize_student_dist=normalize_student_dist,
                    normalize_supervision_dist=normalize_supervision_dist,
                )

                pareto_set = reg["pareto_set"]
                if reg["was_inserted"]:
                    inserted += 1

        # Reemplazo ambiental NSGA-III
        combined = population + offspring
        population = toolbox.select_survivors(combined, population_size)

        if verbose and generations % 5 == 0:
            print(
                f"[gen={generations}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)}"
            )

    total_time = time.time() - start

    return {
        "pareto_set": pareto_set,
        "population": population,
        "stats": {
            "generations": generations,
            "generated": generated,
            "feasible": feasible,
            "failures": failures,
            "inserted_into_pareto": inserted,
            "pareto_size": len(pareto_set),
            "elapsed_seconds": total_time,
            "population_size": population_size,
            "offspring_size": offspring_size,
            "reference_points": len(ref_points),
        },
    }