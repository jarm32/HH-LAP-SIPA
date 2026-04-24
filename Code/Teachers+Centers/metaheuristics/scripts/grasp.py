# Implementación de un GRASP multiobjetivo para el problema SIPA mediante:
# - Constructivo greedy-randomized sobre student_to_placement.
# - RCL por umbral relativo.
# - Búsqueda local por swap entre dos estudiantes (first improvement).
# - Reconstrucción de profesores reutilizando _assign_professors_with_repair.
# - Registro en Pareto externo de la solución final mejorada.


# --------------------------------------------------
# Librerías
# --------------------------------------------------
import random
import time
from itertools import combinations
import numpy as np

from metaheuristics.scripts.random_feasible_fixing import _assign_professors_with_repair, generate_random_feasible_fixing
from tools.evaluator import evaluate_solution_scalar
from tools.multiobjective_search import register_solution_in_pareto
from tools.solution import Solution


# --------------------------------------------------
# Utilidades internas
# --------------------------------------------------

def _minmax_normalize_rows(a): # matriz numpy de n filas y m columnas
    """
    Normaliza la matriz fila a fila a [0,1]. Si una fila es constante, la deja a 0
    """
    # Inicialización (cálculo de mínimos y máximos por fila)
    mins = a.min(axis=1, keepdims=True)
    maxs = a.max(axis=1, keepdims=True)
    denom = maxs - mins
    out = np.zeros_like(a, dtype=np.float64)

    mask = denom[:, 0] > 1e-12 # Evitar división por cero
    out[mask] = (a[mask] - mins[mask]) / denom[mask] # Normalización
    return out # matriz inicial normalizada fila a fila (por estudiante) en rango [0,1]


def _precompute_greedy_matrix(problem, normalize_student_dist = True): 
                             # instancia del problema, booleano para normalizar distancias estudiante-empresa
    """
    Precalcula para cada par (estudiante i, plaza j) las utilidades 
    (tau_ij, eta_ij, g_ij = 0.5 * tau_ij + 0.5 * eta_ij) para acelerar el constructivo (greedy-randomized)
    """
    # Extracción de datos (datos del problema a arrays)
    placement_company = np.asarray(problem.placement_company, dtype=np.int64)          # [P]
    Phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)                   # [P, C]
    Theta = np.asarray(problem.student_pref, dtype=np.float64)                         # [S, C]
    Psi = np.asarray(problem.student_dev, dtype=np.float64)                            # [S, C]
    w_dist = np.asarray(problem.student_w_distance, dtype=np.float64)[:, None]         # [S, 1]
    w_dev = np.asarray(problem.student_w_dev, dtype=np.float64)[:, None]               # [S, 1]

    # Distancia estudiante -> empresa cada plaza
    dist = np.asarray(problem.student_company_dist, dtype=np.float64)                  # [S, B]
    dist_norm = _minmax_normalize_rows(dist) if normalize_student_dist else dist       # [S, B]
    dist_by_placement = dist_norm[:, placement_company]                                # [S, P]

    # Afinidades estudiante-plaza por preferencias y desviaciones
    pref_match = Theta @ Phi.T # pref_match[i, j] = Theta_i · Phi_j                    # [S, P]
    comp_match = Psi @ Phi.T # comp_match[i, j] = Psi_i · Phi_j                        # [S, P]

    # Construcción de objetivos greedy (tau, eta) y su combinación g para cada par (i,j)
    tau_matrix = w_dist * (1.0 - dist_by_placement) + w_dev * pref_match               # [S, P] --> utilidad del estudiante por la plaza según distancia y preferencias
    eta_matrix = comp_match                                                            # [S, P] --> utilidad de la empresa por el estudiante según compatibilidad
    g_matrix = 0.5 * tau_matrix + 0.5 * eta_matrix                                     # [S, P]

    return tau_matrix, eta_matrix, g_matrix # matrices de tamaño [n_students, n_placements] con los valores precalculados (tau, eta, g) para cada par (i,j)


