# Heurística híbrida HH-LAP-SIPA v1 que genera subconjuntos factibles de prácticas, calcula cargas objetivo, agrupa prácticas en clústeres, construye varias asignaciones profesor-práctica 
# mediante clústeres + path relinking y resuelve de forma exacta dos asignaciones estudiante-práctica mediante LAP (una maximizando tau y otra maximizando eta).
# Cada solución completa generada se valida, se evalúa según los objetivos del modelo y se registra en el Pareto externo.

# ----------------------------
# Imports
# ----------------------------
import math
import random
import time
import numpy as np

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
# Cálculo previo de cargas objetivo por profesor
# -----------------------------------------------------------------------------

def compute_target_professor_loads(problem):
                                   # instancia del problema
    """
    Calcula una carga objetivo entera para cada profesor, proporcional a su capacidad máxima
    """
    # Capacidades y validación de capacidad total
    capacities = [int(c) for c in problem.prof_capacity]
    total_capacity = sum(capacities)
    n_required = int(problem.n_students)

    if total_capacity < n_required:
        raise ValueError("Total professor capacity is lower than the number of students")
    if n_required == 0:
        return [0] * problem.n_professors

    # Carga proporcional real y parte entera inicial
    ideal_loads = [(capacities[t] * n_required / total_capacity) if total_capacity > 0 else 0.0 for t in range(problem.n_professors)]
    target_loads = [min(int(math.floor(x)), capacities[t]) for t, x in enumerate(ideal_loads)]

    # Reparto de las prácticas restantes según mayor parte decimal pendiente, sin superar capacidades
    remaining = n_required - sum(target_loads)
    fractional_order = sorted(range(problem.n_professors), key=lambda t: (ideal_loads[t] - math.floor(ideal_loads[t]), capacities[t] - target_loads[t]), reverse=True)

    # Bucle de reparto controlado. Se itera tantas veces como haga falta por si algunos profesores ya están llenos.
    while remaining > 0:
        progressed = False
        for t in fractional_order:
            if remaining <= 0:
                break
            if target_loads[t] < capacities[t]:
                target_loads[t] += 1
                remaining -= 1
                progressed = True

        if not progressed:
            raise ValueError("Could not build target professor loads within professor capacities")

    return target_loads # Lista de cargas objetivo por profesor tal que sum(target_loads) = n_students y 0 <= target_loads[t] <= prof_capacity[t]


# -----------------------------------------------------------------------------
# Agrupación de prácticas por empresa y extracción de clústeres activos
# -----------------------------------------------------------------------------

def build_global_company_clusters(problem):
                                  # instancia del problema
    """
    Construye clústeres globales agrupando prácticas por empresa.
    Se descartan empresas sin prácticas
    """
    # Agrupación de todas las prácticas por empresa
    clusters_by_company = [[] for _ in range(problem.n_companies)]
    for j in range(problem.n_placements):
        k = int(problem.placement_company[j])
        clusters_by_company[k].append(j)

    return [cluster for cluster in clusters_by_company if cluster] # lista de clústeres, donde cada clúster es una lista de prácticas de la misma empresa


def build_selected_placement_clusters(problem, selected_placements, global_clusters = None):
                                     # instancia del problema, lista de prácticas seleccionadas, clústeres globales opcionales
    """
    Extrae los clústeres activos de P'. Cada clúster activo contiene las prácticas seleccionadas
    de P' que pertenecen a una misma empresa. Los clústeres se ordenan por tamaño descendente
    """
    # Si no se reciben clústeres globales ya precalculados, se construyen en este momento
    if global_clusters is None:
        global_clusters = build_global_company_clusters(problem)

    selected_set = set(selected_placements)
    active_clusters = []

    # Filtrado de prácticas seleccionadas dentro de cada clúster global
    for cluster in global_clusters:
        active = [j for j in cluster if j in selected_set]
        if active:
            active_clusters.append(active)

    # Orden por tamaño descendente para priorizar primero los clústeres más grandes
    active_clusters.sort(key=lambda c: len(c), reverse=True)

    return active_clusters # Lista de clústeres activos, cada uno con prácticas seleccionadas de P'


