# Motor común de búsqueda multiobjetivo --> evalúa soluciones, mantiene el conjunto de Pareto
# y proporciona utilidades compartidas para ejecutar y comparar distintas metaheurísticas.

# ----------------------------
# Librerías
# ----------------------------
import time

from tools.pareto_front import EvaluatedSolution, prune_pareto_set_by_size, update_pareto_set
from tools.evaluator import evaluate_solution_multi, evaluate_solution_scalar


# -----------------------------------------------------------------
# Registro y actualización del Pareto global externo
# -----------------------------------------------------------------

def register_solution_in_pareto(
    sol,                                # solución a evaluar y registrar
    pareto_set,                         # Pareto actual
    iteration,                          # iteración en la que se genera la solución
    seed,                               # semilla
    weights,                            # pesos para la evaluación escalar auxiliar
    max_pareto_size=None,               # tamaño máximo del Pareto externo (None para ilimitado)
    normalize_student_dist=True,        # booleano para normalización de distancia de estudiantes
    normalize_supervision_dist=True,    # booleano para normalización de distancia de supervisores
    precomputed_multi_eval=None,        # evaluación multiobjetivo ya calculada
    precomputed_scalar_eval=None        # evaluación escalar ya calculada
):
    """
    Evalúa una Solution, la convierte en EvaluatedSolution y la intenta registrar
    en el Pareto global externo.

    Puede reutilizar evaluaciones ya calculadas para no repetir trabajo.
    """
    # Evaluación multiobjetivo
    multi_eval = precomputed_multi_eval
    if multi_eval is None:
        multi_eval = evaluate_solution_multi(sol, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

    # Si la solución no es válida, no se procesa más
    if not multi_eval.get("valid", False):
        return {
            "pareto_set": pareto_set,
            "valid": False,
            "was_inserted": False,
            "removed_count": 0,
            "pruned": False,
            "evaluation": None,
        }

    # Evaluación escalar auxiliar
    scalar_eval = precomputed_scalar_eval
    if scalar_eval is None:
        scalar_eval = evaluate_solution_scalar(sol, weights, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)
    
    # Combina evaluación multiobjetivo + escalar en un único diccionario para almacenar en el Pareto
    eval_result = dict(multi_eval)
    eval_result["objective_value"] = scalar_eval["objective_value"]

    # Construcción del objeto evaluado
    candidate = EvaluatedSolution(sol=sol, evaluation=eval_result, iteration=iteration, seed=seed)

    # Actualización del Pareto
    new_pareto_set, was_inserted, removed_count = update_pareto_set(pareto_set, candidate)

    # Poda opcional por tamaño máximo
    pruned = False
    if max_pareto_size is not None and len(new_pareto_set) > max_pareto_size:
        new_pareto_set = prune_pareto_set_by_size(new_pareto_set, max_pareto_size)
        pruned = True

    return {
        "pareto_set": new_pareto_set,
        "valid": True,
        "was_inserted": was_inserted,
        "removed_count": removed_count,
        "pruned": pruned,
        "evaluation": eval_result,
    } # diccionario con: Pareto actualizado, si la solución era válida, si entró en el Pareto, cuántas soluciones dominadas eliminó, si hubo poda por tamaño y evaluación final almacenada (incluye objective_value)


# -----------------------------------------------------------------
# Baseline de búsqueda aleatoria multiobjetivo
# -----------------------------------------------------------------

def random_search_pareto(problem, generator_fn, weights, time_limit_seconds = 60,
                         # Objeto Problem (instancia), función que genera soluciones, pesos para evaluación escalar, límite de tiempo
                         max_iterations = None, generator_kwargs = None, max_pareto_size = None, base_seed = None, normalize_student_dist = True, normalize_supervision_dist = True, verbose = True):
                         # tope de iteraciones, argumentos extra generador, tamaño máximo Pareto, semilla, normalizar o no distancias del estudiante y de la supervisión, mostrar progreso
    """
    Ejecuta una búsqueda aleatoria multiobjetivo: genera soluciones con el generador dado
    y las intenta registrar en el Pareto global externo mientras haya tiempo. Añade estadísticas
    de ejecución y aplica poda al Pareto si se fija un tamaño máximo.

    generator_fn es, en este caso, generate_random_feasible_fixing
    """
    # Validación inicial e inicialización de parámetros y contadores
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")

    generator_kwargs = generator_kwargs or {}
    start = time.time()
    iteration = 0
    generated = 0
    feasible = 0
    failures = 0
    inserted = 0
    pareto_set = [] # Pareto vacío

    # Bucle principal
    while True:

        # Criterios de parada
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break # por tiempo
        if max_iterations is not None and iteration >= max_iterations:
            break # por iteraciones
        
        # Semilla para reproducibilidad
        seed = None if base_seed is None else base_seed + iteration

        # Contadores
        iteration += 1
        generated += 1

        # Generación de solución
        try:
            sol = generator_fn(problem, seed=seed, **generator_kwargs)
        except Exception:
            failures += 1
            continue
        
        # Evalúa la solución y delega su registro/actualización en el Pareto externo
        reg = register_solution_in_pareto(sol=sol, pareto_set=pareto_set, iteration=iteration, seed=seed, weights=weights, max_pareto_size=max_pareto_size, 
                                          normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)
        
        # Si la solución no era válida, se cuenta como fallo y se descarta
        if not reg["valid"]:
            failures += 1
            continue
        
        # La solución era válida y ha sido procesada correctamente
        feasible += 1

        # Actualiza el Pareto externo con el resultado devuelto por la función común
        pareto_set = reg["pareto_set"]

        # Cuenta cuántas soluciones llegaron a entrar en el Pareto
        if reg["was_inserted"]:
            inserted += 1

        # Imprime estado cada 50 iteraciones
        if verbose and iteration % 50 == 0:
            print(
                f"[it={iteration}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)}"
            )

    # Calcula el tiempo total de ejecución
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
            "elapsed_seconds": total_time}
            } # Diccionario con el Pareto externo final y las estadísticas de la ejecución