def _preprocess_dependencies(problem): #instancia del problema
    """
    Preprocesa dependencias para: saber si una plaza pertenece a algún bloque, 
    mapear plaza -> bloque y conocer tamaños de bloque
    """
    # Inicialización
    placement_to_block = [-1] * problem.n_placements
    dep_blocks = []

    # Procesamiento de dependencias
    for b, dep in enumerate(problem.dependencies):
        block = list(dep)
        dep_blocks.append(block)
        for j in block:
            placement_to_block[j] = b

    return {
        "placement_to_block": placement_to_block,  # j -> id bloque o -1
        "dep_blocks": dep_blocks,                  # lista de bloques
    } # diccionario con mapping plaza -> bloque y lista de bloques (bloque = lista de plazas)


def _copy_solution(sol): # solución del problema
    """
    Duplica la solución para no modificar la original
    """
    new_sol = Solution(sol.problem)
    new_sol.student_to_placement = list(sol.student_to_placement)
    new_sol.placement_to_professor = list(sol.placement_to_professor)
    new_sol.company_load = list(sol.company_load)
    new_sol.professor_load = list(sol.professor_load)
    new_sol.placement_filled = list(sol.placement_filled)
    return new_sol # copia independiente de la solución


def _reset_professor_assignment(sol): # solución del problema
    """
    Elimina la asignación plaza -> profesor para recalcularla
    """
    sol.placement_to_professor = [-1] * sol.problem.n_placements
    sol.professor_load = [0] * sol.problem.n_professors


def _build_solution_from_assignment_vector(problem, assignments, rng):
                                          # instancia del problema, vector student_to_placement, generador aleatorio
    """
    Reconstruye una Solution completa y válida desde student_to_placement -->
    asigna los profesores y verifica todas las restricciones
    
    Devuelve None si no consigue una solución válida
    """
    # Validaciones básicas
    if len(assignments) != problem.n_students: # tamaño correcto
        return None

    if any(j < 0 or j >= problem.n_placements for j in assignments): # plazas válidas
        return None

    if len(set(assignments)) != len(assignments): # sin duplicados
        return None

    # Inicialización de la solución
    sol = Solution(problem)

    # Cargar student -> placement
    for i, j in enumerate(assignments):
        sol.student_to_placement[i] = j
        sol.placement_filled[j] = True
        k = problem.placement_company[j]
        sol.company_load[k] += 1

    # Comprobar cuotas de empresa
    for k in range(problem.n_companies):
        if sol.company_load[k] < problem.company_min[k]:
            return None
        if sol.company_load[k] > problem.company_max[k]:
            return None

    # Comprobar dependencias
    if not sol.dependencies_ok():
        return None

    # Asignación de profesores
    _reset_professor_assignment(sol)
    ok = _assign_professors_with_repair(problem, sol, rng)
    if not ok:
        return None

    # Validación final
    if not sol.validate():
        return None

    return sol # reconstrucción completa de la solución a partir del vector de asignaciones student_to_placement, con validaciones y asignación de profesores


def _is_candidate_locally_feasible(problem, j, company_load, used_placements, remaining_students_after, dep_data, current_open_block):
                                   # instancia del problema, plaza candidata, carga actual por empresa, vector de plazas usadas, 
                                   # nº de estudiantes que quedarían sin asignar tras elegir esta plaza, datos de dependencias (preprocesado), bloque de dependencia abierto (si hay)
    """
    Determina si una plaza j puede elegirse en el constructivo sin romper factibilidad: True si es factible, False si no lo es
    """
    # Plaza no usada
    if used_placements[j]:
        return False

    # Inicializar datos
    placement_to_block = dep_data["placement_to_block"]
    dep_blocks = dep_data["dep_blocks"]
    k = int(problem.placement_company[j])

    # No superar el máximo de empresa
    if company_load[k] + 1 > int(problem.company_max[k]):
        return False

    # Restricción de bloque de dependencia abierto (si existe, hay que completarlo antes de seguir)
    block_id = placement_to_block[j]
    if current_open_block is not None and block_id != current_open_block:
        return False

    # Si se abre un bloque nuevo, debe poder completarse
    if current_open_block is None and block_id != -1:
        block_size = len(dep_blocks[block_id])

        # Al elegir una plaza del bloque, deben quedar suficientes estudiantes para terminar el resto del bloque
        if remaining_students_after < (block_size - 1):
            return False

        # La empresa del bloque debe soportar todas las plazas del bloque
        if company_load[k] + block_size > int(problem.company_max[k]):
            return False

    return True


