"""
Algoritmo genético multiobjetivo NSGA-III para el SIPA modificado.

Incluye:
- población inicial factible a partir de generate_random_feasible_fixing
- conversión individuo <-> Solution
- evaluación multiobjetivo compatible con DEAP
- selección de padres sencilla basada en frentes no dominados
- reemplazo ambiental con NSGA-III (DEAP)
- cruce simple
- mutación simple
- repair robusto con respaldo en una solución factible aleatoria
- Pareto global externo y estadísticas de ejecución
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from deap import base, creator, tools
except ImportError as exc:  # pragma: no cover - depende del entorno del usuario
    raise ImportError(
        "DEAP no está instalado. Instálalo para usar ga_nsga3.py, por ejemplo con: pip install deap"
    ) from exc

from metaheuristics.scripts.random_feasible_fixing import (
    _assign_professors_with_repair,
    generate_random_feasible_fixing,
)
from tools.evaluator import ObjectiveWeights, evaluate_solution_multi, evaluate_solution_scalar
from tools.pareto_front import EvaluatedSolution, prune_pareto_set_by_size, update_pareto_set
from tools.solution import Solution


# ---------------------------------------------------------------------------
# Configuración DEAP
# ---------------------------------------------------------------------------

if not hasattr(creator, "FitnessSIPANSGA3"):
    # max, max, min, min
    creator.create("FitnessSIPANSGA3", base.Fitness, weights=(1.0, 1.0, -1.0, -1.0))

if not hasattr(creator, "IndividualSIPANSGA3"):
    creator.create("IndividualSIPANSGA3", list, fitness=creator.FitnessSIPANSGA3)


# ---------------------------------------------------------------------------
# Estructuras auxiliares
# ---------------------------------------------------------------------------

@dataclass
class NSGA3Stats:
    generations: int = 0
    generated: int = 0
    feasible: int = 0
    failures: int = 0
    inserted_into_pareto: int = 0
    pareto_size: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, float | int]:
        return {
            "generations": self.generations,
            "generated": self.generated,
            "feasible": self.feasible,
            "failures": self.failures,
            "inserted_into_pareto": self.inserted_into_pareto,
            "pareto_size": self.pareto_size,
            "elapsed_seconds": self.elapsed_seconds,
        }


# ---------------------------------------------------------------------------
# Conversión individuo <-> solución
# ---------------------------------------------------------------------------

def solution_to_individual(sol: Solution):
    """Convierte una Solution factible en un individuo DEAP."""
    ind = creator.IndividualSIPANSGA3(list(sol.student_to_placement))
    ind._solution_cache = sol
    ind._multi_eval_cache = None
    return ind


def individual_to_solution(
    problem,
    individual: Sequence[int],
    rng: random.Random,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    repair_seed: Optional[int] = None,
) -> Tuple[Solution, Dict[str, object]]:
    """
    Convierte un individuo en una Solution factible.

    Estrategia de repair empleada:
    1. sanea el cromosoma (índices válidos y sin duplicados evidentes),
    2. genera una solución factible de respaldo,
    3. intenta preservar asignaciones heredadas que encajen con las plazas ocupadas
       en la solución de respaldo mediante intercambios entre estudiantes,
    4. valida y, si fuera necesario, reconstruye la capa plaza->profesor.
    """
    desired = _sanitize_individual(problem, individual, rng)
    sol = _repair_from_template(problem, desired, rng, repair_seed=repair_seed)

    multi_eval = evaluate_solution_multi(
        sol,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )
    if not multi_eval.get("valid", False):
        raise ValueError("La solución reparada no es válida")

    return sol, multi_eval


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def _sanitize_individual(problem, individual: Sequence[int], rng: random.Random) -> List[int]:
    """
    Limpieza básica del cromosoma:
    - longitud correcta
    - genes enteros
    - índices de plaza válidos
    - elimina duplicados evidentes dejando solo una ocurrencia
    """
    n = problem.n_students
    genes = list(individual[:n]) + [-1] * max(0, n - len(individual))

    cleaned = [-1] * n
    used = set()

    order = list(range(n))
    rng.shuffle(order)
    for i in order:
        g = genes[i]
        try:
            j = int(g)
        except Exception:
            continue
        if 0 <= j < problem.n_placements and j not in used:
            cleaned[i] = j
            used.add(j)

    return cleaned


def _repair_from_template(problem, desired: Sequence[int], rng: random.Random, repair_seed: Optional[int] = None) -> Solution:
    """
    Repair robusto y simple:
    - crea una solución factible completa con el generador actual,
    - intenta preservar el máximo posible de asignaciones heredadas siempre que la
      plaza deseada ya esté presente en el conjunto de plazas ocupadas del template,
      usando intercambios entre estudiantes,
    - reconstruye profesores si fuera necesario.

    Nota: este repair prioriza factibilidad y robustez sobre agresividad genética.
    """
    template = generate_random_feasible_fixing(problem, seed=repair_seed)

    # Mapa plaza -> estudiante en la solución factible de respaldo
    placement_owner = {
        int(j): i
        for i, j in enumerate(template.student_to_placement)
        if j is not None and j != -1
    }

    # Intentar imponer asignaciones heredadas mediante swaps entre estudiantes.
    for i, desired_j in enumerate(desired):
        if desired_j == -1:
            continue
        if desired_j not in placement_owner:
            # Esa plaza no está en el conjunto ocupado del template: se ignora.
            continue

        current_j = template.student_to_placement[i]
        if current_j == desired_j:
            continue

        other = placement_owner[desired_j]
        other_j = template.student_to_placement[other]

        # Swap estudiante i <-> estudiante other
        template.student_to_placement[i] = desired_j
        template.student_to_placement[other] = current_j

        placement_owner[desired_j] = i
        if current_j != -1:
            placement_owner[current_j] = other

    # Por seguridad, comprobar coherencia de la capa estudiante->plaza.
    if not _student_placement_layer_seems_valid(problem, template):
        template = generate_random_feasible_fixing(problem, seed=None if repair_seed is None else repair_seed + 1)

    # Si por alguna razón la capa de profesores se ha roto, reconstruirla.
    if not _professor_layer_valid(problem, template):
        template.placement_to_professor = [-1] * problem.n_placements
        template.professor_load = [0] * problem.n_professors
        ok = _assign_professors_with_repair(problem, template, rng)
        if not ok:
            template = generate_random_feasible_fixing(problem, seed=None if repair_seed is None else repair_seed + 2)

    if not template.validate():
        # Último respaldo totalmente factible
        template = generate_random_feasible_fixing(problem, seed=None if repair_seed is None else repair_seed + 3)

    return template


def _student_placement_layer_seems_valid(problem, sol: Solution) -> bool:
    """Chequeo rápido de la capa estudiante->plaza antes de validar todo."""
    assigned = sol.student_to_placement
    if len(assigned) != problem.n_students:
        return False
    if any(j == -1 for j in assigned):
        return False
    if len(set(assigned)) != len(assigned):
        return False

    # company_load debe ser consistente con las asignaciones
    loads = [0] * problem.n_companies
    for j in assigned:
        if not (0 <= j < problem.n_placements):
            return False
        k = problem.placement_company[j]
        loads[k] += 1

    for k in range(problem.n_companies):
        if loads[k] < problem.company_min[k] or loads[k] > problem.company_max[k]:
            return False

    # Dependencias
    for dep in problem.dependencies:
        if not dep:
            continue
        count = sum(1 for j in dep if j in set(assigned))
        if 0 < count < len(dep):
            return False

    return True


def _professor_layer_valid(problem, sol: Solution) -> bool:
    for j in range(problem.n_placements):
        if sol.placement_filled[j]:
            t = sol.placement_to_professor[j]
            if t == -1 or not (0 <= t < problem.n_professors):
                return False
    for t in range(problem.n_professors):
        if sol.professor_load[t] > problem.prof_capacity[t]:
            return False
    return True


# ---------------------------------------------------------------------------
# Evaluación y toolbox
# ---------------------------------------------------------------------------

def evaluate_individual_factory(problem, normalize_student_dist: bool, normalize_supervision_dist: bool):
    """Devuelve la función evaluate compatible con DEAP."""

    def _evaluate(individual):
        rng = random.Random()
        sol, multi_eval = individual_to_solution(
            problem,
            individual,
            rng=rng,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )
        individual._solution_cache = sol
        individual._multi_eval_cache = multi_eval
        c = multi_eval["components"]
        return (
            float(c["tau_sum"]),
            float(c["eta_sum"]),
            float(c["lbar_sum"]),
            float(c["sigma_sum"]),
        )

    return _evaluate


def build_deap_toolbox(
    problem,
    ref_points,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
):
    toolbox = base.Toolbox()
    toolbox.register(
        "evaluate",
        evaluate_individual_factory(
            problem,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        ),
    )
    toolbox.register("mate", crossover_simple)
    toolbox.register("mutate", mutate_simple)
    toolbox.register("select_survivors", tools.selNSGA3, ref_points=ref_points)
    return toolbox


# ---------------------------------------------------------------------------
# Operadores genéticos
# ---------------------------------------------------------------------------

def crossover_simple(ind1, ind2, rng: Optional[random.Random] = None):
    """
    Cruce simple por máscara de estudiantes.
    Cada estudiante hereda del padre A o B según una máscara aleatoria.
    """
    rng = rng or random
    size = min(len(ind1), len(ind2))
    if size == 0:
        return ind1, ind2

    mask = [rng.random() < 0.5 for _ in range(size)]
    for i, take_from_1 in enumerate(mask):
        if not take_from_1:
            ind1[i], ind2[i] = ind2[i], ind1[i]

    _invalidate_individual(ind1)
    _invalidate_individual(ind2)
    return ind1, ind2


def mutate_simple(individual, problem, rng: Optional[random.Random] = None):
    """
    Mutación simple con dos variantes:
    - move: cambia la plaza deseada de un estudiante
    - swap: intercambia las plazas deseadas entre dos estudiantes
    """
    rng = rng or random
    n = len(individual)
    if n == 0:
        return (individual,)

    if n >= 2 and rng.random() < 0.5:
        i, j = rng.sample(range(n), 2)
        individual[i], individual[j] = individual[j], individual[i]
    else:
        i = rng.randrange(n)
        individual[i] = rng.randrange(problem.n_placements)

    _invalidate_individual(individual)
    return (individual,)


def _invalidate_individual(individual) -> None:
    if hasattr(individual, "fitness") and individual.fitness.valid:
        del individual.fitness.values
    if hasattr(individual, "_solution_cache"):
        individual._solution_cache = None
    if hasattr(individual, "_multi_eval_cache"):
        individual._multi_eval_cache = None


# ---------------------------------------------------------------------------
# Selección de padres
# ---------------------------------------------------------------------------

def select_parents_by_rank(population, k: int, rng: random.Random):
    """
    Selección sencilla de padres basada en frentes no dominados.
    Prioriza mejor rango y desempata aleatoriamente.
    """
    if k <= 0:
        return []
    if not population:
        raise ValueError("Population is empty")

    fronts = tools.sortNondominated(population, len(population), first_front_only=False)
    rank_by_id = {}
    for rank, front in enumerate(fronts):
        for ind in front:
            rank_by_id[id(ind)] = rank

    selected = []
    tournsize = 2
    for _ in range(k):
        aspirants = rng.sample(population, min(tournsize, len(population)))
        best = aspirants[0]
        best_rank = rank_by_id[id(best)]
        for cand in aspirants[1:]:
            cand_rank = rank_by_id[id(cand)]
            if cand_rank < best_rank:
                best = cand
                best_rank = cand_rank
            elif cand_rank == best_rank and rng.random() < 0.5:
                best = cand
                best_rank = cand_rank
        selected.append(best)
    return selected


# ---------------------------------------------------------------------------
# Inicialización y evaluación de población
# ---------------------------------------------------------------------------

def init_population(problem, population_size: int, base_seed: Optional[int] = None):
    population = []
    for idx in range(population_size):
        seed = None if base_seed is None else base_seed + idx
        sol = generate_random_feasible_fixing(problem, seed=seed)
        population.append(solution_to_individual(sol))
    return population


def evaluate_population(toolbox, population, stats: NSGA3Stats) -> None:
    for ind in population:
        if ind.fitness.valid:
            continue
        try:
            fit = toolbox.evaluate(ind)
            ind.fitness.values = fit
            stats.generated += 1
            stats.feasible += 1
        except Exception:
            stats.generated += 1
            stats.failures += 1
            raise


# ---------------------------------------------------------------------------
# Pareto externo
# ---------------------------------------------------------------------------

def _register_individual_in_external_pareto(
    individual,
    pareto_set,
    weights: ObjectiveWeights,
    iteration: int,
    seed: Optional[int],
    normalize_student_dist: bool,
    normalize_supervision_dist: bool,
):
    sol = getattr(individual, "_solution_cache", None)
    multi_eval = getattr(individual, "_multi_eval_cache", None)

    if sol is None or multi_eval is None:
        rng = random.Random(seed)
        sol, multi_eval = individual_to_solution(
            sol.problem if sol is not None else None,
            individual,
            rng=rng,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
            repair_seed=seed,
        )

    scalar_eval = evaluate_solution_scalar(
        sol,
        weights,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )

    eval_result = copy.deepcopy(multi_eval)
    eval_result["objective_value"] = scalar_eval["objective_value"]

    cand = EvaluatedSolution(sol=sol, evaluation=eval_result, iteration=iteration, seed=seed)
    pareto_set, was_inserted, _ = update_pareto_set(pareto_set, cand)
    return pareto_set, was_inserted


# ---------------------------------------------------------------------------
# Algoritmo principal
# ---------------------------------------------------------------------------

def run_nsga3(
    problem,
    weights: ObjectiveWeights,
    population_size: int = 50,
    offspring_size: int = 50,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.2,
    time_limit_seconds: float = 60.0,
    max_generations: Optional[int] = None,
    divisions: int = 12,
    max_pareto_size: Optional[int] = None,
    base_seed: Optional[int] = None,
    normalize_student_dist: bool = True,
    normalize_supervision_dist: bool = True,
    verbose: bool = True,
):
    """
    Ejecuta NSGA-III sobre el problema SIPA modificado.

    Devuelve:
    - población final
    - Pareto global externo
    - estadísticas
    - reference points usados
    """
    if population_size <= 0:
        raise ValueError("population_size must be > 0")
    if offspring_size <= 0:
        raise ValueError("offspring_size must be > 0")
    if not (0.0 <= crossover_prob <= 1.0):
        raise ValueError("crossover_prob must be in [0,1]")
    if not (0.0 <= mutation_prob <= 1.0):
        raise ValueError("mutation_prob must be in [0,1]")
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")

    weights.validate()
    rng = random.Random(base_seed)
    ref_points = tools.uniform_reference_points(nobj=4, p=divisions)
    toolbox = build_deap_toolbox(
        problem,
        ref_points,
        normalize_student_dist=normalize_student_dist,
        normalize_supervision_dist=normalize_supervision_dist,
    )

    start = time.time()
    stats = NSGA3Stats()
    pareto_set = []

    # Población inicial factible
    population = init_population(problem, population_size, base_seed=base_seed)
    evaluate_population(toolbox, population, stats)

    # Registrar población inicial en el Pareto externo
    for idx, ind in enumerate(population):
        seed = None if base_seed is None else base_seed + idx
        pareto_set, was_inserted = _register_individual_in_external_pareto(
            ind,
            pareto_set,
            weights,
            iteration=0,
            seed=seed,
            normalize_student_dist=normalize_student_dist,
            normalize_supervision_dist=normalize_supervision_dist,
        )
        if was_inserted:
            stats.inserted_into_pareto += 1

    # Asignar orden inicial coherente con NSGA-III
    population = toolbox.select_survivors(population, population_size)

    generation = 0
    while True:
        elapsed = time.time() - start
        if elapsed >= time_limit_seconds:
            break
        if max_generations is not None and generation >= max_generations:
            break

        generation += 1
        stats.generations = generation

        # Selección de padres
        parents = select_parents_by_rank(population, offspring_size, rng)

        # Variación
        offspring = []
        i = 0
        while len(offspring) < offspring_size:
            p1 = creator.IndividualSIPANSGA3(list(parents[i % len(parents)]))
            p2 = creator.IndividualSIPANSGA3(list(parents[(i + 1) % len(parents)]))
            i += 2

            if rng.random() < crossover_prob:
                p1, p2 = crossover_simple(p1, p2, rng=rng)

            if rng.random() < mutation_prob:
                mutate_simple(p1, problem, rng=rng)
            if rng.random() < mutation_prob and len(offspring) + 1 < offspring_size:
                mutate_simple(p2, problem, rng=rng)

            offspring.append(p1)
            if len(offspring) < offspring_size:
                offspring.append(p2)

        # Evaluar descendencia
        try:
            evaluate_population(toolbox, offspring, stats)
        except Exception:
            # si un descendiente falla en evaluación, se regenera población de respaldo mínima
            repaired_offspring = []
            for idx in range(len(offspring)):
                sol = generate_random_feasible_fixing(problem, seed=None if base_seed is None else base_seed + generation * 10000 + idx)
                ind = solution_to_individual(sol)
                fit = toolbox.evaluate(ind)
                ind.fitness.values = fit
                repaired_offspring.append(ind)
                stats.generated += 1
                stats.feasible += 1
            offspring = repaired_offspring

        # Registrar descendencia en el Pareto externo
        for idx, ind in enumerate(offspring):
            seed = None if base_seed is None else base_seed + generation * 10000 + idx
            pareto_set, was_inserted = _register_individual_in_external_pareto(
                ind,
                pareto_set,
                weights,
                iteration=generation,
                seed=seed,
                normalize_student_dist=normalize_student_dist,
                normalize_supervision_dist=normalize_supervision_dist,
            )
            if was_inserted:
                stats.inserted_into_pareto += 1

        if max_pareto_size is not None and len(pareto_set) > max_pareto_size:
            pareto_set = prune_pareto_set_by_size(pareto_set, max_pareto_size)

        # Reemplazo ambiental NSGA-III
        combined = population + offspring
        population = toolbox.select_survivors(combined, population_size)

        if verbose and generation % 10 == 0:
            print(
                f"[gen={generation}] "
                f"generated={stats.generated} feasible={stats.feasible} failures={stats.failures} "
                f"pareto_size={len(pareto_set)}"
            )

    stats.pareto_size = len(pareto_set)
    stats.elapsed_seconds = time.time() - start

    return {
        "population": population,
        "pareto_set": pareto_set,
        "stats": stats.to_dict(),
        "reference_points": ref_points,
    }


__all__ = [
    "build_deap_toolbox",
    "crossover_simple",
    "evaluate_individual_factory",
    "individual_to_solution",
    "init_population",
    "mutate_simple",
    "run_nsga3",
    "select_parents_by_rank",
    "solution_to_individual",
]
