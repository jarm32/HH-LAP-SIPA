import time
from typing import Any, Callable, Dict, List, Optional

from metaheuristics.pareto import EvaluatedSolution, prune_pareto_set_by_size, update_pareto_set
from tools.evaluator import evaluate_solution


def random_search_pareto(
    problem,
    generator_fn: Callable[..., Any],
    weights,
    time_limit_seconds: float,
    max_iterations: Optional[int] = None,
    generator_kwargs: Optional[Dict[str, Any]] = None,
    max_pareto_size: Optional[int] = None,
    base_seed: Optional[int] = None,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    verbose: bool = True,
):
    """
    Búsqueda baseline multiobjetivo:
      mientras haya tiempo, genera soluciones, evalúa y actualiza Pareto.

    generator_fn debe tener forma compatible con:
      generator_fn(problem, seed=..., **generator_kwargs)

    Devuelve un dict con:
      - pareto_set
      - stats
    """
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")

    generator_kwargs = generator_kwargs or {}

    start = time.time()
    iteration = 0
    generated = 0
    feasible = 0
    failures = 0
    inserted = 0

    pareto_set: List[EvaluatedSolution] = []

    while True:
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break

        if max_iterations is not None and iteration >= max_iterations:
            break

        seed = None if base_seed is None else base_seed + iteration

        iteration += 1
        generated += 1

        try:
            sol = generator_fn(problem, seed=seed, **generator_kwargs)
        except Exception:
            failures += 1
            continue

        eval_result = evaluate_solution(
            sol,
            weights,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )

        if not eval_result.get("valid", False):
            failures += 1
            continue

        feasible += 1

        cand = EvaluatedSolution(
            sol=sol,
            evaluation=eval_result,
            iteration=iteration,
            seed=seed,
        )

        pareto_set, was_inserted, _ = update_pareto_set(pareto_set, cand)

        if was_inserted:
            inserted += 1

        if max_pareto_size is not None and len(pareto_set) > max_pareto_size:
            pareto_set = prune_pareto_set_by_size(pareto_set, max_pareto_size)

        if verbose and iteration % 50 == 0:
            print(
                f"[it={iteration}] "
                f"generated={generated} feasible={feasible} failures={failures} "
                f"pareto_size={len(pareto_set)}"
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
        }
    }


def print_pareto_set(pareto_set):
    """
    Imprime un resumen legible del Pareto set.
    """
    if not pareto_set:
        print("Pareto set vacío.")
        return

    print("\n=== PARETO SET ===")
    for idx, item in enumerate(pareto_set, start=1):
        c = item.evaluation["components"]
        obj = item.evaluation["objective_value"]
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
    """
    Guarda los resultados de la ejecución en un archivo txt.
    """

    with open(filepath, "w", encoding="utf-8") as f:

        f.write("===== SIPA RANDOM BASELINE RESULTS =====\n\n")

        f.write(f"Instance: {instance_name}\n\n")

        f.write("---- STATS ----\n")
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