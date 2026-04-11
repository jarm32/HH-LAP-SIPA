# Motor de búsqueda multiobjetivo --> genera soluciones, las evalúa y mantiene el conjunto de Pareto
# Marco común para ejecutar y comparar distintas metaheurísticas.

# Librerías
import time

from tools.pareto_front import EvaluatedSolution, prune_pareto_set_by_size, update_pareto_set
from tools.evaluator import evaluate_solution_multi, evaluate_solution_scalar

# Función de registro en Pareto --> evalúa una solución, la envuelve como EvaluatedSolution y la intenta registrar en el Pareto global externo
def register_solution_in_pareto(
    sol,
    pareto_set,
    iteration,
    seed,
    weights,
    max_pareto_size=None,
    normalize_student_dist=True,
    normalize_supervision_dist=True,
    precomputed_multi_eval=None,
    precomputed_scalar_eval=None,
):
    """
    Evalúa una Solution, la envuelve como EvaluatedSolution y la intenta registrar
    en el Pareto global externo.

    Puede reutilizar evaluaciones ya calculadas para no repetir trabajo.

    Devuelve un diccionario con:
    - pareto_set: Pareto actualizado
    - valid: si la solución era válida
    - was_inserted: si entró en el Pareto
    - removed_count: cuántas soluciones dominadas eliminó
    - pruned: si hubo poda por tamaño
    - evaluation: evaluación final almacenada (incluye objective_value)
    """
    multi_eval = precomputed_multi_eval
    if multi_eval is None:
        multi_eval = evaluate_solution_multi(
            sol,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )

    if not multi_eval.get("valid", False):
        return {
            "pareto_set": pareto_set,
            "valid": False,
            "was_inserted": False,
            "removed_count": 0,
            "pruned": False,
            "evaluation": None,
        }

    scalar_eval = precomputed_scalar_eval
    if scalar_eval is None:
        scalar_eval = evaluate_solution_scalar(
            sol,
            weights,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )

    eval_result = dict(multi_eval)
    eval_result["objective_value"] = scalar_eval["objective_value"]

    candidate = EvaluatedSolution(
        sol=sol,
        evaluation=eval_result,
        iteration=iteration,
        seed=seed,
    )

    new_pareto_set, was_inserted, removed_count = update_pareto_set(pareto_set, candidate)

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
    }


# Baseline --> Búsqueda aleatoria
def random_search_pareto(problem, generator_fn, weights, time_limit_seconds = 60,
                         # Objeto Problem (instancia), función que genera soluciones, pesos para evaluación escalar, límite de tiempo
                         max_iterations = None, generator_kwargs = None, max_pareto_size = None, base_seed = None, normalize_student_dist = True, normalize_supervision_dist = True, verbose = True):
                         # tope de iteraciones, argumentos extra generador, tamaño máximo Pareto, semilla, normalizar o no distancias del estudiante y de la supervisión, mostrar progreso
    """
    Ejecuta una búsqueda aleatoria multiobjetivo --> genera soluciones, las evalúa y mantiene el cjto Pareto
    mientras haya tiempo. Añade estadísticas y poda el conjunto en caso de que tenga tamaño máximo 

    generator_fn es, en este caso, generate_random_feasible_fixing
    """
    # Validación inicial + Inicialización
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

        reg = register_solution_in_pareto(
            sol=sol,
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

        feasible += 1
        pareto_set = reg["pareto_set"]

        if reg["was_inserted"]:
            inserted += 1

        # Imprime estado cada 50 iteraciones
        if verbose and iteration % 50 == 0:
            print(
                f"[it={iteration}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)}"
            )

    # Actualiza el tiempo para cumplir el time_limit_seconds
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
            } # Cjto Pareto, junto con estadísticas de la ejecución


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
            f"sigma={c['sigma_sum']:.6f}"
        )


def save_results_to_txt(filepath, instance_name, stats, pareto_set):
                        # Ruta archivo del archivo, nombre de la instancia sobre la que se trabaja, estadísticas de la ejecución, cjto Pareto
    """
    Guarda los resultados de la ejecución en un archivo txt
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("===== SIPA RANDOM BASELINE RESULTS =====\n\n")
        f.write(f"Instance: {instance_name}\n\n")
        f.write("---- STATS ----\n")

        # stats = iterations, generated, feasible, failures, inserted_into_pareto, pareto_size, elapsed_seconds
        for k, v in stats.items():
            f.write(f"{k}: {v}\n")

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
                f"sigma={c['sigma_sum']:.6f}\n"
            )