def _compute_rcl(candidate_pairs, g_matrix, alpha_rcl):
                # lista de tuplas (i, j) factibles, matriz g precalculada (g(i,j)), parámetro de control de la RCL
    """
    Selecciona las mejores candidatas según el score greedy, pero permitiendo cierta aleatoriedad controlada por el parámetro alpha_rcl.
    alpha_rcl ∈ [0,1]; menor --> más greedy, mayor --> más aleatorio
    """
    if not candidate_pairs: # Caso trivial
        return []

    # Calcular scores y umbral
    scores = [float(g_matrix[i, j]) for i, j in candidate_pairs] # g(i,j) para cada par candidato
    g_max, g_min = max(scores), min(scores)
    threshold = g_max - alpha_rcl * (g_max - g_min)

    rcl = [(i, j) for (i, j), s in zip(candidate_pairs, scores) if s >= threshold]
    return rcl # lista de tuplas (i, j) que entran en la RCL


def _balanced_scalar_score(eval_data, problem, weights):
                          # datos de evaluación de la solución, instancia del problema, pesos para la combinación escalar
    """
    Calcula un score escalar normalizado para equilibrar la influencia de los cuatro objetivos
    durante la búsqueda local.

    Normaliza:
    - tau_sum y eta_sum por número de estudiantes
    - lbar_sum por número de profesores
    - sigma_sum por número de centros, si existe; si no, se deja sin normalizar
    """
    n_students = max(int(problem.n_students), 1)
    n_professors = max(int(problem.n_professors), 1)
    n_centers = max(int(problem.n_centers), 1)

    components = eval_data["components"]

    tau_norm = float(components["tau_sum"]) / n_students
    eta_norm = float(components["eta_sum"]) / n_students
    lbar_norm = float(components["lbar_sum"]) / n_professors
    sigma_norm = float(components["sigma_sum"]) / n_centers

    return (
        weights.alpha * tau_norm
        + weights.beta * eta_norm
        - weights.gamma * lbar_norm
        - weights.delta * sigma_norm
    ) # score escalar combinado, con normalización para equilibrar la influencia de cada objetivo durante la búsqueda local


# --------------------------------------------------
# Constructivo GRASP
# --------------------------------------------------

def construct_grasp_solution(problem, alpha_rcl = 0.3, seed = None, normalize_student_dist = True, max_attempts = 50, deadline = None):
                             # instancia del problema, parámetro de control de la RCL, semilla, booleano para normalizar distancias estudiante-empresa, 
                             # nº máximo de intentos para construir una solución factible, tiempo límite absoluto (prioritario sobre max_attempts)
    """
    Construye una solución factible (estudiantes, plazas, profesores) mediante un proceso greedy-randomized. 
    Si una construcción falla, reintenta desde cero hasta encontrar una solución válida, agotar tiempo o intentos
    """
    # Validación e inicialización general (acelerar constructivo)
    if not (0.0 <= alpha_rcl <= 1.0): 
        raise ValueError(f"alpha_rcl must be in [0,1], got {alpha_rcl}") # Validar rango de alpha_rcl

    rng = random.Random(seed) # Generador aleatorio para decisiones del constructivo
    _, _, g_matrix = _precompute_greedy_matrix(problem, normalize_student_dist=normalize_student_dist) # Precalcular matriz g para acelerar el constructivo
    dep_data = _preprocess_dependencies(problem) # Preprocesar dependencias

    placement_to_block = dep_data["placement_to_block"]
    dep_blocks = dep_data["dep_blocks"]

    # Reintentos completos de construcción
    for _ in range(max_attempts):
        if deadline is not None and time.time() >= deadline:
            break
        
        # Estado inicial de un intento
        assignments = [-1] * problem.n_students
        used_placements = [False] * problem.n_placements
        company_load = [0] * problem.n_companies
        unassigned_students = list(range(problem.n_students))
        rng.shuffle(unassigned_students)

        # Estado auxiliar para dependencias
        current_open_block = None
        remaining_in_open_block = set()

        success = True

        # Bucle principal de construcción --> Cada vuelta de este bucle añade una nueva asignación estudiante–plaza a la solución
        while unassigned_students:
            if deadline is not None and time.time() >= deadline:
                success = False
                break

            # Determinar qué plazas se pueden considerar en este momento
            if current_open_block is not None:
                candidate_placements = list(remaining_in_open_block) # Si hay un bloque de dependencia abierto, solo se puede elegir entre las plazas que faltan de ese bloque
            else:
                candidate_placements = [j for j in range(problem.n_placements) if not used_placements[j]] # Si no hay bloque abierto, se pueden considerar todas las plazas no usadas

            remaining_students_after = len(unassigned_students) - 1

            # Generar todas las parejas factibles (i, j)
            candidate_pairs = []
            for i in unassigned_students:
                for j in candidate_placements:
                    if _is_candidate_locally_feasible(problem=problem, j=j, company_load=company_load, used_placements=used_placements, remaining_students_after=remaining_students_after, dep_data=dep_data,
                                                      current_open_block=current_open_block): # Para cada estudiante pendiente y cada plaza candidata, comprueba si esa asignación es localmente viable
                        candidate_pairs.append((i, j))

            # Intento bloqueado porque no hay ninguna pareja localmente factible
            if not candidate_pairs:
                success = False
                break

            # Construir la RCL a partir de las parejas factibles
            rcl = _compute_rcl(candidate_pairs, g_matrix, alpha_rcl=alpha_rcl)
            if not rcl:
                success = False
                break
            
            # Elección aleatoria dentro de la RCL
            i_sel, j_sel = rng.choice(rcl)

            # Aplicar la asignación elegida (actualiza el estado de la construcción)
            assignments[i_sel] = j_sel
            used_placements[j_sel] = True
            k = int(problem.placement_company[j_sel])
            company_load[k] += 1
            unassigned_students.remove(i_sel)

            # Actualiza el estado de dependencias --> bloque nuevo = se inicializa el seguimiento de ese bloque; bloque abierto = se marca esa plaza como completada dentro del bloque; se completa un bloque = se cierra
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

        # Comprobar si el intento ha terminado con éxito --> si no, se reintenta desde cero
        if sol is not None and sol.validate():
            return sol # solución factible completa, faltándole la optimización que añade la búsqueda local

    # Fallo final tras agotar intentos
    raise ValueError(f"Failed to construct a feasible GRASP solution after {max_attempts} attempts")