# -----------------------------------------------------------------------------
# Utilidades de supervisión, factibilidad y costes
# -----------------------------------------------------------------------------

def _professor_assignment_is_feasible(problem, selected_placements, professor_assignment):
                                     # instancia del problema, lista de índices de prácticas seleccionadas, diccionario de asignación práctica-profesor
    """
    Valida que toda práctica de P' tenga profesor asignado,
    y que no se supere Ct
    """
    # Inicialización de cargas por profesor
    load = [0] * problem.n_professors

    # Revisión de asignación de cada práctica seleccionada
    for j in selected_placements:
        if j not in professor_assignment:
            return False
        t = int(professor_assignment[j])
        if t < 0 or t >= problem.n_professors:
            return False
        load[t] += 1
        if load[t] > int(problem.prof_capacity[t]):
            return False

    # Si se han asignado profesores válidos a todas las prácticas seleccionadas y no se ha superado la capacidad de ningún profesor, la asignación es factible
    return True


def _loads_from_assignment(problem, selected_placements, professor_assignment):
                          # instancia del problema, prácticas seleccionadas, diccionario placement -> professor
    """
    Calcula la carga de cada profesor a partir de una asignación práctica-profesor
    """
    loads = [0] * problem.n_professors
    for j in selected_placements:
        t = int(professor_assignment[j])
        loads[t] += 1
    return loads # Lista con la carga de cada profesor

# -----------------------------------------------------------------------------
# Construcción inicial profesor-práctica por clústeres
# -----------------------------------------------------------------------------

def assign_professors_by_clusters(problem, selected_placements, clusters, target_loads, rng = None):
                                 # instancia del problema, prácticas seleccionadas, clústeres activos, cargas objetivo, generador aleatorio
    """
    Construye una asignación inicial profesor-práctica usando clústeres activos de P'.
    Intenta asignar tantas prácticas como sea posible de un mismo clúster a un mismo profesor,
    priorizando carga objetivo restante y capacidad disponible
    """
    # Inicialización y validaciones básicas
    selected = list(selected_placements)
    rng = rng or random.Random()

    if len(selected) > int(np.sum(problem.prof_capacity)):
        return None
    if len(target_loads) != problem.n_professors:
        raise ValueError("target_loads must have length n_professors")

    # Copia de clústeres pendientes, ordenados por tamaño descendente
    pending_clusters = [list(c) for c in clusters if c]
    pending_clusters.sort(key=lambda c: len(c), reverse=True)

    professor_assignment = {}
    professor_load = [0] * problem.n_professors

    # Bucle de asignación hasta que no queden clústeres pendientes
    while pending_clusters:
        pending_clusters.sort(key=lambda c: len(c), reverse=True)
        cluster = pending_clusters.pop(0)

        # Se busca un profesor con capacidad disponible
        candidates = [t for t in range(problem.n_professors) if professor_load[t] < int(problem.prof_capacity[t])]
        if not candidates:
            return None
        
        # Ordenación de candidatos (mayor carga objetivo restante y mayor capacidad libre)
        scored_candidates = []
        for t in candidates:
            cap_remaining = int(problem.prof_capacity[t]) - professor_load[t]
            target_remaining = max(int(target_loads[t]) - professor_load[t], 0)
            scored_candidates.append((target_remaining, cap_remaining, t))

        best_score = max(scored_candidates, key=lambda x: (x[0], x[1]))[:2]
        best_candidates = [t for tr, cr, t in scored_candidates if (tr, cr) == best_score]
        chosen_t = rng.choice(best_candidates)

        # Número de prácticas del clúster que se asignan al profesor elegido
        cap_remaining = int(problem.prof_capacity[chosen_t]) - professor_load[chosen_t]
        target_remaining = max(int(target_loads[chosen_t]) - professor_load[chosen_t], 0)
        desired_take = target_remaining if target_remaining > 0 else cap_remaining
        take = min(len(cluster), cap_remaining, max(1, desired_take))

        # Asignación de una parte o de todo el clúster
        assigned_now = cluster[:take]
        remaining_cluster = cluster[take:]

        for j in assigned_now:
            professor_assignment[j] = chosen_t
            professor_load[chosen_t] += 1

        # Si quedan prácticas del clúster sin asignar, se reinsertan para asignarlas a otro profesor
        if remaining_cluster:
            pending_clusters.append(remaining_cluster)

    # Validación final de la asignación profesor-práctica
    if not _professor_assignment_is_feasible(problem, selected, professor_assignment):
        return None

    return professor_assignment # Diccionario {placement_j: professor_t} usado como start_professor_assignment


