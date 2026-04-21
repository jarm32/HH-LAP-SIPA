# Algoritmo GRASP multiobjetivo baseline para SIPA modificado.
# Implementa:
# - constructivo greedy-randomized sobre student_to_placement
# - RCL por umbral relativo
# - búsqueda local por swap entre dos estudiantes (first improvement)
# - registro en Pareto externo de la solución final mejorada
# - reconstrucción de profesores reutilizando _assign_professors_with_repair

# --------------------------------------------------
# Librerías
# --------------------------------------------------
import random
import time
from itertools import combinations

import numpy as np

from metaheuristics.scripts.random_feasible_fixing import _assign_professors_with_repair
from tools.evaluator import evaluate_solution_scalar, ObjectiveWeights
from tools.multiobjective_search import register_solution_in_pareto
from tools.solution import Solution


# --------------------------------------------------
# Utilidades internas
# --------------------------------------------------

def _minmax_normalize_rows(a: np.ndarray) -> np.ndarray:
    """
    Normaliza cada fila a [0,1]. Si una fila es constante, la deja a 0.
    """
    mins = a.min(axis=1, keepdims=True)
    maxs = a.max(axis=1, keepdims=True)
    denom = maxs - mins

    out = np.zeros_like(a, dtype=np.float64)
    mask = denom[:, 0] > 1e-12
    out[mask] = (a[mask] - mins[mask]) / denom[mask]
    return out


def _precompute_greedy_matrix(problem, normalize_student_dist: bool = True):
    """
    Precalcula para cada par (estudiante i, plaza j):
      - tau_ij
      - eta_ij
      - g_ij = 0.5 * tau_ij + 0.5 * eta_ij

    Devuelve:
      tau_matrix: [n_students, n_placements]
      eta_matrix: [n_students, n_placements]
      g_matrix:   [n_students, n_placements]
    """
    # Datos base
    placement_company = np.asarray(problem.placement_company, dtype=np.int64)          # [P]
    Phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)                   # [P, C]
    Theta = np.asarray(problem.student_pref, dtype=np.float64)                         # [S, C]
    Psi = np.asarray(problem.student_dev, dtype=np.float64)                            # [S, C]
    w_dist = np.asarray(problem.student_w_distance, dtype=np.float64)[:, None]         # [S, 1]
    w_dev = np.asarray(problem.student_w_dev, dtype=np.float64)[:, None]               # [S, 1]

    # Distancia estudiante -> empresa de la plaza
    dist = np.asarray(problem.student_company_dist, dtype=np.float64)                  # [S, B]
    dist_norm = _minmax_normalize_rows(dist) if normalize_student_dist else dist       # [S, B]
    dist_by_placement = dist_norm[:, placement_company]                                # [S, P]

    # Productos competencia-preferencia y competencia-desarrollo
    # pref_match[i, j] = Theta_i · Phi_j
    # comp_match[i, j] = Psi_i   · Phi_j
    pref_match = Theta @ Phi.T                                                         # [S, P]
    comp_match = Psi @ Phi.T                                                           # [S, P]

    tau_matrix = w_dist * (1.0 - dist_by_placement) + w_dev * pref_match               # [S, P]
    eta_matrix = comp_match                                                            # [S, P]
    g_matrix = 0.5 * tau_matrix + 0.5 * eta_matrix                                     # [S, P]

    return tau_matrix, eta_matrix, g_matrix


def _preprocess_dependencies(problem):
    """
    Preprocesa dependencias para:
    - saber si una plaza pertenece a algún bloque
    - mapear plaza -> bloque
    - conocer tamaños de bloque
    """
    placement_to_block = [-1] * problem.n_placements
    dep_blocks = []

    for b, dep in enumerate(problem.dependencies):
        block = list(dep)
        dep_blocks.append(block)
        for j in block:
            placement_to_block[j] = b

    return {
        "placement_to_block": placement_to_block,  # j -> id bloque o -1
        "dep_blocks": dep_blocks,                  # lista de bloques
    }


