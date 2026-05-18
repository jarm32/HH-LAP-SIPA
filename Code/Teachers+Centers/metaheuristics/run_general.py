# -*- coding: utf-8 -*-
# Lanzador general de experimentos SIPA --> Ejecuta los algoritmos sobre varias instancias, con 30 repeticiones, guardando estadísticas, frente de Pareto, asignaciones y logs
# 30 ejecuciones para cada instancia por algoritmo (30*20*5 = 3000 ejecuciones)

# Librerías
import argparse
import csv
import glob
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime

from tools.problem import load_instance
from tools.evaluator import ObjectiveWeights
from tools.multiobjective_search import random_search_pareto

from metaheuristics.scripts.random_feasible_fixing import generate_random_feasible_fixing
from metaheuristics.scripts.ga_nsga3 import run_nsga3
from metaheuristics.scripts.grasp import run_grasp
from metaheuristics.scripts.hh_lap_sipa_v0 import run_hh_lap_sipa as run_hh_lap_sipa_v0
from metaheuristics.scripts.hh_lap_sipa_v1 import run_hh_lap_sipa_v1


# ----------------------------------------
# Configuración general
# ----------------------------------------

TIME_LIMITS_SECONDS = {
    200: 300,     # 5 min
    400: 450,     # 7.5 min
    600: 450,     # 7.5 min
    800: 600,     # 10 min
    1000: 600,    # 10 min
}

DEFAULT_RUNS = 30

DEFAULT_WEIGHTS = ObjectiveWeights(
    alpha=0.35,
    beta=0.35,
    gamma=0.20,
    delta=0.10,
)

# Semilla base, con cada ejecución --> seed = BASE_SEED + algo dependiente de algoritmo/instancia/run
BASE_SEED = 1234


# ----------------------------------------
# Utilidades generales
# ----------------------------------------

# Devuelve la fecha/hora actual como string formateado, para logs y resultados
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Asegura que una carpeta exista, si no existe la crea
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

#  Agrega una fila a un CSV, creando el archivo con encabezados si no existe
def append_csv_row(path, fieldnames, row):
    file_exists = os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)

# Escribe un diccionario a un archivo JSON con indentación
def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)

# Escribe una línea en el log, con timestamp, y la imprime por consola
def log_line(log_path, message):
    line = "[{}] {}".format(now_str(), message)
    print(line)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# Extrae el número de estudiantes desde nombres como:
def parse_n_students_from_instance_name(instance_name):
    """
    Extrae el número de estudiantes desde nombres como:
    problem_instance_ext_200_0.txt
    problem_instance_ext_1000_3.txt
    """
    m = re.search(r"problem_instance_ext_(\d+)_", instance_name)
    if not m:
        raise ValueError("No se pudo extraer n_students del nombre: {}".format(instance_name))
    return int(m.group(1))

# Construye la semilla
def build_seed(algorithm_name, instance_name, run_id):
    """
    Semilla reproducible y distinta para cada algoritmo/instancia/run.
    Evita usar hash(), porque en Python puede variar entre ejecuciones.
    """
    text = "{}|{}|{}".format(algorithm_name, instance_name, run_id)
    acc = BASE_SEED

    for ch in text:
        acc = (acc * 131 + ord(ch)) % 1000000007

    return acc

# Checkpoint para marcar que una ejecución ya se hizo, con formato --> checkpoints/random__problem_instance_ext_200_0__run_00.done
def result_done_marker(results_dir, algorithm_name, instance_name, run_id):
    checkpoints_dir = os.path.join(results_dir, "checkpoints")
    ensure_dir(checkpoints_dir)

    safe_instance = instance_name.replace(".txt", "")
    filename = "{}__{}__run_{:02d}.done".format(algorithm_name, safe_instance, run_id)

    return os.path.join(checkpoints_dir, filename)

# Verifica si el checkpoint de done existe para esa ejecución
def is_done(results_dir, algorithm_name, instance_name, run_id):
    return os.path.exists(result_done_marker(results_dir, algorithm_name, instance_name, run_id))