# -----------------------------------------------------------------------------
# Construcción de asignación guía orientada a cargas objetivo
# -----------------------------------------------------------------------------

def build_load_balanced_professor_assignment(problem, selected_placements, target_loads, rng = None, global_clusters = None):
                                           # instancia del problema, prácticas seleccionadas, cargas objetivo, generador aleatorio, clústeres globales opcionales
    """
    Construye una asignación guía profesor-práctica orientada principalmente a alcanzar las cargas objetivo.
    La guía sirve como destino del path relinking y debe ser factible respecto a capacidades
    """
    # Inicialización y validaciones
    selected = list(selected_placements)
    rng = rng or random.Random()

    if len(selected) > int(np.sum(problem.prof_capacity)):
        return None
    if len(target_loads) != problem.n_professors:
        raise ValueError("target_loads must have length n_professors")

    # Orden controlado de prácticas: se agrupan por clústeres activos y se baraja dentro de cada clúster
    clusters = build_selected_placement_clusters(problem, selected, global_clusters=global_clusters)
    pending_placements = []
    for cluster in clusters:
        cluster_copy = list(cluster)
        rng.shuffle(cluster_copy)
        pending_placements.extend(cluster_copy)

    # Por seguridad, si alguna práctica no aparece en los clústeres activos, se añade al final
    missing = [j for j in selected if j not in set(pending_placements)]
    rng.shuffle(missing)
    pending_placements.extend(missing)

    # Construcción guiada por cargas objetivo
    professor_assignment = {}
    professor_load = [0] * problem.n_professors
    cursor = 0

    # Se priorizan profesores con mayor carga objetivo
    professor_order = list(range(problem.n_professors))
    professor_order.sort(key=lambda t: int(target_loads[t]), reverse=True)

    for t in professor_order:
        target = min(int(target_loads[t]), int(problem.prof_capacity[t]))
        while professor_load[t] < target and cursor < len(pending_placements):
            j = pending_placements[cursor]
            cursor += 1
            if j in professor_assignment:
                continue
            professor_assignment[j] = t
            professor_load[t] += 1

    # Si quedan prácticas pendientes, se asignan a profesores con capacidad disponible
    remaining = [j for j in pending_placements if j not in professor_assignment]
    for j in remaining:
        candidates = [t for t in range(problem.n_professors) if professor_load[t] < int(problem.prof_capacity[t])]
        if not candidates:
            return None
        # Se elige el profesor con más capacidad restante; empate aleatorio
        max_room = max(int(problem.prof_capacity[t]) - professor_load[t] for t in candidates)
        best_candidates = [t for t in candidates if int(problem.prof_capacity[t]) - professor_load[t] == max_room]
        chosen_t = rng.choice(best_candidates)
        professor_assignment[j] = chosen_t
        professor_load[chosen_t] += 1

    # Validación final
    if not _professor_assignment_is_feasible(problem, selected, professor_assignment):
        return None

    return professor_assignment # Diccionario {placement_j: professor_t} usado como guide_professor_assignment


# -----------------------------------------------------------------------------
# Path relinking entre asignaciones profesor-práctica
# -----------------------------------------------------------------------------