# -----------------------------------------------------------------
# Utilidades de visualización y exportación de resultados
# -----------------------------------------------------------------

def summarize_pareto_set(pareto_set): # pareto actual
    """
    Calcula un resumen del frente de Pareto final:
    - máximos de cada objetivo
    - medias de cada objetivo
    - máximo global (objective_value)
    - media global (objective_value)
    """
    # Validación inicial
    if not pareto_set:
        return {
            "max_tau": None,
            "mean_tau": None,
            "max_eta": None,
            "mean_eta": None,
            "max_lbar": None,
            "mean_lbar": None,
            "max_omega": None,
            "mean_omega": None,
            "max_objective_value": None,
            "mean_objective_value": None,
        }

    # Inicialización de las listas por componente
    tau_vals = []
    eta_vals = []
    lbar_vals = []
    omega_vals = []
    obj_vals = []
    
    # Recorre cada solución del Pareto y extrae sus componentes para calcular máximos y medias
    for item in pareto_set:
        c = item.evaluation["components"]
        tau_vals.append(float(c["tau_sum"]))
        eta_vals.append(float(c["eta_sum"]))
        lbar_vals.append(float(c["lbar_sum"]))
        omega_vals.append(float(c["omega"]))
        obj_vals.append(float(item.evaluation["objective_value"]))

    return {
        "max_tau": max(tau_vals),
        "mean_tau": sum(tau_vals) / len(tau_vals),
        "max_eta": max(eta_vals),
        "mean_eta": sum(eta_vals) / len(eta_vals),
        "max_lbar": max(lbar_vals),
        "mean_lbar": sum(lbar_vals) / len(lbar_vals),
        "max_omega": max(omega_vals),
        "mean_omega": sum(omega_vals) / len(omega_vals),
        "max_objective_value": max(obj_vals),
        "mean_objective_value": sum(obj_vals) / len(obj_vals),
    } # Diccionario con resumen de máximos y medias de cada componente del Pareto y del objective_value global

def print_pareto_set(pareto_set):
                    # Conjunto Pareto actual --> los elementos son las soluciones empaquetadas en EvaluatedSolution
    """
    Imprime un resumen legible del Pareto set
    """
    # Validación inicial
    if not pareto_set:
        print("Pareto set vacío.")
        return

    # Recorre cada solución
    print("\n=== PARETO SET ===")
    for idx, item in enumerate(pareto_set, start=1):
        # Extraer datos
        c = item.evaluation["components"]
        obj = item.evaluation["objective_value"]
        
        # Print formateado
        print(
            f"[{idx}] "
            f"iter={item.iteration} seed={item.seed} "
            f"obj={obj:.6f} | "
            f"tau={c['tau_sum']:.6f}, "
            f"eta={c['eta_sum']:.6f}, "
            f"lbar={c['lbar_sum']:.6f}, "
            f"omega={c['omega']:.6f}"
        )


