# -*- coding: utf-8 -*-
# Lee los frentes Pareto generados por run_general.py en results/pareto/ y calcula el hipervolumen (algoritmo + instancia + run_id)
# Después genera un resumen (algoritmo + instancia), con archivos de salida results/hypervolume/hypervolume_by_run.csv y results/hypervolume/hypervolume_summary.csv

# Librerías
import argparse
import csv
import glob
import os
import re
import numpy as np

from tools.hypervolume import normalize_for_hypervolume, compute_hypervolume_deap


ALGORITHMS = ["random", "nsga3", "grasp", "hh_lap_v0", "hh_lap_v1"]

# Se asegura de que existe el directorio
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Lee un CSV generado por run_general.py y extrae tau_sum, eta_sum, lbar_sum, sigma_sum
def load_pareto_from_csv(filepath):
    """
    Lee un CSV generado por run_general.py y extrae:
    tau_sum, eta_sum, lbar_sum, sigma_sum
    """
    points = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            tau = float(row["tau_sum"])
            eta = float(row["eta_sum"])
            lbar = float(row["lbar_sum"])
            sigma = float(row["sigma_sum"])
            points.append([tau, eta, lbar, sigma])

    return np.asarray(points, dtype=float)

# Extrae algoritmo, instancia y run_id de un nombre de archivo generado por run_general.py
def parse_pareto_filename(filepath):
    """
    Espera nombres generados por run_general.py:

    random__problem_instance_ext_200_0__run_00.csv
    nsga3__problem_instance_ext_1000_3__run_29.csv

    Devuelve:
    algorithm, instance_name, run_id
    """
    filename = os.path.basename(filepath)

    m = re.match(r"(.+)__(problem_instance_ext_\d+_\d+)__run_(\d+)\.csv$", filename)

    if not m:
        return None

    algorithm = m.group(1)
    instance_name = m.group(2) + ".txt"
    run_id = int(m.group(3))

    return algorithm, instance_name, run_id

# Extrae el número de estudiantes de un nombre de instancia
def parse_n_students(instance_name):
    m = re.search(r"problem_instance_ext_(\d+)_", instance_name)
    if not m:
        return None
    return int(m.group(1))

# Descubre todos los CSV de Pareto generados por run_general.py, filtrando por algoritmo y tamaño si se especifica
def discover_pareto_files(pareto_dir, algorithms=None, sizes=None):
    pattern = os.path.join(pareto_dir, "*.csv")
    files = sorted(glob.glob(pattern))

    records = []

    algorithms_set = set(algorithms) if algorithms else None
    sizes_set = set(sizes) if sizes else None

    for filepath in files:
        parsed = parse_pareto_filename(filepath)
        if parsed is None:
            continue

        algorithm, instance_name, run_id = parsed
        n_students = parse_n_students(instance_name)

        if algorithms_set is not None and algorithm not in algorithms_set:
            continue

        if sizes_set is not None and n_students not in sizes_set:
            continue

        records.append({
            "algorithm": algorithm,
            "instance": instance_name,
            "n_students": n_students,
            "run_id": run_id,
            "filepath": filepath,
        })

    return records

# Calcula cotas globales por instancia (Para que los hipervolúmenes de los 30 runs sean comparables, usamos las mismas cotas para todos los algoritmos y todos los runs de una misma instancia)
def compute_instance_bounds(records):
    bounds_by_instance = {}

    instances = sorted(set(r["instance"] for r in records))

    for instance in instances:
        all_points = []

        for r in records:
            if r["instance"] != instance:
                continue

            points = load_pareto_from_csv(r["filepath"])
            if len(points) > 0:
                all_points.append(points)

        if not all_points:
            continue

        merged = np.vstack(all_points)
        mins = merged.min(axis=0)
        maxs = merged.max(axis=0)

        bounds_by_instance[instance] = {
            "mins": mins,
            "maxs": maxs,
        }

    return bounds_by_instance

