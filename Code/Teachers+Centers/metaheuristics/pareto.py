from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


# Orden de objetivos del problema:
#   - tau_sum   : maximizar
#   - eta_sum   : maximizar
#   - lbar_sum  : minimizar
#   - sigma_sum : minimizar

OBJECTIVE_SENSE = {
    "tau_sum": "max",
    "eta_sum": "max",
    "lbar_sum": "min",
    "sigma_sum": "min",
}


@dataclass
class EvaluatedSolution:
    sol: Any
    evaluation: Dict[str, Any]
    iteration: int
    seed: int | None = None

    @property
    def components(self) -> Dict[str, float]:
        return self.evaluation["components"]


def get_objective_vector(evaluation: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """
    Devuelve el vector objetivo en orden fijo:
    (tau_sum, eta_sum, lbar_sum, sigma_sum)
    """
    c = evaluation["components"]
    return (
        float(c["tau_sum"]),
        float(c["eta_sum"]),
        float(c["lbar_sum"]),
        float(c["sigma_sum"]),
    )


def dominance_relation(eval_a: Dict[str, Any], eval_b: Dict[str, Any]) -> str:
    """
    Compara dos evaluaciones multiobjetivo.

    Devuelve:
      - "a_dominates_b"
      - "b_dominates_a"
      - "equal"
      - "non_comparable"
    """
    a = eval_a["components"]
    b = eval_b["components"]

    a_better_or_equal_all = True
    a_strictly_better_one = False

    b_better_or_equal_all = True
    b_strictly_better_one = False

    for obj, sense in OBJECTIVE_SENSE.items():
        va = float(a[obj])
        vb = float(b[obj])

        if sense == "max":
            if va < vb:
                a_better_or_equal_all = False
            elif va > vb:
                a_strictly_better_one = True

            if vb < va:
                b_better_or_equal_all = False
            elif vb > va:
                b_strictly_better_one = True

        elif sense == "min":
            if va > vb:
                a_better_or_equal_all = False
            elif va < vb:
                a_strictly_better_one = True

            if vb > va:
                b_better_or_equal_all = False
            elif vb < va:
                b_strictly_better_one = True

        else:
            raise ValueError(f"Unknown sense for objective {obj}: {sense}")

    if a_better_or_equal_all and a_strictly_better_one:
        return "a_dominates_b"
    if b_better_or_equal_all and b_strictly_better_one:
        return "b_dominates_a"
    if not a_strictly_better_one and not b_strictly_better_one:
        return "equal"
    return "non_comparable"


def update_pareto_set(
    pareto_set: List[EvaluatedSolution],
    candidate: EvaluatedSolution,
) -> tuple[List[EvaluatedSolution], bool, int]:
    """
    Actualiza el Pareto set con una nueva solución.

    Devuelve:
      - nuevo pareto_set
      - inserted: bool
      - removed_count: int
    """
    survivors: List[EvaluatedSolution] = []
    candidate_dominated = False
    removed_count = 0

    for current in pareto_set:
        rel = dominance_relation(candidate.evaluation, current.evaluation)

        if rel == "a_dominates_b":
            removed_count += 1
            continue

        if rel == "b_dominates_a" or rel == "equal":
            candidate_dominated = True

        survivors.append(current)

    if candidate_dominated:
        return survivors, False, removed_count

    survivors.append(candidate)
    return survivors, True, removed_count


def prune_pareto_set_by_size(
    pareto_set: List[EvaluatedSolution],
    max_size: int,
) -> List[EvaluatedSolution]:
    """
    Poda simple por tamaño.

    Estrategia:
    - si el conjunto supera max_size,
      elimina repetidamente la solución más "parecida" a otra.
    - La similitud se calcula en el espacio normalizado de objetivos.

    Es una poda sencilla de diversidad, suficiente para baseline.
    """
    if max_size <= 0:
        raise ValueError("max_size must be > 0")

    if len(pareto_set) <= max_size:
        return pareto_set

    current = pareto_set[:]

    while len(current) > max_size:
        vectors = [get_objective_vector(x.evaluation) for x in current]
        norm_vectors = _normalize_vectors_for_distance(vectors)

        min_dist = float("inf")
        pair = None

        for i in range(len(norm_vectors)):
            for j in range(i + 1, len(norm_vectors)):
                d = _euclidean_distance(norm_vectors[i], norm_vectors[j])
                if d < min_dist:
                    min_dist = d
                    pair = (i, j)

        if pair is None:
            current.pop()
            continue

        i, j = pair

        # desempate: quitamos la de peor objective_value escalar
        oi = float(current[i].evaluation.get("objective_value", 0.0))
        oj = float(current[j].evaluation.get("objective_value", 0.0))

        remove_idx = i if oi <= oj else j
        current.pop(remove_idx)

    return current


def _normalize_vectors_for_distance(
    vectors: List[Tuple[float, float, float, float]]
) -> List[Tuple[float, float, float, float]]:
    cols = list(zip(*vectors))
    mins = [min(col) for col in cols]
    maxs = [max(col) for col in cols]

    normalized = []
    for v in vectors:
        row = []
        for x, mn, mx in zip(v, mins, maxs):
            if mx > mn:
                row.append((x - mn) / (mx - mn))
            else:
                row.append(0.0)
        normalized.append(tuple(row))
    return normalized


def _euclidean_distance(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5