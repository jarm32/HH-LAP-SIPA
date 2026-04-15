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


# -----------------------------------------------------------------
# Utilidades de conversión y reconstrucción Solution ↔ Individuo
# -----------------------------------------------------------------

def solution_to_individual(sol): # objeto Solution
    """
    Convierte una Solution a individuo DEAP (individuo genético) usando como cromosoma student_to_placement.
    Además, guarda una copia de la solución para evitar reconstruirla en evaluaciones posteriores
    """
    # Crea el individuo DEAP usando como genes la lista de plazas asignadas a cada estudiante
    ind = creator.IndividualSIPA(list(sol.student_to_placement))

    # Guarda una copia de la solución
    ind.cached_solution = _copy_solution(sol)

    # Caché de evaluación multiobjetivo (se rellenará tras evaluar el individuo)
    ind.cached_multi_eval = None

    return ind # individuo DEAP del tipo IndividualSIPA


def _copy_solution(sol): # objeto Solution
    """
    Crea una copia manual de la solución para poder modificarla sin alterar la original
    """
    # Nueva solución vacía
    new_sol = Solution(sol.problem)

    # Copia una a una las estructuras internas relevantes de la solución
    new_sol.student_to_placement = list(sol.student_to_placement)
    new_sol.placement_to_professor = list(sol.placement_to_professor)
    new_sol.company_load = list(sol.company_load)
    new_sol.professor_load = list(sol.professor_load)
    new_sol.placement_filled = list(sol.placement_filled)

    return new_sol # otra solución con el mismo contenido, pero independiente


def _reset_professor_assignment(sol): # objeto Solution
    """
    Borra la parte de la solución que asigna plazas a profesores
    """
    # Marca todas las plazas como no asignadas a ningún profesor y reinicia las cargas
    sol.placement_to_professor = [-1] * sol.problem.n_placements
    sol.professor_load = [0] * sol.problem.n_professors


def _build_solution_from_assignment_vector(problem, assignments, rng): # individual_to_solution
                                          # instancia del problema, lista de longitud n_students con la plaza asignada a cada estudiante, generador aleatorio 
    """
    Reconstruye una Solution completa a partir de un vector student_to_placement, comprobando primero sea viable. 
    
    En caso positivo, reconstruye la capa [plaza -> profesor] y devuelve la solución final si pasa todas las validaciones.
    En caso negativo, devuelve None
    """
    # Validaciones básicas del vector
    if len(assignments) != problem.n_students: # 1 plaza por estudiante
        return None

    if any(j < 0 or j >= problem.n_placements for j in assignments): # Todas las plazas son índices válidos
        return None

    if len(set(assignments)) != len(assignments): # No hay plazas repetidas
        return None

    # Crea una solución vacía
    sol = Solution(problem)

    # Carga en la solución la asignación [estudiante -> plaza] y actualiza estructuras auxiliares
    for i, j in enumerate(assignments):
        sol.student_to_placement[i] = j
        sol.placement_filled[j] = True
        k = problem.placement_company[j]
        sol.company_load[k] += 1

    # Comprueba que cada empresa respete sus mínimos y máximos
    for k in range(problem.n_companies):
        if sol.company_load[k] < problem.company_min[k]:
            return None
        if sol.company_load[k] > problem.company_max[k]:
            return None

    # Comprueba que no haya bloques de dependencias parcialmente ocupados
    if not sol.dependencies_ok():
        return None

    # Reconstrucción de la capa [plaza -> profesor]

    # Limpia cualquier asignación previa de profesores
    _reset_professor_assignment(sol)

    # Intenta asignar un profesor a cada plaza ocupada respetando capacidades
    ok = _assign_professors_with_repair(problem, sol, rng)
    if not ok:
        return None

    # Validación global final de toda la solución
    if not sol.validate():
        return None

    return sol # Solution válida si puede construirla


# ---------------------------------------------------------------
# Utilidades de repair del cromosoma
# ---------------------------------------------------------------