# Calcula HV para cada archivo: algoritmo + instancia + run_id
def compute_hypervolume_by_run(records, bounds_by_instance):
    """
    Calcula HV para cada archivo:
    algoritmo + instancia + run_id
    """
    rows = []

    for r in records:
        instance = r["instance"]

        if instance not in bounds_by_instance:
            hv = 0.0
            n_points = 0
            mins = ["", "", "", ""]
            maxs = ["", "", "", ""]
        else:
            points = load_pareto_from_csv(r["filepath"])
            n_points = len(points)

            mins = bounds_by_instance[instance]["mins"]
            maxs = bounds_by_instance[instance]["maxs"]

            if n_points == 0:
                hv = 0.0
            else:
                normalized = normalize_for_hypervolume(points, mins, maxs)
                hv = compute_hypervolume_deap(normalized)

        rows.append({
            "algorithm": r["algorithm"],
            "instance": r["instance"],
            "n_students": r["n_students"],
            "run_id": r["run_id"],
            "pareto_points": n_points,
            "hypervolume": float(hv),
            "min_tau": float(mins[0]) if not isinstance(mins[0], str) else "",
            "min_eta": float(mins[1]) if not isinstance(mins[1], str) else "",
            "min_lbar": float(mins[2]) if not isinstance(mins[2], str) else "",
            "min_sigma": float(mins[3]) if not isinstance(mins[3], str) else "",
            "max_tau": float(maxs[0]) if not isinstance(maxs[0], str) else "",
            "max_eta": float(maxs[1]) if not isinstance(maxs[1], str) else "",
            "max_lbar": float(maxs[2]) if not isinstance(maxs[2], str) else "",
            "max_sigma": float(maxs[3]) if not isinstance(maxs[3], str) else "",
        })

    return rows

# Resume HV por algoritmo + instancia.
def compute_summary(by_run_rows):
    """
    Resume HV por algoritmo + instancia.
    """
    groups = {}

    for row in by_run_rows:
        key = (row["algorithm"], row["instance"], row["n_students"])

        if key not in groups:
            groups[key] = []

        groups[key].append(float(row["hypervolume"]))

    summary_rows = []

    for key in sorted(groups.keys()):
        algorithm, instance, n_students = key
        values = np.asarray(groups[key], dtype=float)

        summary_rows.append({
            "algorithm": algorithm,
            "instance": instance,
            "n_students": n_students,
            "n_runs": len(values),
            "mean_hv": float(np.mean(values)),
            "std_hv": float(np.std(values)),
            "min_hv": float(np.min(values)),
            "max_hv": float(np.max(values)),
        })

    return summary_rows

# Escribe un CSV con los fieldnames y rows dados
def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

def main():
    # Argumentos de la llamada
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--results_dir",
        default="../results",
        help="Carpeta results generada por run_general.py",
    )

    parser.add_argument(
        "--algorithms",
        nargs="*",
        default=ALGORITHMS,
        help="Algoritmos a incluir",
    )

    parser.add_argument(
        "--sizes",
        nargs="*",
        type=int,
        default=None,
        help="Tamaños a incluir. Ejemplo: --sizes 200 400 600",
    )

    args = parser.parse_args()

    results_dir = args.results_dir
    pareto_dir = os.path.join(results_dir, "pareto")
    output_dir = os.path.join(results_dir, "hypervolume")

    ensure_dir(output_dir)

    records = discover_pareto_files(
        pareto_dir=pareto_dir,
        algorithms=args.algorithms,
        sizes=args.sizes,
    )

    if not records:
        raise ValueError("No se encontraron CSV de Pareto en {}".format(pareto_dir))

    bounds_by_instance = compute_instance_bounds(records)

    by_run_rows = compute_hypervolume_by_run(records, bounds_by_instance)
    summary_rows = compute_summary(by_run_rows)

    by_run_path = os.path.join(output_dir, "hypervolume_by_run.csv")
    summary_path = os.path.join(output_dir, "hypervolume_summary.csv")

    by_run_fields = [
        "algorithm",
        "instance",
        "n_students",
        "run_id",
        "pareto_points",
        "hypervolume",
        "min_tau",
        "min_eta",
        "min_lbar",
        "min_sigma",
        "max_tau",
        "max_eta",
        "max_lbar",
        "max_sigma",
    ]

    summary_fields = [
        "algorithm",
        "instance",
        "n_students",
        "n_runs",
        "mean_hv",
        "std_hv",
        "min_hv",
        "max_hv",
    ]

    write_csv(by_run_path, by_run_fields, by_run_rows)
    write_csv(summary_path, summary_fields, summary_rows)

    print("Hypervolume by run saved in: {}".format(by_run_path))
    print("Hypervolume summary saved in: {}".format(summary_path))


if __name__ == "__main__":
    main()