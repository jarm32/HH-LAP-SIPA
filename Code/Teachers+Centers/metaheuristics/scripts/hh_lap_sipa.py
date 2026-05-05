# Heurística híbrida (HH-LAP-SIPA) que genera subconjuntos factibles de prácticas, asigna profesores mediante construcción/repair guiado
# y resuelve de forma exacta dos asignaciones estudiante-práctica mediante LAP (una maximizando tau y otra maximizando eta).
# Cada solución completa generada se valida, se evalúa según los objetivos del modelo y se registra en el Pareto externo.

# ----------------------------
# Imports
# ----------------------------
import math
import random
import time
from dataclasses import dataclass
import numpy as np
from typing import Dict, List, Optional, Sequence, Tuple

from tools.solution import Solution
from tools.multiobjective_search import register_solution_in_pareto
from metaheuristics.scripts.random_feasible_fixing import _preprocess, _choose_final_placements

from lapjv import lapjv
from scipy.optimize import linear_sum_assignment

# -----------------------------------------------------------------------------
# Selección inicial factible de prácticas P'
# -----------------------------------------------------------------------------

def generate_random_feasible_placements(problem, seed = None, max_attempts = 50):
                                       # instancia del problema, semilla, nº máximo de intentos para generar P' válido 
    """
    Genera un subconjunto P' aleatorio y factible (|P'| = n_students, cuotas por empresa y dependencias completas). 
    Reutiliza funciones ya existentes de random_feasible_fixing (heurística aleatoria), pero en lugar de construir
    una solución completa, devuelve solo las prácticas seleccionadas
    """
    # Inicialización
    rng = random.Random(seed)
    pre = _preprocess(problem)

    # Intentos de generación
    for _ in range(max_attempts):
        try:
            selected = list(_choose_final_placements(problem, pre, rng)) # Lista de índices de prácticas seleccionadas
        except ValueError:
            continue
        
        # Validación estructural de factibilidad de P' antes de intentar asignar profesores o resolver LAP
        if _selected_placements_are_structurally_feasible(problem, selected):
            return selected # Lista de índices de prácticas seleccionadas

    # Si no se encuentra un subconjunto factible después de max_attempts, se lanza una excepción
    raise ValueError(f"No feasible placement subset found after {max_attempts} attempts")


def _selected_placements_are_structurally_feasible(problem, selected_placements):
                                                  # instancia del problema, lista de índices de prácticas seleccionadas
    """
    Comprueba que P' cumple tamaño, unicidad, índices válidos, cuotas de empresa y dependencias completas.
    Devuelve True si P' es estructuralmente factible, False en caso contrario
    """
    selected = list(selected_placements)

    # Revisión de tamaño, duplicados e índices
    if len(selected) != problem.n_students:
        return False
    if len(set(selected)) != len(selected):
        return False
    if any(j < 0 or j >= problem.n_placements for j in selected):
        return False

    selected_set = set(selected)

    # Revisión de cuotas por empresa
    company_load = [0] * problem.n_companies
    for j in selected:
        company_load[int(problem.placement_company[j])] += 1 # Prácticas por empresa

    for k in range(problem.n_companies):
        if company_load[k] < int(problem.company_min[k]):
            return False
        if company_load[k] > int(problem.company_max[k]):
            return False

    # Revisión de dependencias completas
    for dep in problem.dependencies:
        if not dep:
            continue
        count = sum(1 for j in dep if j in selected_set)
        if 0 < count < len(dep):
            return False

    return True # P' es estructuralmente factible


# -----------------------------------------------------------------------------
# Asignación práctica-profesor mediante construcción/repair guiado
# -----------------------------------------------------------------------------

@dataclass
class _SupervisionCostContext:
    """
    Matrices de distancias (costes) para poder estimar el coste 
    incremental de asignar una práctica a un profesor
    """

    center_company: np.ndarray # Distancia entre el centro educativo del profesor y la empresa
    company_company: np.ndarray # Distancia entre empresas