# Crea el checkpoint de done para esa ejecución
def mark_done(results_dir, algorithm_name, instance_name, run_id):
    path = result_done_marker(results_dir, algorithm_name, instance_name, run_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write("done_at={}\n".format(now_str()))


# ----------------------------------------
# Guardado de resultados
# ----------------------------------------

STATS_FIELDS = [
    "timestamp",
    "algorithm",
    "instance",
    "n_students",
    "run_id",
    "seed",
    "time_limit_seconds",
    "elapsed_seconds",
    "status",
    "error_message",
    "pareto_size",
    "generated",
    "feasible",
    "failures",
    "inserted_into_pareto",
    "iterations",
    "generations",
    "population_size",
    "offspring_size",
    "reference_points",
]

PARETO_FIELDS = [
    "timestamp",
    "algorithm",
    "instance",
    "n_students",
    "run_id",
    "solution_id",
    "seed",
    "iteration",
    "objective_value",
    "tau_sum",
    "eta_sum",
    "lbar_sum",
    "sigma_sum",
]

# Guarda las estadísticas de una ejecución en un CSV acumulativo, con una fila por ejecución
def save_stats(results_dir, algorithm_name, instance_name, n_students,
               run_id, seed, time_limit_seconds, result, status, error_message):
    statistics_dir = os.path.join(results_dir, "statistics")
    ensure_dir(statistics_dir)

    stats_path = os.path.join(statistics_dir, "statistics_all.csv")

    stats = {}
    if result is not None:
        stats = result.get("stats", {})

    row = {
        "timestamp": now_str(),
        "algorithm": algorithm_name,
        "instance": instance_name,
        "n_students": n_students,
        "run_id": run_id,
        "seed": seed,
        "time_limit_seconds": time_limit_seconds,
        "elapsed_seconds": stats.get("elapsed_seconds", ""),
        "status": status,
        "error_message": error_message,
        "pareto_size": stats.get("pareto_size", ""),
        "generated": stats.get("generated", ""),
        "feasible": stats.get("feasible", ""),
        "failures": stats.get("failures", ""),
        "inserted_into_pareto": stats.get("inserted_into_pareto", ""),
        "iterations": stats.get("iterations", ""),
        "generations": stats.get("generations", ""),
        "population_size": stats.get("population_size", ""),
        "offspring_size": stats.get("offspring_size", ""),
        "reference_points": stats.get("reference_points", ""),
    }

    append_csv_row(stats_path, STATS_FIELDS, row)

# Guarda el frente de Pareto de una ejecución en un CSV, con una fila por solución del frente
def save_pareto(results_dir, algorithm_name, instance_name, n_students,
                run_id, seed, result):
    pareto_dir = os.path.join(results_dir, "pareto")
    ensure_dir(pareto_dir)

    safe_instance = instance_name.replace(".txt", "")
    pareto_path = os.path.join(
        pareto_dir,
        "{}__{}__run_{:02d}.csv".format(algorithm_name, safe_instance, run_id)
    )

    pareto_set = result.get("pareto_set", [])

    with open(pareto_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PARETO_FIELDS)
        writer.writeheader()

        for idx, item in enumerate(pareto_set):
            c = item.evaluation["components"]

            row = {
                "timestamp": now_str(),
                "algorithm": algorithm_name,
                "instance": instance_name,
                "n_students": n_students,
                "run_id": run_id,
                "solution_id": idx,
                "seed": seed,
                "iteration": item.iteration,
                "objective_value": item.evaluation.get("objective_value", ""),
                "tau_sum": c.get("tau_sum", ""),
                "eta_sum": c.get("eta_sum", ""),
                "lbar_sum": c.get("lbar_sum", ""),
                "sigma_sum": c.get("sigma_sum", ""),
            }

            writer.writerow(row)

# Guarda las asignaciones de cada solución del frente de Pareto en un JSON, con toda la información relevante para análisis posteriores
def solution_to_assignment_dict(item, solution_id):
    sol = item.sol

    return {
        "solution_id": solution_id,
        "iteration": item.iteration,
        "seed": item.seed,
        "objective_value": item.evaluation.get("objective_value", None),
        "components": item.evaluation.get("components", {}),
        "student_to_placement": list(sol.student_to_placement),
        "placement_to_professor": list(sol.placement_to_professor),
        "company_load": list(sol.company_load),
        "professor_load": list(sol.professor_load),
    }

# Guarda las asignaciones de cada solución del frente de Pareto en un JSON, con toda la información relevante para análisis posteriores
def save_assignments(results_dir, algorithm_name, instance_name, n_students,
                     run_id, seed, result):
    assignments_dir = os.path.join(results_dir, "assignments")
    ensure_dir(assignments_dir)

    safe_instance = instance_name.replace(".txt", "")
    assignments_path = os.path.join(
        assignments_dir,
        "{}__{}__run_{:02d}.json".format(algorithm_name, safe_instance, run_id)
    )

    pareto_set = result.get("pareto_set", [])

    data = {
        "algorithm": algorithm_name,
        "instance": instance_name,
        "n_students": n_students,
        "run_id": run_id,
        "seed": seed,
        "created_at": now_str(),
        "pareto_size": len(pareto_set),
        "solutions": [],
    }

    for idx, item in enumerate(pareto_set):
        data["solutions"].append(solution_to_assignment_dict(item, idx))

    write_json(assignments_path, data)

# Guarda el resultado completo de una ejecución, incluyendo estadísticas, frente de Pareto y asignaciones
def save_full_result(results_dir, algorithm_name, instance_name, n_students,
                     run_id, seed, time_limit_seconds, result, save_assignments_flag=False):
    save_pareto(
        results_dir=results_dir,
        algorithm_name=algorithm_name,
        instance_name=instance_name,
        n_students=n_students,
        run_id=run_id,
        seed=seed,
        result=result,
    )

    if save_assignments_flag:
        save_assignments(
            results_dir=results_dir,
            algorithm_name=algorithm_name,
            instance_name=instance_name,
            n_students=n_students,
            run_id=run_id,
            seed=seed,
            result=result,
        )

    save_stats(
        results_dir=results_dir,
        algorithm_name=algorithm_name,
        instance_name=instance_name,
        n_students=n_students,
        run_id=run_id,
        seed=seed,
        time_limit_seconds=time_limit_seconds,
        result=result,
        status="ok",
        error_message="",
    )


# ----------------------------------------
# Algoritmos
# ----------------------------------------

# Ejecuta Random Search con parámetros predefinidos, y opciones de normalización para asegurar comparabilidad entre instancias
def execute_random(problem, time_limit_seconds, seed, verbose):
    return random_search_pareto(
        problem=problem,
        generator_fn=generate_random_feasible_fixing,
        weights=DEFAULT_WEIGHTS,
        time_limit_seconds=time_limit_seconds,
        max_iterations=None,
        generator_kwargs=None,
        max_pareto_size=None,
        base_seed=seed,
        normalize_student_dist=True,
        normalize_supervision_dist=True,
        verbose=verbose
    )

# Ejecuta NSGA-III con parámetros predefinidos, y opciones de normalización y referencia para asegurar diversidad en el frente de Pareto
def execute_nsga3(problem, time_limit_seconds, seed, verbose):
    return run_nsga3(
        problem=problem,
        weights=DEFAULT_WEIGHTS,
        population_size=50,
        offspring_size=50,
        cx_prob=0.8,
        mut_prob=0.2,
        time_limit_seconds=time_limit_seconds,
        max_generations=None,
        max_pareto_size=None,
        base_seed=seed,
        normalize_student_dist=True,
        normalize_supervision_dist=True,
        ref_points_p=5,
        verbose=verbose
    )

# Ejecuta GRASP con parámetros predefinidos
def execute_grasp(problem, time_limit_seconds, seed, verbose):
    return run_grasp(
        problem=problem,
        weights=DEFAULT_WEIGHTS,
        alpha_rcl=0.5,
        time_limit_seconds=time_limit_seconds,
        max_iterations=None,
        max_pareto_size=None,
        base_seed=seed,
        normalize_student_dist=True,
        normalize_supervision_dist=True,
        constructive_max_attempts=5,
        constructive_time_limit_seconds=30,
        use_random_fallback=True,
        random_fallback_max_attempts=50,
        local_max_neighbors_per_pass=1000,
        local_max_improvements=30,
        verbose=verbose
    )

# Ejecuta HH-LAP-SIPA v0
def execute_hh_lap_v0(problem, time_limit_seconds, seed, verbose):
    return run_hh_lap_sipa_v0(
        problem=problem,
        weights=DEFAULT_WEIGHTS,
        time_limit_seconds=time_limit_seconds,
        max_iterations=None,
        max_pareto_size=None,
        base_seed=seed,
        placement_max_attempts=50,
        lap_solver="lapjv",
        normalize_student_dist=True,
        normalize_supervision_dist=True,
        professor_lbar_weight=1.0,
        professor_sigma_weight=1.0,
        verbose=verbose
    )

# Ejecuta HH-LAP-SIPA v1
def execute_hh_lap_v1(problem, time_limit_seconds, seed, verbose):
    return run_hh_lap_sipa_v1(
        problem=problem,
        weights=DEFAULT_WEIGHTS,
        time_limit_seconds=time_limit_seconds,
        max_iterations=None,
        max_pareto_size=None,
        base_seed=seed,
        placement_max_attempts=50,
        lap_solver="lapjv",
        normalize_student_dist=True,
        normalize_supervision_dist=True,
        max_path_relinking_steps=10,
        verbose=verbose
    )


ALGORITHM_REGISTRY = {
    "random": execute_random,
    "nsga3": execute_nsga3,
    "grasp": execute_grasp,
    "hh_lap_v0": execute_hh_lap_v0,
    "hh_lap_v1": execute_hh_lap_v1,
}


# ----------------------------------------
# Ejecución principal
# ----------------------------------------

# Obtiene las rutas de las instancias a ejecutar, filtrando por tamaños si se especifican
def get_instances(instances_dir, selected_sizes):
    pattern = os.path.join(instances_dir, "problem_instance_ext_*.txt")
    paths = sorted(glob.glob(pattern))

    if selected_sizes:
        selected_sizes = set(selected_sizes)
        filtered = []

        for path in paths:
            name = os.path.basename(path)
            n_students = parse_n_students_from_instance_name(name)
            if n_students in selected_sizes:
                filtered.append(path)

        paths = filtered

    return paths

# Valida que los algoritmos solicitados estén registrados en ALGORITHM_REGISTRY
def validate_algorithms(algorithm_names):
    for name in algorithm_names:
        if name not in ALGORITHM_REGISTRY:
            raise ValueError(
                "Algoritmo no registrado: {}. Disponibles: {}".format(
                    name,
                    ", ".join(sorted(ALGORITHM_REGISTRY.keys()))
                )
            )

# Función principal que ejecuta los experimentos según los argumentos, iterando sobre algoritmos, instancias y repeticiones, con manejo de logs, checkpoints y guardado de resultados
def run_experiment(args):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    instances_dir = args.instances_dir
    results_dir = args.results_dir

    if not os.path.isabs(instances_dir):
        instances_dir = os.path.join(base_dir, instances_dir)

    if not os.path.isabs(results_dir):
        results_dir = os.path.join(base_dir, results_dir)

    ensure_dir(results_dir)
    ensure_dir(os.path.join(results_dir, "statistics"))
    ensure_dir(os.path.join(results_dir, "pareto"))
    ensure_dir(os.path.join(results_dir, "assignments"))
    ensure_dir(os.path.join(results_dir, "logs"))
    ensure_dir(os.path.join(results_dir, "checkpoints"))

    log_path = os.path.join(results_dir, "logs", "run_general.log")

    algorithm_names = args.algorithms
    validate_algorithms(algorithm_names)

    instance_paths = get_instances(instances_dir, args.sizes)

    if not instance_paths:
        raise ValueError("No se encontraron instancias en {}".format(instances_dir))

    log_line(log_path, "Inicio de run_general.py")
    log_line(log_path, "Instancias dir: {}".format(instances_dir))
    log_line(log_path, "Results dir: {}".format(results_dir))
    log_line(log_path, "Algoritmos: {}".format(", ".join(algorithm_names)))
    log_line(log_path, "Runs por algoritmo/instancia: {}".format(args.runs))
    log_line(log_path, "Resume: {}".format(args.resume))
    log_line(log_path, "Dry run: {}".format(args.dry_run))
    log_line(log_path, "Número de instancias encontradas: {}".format(len(instance_paths)))

    total_jobs = len(algorithm_names) * len(instance_paths) * args.runs
    job_counter = 0

    for algorithm_name in algorithm_names:
        execute_fn = ALGORITHM_REGISTRY[algorithm_name]

        for instance_path in instance_paths:
            instance_name = os.path.basename(instance_path)
            n_students = parse_n_students_from_instance_name(instance_name)

            if n_students not in TIME_LIMITS_SECONDS:
                raise ValueError(
                    "No hay tiempo definido para n_students={}".format(n_students)
                )

            time_limit_seconds = TIME_LIMITS_SECONDS[n_students]

            for run_id in range(args.runs):
                job_counter += 1
                seed = build_seed(algorithm_name, instance_name, run_id)

                prefix = "[{}/{}] {} | {} | run {:02d} | {}s".format(
                    job_counter,
                    total_jobs,
                    algorithm_name,
                    instance_name,
                    run_id,
                    time_limit_seconds,
                )

                if args.resume and is_done(results_dir, algorithm_name, instance_name, run_id):
                    log_line(log_path, "{} | SKIP resume".format(prefix))
                    continue

                if args.dry_run:
                    log_line(log_path, "{} | DRY RUN".format(prefix))
                    continue

                log_line(log_path, "{} | START | seed={}".format(prefix, seed))

                result = None
                start_job = time.time()

                try:
                    problem = load_instance(instance_path)

                    result = execute_fn(
                        problem=problem,
                        time_limit_seconds=time_limit_seconds,
                        seed=seed,
                        verbose=args.verbose
                    )

                    save_full_result(
                        results_dir=results_dir,
                        algorithm_name=algorithm_name,
                        instance_name=instance_name,
                        n_students=n_students,
                        run_id=run_id,
                        seed=seed,
                        time_limit_seconds=time_limit_seconds,
                        result=result,
                        save_assignments_flag=args.save_assignments
                    )

                    mark_done(results_dir, algorithm_name, instance_name, run_id)

                    elapsed = time.time() - start_job
                    pareto_size = len(result.get("pareto_set", []))

                    log_line(
                        log_path,
                        "{} | OK | elapsed={:.2f}s | pareto_size={}".format(
                            prefix,
                            elapsed,
                            pareto_size,
                        )
                    )

                except Exception as e:
                    elapsed = time.time() - start_job
                    error_message = "{}".format(e)

                    log_line(
                        log_path,
                        "{} | ERROR | elapsed={:.2f}s | {}".format(
                            prefix,
                            elapsed,
                            error_message,
                        )
                    )

                    log_line(log_path, traceback.format_exc())

                    save_stats(
                        results_dir=results_dir,
                        algorithm_name=algorithm_name,
                        instance_name=instance_name,
                        n_students=n_students,
                        run_id=run_id,
                        seed=seed,
                        time_limit_seconds=time_limit_seconds,
                        result=result,
                        status="error",
                        error_message=error_message,
                    )

                    if args.stop_on_error:
                        raise

    log_line(log_path, "Fin de run_general.py")

# Argumentos de la llamada
def parse_args(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--instances_dir",
        default="instances",
        help="Carpeta con las instancias .txt",
    )

    parser.add_argument(
        "--results_dir",
        default="results",
        help="Carpeta donde guardar resultados",
    )

    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=["random", "nsga3"],
        help="Algoritmos a ejecutar. Ejemplo: --algorithms random nsga3",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="Número de repeticiones por algoritmo e instancia",
    )

    parser.add_argument(
        "--sizes",
        nargs="*",
        type=int,
        default=None,
        help="Filtrar por tamaños. Ejemplo: --sizes 200 400 600",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Saltar ejecuciones ya completadas",
    )

    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Solo muestra lo que se ejecutaría, sin ejecutar",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar progreso interno de los algoritmos",
    )

    parser.add_argument(
        "--stop_on_error",
        action="store_true",
        help="Detener todo si una ejecución falla",
    )

    parser.add_argument(
        "--save_assignments",
        action="store_true",
        help="Guardar asignaciones completas del Pareto en JSON. Por defecto no se guardan.",
    )

    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    run_experiment(args)


if __name__ == "__main__":
    main(sys.argv[1:])