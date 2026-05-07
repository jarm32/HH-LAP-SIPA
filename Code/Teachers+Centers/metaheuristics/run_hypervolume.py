# Lee archivos de resultados generados por las heurísticas --> extrae sus frentes Pareto y calcula el hipervolumen para comparar la calidad de los algoritmos

# cd C:\Code\VRAIN-practicas\Code\Teachers+Centers
# python -m metaheuristics.run_hypervolume

# Librerías
import re
import numpy as np

from tools.hypervolume import normalize_for_hypervolume, compute_hypervolume_deap


def load_pareto_from_txt(filepath):
                        # ruta del archivo .txt de resultados generado por save_results_to_txt
    """
    Lee un archivo y extrae los puntos Pareto:
    tau, eta, lbar, sigma

    Lee un archivo de resultados y extrae únicamente las líneas que contienen valores de soluciones Pareto
    """
    points = []

    # Patrón que busca las líneas de los objetivos
    pattern = re.compile(
        r"tau=([0-9eE+\-.]+),\s*"
        r"eta=([0-9eE+\-.]+),\s*"
        r"lbar=([0-9eE+\-.]+),\s*"
        r"sigma=([0-9eE+\-.]+)"
    )

    with open(filepath, "r", encoding="utf-8") as f:
        
        # Recorre el archivo línea por línea y comprueba si la línea contiene valores Pareto
        for line in f:
            match = pattern.search(line)
            
            # Si la línea coincide con el patrón, convierte los cuatro valores objetivo a float
            if match:
                tau = float(match.group(1))
                eta = float(match.group(2))
                lbar = float(match.group(3))
                sigma = float(match.group(4))
                points.append([tau, eta, lbar, sigma])

    return np.asarray(points, dtype=float) # matriz NumPy donde cada fila es una solución Pareto y las columnas son [tau, eta, lbar, sigma]


def compute_hv_from_result_files(files_by_algorithm):
                                # diccionario que asocia cada algoritmo con su archivo de resultados
    """
    Carga los frentes Pareto desde varios archivos, calcula cotas globales comunes 
    y obtiene el hipervolumen de cada algoritmo
    """
    points_by_algorithm = {}

    # Carga el frente Pareto de cada archivo y lo guarda asociado al nombre del algoritmo
    for alg, filepath in files_by_algorithm.items():
        points = load_pareto_from_txt(filepath)
        points_by_algorithm[alg] = points  

    # Filtra los frentes vacíos
    all_non_empty = [p for p in points_by_algorithm.values() if len(p) > 0]
    if not all_non_empty:
        raise ValueError("No se han encontrado puntos Pareto en los archivos.")

    # Une todos los puntos Pareto de todos los algoritmos y calcula los mínimos y máximos globales por objetivo
    all_points = np.vstack(all_non_empty)
    mins = all_points.min(axis=0)
    maxs = all_points.max(axis=0)

    hv_by_algorithm = {}
    
    # Recorre cada algoritmo y su frente Pareto ya cargado
    for alg, points in points_by_algorithm.items():

        # Si un algoritmo no tiene soluciones Pareto, se le asigna hipervolumen 0
        if len(points) == 0:
            hv_by_algorithm[alg] = 0.0
            continue
        
        # Normaliza el frente del algoritmo usando las mismas cotas globales que el resto
        normalized = normalize_for_hypervolume(points, mins, maxs)

        # Calcula el hipervolumen del frente normalizado y lo guarda
        hv_by_algorithm[alg] = compute_hypervolume_deap(normalized)

    return hv_by_algorithm, mins, maxs # hipervolumen de cada algoritmo, mínimos y máximos globales usados para normalizar


def main():
    for i in [5,20,40,60]:
        for j in range(4):
            instance = f"problem_instance_ext_{i}0_{j}.txt"

            files_by_algorithm = {
                "random": f"results/statistics/statistics_random_{instance}",
                "nsga3": f"results/statistics/statistics_nsga3_{instance}",
                "grasp":f"results/statistics/statistics_random_{instance}",
                "hh_lap":f"results/statistics/statistics_hh_lap_sipa_{instance}"
            }

            hv_by_algorithm, mins, maxs = compute_hv_from_result_files(files_by_algorithm)

            print("\n=== HYPERVOLUME COMPARISON ===")
            print(f"Instance: {instance}")
            print(f"Global mins: {mins}")
            print(f"Global maxs: {maxs}")

            for alg, hv in sorted(hv_by_algorithm.items(), key=lambda x: x[1], reverse=True):
                print(f"{alg}: HV = {hv:.6f}")


if __name__ == "__main__":
    main()