def assign_professors_with_guided_repair(
    problem,
    selected_placements: Sequence[int],
    rng: Optional[random.Random] = None,
    lbar_weight: float = 1.0,
    sigma_weight: float = 1.0,
    normalize_supervision_dist: bool = True,
) -> Optional[Dict[int, int]]:
    """
    Asigna un profesor a cada práctica seleccionada de P'.

    No se resuelve mediante LAP: un profesor puede supervisar varias prácticas.
    La construcción elige, para cada práctica, el profesor con capacidad disponible
    que menor incremento estimado produce en los objetivos de supervisión.

    Devuelve:
        dict {placement_j: professor_t} si se logra una asignación factible;
        None en caso contrario.
    """
    selected = list(selected_placements)
    rng = rng or random.Random()

    if len(selected) > int(np.sum(problem.prof_capacity)):
        return None

    context = _build_supervision_cost_context(problem, normalize_supervision_dist)

    # Orden aleatorio para evitar que la construcción esté totalmente determinada
    # por el orden de índices de las prácticas.
    order = selected[:]
    rng.shuffle(order)

    professor_assignment: Dict[int, int] = {}
    placements_by_professor: List[List[int]] = [[] for _ in range(problem.n_professors)]
    professor_load = [0] * problem.n_professors

    lbar_by_professor = [0.0] * problem.n_professors
    sigma_sum = _sigma_sum_for_loads(problem, professor_load)

    for j in order:
        candidates = [
            t
            for t in range(problem.n_professors)
            if professor_load[t] < int(problem.prof_capacity[t])
        ]

        if not candidates:
            # Con las restricciones actuales no debería ocurrir si la capacidad total
            # es suficiente, pero se deja como salvaguarda de factibilidad.
            return None

        best_cost = float("inf")
        best_candidates: List[Tuple[int, float, float]] = []  # (profesor, nuevo_lbar, nuevo_sigma)

        for t in candidates:
            current_lbar = lbar_by_professor[t]
            new_lbar = _lbar_for_professor(
                problem=problem,
                context=context,
                professor=t,
                placements=placements_by_professor[t] + [j],
            )

            new_loads = professor_load[:]
            new_loads[t] += 1
            new_sigma_sum = _sigma_sum_for_loads(problem, new_loads)

            incremental_cost = (
                lbar_weight * (new_lbar - current_lbar)
                + sigma_weight * (new_sigma_sum - sigma_sum)
            )

            if incremental_cost < best_cost - 1e-12:
                best_cost = incremental_cost
                best_candidates = [(t, new_lbar, new_sigma_sum)]
            elif abs(incremental_cost - best_cost) <= 1e-12:
                best_candidates.append((t, new_lbar, new_sigma_sum))

        chosen_t, chosen_lbar, chosen_sigma = rng.choice(best_candidates)

        professor_assignment[j] = chosen_t
        placements_by_professor[chosen_t].append(j)
        professor_load[chosen_t] += 1
        lbar_by_professor[chosen_t] = chosen_lbar
        sigma_sum = chosen_sigma

    if not _professor_assignment_is_feasible(problem, selected, professor_assignment):
        return None

    return professor_assignment


def _professor_assignment_is_feasible(
    problem,
    selected_placements: Sequence[int],
    professor_assignment: Dict[int, int],
) -> bool:
    """Valida que toda práctica de P' tenga profesor y que no se supere Ct."""
    load = [0] * problem.n_professors

    for j in selected_placements:
        if j not in professor_assignment:
            return False
        t = professor_assignment[j]
        if t < 0 or t >= problem.n_professors:
            return False
        load[t] += 1
        if load[t] > int(problem.prof_capacity[t]):
            return False

    return True


def _build_supervision_cost_context(problem, normalize_supervision_dist: bool) -> _SupervisionCostContext:
    """Prepara matrices de distancia para estimar costes de supervisión."""
    center_company = np.asarray(problem.center_company_dist, dtype=np.float64).copy()
    company_company = np.asarray(problem.company_company_dist, dtype=np.float64).copy()

    if normalize_supervision_dist:
        dmin = float(min(center_company.min(), company_company.min()))
        dmax = float(max(center_company.max(), company_company.max()))
        if dmax > dmin:
            center_company = (center_company - dmin) / (dmax - dmin)
            company_company = (company_company - dmin) / (dmax - dmin)
        else:
            center_company = np.zeros_like(center_company, dtype=np.float64)
            company_company = np.zeros_like(company_company, dtype=np.float64)

    return _SupervisionCostContext(center_company=center_company, company_company=company_company)


