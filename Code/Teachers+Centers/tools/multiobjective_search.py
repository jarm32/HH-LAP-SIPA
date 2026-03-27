# Motor de búsqueda multiobjetivo --> genera soluciones, las evalúa y mantiene el conjunto de Pareto
# Marco común para ejecutar y comparar distintas metaheurísticas.

# Librerías
import time
from typing import Any, Callable, Dict, List, Optional

from tools.pareto_front import EvaluatedSolution, prune_pareto_set_by_size, update_pareto_set
from tools.evaluator import evaluate_solution_multi, evaluate_solution_scalar

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

        # Evaluación multiobjetivo pura para Pareto
        eval_result = evaluate_solution_multi(sol, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

        if not eval_result.get("valid", False): # Descarta soluciones no válidas (no ha encontrado nada, pasa a la siguiente iteración)
            failures += 1
            continue

        # Evaluación escalar auxiliar para poda
        scalar_eval = evaluate_solution_scalar(sol, weights, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

        eval_result["objective_value"] = scalar_eval["objective_value"] # Añade ese valor a la evaluación

        # La solución es factible
        feasible += 1

        # Crea objeto empaquetador y actualiza el cjto Pareto
        cand = EvaluatedSolution(sol=sol, evaluation=eval_result, iteration=iteration, seed=seed)
        pareto_set, was_inserted, _ = update_pareto_set(pareto_set, cand)

        if was_inserted: # Contea el nº de inserciones (para estadísticas)
            inserted += 1

        # Poda por tamaño
        if max_pareto_size is not None and len(pareto_set) > max_pareto_size:
            pareto_set = prune_pareto_set_by_size(pareto_set, max_pareto_size)

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