# --------------------------------------------------
# Búsqueda local
# --------------------------------------------------

def local_search_swap_first_improvement(initial_sol, weights, seed = None, normalize_student_dist = True, normalize_supervision_dist = True, 
                                        deadline = None, max_neighbors_per_pass = 1000, max_local_improvements = 30):
                                       # solución sobre la que trabajar, pesos de los objetivos, semilla, booleanos para normalizar distancias estudiante-empresa y supervisión, 
                                       # tiempo límite absoluto, máximo de vecinos evaluados por pasada y máximo de mejoras aceptadas
    """
    Aplica búsqueda local basada en swap entre dos estudiantes. Explora vecinos y acepta el primero (first improvement)
    que mejora un score escalar auxiliar normalizado, ya que este proporciona una dirección clara de avance
    sin dejar que tau_sum y eta_sum dominen completamente sobre lbar_sum y sigma_sum.

    Para controlar el coste temporal, limita el número de vecinos evaluados por pasada y el número total de mejoras
    aceptadas. Así se evita que una única solución consuma todo el presupuesto temporal.

    El filtrado multiobjetivo real se delega en el Pareto externo
    """
    # Inicialización y evaluación de la solución inicial
    rng = random.Random(seed)
    current_sol = _copy_solution(initial_sol)
    current_eval = evaluate_solution_scalar(current_sol, weights, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)
    if not current_eval.get("valid", False):
        return current_sol, 0 # Si no es válida, no hace búsqueda local

    # Inicialización de variables
    current_obj = _balanced_scalar_score(current_eval, current_sol.problem, weights)
    improvements = 0

    # Bucle principal de búsqueda local
    while True: # Se repite mientras se encuentren mejoras
        # Sale si se alcanza el número máximo de mejoras aceptadas para controlar el coste temporal
        if max_local_improvements is not None and improvements >= max_local_improvements:
            break
        
        # Sale si se alcanza el límite de tiempo
        if deadline is not None and time.time() >= deadline: 
            break
            
        # Generación de vecinos (pares de estudiantes)
        improved = False
        students = list(range(current_sol.problem.n_students))
        all_pairs = list(combinations(students, 2))
        rng.shuffle(all_pairs)

        # Limitar el número de vecinos evaluados en esta pasada para reducir coste temporal
        if max_neighbors_per_pass is not None:
            pairs = all_pairs[:max_neighbors_per_pass]
        else:
            pairs = all_pairs

        # Copia de la asignación actual student_to_placement
        current_assignments = list(current_sol.student_to_placement)

        # Exploración de vecinos
        for i, j in pairs:
            # Sale si se alcanza el límite de tiempo
            if deadline is not None and time.time() >= deadline:
                break

            # Construcción del vecino: Swap
            neighbor_assignments = list(current_assignments)
            neighbor_assignments[i], neighbor_assignments[j] = neighbor_assignments[j], neighbor_assignments[i]

            # Reconstrucción de la solución
            neighbor_sol = _build_solution_from_assignment_vector(current_sol.problem, neighbor_assignments, rng)
            if neighbor_sol is None: # Si no es factible, se descarta
                continue
            
            # Evaluación del vecino para comparar con la solución actual
            neighbor_eval = evaluate_solution_scalar(neighbor_sol, weights, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)
            if not neighbor_eval.get("valid", False):
                continue

            neighbor_obj = _balanced_scalar_score(neighbor_eval, current_sol.problem, weights)

            # Criterio de aceptación: First improvement usando score normalizado
            if neighbor_obj > current_obj + 1e-12:
                # Actualización de la solución
                current_sol = neighbor_sol
                current_obj = neighbor_obj
                improvements += 1
                improved = True
                break
        
        # Fin del ciclo si no hay mejora
        if not improved:
            break

    return current_sol, improvements # tupla: (solución mejorada tras búsqueda local, número de mejoras realizadas durante la búsqueda local)