def path_relink_professor_assignments(problem, selected_placements, start_assignment, guide_assignment, max_steps = 10, rng = None):
                                    # instancia del problema, prácticas seleccionadas, asignación inicial, asignación guía, máximo de pasos, generador aleatorio
    """
    Genera una secuencia de asignaciones profesor-práctica entre start_assignment y guide_assignment.
    Solo acepta movimientos inmediatos factibles, moviendo prácticas hacia el profesor indicado por la guía
    """
    # Inicialización
    selected = list(selected_placements)
    rng = rng or random.Random()

    if not _professor_assignment_is_feasible(problem, selected, start_assignment):
        return []
    if not _professor_assignment_is_feasible(problem, selected, guide_assignment):
        return []

    current = dict(start_assignment)
    current_load = _loads_from_assignment(problem, selected, current)

    # Se guarda la asignación inicial
    assignments = [dict(current)]
    seen = {_assignment_signature(selected, current)}
    steps = 0

    # Número máximo de pasos. Si max_steps es None, se permite intentar todos los movimientos diferenciales
    limit = len(selected) if max_steps is None else int(max_steps)

    while steps < limit:
        # Prácticas cuyo profesor actual difiere del profesor guía
        diff = [j for j in selected if current[j] != guide_assignment[j]]
        if not diff:
            break

        rng.shuffle(diff)
        moved = False

        # Se intenta mover una práctica hacia el profesor marcado por la guía
        for j in diff:
            old_t = int(current[j])
            new_t = int(guide_assignment[j])

            if old_t == new_t:
                continue

            # El movimiento es factible si el profesor destino tiene capacidad disponible
            if current_load[new_t] + 1 > int(problem.prof_capacity[new_t]):
                continue

            current[j] = new_t
            current_load[old_t] -= 1
            current_load[new_t] += 1

            if _professor_assignment_is_feasible(problem, selected, current):
                sig = _assignment_signature(selected, current)
                if sig not in seen:
                    assignments.append(dict(current))
                    seen.add(sig)
                moved = True
                steps += 1
                break

            # Si por algún motivo no es factible, se deshace el movimiento
            current[j] = old_t
            current_load[old_t] += 1
            current_load[new_t] -= 1

        # Si no se puede aplicar ningún movimiento factible, termina el path relinking
        if not moved:
            break

    return assignments # Lista de asignaciones profesor-práctica factibles, incluyendo la asignación inicial


def _assignment_signature(selected_placements, professor_assignment):
                         # lista de prácticas seleccionadas, diccionario placement -> professor
    """
    Construye una firma hashable de una asignación profesor-práctica para evitar duplicados
    """
    selected_sorted = sorted(selected_placements)
    return tuple((j, int(professor_assignment[j])) for j in selected_sorted)


# -----------------------------------------------------------------------------
# Matrices de beneficio estudiante-práctica
# -----------------------------------------------------------------------------

def build_tau_matrix(problem, selected_placements, normalize_student_dist = True):
                    # instancia del problema, lista de índices de prácticas seleccionadas, booleano para saber si se normalizan las distancias entre estudiantes y empresas
    """
    Construye la matriz tau, donde cada posición representa la utilidad
    de asignar una práctica seleccionada a un estudiante
    """
    # Selección y distancias
    selected = list(selected_placements)
    dist = np.asarray(problem.student_company_dist, dtype=np.float64)
    dist_norm = _minmax_normalize_rows(dist) if normalize_student_dist else dist

    # Competencias, preferencias y empresas
    phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)[selected]
    theta = np.asarray(problem.student_pref, dtype=np.float64)
    companies = np.asarray(problem.placement_company, dtype=np.int64)[selected]

    # Cálculo de componentes de tau
    pref_match = theta @ phi.T
    dij = dist_norm[:, companies]

    # Conversión de los pesos de los estudiantes a columnas
    w_dist = np.asarray(problem.student_w_distance, dtype=np.float64)[:, None]
    w_dev = np.asarray(problem.student_w_dev, dtype=np.float64)[:, None]

    # Matriz final (CL de la distancia normalizada (dij) y el grado de coincidencia de preferencias (pref_match), ponderada por los pesos individuales de cada estudiante para cada componente) (más es mejor)
    tau_matrix = w_dist * (1.0 - dij) + w_dev * pref_match

    return np.asarray(tau_matrix, dtype=np.float64) # Matriz de beneficios Tau para cada estudiante y cada práctica seleccionada, de tamaño n_students x len(P')