def _dependency_placement_set(problem): # instancia del problema
    """
    Construye el conjunto de plazas que están afectadas por alguna dependencia
    """
    dep_set = set()
    
    # Recorre todos los bloques de dependencias y añade sus plazas al conjunto
    for block in problem.dependencies:
        for j in block:
            dep_set.add(j)
    return dep_set # set con todas las plazas que participan en dependencias


def _placement_owner(assignments): # lista de longitud n_students con la plaza j asignada a cada estudiante i (assignments[i] = j)
    """
    Invierte la representación student -> placement para poder saber rápidamente qué estudiante ocupa una plaza concreta
    """
    return {j: i for i, j in enumerate(assignments)} # diccionario placement -> student


def _try_align_assignments_with_template(problem, desired, template_sol, rng):
                                        # instancia del problema, lista con las plazas que el cromosoma propone asignar a cada estudiante,
                                        # solución factible base sobre la que se intenta trabajar, generador aleatorio
    """
    Parte de una solución factible base y trata de incorporar información del individuo
    sin romper factibilidad estructural.

    Lo hace usando dos movimientos (leves):
    - Si la plaza deseada ya está en la solución base, intercambia estudiantes
    - Si no, solo permite sustituciones en las que la plaza actual y la plaza deseada pertenezcan a la misma empresa, y no estén en dependencias
    """
    assignments = list(template_sol.student_to_placement) # Solución base
    owner = _placement_owner(assignments) # Diccionario placement -> student
    dep_set = _dependency_placement_set(problem) # Plazas en dependencias

    # Recorremos los estudiantes en orden aleatorio
    order = list(range(problem.n_students))
    rng.shuffle(order)

    # Para cada estudiante, alinea su plaza asignada con la plaza deseada por el cromosoma
    for i in order:
        j_des = desired[i]

        # Se ignoran genes que no representen una plaza válida
        if not isinstance(j_des, int):
            continue
        if j_des < 0 or j_des >= problem.n_placements:
            continue

        j_cur = assignments[i] # Misma plaza que tengo asignada en la solución base
        if j_des == j_cur:
            continue

        # Caso 1 --> la plaza deseada ya está ocupada en la solución base --> swap de estudiantes para acercar la asignación al cromosoma sin cambiar el conjunto de plazas ocupadas
        if j_des in owner:
            other = owner[j_des]
            if other == i:
                continue

            assignments[i], assignments[other] = assignments[other], assignments[i]
            owner[assignments[i]] = i
            owner[assignments[other]] = other
            continue

        # Caso 2 --> la plaza deseada no está ocupada en la solución base --> solo se permite el cambio si no rompe restricciones (misma empresa, no dependencias)
        same_company = problem.placement_company[j_cur] == problem.placement_company[j_des]
        both_nondep = (j_cur not in dep_set) and (j_des not in dep_set)

        if same_company and both_nondep:
            del owner[j_cur]
            assignments[i] = j_des
            owner[j_des] = i

    return assignments # lista de plazas asignadas a cada estudiante más cercana a la deseada


def repair_individual(problem, individual, rng, template_sol = None, seed = None):
                     # instancia del problema, cromosoma a reparar, generador aleatorio, solución factible base para intentar alinear, semilla
    """
    Intenta reparar el individuo construyendo una solución válida a partir de una solución factible base:
    1. Parte de una solución factible base
    2. Intenta incorporar la información del individuo
    3. Reconstruye profesores 
    4. Si falla, cae a una solución factible generada de nuevo

    No corrige directamente el cromosoma, sino que intenta proyectarlo sobre una solución factible
    """
    # Conversión del individuo a lista de plazas deseadas
    desired = []
    for x in individual:
        try:
            desired.append(int(x))
        except Exception:
            desired.append(-1)

    # Construcción de plantillas candidatas
    candidate_templates = []

    # Añade la solución plantilla heredada, si existe
    if template_sol is not None:
        candidate_templates.append(_copy_solution(template_sol))

    # Genera varias soluciones factibles auxiliares como posibles bases de repair
    for extra in range(3):
        local_seed = None if seed is None else seed + 1000 + extra
        base_sol = generate_random_feasible_fixing(problem, seed=local_seed)
        candidate_templates.append(base_sol)

    # Intento de alineación y reconstrucción de solución a partir de cada plantilla candidata hasta encontrar una solución válida
    for base_sol in candidate_templates:
        assignments = _try_align_assignments_with_template(problem, desired, base_sol, rng) # Intenta acercar la plantilla al individuo sin romper factibilidad
        repaired = _build_solution_from_assignment_vector(problem, assignments, rng) # Reconstruye y valida una Solution a partir del intento de acercamiento anterior
        if repaired is not None and repaired.validate():
            return repaired # Si la solución es válida, la devuelve como resultado del repair

    # Último recurso --> Si ninguna plantilla funciona, se devuelve una solución factible nueva
    fallback_seed = None if seed is None else seed + 999999
    return generate_random_feasible_fixing(problem, seed=fallback_seed) # Solución factible garantizada, aunque sin relación con el individuo original (generada de nuevo)


