# Control del tiempo de ejecución de las metaheurísticas mediante multiprocessing

# Librerías
import multiprocessing as mp
import time
import traceback

from tools.pareto_front import update_pareto_set
from tools.solution import Solution
from tools.pareto_front import EvaluatedSolution


def _pack_solution(item):
                  # Solución a transmitir tras final
    """
    Convierte una solución en un diccionario compacto
    """
    return {
        "student_to_placement": list(item.sol.student_to_placement),
        "placement_to_professor": list(item.sol.placement_to_professor),
        "evaluation": item.evaluation,
        "iteration": item.iteration,
        "seed": item.seed,
    }


def _unpack_solution(data, problem):
                    # Datos recibidos de la solución, instancia del problema
    """
    Reconstruye una solución evaluada a partir de los datos recibidos,
    utilizando el Problem que ya tiene cargado el proceso principal
    """
    sol = Solution(problem)

    # Reconstrucción de las asignaciones
    for student, placement in enumerate(data["student_to_placement"]):
        professor = data["placement_to_professor"][placement]
        sol.assign(student, placement, professor)

    # Reconstrucción de la solución evaluada
    return EvaluatedSolution(sol=sol, evaluation=data["evaluation"], iteration=data["iteration"], seed=data["seed"])


def _worker(conn, execute_fn, problem, time_limit_seconds, seed, verbose):
            # Canal de comunicación, función de búsqueda, problema, límite temporal, semilla y modo detallado
    """
    Ejecuta la heurística
    """
    try:
        # Confirma al proceso principal que ya está preparado
        conn.send(("ready", None))
        tipo, deadline = conn.recv()
        if tipo != "start":
            raise RuntimeError("No se recibió la orden de inicio")

        def informar(tipo_evento, contenido):
            """
            Las heurísticas lo usarán para comunicar
            la solución y los stats
            """
            if time.monotonic() >= deadline:
                return
            if tipo_evento == "solution":
                conn.send(("solution", _pack_solution(contenido)))
            elif tipo_evento == "stats":
                conn.send(("stats", dict(contenido)))
            else:
                raise ValueError("Tipo de evento desconocido: " + str(tipo_evento))

        # La heurística recibirá estos parámetros cuando adaptemos sus funciones.
        resultado = execute_fn(problem=problem, time_limit_seconds=time_limit_seconds, seed=seed,
                               verbose=verbose, deadline=deadline, progress_callback=informar)
        conn.send(("done", resultado)) # Resultado entero cuando la heurística termina normal

    except Exception:
        try:
            conn.send(("error", traceback.format_exc()))
        except (OSError, EOFError):
            pass
    finally:
        conn.close()


def run_with_deadline(execute_fn, problem, time_limit_seconds, seed, verbose=False, *, startup_timeout_seconds=120.0):
                      # Función de búsqueda, instancia, límite de búsqueda, semilla, detalle y máximo de espera para iniciar
    """
    Ejecuta una heurística en un proceso independiente hasta su tiempo máximo.
    Conserva las soluciones y devuelve el último Pareto
    """
    # Arranca el proceso sin heredar el estado interno de Python.
    ctx = mp.get_context("spawn")
    receptor, emisor = ctx.Pipe(duplex=True)
    proceso = ctx.Process(target=_worker, args=(emisor, execute_fn, problem, time_limit_seconds, seed, verbose))

    try:
        proceso.start()
    except Exception:
        receptor.close()
        emisor.close()
        raise
    emisor.close()

    pareto_set = []
    stats = {}
    resultado_final = None
    status = "error"
    error_message = None
    inicio = None

    try:
        # Espera de arranque: no consume el presupuesto de optimización
        fin_espera = time.monotonic() + startup_timeout_seconds
        preparado = False
        while time.monotonic() < fin_espera:
            if receptor.poll(min(0.05, fin_espera - time.monotonic())):
                tipo, contenido = receptor.recv()
                if tipo == "ready":
                    preparado = True
                    break
                if tipo == "error":
                    error_message = contenido
                    break
            if not proceso.is_alive():
                error_message = "El proceso terminó antes de iniciar la búsqueda"
                break

        if not preparado and error_message is None:
            error_message = "Se agotó el tiempo máximo de preparación del proceso"

        if preparado:
            # El presupuesto comienza justo antes de ordenar el inicio
            inicio = time.monotonic()
            deadline = inicio + time_limit_seconds
            receptor.send(("start", deadline))

            # Recibe los avances hasta que termine la búsqueda o venza el plazo
            while True:
                restante = deadline - time.monotonic()
                if restante <= 0:
                    status = "time_limit_reached"
                    break

                if receptor.poll(min(0.05, restante)):
                    # Evita incorporar soluciones recibidas fuera del plazo
                    if time.monotonic() >= deadline:
                        status = "time_limit_reached"
                        break
                    try:
                        tipo, contenido = receptor.recv()
                    except EOFError:
                        error_message = "El proceso cerró la comunicación inesperadamente"
                        break

                    if tipo == "solution":
                        candidato = _unpack_solution(contenido, problem)
                        pareto_set, _, _ = update_pareto_set(pareto_set, candidato)
                    elif tipo == "stats":
                        stats.update(contenido)
                    elif tipo == "done":
                        resultado_final = contenido
                        status = "completed"
                        break
                    elif tipo == "error":
                        error_message = contenido
                        break
                elif not proceso.is_alive():
                    error_message = "El proceso terminó sin comunicar un resultado final"
                    break

    except (EOFError, OSError, ValueError, TypeError) as exc:
        status = "error"
        error_message = f"Error del controlador: {exc}"
    finally:
        # Si la heurística continúa trabajando, se termina forzosamente
        if proceso.is_alive():
            proceso.terminate()
        proceso.join(timeout=1.0)
        if proceso.is_alive():
            proceso.kill()
            proceso.join()
        receptor.close()

    # Si termina normalmente, devuelve exactamente el resultado original
    if status == "completed":
        return resultado_final, status, error_message

    # Estadísticas calculadas por el controlador, incluso tras interrupción
    stats["elapsed_seconds"] = min(time.monotonic() - inicio, time_limit_seconds) if inicio is not None else 0.0
    stats["pareto_size"] = len(pareto_set)
    resultado = {"pareto_set": pareto_set, "stats": stats}
    return resultado, status, error_message