def build_eta_matrix(problem, selected_placements):
                    # instancia del problema, lista de índices de prácticas seleccionadas
    """
    Construye la matriz eta, donde cada posición representa la utilidad
    para la empresa de asignar cierto estudiante a cierta práctica
    """
    # Selección, necesidades competenciales de prácticas y perfil competencial de estudiantes
    selected = list(selected_placements)
    phi = np.asarray(problem.placement_comp_needs, dtype=np.float64)[selected]
    psi = np.asarray(problem.student_dev, dtype=np.float64)

    # Matriz final (CL del grado de coincidencia entre las necesidades competenciales de la práctica y el perfil competencial del estudiante) (más es mejor)
    eta_matrix = psi @ phi.T

    return np.asarray(eta_matrix, dtype=np.float64) # Matriz de beneficios Eta para cada estudiante y cada práctica seleccionada, de tamaño n_students x len(P')


def _minmax_normalize_rows(a):
                          # Matriz a normalizar
    """
    Normaliza cada fila usando min-max. Si una fila es constante, devuelve ceros para esa fila
    """
    # Mínimos, máximos y denominador
    a = np.asarray(a, dtype=np.float64)
    mins = a.min(axis=1, keepdims=True)
    maxs = a.max(axis=1, keepdims=True)
    denom = maxs - mins

    # Normalización con cuidado de filas constantes para evitar división por cero
    out = np.zeros_like(a, dtype=np.float64)
    mask = denom[:, 0] > 1e-12
    out[mask] = (a[mask] - mins[mask]) / denom[mask]

    return out # Matriz normalizada por filas, con el mismo tamaño que la matriz de entrada


# -----------------------------------------------------------------------------
# Resolución LAP estudiante-práctica
# -----------------------------------------------------------------------------

def solve_lapjv_max(benefit_matrix, solver = "lapjv"):
                   # Matriz de beneficios para el LAP (tau o eta), elección del solver ("lapjv" o "scipy")
    """
    Resuelve un LAP de maximización. Usa lapjv como solver principal y, si se indica "scipy" o si lapjv falla,
    usa scipy.optimize.linear_sum_assignment como alternativa
    """
    # Conversión y validación de la matriz
    benefits = np.asarray(benefit_matrix, dtype=np.float64)

    if benefits.ndim != 2 or benefits.shape[0] != benefits.shape[1]:
        raise ValueError(f"LAP matrix must be square. Got shape {benefits.shape}")
    if not np.all(np.isfinite(benefits)):
        raise ValueError("LAP benefit matrix contains non-finite values")

    # Si se ha indicado explícitamente usar scipy, se salta lapjv y se va directamente a scipy
    if solver == "scipy":
        return _solve_lap_with_scipy(benefits)

    # Validación del solver indicado
    if solver != "lapjv":
        raise ValueError(f"Unknown LAP solver: {solver}")

    # Intento de resolución con lapjv, que es más rápido pero puede fallar en casos numéricos difíciles.
    try:
        # Se convierte el problema de maximización en uno de minimización para resolverlo con lapjv
        cost_matrix = -benefits

        # lapjv devuelve row_ind, col_ind (_ para obviarlo) y el coste total (_ para obviarlo). row_ind[i] es la práctica (columna) asignada a la fila i
        row_ind, _, _ = lapjv(cost_matrix)
        row_to_col = [int(c) for c in row_ind]

        # Validación de la solución devuelta por lapjv (asignación completa y bijectiva)
        if len(row_to_col) != benefits.shape[0]:
            raise ValueError("lapjv returned an assignment with unexpected length")
        if len(set(row_to_col)) != len(row_to_col):
            raise ValueError("lapjv returned a non-bijective assignment")

        return row_to_col # Lista donde row_to_col[i] indica la práctica (columna) seleccionada asignada al estudiante i

    # Si lapjv falla, se intenta resolver con scipy como alternativa más robusta pero lenta
    except Exception:
        return _solve_lap_with_scipy(benefits)