# -----------------------------------------------------------------
# Inicialización de individuos y población
# -----------------------------------------------------------------

def _init_individual(problem, seed=None):
                    # instancia del problema, semilla
    """
    Genera una solución factible usando el generador existente y la convierte en un individuo del GA (DEAP)
    """
    # Genera una solución factible del problema
    sol = generate_random_feasible_fixing(problem, seed=seed)

    # Convierte la solución en un individuo DEAP
    return solution_to_individual(sol) # IndividualSIPA factible


def _init_population(problem, population_size, base_seed = None):
                    # instancia del problema, nº de individuos a generar, semilla
    """
    Construye la población inicial generando múltiples individuos factibles
    """
    population = []

    # Generación de individuos
    for i in range(population_size):
        # Si hay semilla base, cada individuo usa una semilla distinta (base_seed + i) para mantener reproducibilidad y evitar clones
        seed = None if base_seed is None else base_seed + i
        
        # Se genera cada individuo como solución factible convertida a cromosoma
        population.append(_init_individual(problem, seed=seed))

    return population # lista de individuos DEAP (población inicial factible)


# -----------------------------------------------------------------
# Operadores genéticos
# -----------------------------------------------------------------

def crossover_simple(ind1, ind2, problem, rng, seed = None):
                    # dos individuos padres a cruzar, instancia del problema, generador aleatorio, semilla
    """
    Cruza dos individuos mezclando los genes de los padres con una máscara aleatoria y repara los descendientes resultantes
    """
    # Recupera las soluciones de los padres cacheadas para usarlas como plantilla en el repair
    parent1_sol = getattr(ind1, "cached_solution", None)
    parent2_sol = getattr(ind2, "cached_solution", None)

    # Copia temporal de los genes de ambos padres para el cruce
    child1_genes = list(ind1)
    child2_genes = list(ind2)

    # Cruce (por máscara aleatoria) --> para cada estudiante, decide de qué padre hereda
    for i in range(len(child1_genes)):
        if rng.random() < 0.5:
            child1_genes[i], child2_genes[i] = child2_genes[i], child1_genes[i]

    # Repara ambos cromosomas descendientes para obtener soluciones válidas
    child1_sol = repair_individual(problem=problem, individual=child1_genes, rng=rng, template_sol=parent1_sol, seed=seed)
    child2_sol = repair_individual(problem=problem, individual=child2_genes, rng=rng, template_sol=parent2_sol, seed=None if seed is None else seed + 1)

    # Sustituye el contenido de los individuos por los genes reparados
    ind1[:] = list(child1_sol.student_to_placement)
    ind2[:] = list(child2_sol.student_to_placement)

    # Actualiza la caché de solución y borra la de evaluación
    ind1.cached_solution = child1_sol
    ind2.cached_solution = child2_sol
    ind1.cached_multi_eval = None
    ind2.cached_multi_eval = None

    # Invalida el fitness anterior, ya que los individuos han cambiado
    if ind1.fitness.valid:
        del ind1.fitness.values
    if ind2.fitness.valid:
        del ind2.fitness.values

    return ind1, ind2 # los dos individuos descendientes modificados


