# Gestiona el conjunto de soluciones no dominadas: recibe soluciones ya evaluadas y decide cuáles se quedan en el frente de Pareto y cuáles se descartan.


# Librerías
from dataclasses import dataclass
from typing import Dict, Any


# Definición de objetivos
OBJECTIVE_SENSE = {
    "tau_sum": "max",
    "eta_sum": "max",
    "lbar_sum": "min",
    "sigma_sum": "min"
}


@dataclass
class EvaluatedSolution:
    sol: Any # Objeto Solution
    evaluation: Dict[str, Any] # Resultado de evaluate_solution_multi + valor escalar
    iteration: int # En qué iteración se generó
    seed: int | None = None

    @property # Acceso rápido a los 4 componentes de la f.o.
    def components(self) -> Dict[str, float]:
        return self.evaluation["components"]


def get_objective_vector(evaluation):
                        # Diccionario resultante de la evaluación
    """
    Convierte la evaluación en un vector ordenado de objetivos
    """
    c = evaluation["components"]
    return (
        float(c["tau_sum"]),
        float(c["eta_sum"]),
        float(c["lbar_sum"]),
        float(c["sigma_sum"]),
    ) # Tupla con las 4 componentes


def dominance_relation(eval_a, eval_b):
                       # Evaluación de dos soluciones
    """
    Compara dos evaluaciones multiobjetivo para saber si:
    a domina b, b domina a, son iguales o no son comparables
    """
    a = eval_a["components"]
    b = eval_b["components"]

    # Para que a domine b
    a_better_or_equal_all = True 
    a_strictly_better_one = False

    # Para que b domine a
    b_better_or_equal_all = True
    b_strictly_better_one = False

    # Itera por los 4 objetivos usando su sentido (max o min)
    for obj, sense in OBJECTIVE_SENSE.items():
        # Valor de a y b para la componente iterada
        va = float(a[obj])
        vb = float(b[obj])

        if sense == "max": # Caso max
            if va < vb:
                a_better_or_equal_all = False
            elif va > vb:
                a_strictly_better_one = True

            if vb < va:
                b_better_or_equal_all = False
            elif vb > va:
                b_strictly_better_one = True

        elif sense == "min": # Caso min
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

    if a_better_or_equal_all and a_strictly_better_one: # a domina b
        return "a_dominates_b"
    if b_better_or_equal_all and b_strictly_better_one: # b domina a
        return "b_dominates_a"
    if not a_strictly_better_one and not b_strictly_better_one: # Son iguales
        return "equal"
    return "non_comparable" # Si no pasa nada de lo anterior, no son comparables


def update_pareto_set(pareto_set, candidate):
                     # Conjunto pareto actual, nueva solución a evaluar
    """
    Actualiza el Pareto set con una nueva solución.
    """
    survivors = []
    candidate_dominated = False
    removed_count = 0

    # Comparación contra cada solución actual
    for current in pareto_set:
        rel = dominance_relation(candidate.evaluation, current.evaluation)

        # Si la candidata domina a current, esa solución se elimina del Pareto set
        if rel == "a_dominates_b":
            removed_count += 1
            continue # Salta de iteración, que a esta ya le ha ganado, por lo que no se añade a current
        
        # Si no la domina, marca que la candidata no debe entrar
        if rel == "b_dominates_a" or rel == "equal":
            candidate_dominated = True

        survivors.append(current) # Current ha sobrevivido 

    if candidate_dominated: 
        return survivors, False, removed_count
        # nuevo conjunto pareto, flag que indica que el candidato NO se ha añadido, cuántas soluciones del cjto pareto anterior se han eliminado (0)

    survivors.append(candidate) # candidate no ha sido vencida por ninguna current ni es igual a otra --> o ha ganado o no es comparable, por lo que se puede añadir
    return survivors, True, removed_count
           # nuevo conjunto pareto, flag que indica que el candidato se ha añadido, cuántas soluciones del cjto pareto anterior se han eliminado


def prune_pareto_set_by_size(pareto_set, max_size):
                             # Conjunto pareto actual, tamaño máximo permitido del cjto
    """
    Poda por tamaño el cjto tal que:
    - Si el conjunto supera max_size, elimina repetidamente la solución más "parecida" a otra
    - La similitud se calcula en el espacio normalizado de objetivos
    """
    # Validaciones iniciales
    if max_size <= 0:
        raise ValueError("max_size must be > 0")

    if len(pareto_set) <= max_size:
        return pareto_set # No ha habido que recortar nada

    # Bucle de la poda --> hasta que el tamaño final sea correcto
    current = pareto_set[:]
    while len(current) > max_size:
        # Construcción y normalización de los vectores de objetivos 
        vectors = [get_objective_vector(x.evaluation) for x in current]
        norm_vectors = _normalize_vectors_for_distance(vectors)

        # Buscar el par más parecido para eliminar uno
        min_dist = float("inf")
        pair = None

        for i in range(len(norm_vectors)):
            for j in range(i + 1, len(norm_vectors)):
                d = _euclidean_distance(norm_vectors[i], norm_vectors[j])
                if d < min_dist:
                    min_dist = d
                    pair = (i, j)

        if pair is None: # por si hay error y no se encuentran dos soluciones similares
            current.pop()
            continue
        
        i, j = pair

        # Desempate --> quitamos la de peor objective_value escalar
        oi = float(current[i].evaluation.get("objective_value", 0.0))
        oj = float(current[j].evaluation.get("objective_value", 0.0))

        remove_idx = i if oi <= oj else j
        current.pop(remove_idx)

    return current # Pareto recortado


def _normalize_vectors_for_distance(vectors):
                                    # Lista de vectores objetivo a normalizar
    """
    Normaliza cada objetivo de la f.o. de todos los vectores (resultados del
    cjto pareto) usando min-max global
    """
    # Mínimo y máximo de cada objetivo
    cols = list(zip(*vectors))
    mins = [min(col) for col in cols]
    maxs = [max(col) for col in cols]

    # Normalizar cada valor mediante min-max
    normalized = []
    for v in vectors:
        row = []
        for x, mn, mx in zip(v, mins, maxs):
            if mx > mn:
                row.append((x - mn) / (mx - mn)) # min-max
            else: # mx == mn
                row.append(0.0) # Todos a 0 porque max = min
        normalized.append(tuple(row))
    return normalized # vector, pero normalizada componente a componente entre 0 y 1


def _euclidean_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 # distancia euclídea entre los vectores a y b --> cuánto se parecen