def _copy_solution(sol: Solution) -> Solution:
    """
    Copia manual de una solución.
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
    Borra la parte de asignación plaza -> profesor.
    """
    sol.placement_to_professor = [-1] * sol.problem.n_placements
    sol.professor_load = [0] * sol.problem.n_professors


def _build_solution_from_assignment_vector(problem, assignments, rng: random.Random):
    """
    Reconstruye una Solution completa desde student_to_placement.
    Devuelve None si no consigue una solución válida.
    """
    # Validaciones básicas
    if len(assignments) != problem.n_students:
        return None

    if any(j < 0 or j >= problem.n_placements for j in assignments):
        return None

    if len(set(assignments)) != len(assignments):
        return None

    sol = Solution(problem)

    # Cargar student -> placement
    for i, j in enumerate(assignments):
        sol.student_to_placement[i] = j
        sol.placement_filled[j] = True
        k = problem.placement_company[j]
        sol.company_load[k] += 1

    # Cuotas empresa
    for k in range(problem.n_companies):
        if sol.company_load[k] < problem.company_min[k]:
            return None
        if sol.company_load[k] > problem.company_max[k]:
            return None

    # Dependencias
    if not sol.dependencies_ok():
        return None

    # Profesores
    _reset_professor_assignment(sol)
    ok = _assign_professors_with_repair(problem, sol, rng)
    if not ok:
        return None

    if not sol.validate():
        return None

    return sol


def _remaining_min_demand(problem, company_load):
    """
    Suma de mínimos pendientes por cubrir.
    """
    total = 0
    for k in range(problem.n_companies):
        total += max(int(problem.company_min[k]) - int(company_load[k]), 0)
    return total


def _is_candidate_locally_feasible(
    problem,
    j: int,
    company_load,
    used_placements,
    remaining_students_after: int,
    dep_data,
    current_open_block
):
    """
    Filtro local de factibilidad para una plaza j.

    Controla:
    - plaza no usada
    - no superar máximos de empresa
    - si hay un bloque abierto, solo tomar plazas de ese bloque
    - si se abre un nuevo bloque de dependencia, que pueda completarse
    - que sigan siendo alcanzables los mínimos por empresa
    """
    if used_placements[j]:
        return False

    placement_to_block = dep_data["placement_to_block"]
    dep_blocks = dep_data["dep_blocks"]

    k = int(problem.placement_company[j])

    # Máximo empresa
    if company_load[k] + 1 > int(problem.company_max[k]):
        return False

    # Restricción de bloque abierto: si existe, hay que completarlo antes de seguir
    block_id = placement_to_block[j]
    if current_open_block is not None and block_id != current_open_block:
        return False

    # Si se abre un bloque nuevo, debe poder completarse
    if current_open_block is None and block_id != -1:
        block_size = len(dep_blocks[block_id])

        # Al elegir una plaza del bloque, deben quedar suficientes estudiantes
        # para terminar el resto del bloque de forma contigua
        if remaining_students_after < (block_size - 1):
            return False

        # La empresa del bloque debe soportar todas las plazas del bloque
        if company_load[k] + block_size > int(problem.company_max[k]):
            return False

    # Comprobar que tras elegir j siguen siendo alcanzables los mínimos
    company_load_tmp = list(company_load)
    company_load_tmp[k] += 1
    if _remaining_min_demand(problem, company_load_tmp) > remaining_students_after:
        return False

    return True


def _compute_rcl(candidate_pairs, g_matrix, alpha_rcl: float):
    """
    Construye la RCL a partir de candidatas factibles.

    candidate_pairs: lista de tuplas (i, j)
    """
    if not candidate_pairs:
        return []

    scores = [float(g_matrix[i, j]) for i, j in candidate_pairs]
    g_max = max(scores)
    g_min = min(scores)
    threshold = g_max - alpha_rcl * (g_max - g_min)

    rcl = [(i, j) for (i, j), s in zip(candidate_pairs, scores) if s >= threshold]
    return rcl


# --------------------------------------------------
# Constructivo GRASP
# --------------------------------------------------