def _lbar_for_professor(
    problem,
    context: _SupervisionCostContext,
    professor: int,
    placements: Sequence[int],
) -> float:
    """Calcula Lbar_t para un profesor y un conjunto de prácticas."""
    supervised = list(placements)
    nt = len(supervised)
    if nt == 0:
        return 0.0

    center = int(problem.prof_center[professor])
    companies = [int(problem.placement_company[j]) for j in supervised]

    def dist(a: int, b: int) -> float:
        # Nodo 0 = centro del profesor; nodos 1..nt = empresas de las prácticas.
        if a == 0 and b == 0:
            return 0.0
        if a == 0:
            return float(context.center_company[center, companies[b - 1]])
        if b == 0:
            return float(context.center_company[center, companies[a - 1]])
        return float(context.company_company[companies[a - 1], companies[b - 1]])

    lt = _prim_mst_length(num_nodes=nt + 1, dist_fn=dist)
    return float(lt / nt)


def _prim_mst_length(num_nodes: int, dist_fn) -> float:
    """Longitud del MST mediante Prim sobre un grafo completo implícito."""
    in_mst = [False] * num_nodes
    min_edge = [float("inf")] * num_nodes
    min_edge[0] = 0.0
    total = 0.0

    for _ in range(num_nodes):
        u = -1
        best = float("inf")
        for v in range(num_nodes):
            if not in_mst[v] and min_edge[v] < best:
                best = min_edge[v]
                u = v

        if u == -1:
            break

        in_mst[u] = True
        total += best

        for v in range(num_nodes):
            if not in_mst[v]:
                w = dist_fn(u, v)
                if w < min_edge[v]:
                    min_edge[v] = w

    return float(total)


def _sigma_sum_for_loads(problem, professor_load: Sequence[int]) -> float:
    """Calcula sum_e sigma_e a partir de cargas de profesores."""
    profs_by_center = [[] for _ in range(problem.n_centers)]
    for t in range(problem.n_professors):
        e = int(problem.prof_center[t])
        profs_by_center[e].append(t)

    sigma_sum = 0.0
    for profs in profs_by_center:
        if not profs:
            continue

        proportions = []
        for t in profs:
            cap = int(problem.prof_capacity[t])
            proportions.append((professor_load[t] / cap) if cap > 0 else 0.0)

        mean = sum(proportions) / len(proportions)
        var = sum((x - mean) ** 2 for x in proportions) / len(proportions)
        sigma_sum += math.sqrt(var)

    return float(sigma_sum)


# -----------------------------------------------------------------------------
# Matrices de beneficio estudiante-práctica
# -----------------------------------------------------------------------------

def build_tau_matrix(problem, selected_placements: Sequence[int], normalize_student_dist: bool = True) -> np.ndarray:
    """Construye la matriz Tau[i][col] = tau_ij para j en selected_placements."""
    selected = list(selected_placements)
    dist = np.asarray(problem.student_company_dist, dtype=np.float64)
    dist_norm = _minmax_normalize_rows(dist) if normalize_student_dist else dist

    phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)[selected]
    theta = np.asarray(problem.student_pref, dtype=np.float64)
    companies = np.asarray(problem.placement_company, dtype=np.int64)[selected]

    pref_match = theta @ phi.T
    dij = dist_norm[:, companies]

    w_dist = np.asarray(problem.student_w_distance, dtype=np.float64)[:, None]
    w_dev = np.asarray(problem.student_w_dev, dtype=np.float64)[:, None]

    tau_matrix = w_dist * (1.0 - dij) + w_dev * pref_match
    return np.asarray(tau_matrix, dtype=np.float64)


def build_eta_matrix(problem, selected_placements: Sequence[int]) -> np.ndarray:
    """Construye la matriz Eta[i][col] = eta_ij para j en selected_placements."""
    selected = list(selected_placements)
    phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)[selected]
    psi = np.asarray(problem.student_dev, dtype=np.float64)

    eta_matrix = psi @ phi.T
    return np.asarray(eta_matrix, dtype=np.float64)


def _minmax_normalize_rows(a: np.ndarray) -> np.ndarray:
    """Normalización min-max por fila. Si una fila es constante, devuelve 0."""
    a = np.asarray(a, dtype=np.float64)
    mins = a.min(axis=1, keepdims=True)
    maxs = a.max(axis=1, keepdims=True)
    denom = maxs - mins

    out = np.zeros_like(a, dtype=np.float64)
    mask = denom[:, 0] > 1e-12
    out[mask] = (a[mask] - mins[mask]) / denom[mask]
    return out