def mutate_simple(individual, problem, rng, seed = None):
                 # cromosoma/individuo a mutar, instancia del problema, generador aleatorio, semilla
    """
    Aplica una mutación sencilla al cromosoma. Después aplica repair y actualiza la caché y el fitness
    """
    # Copia temporal del cromosoma
    mutated = list(individual)

    # Mutación --> o bien intercambia dos estudiantes, o bien cambia la plaza deseada de uno de ellos por otra aleatoria
    if len(mutated) >= 2 and rng.random() < 0.5:
        i, j = rng.sample(range(len(mutated)), 2)
        mutated[i], mutated[j] = mutated[j], mutated[i]
    else:
        i = rng.randrange(len(mutated))
        mutated[i] = rng.randrange(problem.n_placements)

    # Usa la solución actual como plantilla para el repair
    template_sol = getattr(individual, "cached_solution", None)
    
    # Repara el cromosoma mutado para obtener una solución válida
    repaired_sol = repair_individual(problem=problem, individual=mutated, rng=rng, template_sol=template_sol, seed=seed)

    # Sustituye el individuo por el resultado reparado
    individual[:] = list(repaired_sol.student_to_placement)
    individual.cached_solution = repaired_sol
    individual.cached_multi_eval = None

    # Invalida el fitness anterior
    if individual.fitness.valid:
        del individual.fitness.values

    return (individual,) #individuo mutado


# -----------------------------------------------------------------
# Evaluación y registro en Pareto externo
# -----------------------------------------------------------------