# --------------------------------------------------
# Ejecución principal GRASP
# --------------------------------------------------

def run_grasp(
    problem,                              # Instancia del problema
    weights,                              # Pesos para la evaluación escalar auxiliar
    alpha_rcl = 0.3,                      # Parámetro de la RCL
    time_limit_seconds = 60,              # Límite de tiempo
    max_iterations = None,                # Máximo de iteraciones
    max_pareto_size = None,               # Tamaño máximo opcional del Pareto
    base_seed = None,                     # Semilla base para reproducibilidad (cada iteración suma su número a esta semilla)
    normalize_student_dist = True,        # booleano para normalizar distancias estudiante-empresa
    normalize_supervision_dist = True,    # booleano para normalizar distancias profesor-plaza
    constructive_max_attempts = 5,       # Máximo de intentos del constructivo
    constructive_time_limit_seconds = 30, # Límite de tiempo para cada intento del constructivo (prioritario sobre constructive_max_attempts)
    use_random_fallback = True,           # booleano para activar un fallback aleatorio que intente generar una solución factible de forma completamente aleatoria si el constructivo falla mucho
    random_fallback_max_attempts = 50,    # Máximo de intentos del fallback aleatorio
    local_max_neighbors_per_pass = 1000,  # Máximo de vecinos evaluados por pasada de búsqueda local
    local_max_improvements = 30,          # Máximo de mejoras aceptadas por búsqueda local
    verbose = True                        # booleano para imprimir estadísticas durante la ejecución
):
    """
    Ejecuta repetidamente el esquema GRASP completo (constructivo + búsqueda local + registro en Pareto)
    hasta que se cumple el criterio de parada, acumulando además estadísticas de la ejecución
    """
    # Validaciones iniciales
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0") # Tiempo límite positivo

    if not (0.0 <= alpha_rcl <= 1.0):
        raise ValueError(f"alpha_rcl must be in [0,1], got {alpha_rcl}") # Validar rango de alpha_rcl

    weights.validate() # Pesos válidos para evaluación escalar

    # Inicialización global del tiempo, contadores y Pareto
    start = time.time()
    deadline = start + time_limit_seconds

    iteration = 0
    generated = 0
    feasible = 0
    failures = 0
    inserted = 0
    local_improvements_total = 0
    fallback_used = 0
    pareto_set = []

    # Bucle principal del GRASP (construir, mejorar, registrar)
    while True:
        # Criterios de parada
        now = time.time()
        if now >= deadline: # Tiempo
            break
        if max_iterations is not None and iteration >= max_iterations: # Iteraciones
            break
        
        # Semilla e iteración
        seed = None if base_seed is None else base_seed + iteration
        iteration += 1
        generated += 1

        try:
            # -------- Fase constructiva GRASP con límite local de tiempo --------

            # Límite de tiempo específico para cada intento
            construct_deadline = deadline
            if constructive_time_limit_seconds is not None:
                construct_deadline = min(deadline, time.time() + constructive_time_limit_seconds)

            try:
                # Intento constructivo normal
                constructed_sol = construct_grasp_solution(problem=problem, alpha_rcl=alpha_rcl, seed=seed, normalize_student_dist=normalize_student_dist,
                                                           max_attempts=constructive_max_attempts, deadline=construct_deadline)
            except Exception as e:
                constructed_sol = None
                if verbose:
                    print(f"[GRASP constructive failure] "
                          f"iteration={iteration}, seed={seed}, error={repr(e)}")


            # -------- Fallback aleatorio factible si falla el constructivo --------

            # Fallback que genera una solución factible aleatoria para no perder iteraciones
            if constructed_sol is None and use_random_fallback and time.time() < deadline:
                fallback_seed = None if seed is None else seed + 2000000

                try:
                    # Intento de fallback aleatorio
                    constructed_sol = generate_random_feasible_fixing(problem, seed=fallback_seed, max_attempts=random_fallback_max_attempts)
                    fallback_used += 1

                    if verbose:
                        print(f"[GRASP fallback used] "
                              f"iteration={iteration}, seed={fallback_seed}")

                except Exception as e:
                    constructed_sol = None
                    if verbose:
                        print(f"[GRASP fallback failure] "
                              f"iteration={iteration}, seed={fallback_seed}, error={repr(e)}")

            # Si no se obtiene solución inicial, la iteración falla
            if constructed_sol is None:
                failures += 1
                continue


            # -------- Búsqueda local --------

            # Límite de tiempo para evitar que una iteración consuma todo el tiempo
            ls_seed = None if seed is None else seed + 1000000

            # Aplicar búsqueda local con límites de vecinos evaluados y control temporal
            improved_sol, n_improvements = local_search_swap_first_improvement(initial_sol=constructed_sol, weights=weights, seed=ls_seed, normalize_student_dist=normalize_student_dist,
                                                                               normalize_supervision_dist=normalize_supervision_dist, deadline=deadline, max_neighbors_per_pass=local_max_neighbors_per_pass,
                                                                               max_local_improvements=local_max_improvements)

            # Validación de la solución mejorada
            if not improved_sol.validate():
                failures += 1
                continue

            feasible += 1
            local_improvements_total += n_improvements


            # -------- Registro en Pareto externo --------

            reg = register_solution_in_pareto(sol=improved_sol, pareto_set=pareto_set, iteration=iteration, seed=seed, weights=weights, max_pareto_size=max_pareto_size,
                                              normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

            # Si el registro no es válido, se cuenta como fallo
            if not reg["valid"]:
                failures += 1
                continue

            pareto_set = reg["pareto_set"]

            # Si la solución se ha insertado en el Pareto, se cuenta como mejora real
            if reg["was_inserted"]:
                inserted += 1

        except Exception as e:
            failures += 1
            if verbose:
                print(f"[GRASP failure] "
                     f"iteration={iteration}, seed={seed}, error={repr(e)}")
            continue

        # Salida de progreso
        if verbose and iteration % 10 == 0:
            print(f"[it={iteration}] "
                  f"generated={generated} feasible={feasible} failures={failures} "
                  f"pareto_size={len(pareto_set)} "
                  f"local_improvements={local_improvements_total} "
                  f"fallback_used={fallback_used}")

    total_time = time.time() - start

    return {"pareto_set": pareto_set,
            "stats": {
                "iterations": iteration,
                "generated": generated,
                "feasible": feasible,
                "failures": failures,
                "inserted_into_pareto": inserted,
                "fallback_used": fallback_used,
                "pareto_size": len(pareto_set),
                "elapsed_seconds": total_time,
                "alpha_rcl": alpha_rcl,
                "local_improvements_total": local_improvements_total,
                "constructive_max_attempts": constructive_max_attempts,
                "constructive_time_limit_seconds": constructive_time_limit_seconds,
                "local_max_neighbors_per_pass": local_max_neighbors_per_pass,
                "local_max_improvements": local_max_improvements,
                "use_random_fallback": use_random_fallback,
                "random_fallback_max_attempts": random_fallback_max_attempts
            }
        } # Diccionario con el conjunto Pareto final, estadísticas de ejecución y parámetros usados