# -----------------------------------------------------------------------------
# Resolución LAP
# -----------------------------------------------------------------------------

def solve_lapjv_max(benefit_matrix: np.ndarray, solver: str = "lapjv") -> List[int]:
    """
    Resuelve un LAP de maximización.

    Devuelve una lista row_to_col donde row_to_col[i] es la columna asignada al
    estudiante i.
    """
    benefits = np.asarray(benefit_matrix, dtype=np.float64)

    if benefits.ndim != 2 or benefits.shape[0] != benefits.shape[1]:
        raise ValueError(f"LAP matrix must be square. Got shape {benefits.shape}")
    if not np.all(np.isfinite(benefits)):
        raise ValueError("LAP benefit matrix contains non-finite values")

    if solver == "scipy":
        return _solve_lap_with_scipy(benefits)

    if solver != "lapjv":
        raise ValueError(f"Unknown LAP solver: {solver}")

    try:
        cost_matrix = -benefits
        row_ind, _, _ = lapjv(cost_matrix)
        row_to_col = [int(c) for c in row_ind]

        if len(row_to_col) != benefits.shape[0]:
            raise ValueError("lapjv returned an assignment with unexpected length")
        if len(set(row_to_col)) != len(row_to_col):
            raise ValueError("lapjv returned a non-bijective assignment")

        return row_to_col

    except Exception:
        return _solve_lap_with_scipy(benefits)


def _solve_lap_with_scipy(benefits: np.ndarray) -> List[int]:
    """Fallback con scipy.optimize.linear_sum_assignment."""
    row_ind, col_ind = linear_sum_assignment(benefits, maximize=True)

    row_to_col = [-1] * benefits.shape[0]
    for r, c in zip(row_ind, col_ind):
        row_to_col[int(r)] = int(c)

    if any(c == -1 for c in row_to_col):
        raise ValueError("scipy returned an incomplete LAP assignment")

    return row_to_col


# -----------------------------------------------------------------------------
# Construcción de Solution a partir de P', profesores y LAP
# -----------------------------------------------------------------------------

def build_solution_from_lap_assignment(
    problem,
    selected_placements: Sequence[int],
    professor_assignment: Dict[int, int],
    lap_assignment: Sequence[int],
) -> Optional[Solution]:
    """
    Construye una Solution completa combinando:
    - P'
    - asignación práctica-profesor
    - asignación estudiante-práctica devuelta por LAP
    """
    selected = list(selected_placements)
    assignment = list(lap_assignment)

    if len(selected) != problem.n_students:
        return None
    if len(assignment) != problem.n_students:
        return None
    if len(set(assignment)) != len(assignment):
        return None
    if any(c < 0 or c >= len(selected) for c in assignment):
        return None

    sol = Solution(problem)

    try:
        for student, col in enumerate(assignment):
            placement = selected[col]
            professor = professor_assignment[placement]
            sol.assign(student, placement, professor)
    except (KeyError, ValueError):
        return None

    if not sol.validate():
        return None

    return sol


# -----------------------------------------------------------------------------
# Ejecución HH-LAP-SIPA
# -----------------------------------------------------------------------------