def construct_grasp_solution(
    problem,
    alpha_rcl: float = 0.3,
    seed=None,
    normalize_student_dist: bool = True,
    max_attempts: int = 50,
    deadline=None,
):
    """
    Construye una solución factible mediante un constructivo greedy-randomized.
    Reintenta varias veces si una trayectoria constructiva no termina en solución válida.
    """
    if not (0.0 <= alpha_rcl <= 1.0):
        raise ValueError(f"alpha_rcl must be in [0,1], got {alpha_rcl}")

    rng = random.Random(seed)
    _, _, g_matrix = _precompute_greedy_matrix(problem, normalize_student_dist=normalize_student_dist)
    dep_data = _preprocess_dependencies(problem)

    placement_to_block = dep_data["placement_to_block"]
    dep_blocks = dep_data["dep_blocks"]

    for _ in range(max_attempts):
        if deadline is not None and time.time() >= deadline:
            break

        assignments = [-1] * problem.n_students
        used_placements = [False] * problem.n_placements
        company_load = [0] * problem.n_companies
        unassigned_students = list(range(problem.n_students))
        rng.shuffle(unassigned_students)

        # Bloque de dependencia abierto que debe completarse contiguamente
        current_open_block = None
        remaining_in_open_block = set()

        success = True

        while unassigned_students:
            if deadline is not None and time.time() >= deadline:
                success = False
                break

            # Si hay un bloque abierto, solo se puede elegir dentro de él
            if current_open_block is not None:
                candidate_placements = list(remaining_in_open_block)
            else:
                candidate_placements = [j for j in range(problem.n_placements) if not used_placements[j]]

            remaining_students_after = len(unassigned_students) - 1

            candidate_pairs = []
            for i in unassigned_students:
                for j in candidate_placements:
                    if _is_candidate_locally_feasible(
                        problem=problem,
                        j=j,
                        company_load=company_load,
                        used_placements=used_placements,
                        remaining_students_after=remaining_students_after,
                        dep_data=dep_data,
                        current_open_block=current_open_block
                    ):
                        candidate_pairs.append((i, j))

            if not candidate_pairs:
                success = False
                break

            # RCL y elección aleatoria
            rcl = _compute_rcl(candidate_pairs, g_matrix, alpha_rcl=alpha_rcl)
            if not rcl:
                success = False
                break

            i_sel, j_sel = rng.choice(rcl)

            # Aplicar la asignación
            assignments[i_sel] = j_sel
            used_placements[j_sel] = True
            k = int(problem.placement_company[j_sel])
            company_load[k] += 1
            unassigned_students.remove(i_sel)

            # Gestión de dependencias
            block_id = placement_to_block[j_sel]
            if current_open_block is None and block_id != -1:
                current_open_block = block_id
                remaining_in_open_block = set(dep_blocks[block_id])

            if current_open_block is not None and j_sel in remaining_in_open_block:
                remaining_in_open_block.remove(j_sel)
                if not remaining_in_open_block:
                    current_open_block = None
                    remaining_in_open_block = set()

        if not success:
            continue

        # Reconstrucción completa de la solución
        sol = _build_solution_from_assignment_vector(problem, assignments, rng)
        if sol is not None and sol.validate():
            return sol

    raise ValueError(f"Failed to construct a feasible GRASP solution after {max_attempts} attempts")


# --------------------------------------------------
# Búsqueda local
# --------------------------------------------------