def save_statistics_to_txt(filepath, instance_name, stats, pareto_set, model="---"):
                           # Ruta del archivo de salida, nombre de la instancia sobre la que se trabaja, estadísticas de la ejecución, cjto Pareto, modelo usado
    """
    Guarda las estadísticas de la ejecución en un archivo txt
    """
    # Resumen del Pareto
    summary = summarize_pareto_set(pareto_set)
    
    # Escritura en archivo
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"===== SIPA {model} RESULTS =====\n\n")
        f.write(f"Instance: {instance_name}\n\n")

        # stats = iterations, generated, feasible, failures, inserted_into_pareto, pareto_size, elapsed_seconds
        f.write("---- STATS ----\n")
        for k, v in stats.items():
            f.write(f"{k}: {v}\n")

        # Escritura del resumen
        f.write("\n---- SUMMARY ----\n")
        if summary["max_tau"] is None:
            f.write("Pareto set vacío\n")
        else:
            f.write(f"max_tau: {summary['max_tau']:.6f}\n")
            f.write(f"mean_tau: {summary['mean_tau']:.6f}\n")
            f.write(f"max_eta: {summary['max_eta']:.6f}\n")
            f.write(f"mean_eta: {summary['mean_eta']:.6f}\n")
            f.write(f"max_lbar: {summary['max_lbar']:.6f}\n")
            f.write(f"mean_lbar: {summary['mean_lbar']:.6f}\n")
            f.write(f"max_omega: {summary['max_omega']:.6f}\n")
            f.write(f"mean_omega: {summary['mean_omega']:.6f}\n")
            f.write(f"max_objective_value: {summary['max_objective_value']:.6f}\n")
            f.write(f"mean_objective_value: {summary['mean_objective_value']:.6f}\n")

        # Pareto set detallado
        f.write("\n---- PARETO SET ----\n")
        if not pareto_set:
            f.write("Pareto set vacío\n")
            return

        for idx, item in enumerate(pareto_set, start=1):
            c = item.evaluation["components"]
            obj = item.evaluation["objective_value"]
            f.write(
                f"[{idx}] "
                f"iter={item.iteration} seed={item.seed} "
                f"obj={obj:.6f} | "
                f"tau={c['tau_sum']:.6f}, "
                f"eta={c['eta_sum']:.6f}, "
                f"lbar={c['lbar_sum']:.6f}, "
                f"omega={c['omega']:.6f}\n"
            )

def save_assignments_to_txt(filepath, instance_name, pareto_set, model="---"):
                            # Ruta del archivo de salida, nombre de la instancia sobre la que se trabaja, cjto Pareto, modelo usado
    """
    Guarda las asignaciones completas de cada solución del Pareto en un txt legible
    """
    # Escritura en archivo
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"===== SIPA {model} ASSIGNMENTS =====\n\n")
        f.write(f"Instance: {instance_name}\n\n")

        if not pareto_set:
            f.write("Pareto set vacío\n")
            return

        # Para cada solución del Pareto, se escriben sus componentes y luego las asignaciones detalladas
        for idx, item in enumerate(pareto_set, start=1):
            sol = item.sol
            c = item.evaluation["components"]
            obj = item.evaluation["objective_value"]

            f.write("=" * 80 + "\n")
            f.write(f"SOLUTION [{idx}]\n")
            f.write("=" * 80 + "\n")
            f.write(f"iteration: {item.iteration}\n")
            f.write(f"seed: {item.seed}\n")
            f.write(f"objective_value: {obj:.6f}\n")
            f.write(f"tau_sum: {c['tau_sum']:.6f}\n")
            f.write(f"eta_sum: {c['eta_sum']:.6f}\n")
            f.write(f"lbar_sum: {c['lbar_sum']:.6f}\n")
            f.write(f"omega: {c['omega']:.6f}\n\n")

            # Asignaciones detalladas por estudiante, indicando su placement, empresa asignada y profesor asignado
            f.write("---- STUDENT -> PLACEMENT / COMPANY / PROFESSOR ----\n")
            for i, j in enumerate(sol.student_to_placement):
                company = sol.problem.placement_company[j] if j != -1 else -1
                professor = sol.placement_to_professor[j] if j != -1 else -1
                f.write(
                    f"student {i:03d} -> placement {j:03d} | "
                    f"company {company:03d} | professor {professor:03d}\n"
                )

            # Asignaciones por profesor para facilitar lectura y ver cargas
            f.write("\n---- PROFESSOR -> PLACEMENTS ----\n")
            placements_by_prof = [[] for _ in range(sol.problem.n_professors)]
            for j, t in enumerate(sol.placement_to_professor):
                if t != -1:
                    placements_by_prof[t].append(j)

            # Escribe por cada profesor su carga y los placements que supervisa
            for t, placements in enumerate(placements_by_prof):
                placements_str = ", ".join(str(j) for j in placements) if placements else "-"
                f.write(
                    f"professor {t:03d} | load={sol.professor_load[t]} | placements: {placements_str}\n"
                )

            # Escribe por cada empresa su carga y los mínimos/máximos para comparar
            f.write("\n---- COMPANY LOAD ----\n")
            for k, load in enumerate(sol.company_load):
                f.write(
                    f"company {k:03d} | load={load} | "
                    f"min={sol.problem.company_min[k]} | max={sol.problem.company_max[k]}\n"
                )

            # Escribe por cada profesor su carga y los mínimos/máximos para comparar
            f.write("\n---- PROFESSOR LOAD ----\n")
            for t, load in enumerate(sol.professor_load):
                f.write(
                    f"professor {t:03d} | load={load} | "
                    f"capacity={sol.problem.prof_capacity[t]}\n"
                )

            f.write("\n")

def save_results_to_txt(statistics_filepath, assignments_filepath, instance_name, stats, pareto_set, model="---"):
    """
    Guarda por separado estadísticas y asignaciones
    """
    save_statistics_to_txt(filepath=statistics_filepath, instance_name=instance_name, stats=stats, pareto_set=pareto_set, model=model)

    save_assignments_to_txt(filepath=assignments_filepath, instance_name=instance_name, pareto_set=pareto_set, model=model)