def _solve_lap_with_scipy(benefits):
                         # Matriz de beneficios para el LAP (tau o eta)
    """
    Resuelve el LAP de maximización usando SciPy.
    Se usa como fallback o cuando se seleccione explícitamente
    """
    # SciPy permite resolver directamente el LAP de maximización usando maximize=True
    row_ind, col_ind = linear_sum_assignment(benefits, maximize=True)

    # Convierte la salida de SciPy a una lista indexada por estudiante donde el valor es la práctica asignada
    row_to_col = [-1] * benefits.shape[0]
    for r, c in zip(row_ind, col_ind):
        row_to_col[int(r)] = int(c)

    # Comprueba que todos los estudiantes tengan asignación
    if any(c == -1 for c in row_to_col):
        raise ValueError("scipy returned an incomplete LAP assignment")

    return row_to_col # Lista donde row_to_col[i] indica la práctica (columna) seleccionada asignada al estudiante i


# -----------------------------------------------------------------------------
# Construcción de Solution a partir de P', profesores y LAP
# -----------------------------------------------------------------------------

def build_solution_from_lap_assignment(problem, selected_placements, professor_assignment, lap_assignment):
                                      # instancia del problema, lista de índices de prácticas seleccionadas, diccionario de asignación práctica-profesor,
                                      # lista de asignación estudiante-práctica devuelta por el LAP (cada valor es una columna de selected_placements)
    """
    Construye una solución completa estudiante-práctica-profesor. Para cada estudiante, toma la
    práctica indicada por el LAP y el profesor previamente asignado a esa práctica.

    Devuelve None si la asignación devuelta por LAP no es válida (tamaño incorrecto, índices fuera de rango,
    asignación no bijectiva) o si la solución construida no es factible
    """
    # Validación de la asignación devuelta por el LAP (tamaño, índices válidos, asignación completa y bijectiva)
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

    # Construcción de la solución completa a partir de la asignación del LAP y la asignación de profesores
    sol = Solution(problem)

    try:
        # Para cada estudiante, se asigna la práctica seleccionada por el LAP y el profesor asignado a esa práctica
        for student, col in enumerate(assignment):
            placement = selected[col]
            professor = professor_assignment[placement]
            sol.assign(student, placement, professor)
    except (KeyError, ValueError):
        return None

    # Validación de la solución construida (factibilidad completa)
    if not sol.validate():
        return None

    return sol # objeto Solution completo


# -----------------------------------------------------------------------------
# Registro de soluciones completas en el Pareto externo
# -----------------------------------------------------------------------------

def _register_completed_solution(sol, pareto_set, iteration, seed, weights, max_pareto_size, normalize_student_dist, normalize_supervision_dist):
                               # solución completa, Pareto actual, iteración, semilla, pesos auxiliares, tamaño máximo de Pareto, normalización de distancias
    """
    Valida y registra una solución completa en el Pareto externo.
    Devuelve el resultado de register_solution_in_pareto o None si la solución no es válida
    """
    # Si no se ha podido construir solución o no es válida, se descarta
    if sol is None or not sol.validate():
        return None

    # Registro común en Pareto usando la infraestructura existente
    return register_solution_in_pareto(
        sol=sol,
        pareto_set=pareto_set,
        iteration=iteration,
        seed=seed,
        weights=weights,
        max_pareto_size=max_pareto_size,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist
    )


# -----------------------------------------------------------------------------
# Ejecución HH-LAP-SIPA v1
# -----------------------------------------------------------------------------