def local_search_swap_first_improvement(
    initial_sol: Solution,
    weights: ObjectiveWeights,
    seed=None,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    deadline=None,
):
    """
    Búsqueda local por swap entre dos estudiantes.
    Estrategia: first improvement.
    Acepta un vecino si:
    - sigue siendo válido
    - mejora el objective_value escalar auxiliar
    """
    rng = random.Random(seed)
    current_sol = _copy_solution(initial_sol)

    current_eval = evaluate_solution_scalar(
        current_sol,
        weights,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )
    if not current_eval.get("valid", False):
        return current_sol, 0

    current_obj = float(current_eval["objective_value"])
    improvements = 0

    while True:
        if deadline is not None and time.time() >= deadline:
            break

        improved = False
        students = list(range(current_sol.problem.n_students))
        pairs = list(combinations(students, 2))
        rng.shuffle(pairs)

        current_assignments = list(current_sol.student_to_placement)

        for i, j in pairs:
            if deadline is not None and time.time() >= deadline:
                break

            # Swap
            neighbor_assignments = list(current_assignments)
            neighbor_assignments[i], neighbor_assignments[j] = neighbor_assignments[j], neighbor_assignments[i]

            neighbor_sol = _build_solution_from_assignment_vector(current_sol.problem, neighbor_assignments, rng)
            if neighbor_sol is None:
                continue

            neighbor_eval = evaluate_solution_scalar(
                neighbor_sol,
                weights,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
            )
            if not neighbor_eval.get("valid", False):
                continue

            neighbor_obj = float(neighbor_eval["objective_value"])

            # First improvement
            if neighbor_obj > current_obj + 1e-12:
                current_sol = neighbor_sol
                current_obj = neighbor_obj
                improvements += 1
                improved = True
                break

        if not improved:
            break

    return current_sol, improvements


# --------------------------------------------------
# Ejecución principal GRASP
# --------------------------------------------------

def run_grasp(
    problem,
    weights,
    alpha_rcl: float = 0.3,
    time_limit_seconds: float = 60,
    max_iterations=None,
    max_pareto_size=None,
    base_seed=None,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    constructive_max_attempts: int = 50,
    verbose: bool = True,
):
    """
    Ejecuta GRASP:
      1. Constructivo greedy-randomized
      2. Búsqueda local por swap
      3. Registro en Pareto externo de la solución final mejorada

    Devuelve:
      {
        "pareto_set": ...,
        "stats": ...
      }
    """
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")

    if not (0.0 <= alpha_rcl <= 1.0):
        raise ValueError(f"alpha_rcl must be in [0,1], got {alpha_rcl}")

    weights.validate()

    start = time.time()
    deadline = start + time_limit_seconds

    iteration = 0
    generated = 0
    feasible = 0
    failures = 0
    inserted = 0
    local_improvements_total = 0
    pareto_set = []

    while True:
        now = time.time()
        if now >= deadline:
            break
        if max_iterations is not None and iteration >= max_iterations:
            break

        seed = None if base_seed is None else base_seed + iteration
        iteration += 1
        generated += 1

        try:
            # Constructivo
            constructed_sol = construct_grasp_solution(
                problem=problem,
                alpha_rcl=alpha_rcl,
                seed=seed,
                normalize_student_dist=normalize_student_dist,
                max_attempts=constructive_max_attempts,
                deadline=deadline,
            )

            # Búsqueda local
            ls_seed = None if seed is None else seed + 1000000
            improved_sol, n_improvements = local_search_swap_first_improvement(
                initial_sol=constructed_sol,
                weights=weights,
                seed=ls_seed,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
                deadline=deadline,
            )

            if not improved_sol.validate():
                failures += 1
                continue

            feasible += 1
            local_improvements_total += n_improvements

            # Registrar solo la solución final mejorada
            reg = register_solution_in_pareto(
                sol=improved_sol,
                pareto_set=pareto_set,
                iteration=iteration,
                seed=seed,
                weights=weights,
                max_pareto_size=max_pareto_size,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
            )

            if not reg["valid"]:
                failures += 1
                continue

            pareto_set = reg["pareto_set"]
            if reg["was_inserted"]:
                inserted += 1

        except Exception:
            failures += 1
            continue

        if verbose and iteration % 10 == 0:
            print(
                f"[it={iteration}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)} local_improvements={local_improvements_total}"
            )

    total_time = time.time() - start

    return {
        "pareto_set": pareto_set,
        "stats": {
            "iterations": iteration,
            "generated": generated,
            "feasible": feasible,
            "failures": failures,
            "inserted_into_pareto": inserted,
            "pareto_size": len(pareto_set),
            "elapsed_seconds": total_time,
            "alpha_rcl": alpha_rcl,
            "local_improvements_total": local_improvements_total,
        },
    }