def run_hh_lap_sipa(
    problem,
    weights,
    time_limit_seconds: float = 300.0,
    max_iterations: Optional[int] = None,
    max_pareto_size: Optional[int] = None,
    base_seed: Optional[int] = None,
    placement_max_attempts: int = 50,
    lap_solver: str = "lapjv",
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    professor_lbar_weight: float = 1.0,
    professor_sigma_weight: float = 1.0,
    verbose: bool = True,
) -> Dict[str, object]:
    """
    Ejecuta la heurística HH-LAP-SIPA.

    Devuelve:
        {
            "pareto_set": [...],
            "stats": {...}
        }
    """
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")
    if max_iterations is not None and max_iterations <= 0:
        raise ValueError("max_iterations must be > 0 when provided")

    # La evaluación escalar auxiliar valida los pesos dentro de register_solution_in_pareto,
    # pero validarlos aquí permite fallar pronto.
    if hasattr(weights, "validate"):
        weights.validate()

    start = time.time()
    pareto_set = []

    iteration = 0
    generated_subsets = 0
    professor_assignment_failures = 0
    lap_tau_solutions = 0
    lap_eta_solutions = 0
    feasible_solutions = 0
    inserted_into_pareto = 0
    invalid_solutions = 0
    generation_failures = 0

    while True:
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break
        if max_iterations is not None and iteration >= max_iterations:
            break

        seed = None if base_seed is None else base_seed + iteration
        rng = random.Random(seed)
        iteration += 1

        try:
            selected_placements = generate_random_feasible_placements(
                problem=problem,
                seed=seed,
                max_attempts=placement_max_attempts,
            )
            generated_subsets += 1
        except Exception:
            generation_failures += 1
            continue

        professor_assignment = assign_professors_with_guided_repair(
            problem=problem,
            selected_placements=selected_placements,
            rng=rng,
            lbar_weight=professor_lbar_weight,
            sigma_weight=professor_sigma_weight,
            normalize_supervision_dist=normalize_supervision_dist,
        )

        if professor_assignment is None:
            professor_assignment_failures += 1
            continue

        # -------------------- Solución tau --------------------
        try:
            tau_matrix = build_tau_matrix(
                problem=problem,
                selected_placements=selected_placements,
                normalize_student_dist=normalize_student_dist,
            )
            assignment_tau = solve_lapjv_max(tau_matrix, solver=lap_solver)
            sol_tau = build_solution_from_lap_assignment(
                problem=problem,
                selected_placements=selected_placements,
                professor_assignment=professor_assignment,
                lap_assignment=assignment_tau,
            )
        except Exception:
            sol_tau = None

        if sol_tau is not None and sol_tau.validate():
            reg = register_solution_in_pareto(
                sol=sol_tau,
                pareto_set=pareto_set,
                iteration=iteration,
                seed=seed,
                weights=weights,
                max_pareto_size=max_pareto_size,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
            )
            if reg["valid"]:
                feasible_solutions += 1
                lap_tau_solutions += 1
                pareto_set = reg["pareto_set"]
                if reg["was_inserted"]:
                    inserted_into_pareto += 1
            else:
                invalid_solutions += 1
        else:
            invalid_solutions += 1

        # -------------------- Solución eta --------------------
        try:
            eta_matrix = build_eta_matrix(
                problem=problem,
                selected_placements=selected_placements,
            )
            assignment_eta = solve_lapjv_max(eta_matrix, solver=lap_solver)
            sol_eta = build_solution_from_lap_assignment(
                problem=problem,
                selected_placements=selected_placements,
                professor_assignment=professor_assignment,
                lap_assignment=assignment_eta,
            )
        except Exception:
            sol_eta = None

        if sol_eta is not None and sol_eta.validate():
            reg = register_solution_in_pareto(
                sol=sol_eta,
                pareto_set=pareto_set,
                iteration=iteration,
                seed=seed,
                weights=weights,
                max_pareto_size=max_pareto_size,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
            )
            if reg["valid"]:
                feasible_solutions += 1
                lap_eta_solutions += 1
                pareto_set = reg["pareto_set"]
                if reg["was_inserted"]:
                    inserted_into_pareto += 1
            else:
                invalid_solutions += 1
        else:
            invalid_solutions += 1

        if verbose and iteration % 10 == 0:
            print(
                f"[it={iteration}] "
                f"subsets={generated_subsets} feasible={feasible_solutions} "
                f"prof_fail={professor_assignment_failures} pareto_size={len(pareto_set)}"
            )

    total_time = time.time() - start

    return {
        "pareto_set": pareto_set,
        "stats": {
            "iterations": iteration,
            "generated_subsets": generated_subsets,
            "professor_assignment_failures": professor_assignment_failures,
            "lap_tau_solutions": lap_tau_solutions,
            "lap_eta_solutions": lap_eta_solutions,
            "feasible_solutions": feasible_solutions,
            "inserted_into_pareto": inserted_into_pareto,
            "pareto_size": len(pareto_set),
            "elapsed_seconds": total_time,
            "generation_failures": generation_failures,
            "invalid_solutions": invalid_solutions,
            "lap_solver": lap_solver,
            "time_limit_seconds": time_limit_seconds,
            "max_iterations": max_iterations,
        },
    }