def _evaluate_individual(individual, normalize_student_dist=True, normalize_supervision_dist=True):
                        # individuo a evaluar, booleanos para normalización de objetivos (distancias de estudiantes y supervisores)
    """
    Evalúa el individuo a partir de su Solution cacheada mediante evaluate_solution_multi.
    Si la solución no es válida, devuelve una penalización alta; si lo es, devuelve los cuatro objetivos en el orden esperado por DEAP.
    """
    # Recupera la solución asociada al individuo de su caché para evitar reconstruirla
    sol = getattr(individual, "cached_solution", None)
    if sol is None:
        raise ValueError("Individual has no cached_solution. Repair/init should build it first.")

    # Evalúa la solución con los cuatro objetivos del modelo
    multi_eval = evaluate_solution_multi(sol, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

    # Sol no válida
    if not multi_eval.get("valid", False):
        # Penalización alta; en principio no debería ocurrir si repair funciona
        individual.cached_multi_eval = multi_eval
        return (-1e18, -1e18, 1e18, 1e18)
    
    # Extrae los cuatro componentes de la evaluación en el orden del fitness DEAP
    c = multi_eval["components"]
    values = (
        float(c["tau_sum"]),
        float(c["eta_sum"]),
        float(c["lbar_sum"]),
        float(c["sigma_sum"]),
    )  

    # Guarda la evaluación en caché
    individual.cached_multi_eval = multi_eval

    return values # tupla con los 4 objetivos del fitness


def _register_individual_in_global_pareto(
    individual,                        # individuo ya evaluado
    pareto_set,                        # Pareto actual
    iteration,                         # número de iteración/generación actual
    seed,                              # semilla
    weights,                           # pesos de los objetivos para evaluación escalar (desempate)
    max_pareto_size = None,            # tamaño máximo del Pareto externo (None para ilimitado)
    normalize_student_dist = True,     # booleano para normalización de distancia de estudiantes
    normalize_supervision_dist = True  # booleano para normalización de distancia de supervisores
    ):
    """
    Registra el individuo ya evaluado en el Pareto global externo
    """
    # Recupera la solución y la evaluación cacheadas en el individuo
    sol = individual.cached_solution
    multi_eval = getattr(individual, "cached_multi_eval", None)
    
    # Hace el registro en Pareto usando la función común, pasando la evaluación ya calculada para agilizar
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

    return reg # diccionario con el resultado del registro en Pareto (pareto_set actualizado, valid, was_inserted, removed_count, pruned, evaluation)


# -----------------------------------------------------------------
# Selección de padres
# -----------------------------------------------------------------

def _select_parents(population, k, rng):
                   # población actual, número de padres a seleccionar, generador aleatorio
    """
    Selecciona padres mediante torneos binarios usando como criterio el frente no dominado al que pertenece cada individuo.
    Gana el que esté en mejor frente; si ambos están en el mismo, se desempata aleatoriamente
    """
    # Caso población vacía
    if not population:
        return []

    # Construye los frentes no dominados de la población
    fronts = tools.sortNondominated(population, len(population), first_front_only=False)
    
    # Asigna a cada individuo su rango de frente (0 = mejor frente)
    rank = {}
    for r, front in enumerate(fronts):
        for ind in front:
            rank[id(ind)] = r

    selected = []

    # Realiza k torneos binarios para elegir los padres
    for _ in range(k):
        if len(population) == 1:
            winner = population[0]
        else:
            # Toma dos individuos al azar para el torneo
            a, b = rng.sample(population, 2)
            ra = rank[id(a)]
            rb = rank[id(b)]

            # Gana el individuo del mejor frente; en empate, se desempata al azar
            if ra < rb:
                winner = a
            elif rb < ra:
                winner = b
            else:
                winner = a if rng.random() < 0.5 else b
        
        # Añade una copia del ganador para evitar modificar los individuos originales durante la reproducción
        selected.append(copy.deepcopy(winner))

    return selected # lista con k copias de individuos seleccionados


# -----------------------------------------------------------------
# Configuración del toolbox DEAP
# -----------------------------------------------------------------

def build_deap_toolbox(problem, rng, normalize_student_dist=True, normalize_supervision_dist=True, ref_points_p=5):
                      # instancia del problema, generador aleatorio, booleanos para normalización de objetivos (distancias de estudiantes y supervisores), parámetro generar los puntos de referencia de NSGA-III
    """
    Construye y configura el toolbox de DEAP registrando los operadores del algoritmo (evaluación, cruce, mutación y selección de supervivientes con NSGA-III)
    y generando los puntos de referencia necesarios para la selección de supervivientes NSGA-III
    """
    # Asegura que los tipos de individuo y fitness de DEAP estén definidos
    _ensure_deap_types()

    # Crea el contenedor de operadores de DEAP
    toolbox = base.Toolbox()
    
    # Genera los puntos de referencia uniformes para NSGA-III (4 objetivos)
    ref_points = tools.uniform_reference_points(nobj=4, p=ref_points_p)

    # Registra la función de evaluación del individuo
    toolbox.register("evaluate", _evaluate_individual, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

    # Registra el operador de cruce
    toolbox.register("mate", crossover_simple, problem=problem, rng=rng)

    # Registra el operador de mutación
    toolbox.register("mutate", mutate_simple, problem=problem, rng=rng)

    # Registra la selección de supervivientes (reemplazo) mediante NSGA-III
    toolbox.register("select_survivors", tools.selNSGA3, ref_points=ref_points)

    return toolbox, ref_points
           # objeto Toolbox configurado de DEAP, lista de puntos de referencia generados para NSGA-III


# -----------------------------------------------------------------
# Ejecución principal del algoritmo NSGA-III
# -----------------------------------------------------------------

def run_nsga3(
    problem,                         # instancia del problema
    weights,                         # pesos de los objetivos para evaluación escalar (desempate)
    population_size=50,              # tamaño de la población inicial
    offspring_size=50,               # número de descendientes por generación
    cx_prob=0.8,                     # probabilidad de cruce
    mut_prob=0.2,                    # probabilidad de mutación
    time_limit_seconds=60,           # límite de tiempo de ejecución
    max_generations=None,            # límite opcional de generaciones
    max_pareto_size=None,            # tamaño máximo del Pareto externo
    base_seed=None,                  # semilla 
    normalize_student_dist=True,     # normalización de distancias de estudiantes
    normalize_supervision_dist=True, # normalización de distancias de supervisión
    ref_points_p=5,                  # parámetro para generar reference points de NSGA-III
    verbose=True                     # muestra o no información de progreso
):
    """
    Ejecuta el NSGA-III completo sobre una instancia del problema. 
    Inicializa, evalúa, evoluciona la población por generaciones y mantiene en paralelo un Pareto global externo con las soluciones no dominadas encontradas
    """
    # Validaciones básicas de parámetros
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")
    if population_size <= 0:
        raise ValueError("population_size must be > 0")
    if offspring_size <= 0:
        raise ValueError("offspring_size must be > 0")

    # Valida los pesos de la función objetivo escalar auxiliar para desempate
    weights.validate()

    # Inicializa el generador aleatorio global del algoritmo
    rng = random.Random(base_seed)

    # Construye el toolbox DEAP y genera los puntos de referencia de NSGA-III
    toolbox, ref_points = build_deap_toolbox(problem=problem, rng=rng, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist, ref_points_p=ref_points_p)
    
    # Instante de inicio
    start = time.time()

    # Inicializa el Pareto global externo, la población inicial factible y los contadores de estadísticas
    pareto_set = []
    population = _init_population(problem, population_size, base_seed=base_seed)
    generations, generated, feasible, failures, inserted = 0, 0, 0, 0, 0

    # ------------------------------------------------------
    # Evaluación inicial de la población + actualización del Pareto externo
    # ------------------------------------------------------
    for idx, ind in enumerate(population):
        # Evalúa los individuos de la población inicial
        values = toolbox.evaluate(ind)
        if values[0] <= -1e17:
            failures += 1
            continue
        
        # Guarda el fitness del individuo y actualiza contadores de evaluaciones factibles
        ind.fitness.values = values
        generated += 1
        feasible += 1

        # Intenta registrar el individuo en el Pareto global externo
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

    # ---------------------------------------------------------
    # Bucle generacional principal (selección, cruce, mutación, evaluación y reemplazo hasta cumplir con el criterio de parada)
    # ---------------------------------------------------------
    while True:
        # Comprueba criterios de parada (tiempo o nº máximo de generaciones)
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break
        if max_generations is not None and generations >= max_generations:
            break
        generations += 1

        # Selección de padres desde la población actual
        parents = _select_parents(population, offspring_size, rng)
        offspring = parents

        # Aplica cruce por parejas con probabilidad cx_prob
        for i in range(0, len(offspring) - 1, 2):
            if rng.random() < cx_prob:
                seed = None if base_seed is None else base_seed + generations * 100000 + i
                toolbox.mate(offspring[i], offspring[i + 1], seed=seed)
        
        # Aplica mutación individual con probabilidad mut_prob
        for i in range(len(offspring)):
            if rng.random() < mut_prob:
                seed = None if base_seed is None else base_seed + generations * 200000 + i
                toolbox.mutate(offspring[i], seed=seed)

        # ---------------------------------------------------------
        # Evaluación de la descendencia + actualización del Pareto externo
        # ---------------------------------------------------------
        for i, ind in enumerate(offspring):
            # Solo evalúa si el fitness ha quedado invalidado tras la variación 
            if not ind.fitness.valid:
                values = toolbox.evaluate(ind)

                if values[0] <= -1e17:
                    failures += 1
                    continue
                
                # Guarda el fitness del descendiente
                ind.fitness.values = values
                generated += 1
                feasible += 1

                # Intenta registrar el descendiente en el Pareto global externo
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

        # ---------------------------------------------------------
        # Reemplazo ambiental NSGA-III
        # ---------------------------------------------------------
        # Une población actual y descendencia y selecciona los mejores individuos según NSGA-III para formar la nueva población
        combined = population + offspring
        population = toolbox.select_survivors(combined, population_size)

        # Muestra información de progreso cada 5 generaciones
        if verbose and generations % 5 == 0:
            print(
                f"[gen={generations}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)}"
            )

    # Calcula el tiempo total de ejecución
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
    } # diccionario con el Pareto externo final, la población final y estadísticas de la ejecución