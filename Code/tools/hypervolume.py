# Calcula el hipervolumen de los frentes de Pareto generados por distintas heurísticas.
# Normaliza globalmente los objetivos, transforma todos a maximización y devuelve un indicador comparable de calidad del frente

# Librerías
import numpy as np
from deap.tools._hypervolume import hv


# Objetivos en orden
OBJECTIVES = ["tau_sum", "eta_sum", "lbar_sum", "sigma_sum"]

def pareto_set_to_matrix(pareto_set):
                        # Lista de soluciones evaluadas del frente Pareto
    """
    Convierte el conjunto Pareto, que está guardado como objetos EvaluatedSolution, 
    en una matriz numérica para procesar
    """
    # Cada fila es una solución, las columnas son [tau_sum, eta_sum, lbar_sum, sigma_sum]
    rows = []
    for item in pareto_set:
        c = item.evaluation["components"]
        rows.append([float(c[obj]) for obj in OBJECTIVES])

    return np.asarray(rows, dtype=float) # Convierte la lista en una matriz NumPy de tipo float


def compute_global_bounds(pareto_sets):
                         # Lista de frentes Pareto, cada uno con su formato original (lista de EvaluatedSolution)
    """
    Calcula los mínimos y máximos comunes usando todos los frentes que se quieren comparar
    para normalización global
    """
    # Convierte cada frente Pareto en una matriz numérica
    all_points = []
    for pareto_set in pareto_sets:
        mat = pareto_set_to_matrix(pareto_set)
        # Solo añade frentes que tengan al menos una solución
        if len(mat) > 0:
            all_points.append(mat)

    # Si no hay puntos en ningún frente, no se pueden calcular bounds
    if not all_points:
        raise ValueError("No hay puntos Pareto para calcular bounds.")

    # Concatena todas las matrices de puntos para calcular los mínimos y máximos globales
    all_points = np.vstack(all_points)
    mins = all_points.min(axis=0)
    maxs = all_points.max(axis=0)

    return mins, maxs # Devuelve dos arrays: mins[i] es el mínimo valor del objetivo i entre todos los frentes, y maxs[i] es el máximo valor del objetivo i entre todos los frentes


def normalize_for_hypervolume(points, mins, maxs):
                             # Matriz de soluciones de un frente Pareto concreto, mínimos y máximos globales de los objetivos
    """
    Normaliza los puntos a [0,1] usando las cotas globales y convierte lbar_sum y 
    sigma_sum para que valores bajos pasen a ser valores altos (para que todo se pueda maximizar)
    """
    # Conversión a arrays NumPy para asegurar operaciones numéricas correctas
    points = np.asarray(points, dtype=float)
    mins = np.asarray(mins, dtype=float)
    maxs = np.asarray(maxs, dtype=float)

    # Rango global de cada objetivo: max - min
    denom = maxs - mins
    norm = np.zeros_like(points, dtype=float)

    # Normalización min-max por objetivo
    for col in range(points.shape[1]):
        if denom[col] > 1e-12:
            norm[:, col] = (points[:, col] - mins[col]) / denom[col]
        else:
            # Si un objetivo no varía entre algoritmos, no debe afectar a la comparación
            norm[:, col] = 1.0

    # lbar_sum y sigma_sum son de minimización, por eso se invierten
    # Si alguno no varía, se deja a 1.0 para que no penalice el hipervolumen
    if denom[2] > 1e-12:
        norm[:, 2] = 1.0 - norm[:, 2]
    else:
        norm[:, 2] = 1.0

    if denom[3] > 1e-12:
        norm[:, 3] = 1.0 - norm[:, 3]
    else:
        norm[:, 3] = 1.0

    return np.clip(norm, 0.0, 1.0) # Asegura que no haya valores fuera de [0,1] debido a redondeos


def compute_hypervolume_deap(normalized_points, reference_margin = 0.1):
                            # Matriz de puntos normalizados para un frente Pareto concreto, margen de referencia
    """
    Calcula el hipervolumen de un frente Pareto usando DEAP
    """
    # Si está vacío, hipervolumen = 0
    if len(normalized_points) == 0:
        return 0.0

    # DEAP calcula hipervolumen en minimización, por eso se cambia el signo de los puntos --> punto ideal actual [-1, -1, -1, -1]
    minimization_points = -np.asarray(normalized_points, dtype=float)
    
    # Punto de referencia ligeramente peor que el peor punto normalizado
    reference_point = np.full(normalized_points.shape[1], reference_margin)
    
    # Hipervolumen bruto
    raw_hv = float(hv.hypervolume(minimization_points, reference_point))

    # Máximo volumen posible con puntos normalizados en [0,1] y margen reference_margin
    max_possible_hv = (1.0 + reference_margin) ** normalized_points.shape[1]

    return raw_hv / max_possible_hv # Hipervolumen reescalado a [0,1]


def compare_hypervolumes(results_by_algorithm):
                        # diccionario que asocia cada heurística con su Pareto set
    """
    Compara varios frentes Pareto calculando el hipervolumen de cada uno. 
    Antes de calcularlo, usa mínimos y máximos globales comunes para que la comparación entre heurísticas sea justa
    """
    # Inicialización de parámetros
    pareto_sets = list(results_by_algorithm.values())
    mins, maxs = compute_global_bounds(pareto_sets)
    hv_by_algorithm = {}

    # Recorre cada algoritmo junto con su frente Pareto
    for name, pareto_set in results_by_algorithm.items():

        # Convierte el Pareto set del algoritmo actual en una matriz numérica de objetivos
        points = pareto_set_to_matrix(pareto_set)

        # Si ese algoritmo no tiene soluciones en su Pareto, se le asigna hipervolumen 0 
        if len(points) == 0:
            hv_by_algorithm[name] = 0.0
            continue
        
        # Normaliza el frente Pareto actual usando los mínimos y máximos globales comunes
        normalized = normalize_for_hypervolume(points, mins, maxs)

        # Calcula el hipervolumen del frente normalizado y lo guarda asociado al nombre del algoritmo
        hv_by_algorithm[name] = compute_hypervolume_deap(normalized)

    return hv_by_algorithm # Diccionario con el hipervolumen de cada heurística