def run_hh_lap_sipa_v1(problem, weights, time_limit_seconds = 300.0, max_iterations = None, max_pareto_size = None, base_seed = None, placement_max_attempts = 50,
                       # instancia del problema, pesos para evaluación escalar auxiliar, límite de tiempo (s), máximo de iteraciones, máximo tamaño del Pareto externo, semilla, nº máximo de intentos para generar P',
                       lap_solver = "lapjv", normalize_student_dist = True, normalize_supervision_dist = True, max_path_relinking_steps = 10, verbose = True):
                       # solver LAP, normalización distancias estudiante-empresa, normalización distancias supervisión, máximo pasos de path relinking, mensajes de progreso
    """
    Ejecuta iterativamente HH-LAP-SIPA v1 hasta que se cumple el criterio de parada.
    En cada iteración genera un P', construye varias asignaciones profesor-práctica mediante clústeres + path relinking,
    resuelve LAP tau y LAP eta una sola vez, y combina ambos LAP con cada asignación profesor-práctica generada
    """
    # Validación de parámetros de entrada
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")
    if max_iterations is not None and max_iterations <= 0:
        raise ValueError("max_iterations must be > 0 when provided")
    if max_path_relinking_steps is not None and max_path_relinking_steps <= 0:
        raise ValueError("max_path_relinking_steps must be > 0 when provided")
    if hasattr(weights, "validate"):
        weights.validate()

    # Preprocesado fijo de v1: cargas objetivo y clústeres globales
    target_loads = compute_target_professor_loads(problem)
    global_clusters = build_global_company_clusters(problem)

    # Inicialización de estructuras y estadísticas
    start = time.time()
    pareto_set = []
    iteration = 0
    generated_subsets = 0
    generation_failures = 0
    cluster_assignment_failures = 0
    guide_assignment_failures = 0
    path_relinking_runs = 0
    path_relinking_assignments = 0
    lap_tau_solutions = 0
    lap_eta_solutions = 0
    feasible_solutions = 0
    invalid_solutions = 0
    inserted_into_pareto = 0

    # Bucle principal de la heurística, que se ejecuta hasta alcanzar el límite de tiempo o el número máximo de iteraciones
    while True:
        # Comprobación de criterios de parada
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break
        if max_iterations is not None and iteration >= max_iterations:
            break

        # Se usan semillas diferentes en cada iteración para diversificar la búsqueda, pero de forma reproducible si se proporciona una base_seed
        seed = None if base_seed is None else base_seed + iteration
        rng = random.Random(seed)
        iteration += 1

        # Generación de subconjunto factible P'
        try:
            selected_placements = generate_random_feasible_placements(problem=problem, seed=seed, max_attempts=placement_max_attempts)
            generated_subsets += 1
        except Exception as exc:
            generation_failures += 1
            if verbose:
                print(f"[it={iteration}] Placement subset generation failed: {exc}")
            continue

        # Extracción de clústeres activos para el subconjunto P'
        active_clusters = build_selected_placement_clusters(problem=problem, selected_placements=selected_placements, global_clusters=global_clusters)

        # Construcción de asignación inicial por clústeres
        start_professor_assignment = assign_professors_by_clusters(
            problem=problem,
            selected_placements=selected_placements,
            clusters=active_clusters,
            target_loads=target_loads,
            rng=rng
        )

        # Si no se ha podido construir la asignación inicial, se descarta este P'
        if start_professor_assignment is None:
            cluster_assignment_failures += 1
            continue

        # Construcción de asignación guía orientada a cargas objetivo
        guide_professor_assignment = build_load_balanced_professor_assignment(
            problem=problem,
            selected_placements=selected_placements,
            target_loads=target_loads,
            rng=rng,
            global_clusters=global_clusters
        )

        # Si no se ha podido construir la guía, se descarta este P'
        if guide_professor_assignment is None:
            guide_assignment_failures += 1
            continue

        # Path relinking entre asignación inicial y asignación guía
        professor_assignments = path_relink_professor_assignments(
            problem=problem,
            selected_placements=selected_placements,
            start_assignment=start_professor_assignment,
            guide_assignment=guide_professor_assignment,
            max_steps=max_path_relinking_steps,
            rng=rng
        )

        path_relinking_runs += 1
        path_relinking_assignments += len(professor_assignments)

        if not professor_assignments:
            continue

        # Resolución de los dos LAP una sola vez por P'
        try:
            tau_matrix = build_tau_matrix(problem=problem, selected_placements=selected_placements, normalize_student_dist=normalize_student_dist)
            assignment_tau = solve_lapjv_max(tau_matrix, solver=lap_solver)

            eta_matrix = build_eta_matrix(problem=problem, selected_placements=selected_placements)
            assignment_eta = solve_lapjv_max(eta_matrix, solver=lap_solver)
        except Exception as exc:
            invalid_solutions += 1
            if verbose:
                print(f"[it={iteration}] LAP solving failed: {exc}")
            continue

        # Combinación de cada asignación profesor-práctica con los dos LAP
        for idx_prof_assignment, professor_assignment in enumerate(professor_assignments):
            local_seed = None if seed is None else seed + idx_prof_assignment

            # Construcción, validación y registro de la solución tau
            sol_tau = build_solution_from_lap_assignment(
                problem=problem,
                selected_placements=selected_placements,
                professor_assignment=professor_assignment,
                lap_assignment=assignment_tau
            )

            reg = _register_completed_solution(
                sol=sol_tau,
                pareto_set=pareto_set,
                iteration=iteration,
                seed=local_seed,
                weights=weights,
                max_pareto_size=max_pareto_size,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist
            )

            if reg is not None and reg["valid"]:
                feasible_solutions += 1
                lap_tau_solutions += 1
                pareto_set = reg["pareto_set"]
                if reg["was_inserted"]:
                    inserted_into_pareto += 1
            else:
                invalid_solutions += 1

            # Construcción, validación y registro de la solución eta
            sol_eta = build_solution_from_lap_assignment(
                problem=problem,
                selected_placements=selected_placements,
                professor_assignment=professor_assignment,
                lap_assignment=assignment_eta
            )

            reg = _register_completed_solution(
                sol=sol_eta,
                pareto_set=pareto_set,
                iteration=iteration,
                seed=local_seed,
                weights=weights,
                max_pareto_size=max_pareto_size,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist
            )

            if reg is not None and reg["valid"]:
                feasible_solutions += 1
                lap_eta_solutions += 1
                pareto_set = reg["pareto_set"]
                if reg["was_inserted"]:
                    inserted_into_pareto += 1
            else:
                invalid_solutions += 1

        # Mensajes de progreso cada 10 iteraciones
        if verbose and iteration % 10 == 0:
            print(
                f"[it={iteration}] "
                f"subsets={generated_subsets} feasible={feasible_solutions} "
                f"cluster_fail={cluster_assignment_failures} guide_fail={guide_assignment_failures} "
                f"path_assignments={path_relinking_assignments} pareto_size={len(pareto_set)}"
            )

    # Cálculo del tiempo total transcurrido
    total_time = time.time() - start

    return {
        "pareto_set": pareto_set,
        "stats": {
            "iterations": iteration,
            "generated_subsets": generated_subsets,
            "cluster_assignment_failures": cluster_assignment_failures,
            "guide_assignment_failures": guide_assignment_failures,
            "path_relinking_runs": path_relinking_runs,
            "path_relinking_assignments": path_relinking_assignments,
            "lap_tau_solutions": lap_tau_solutions,
            "lap_eta_solutions": lap_eta_solutions,
            "feasible_solutions": feasible_solutions,
            "invalid_solutions": invalid_solutions,
            "inserted_into_pareto": inserted_into_pareto,
            "pareto_size": len(pareto_set),
            "elapsed_seconds": total_time,
            "generation_failures": generation_failures,
            "lap_solver": lap_solver,
            "time_limit_seconds": time_limit_seconds,
            "max_iterations": max_iterations,
            "max_path_relinking_steps": max_path_relinking_steps,
        },
    } # Diccionario con el conjunto Pareto encontrado y estadísticas de la ejecución