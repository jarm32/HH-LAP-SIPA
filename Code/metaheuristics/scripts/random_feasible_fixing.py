# Generador de soluciones aleatorias factibles (random + fixing) --> 1º Asignación estudiante-plaza (con dependencias y cuotas por empresa) / 2º Asignación plaza-profesor (respetando las capacidades individuales)

# ----------------------------
# Imports
# ----------------------------
import random

from dataclasses import dataclass
from typing import List

from tools.solution import Solution


# ----------------------------
# Preprocesado de bloques de plazas
# ----------------------------

@dataclass
class _Preproc:
    placements_by_company: List[List[int]]
    nondep_by_company: List[List[int]]
    dep_blocks_by_company: List[List[List[int]]]
    placement_in_any_dep: List[bool]
    total_in_deps_by_company: List[int]


def _preprocess(problem): # objeto tipo Problem
    """
    Estructura auxiliar con información preprocesada de la instancia para acelerar la generación de soluciones.

    Contiene solo organización de plazas (bloques de dependencias, plazas no dependientes, etc.), 
    pero no incluye las restricciones del modelo (min/max por empresa, capacidades, etc.); por lo que,
    si se necesitan estas restricciones, se consultan directamente en el objeto problem
    """
    # Clasificación de plazas por empresa y bloques de dependencias
    placements_by_company = [[] for _ in range(problem.n_companies)]
    for j in range(problem.n_placements):
        placements_by_company[problem.placement_company[j]].append(j)

    placement_in_any_dep = [False] * problem.n_placements
    dep_blocks_by_company = [[] for _ in range(problem.n_companies)]
    total_in_deps_by_company = [0] * problem.n_companies

    # Clasificar bloques de dependencias por empresa, y marcar qué plazas están en dependencias
    for dep in problem.dependencies:
        if not dep:
            continue
        k = problem.placement_company[dep[0]]
        block = list(dep)
        dep_blocks_by_company[k].append(block)
        for j in block:
            placement_in_any_dep[j] = True
        total_in_deps_by_company[k] += len(block)
    
    # Clasificar plazas no dependientes por empresa
    nondep_by_company = [[] for _ in range(problem.n_companies)]
    for k in range(problem.n_companies):
        for j in placements_by_company[k]:
            if not placement_in_any_dep[j]:
                nondep_by_company[k].append(j)

    return _Preproc(
        placements_by_company=placements_by_company,
        nondep_by_company=nondep_by_company,
        dep_blocks_by_company=dep_blocks_by_company,
        placement_in_any_dep=placement_in_any_dep,
        total_in_deps_by_company=total_in_deps_by_company,
    ) # Objeto _Preproc con toda la información preprocesada de la instancia para usar en generación de soluciones


# ----------------------------
# Selección aleatoria + arreglos de bloques de dependencias (individuales y múltiples)
# ----------------------------

def _random_initial_dep_selection(pre, rng):
                                  # Problema preprocesado, generador de números aleatorios
    """
    Selección inicial aleatoria de bloques de dependencia
    (individuales o múltiples) a activar por empresa
    """
    selected = {k: [] for k in range(len(pre.dep_blocks_by_company))}

    # Para cada empresa, elige aleatoriamente un subconjunto de sus bloques de dependencias (puede ser vacío)
    for k, blocks in enumerate(pre.dep_blocks_by_company):
        if not blocks:
            continue
        n = rng.randint(0, len(blocks))
        if n > 0:
            chosen = rng.sample(blocks, n)
            selected[k] = [list(b) for b in chosen]
    return selected # {empresa1: [bloque1, bloque2, ...], ...} --> diccionario que almacena los bloques de plazas por empresa (bloque1 = [plaza1, plaza2, ...])


def _recompute_counters(problem, pre, selected_blocks):
                        # Problema original, Problema preprocesado, diccionario de la selección actual de bloques de dependencias por empresa
    """
    Recalcula todas las cantidades necesarias para saber si la selección actual de dependencias es viable o hay que arreglarla
    """
    # Contar plazas ya seleccionadas por empresa
    selected_from_company = [0] * problem.n_companies
    total_selected = 0

    for k in range(problem.n_companies):
        s = sum(len(b) for b in selected_blocks.get(k, []))
        selected_from_company[k] = s
        total_selected += s

    # Contar no-deps disponibles por empresa
    unassigned_nondep = [len(pre.nondep_by_company[k]) for k in range(problem.n_companies)]
    
    # Calcular lo que falta por cubrir (must_send) y lo que se podría cubrir (can_send) por empresa, para cumplir mínimos/máximos
    must_send = [0] * problem.n_companies
    can_send = [0] * problem.n_companies
    for k in range(problem.n_companies):
        must_send[k] = max(problem.company_min[k] - selected_from_company[k], 0)
        can_send[k] = min(max(problem.company_max[k] - selected_from_company[k], 0), unassigned_nondep[k])

    # Suma total de plazas que se podrían cubrir con no-deps (holgura total)
    total_can = sum(can_send)
    return selected_from_company, total_selected, must_send, can_send, unassigned_nondep, total_can
           # lista que indica cuántas plazas dependientes están seleccionadas por empresa, total de plazas seleccionadas,
           # lista de plazas mínimas que aún faltan por cubrir por empresa, lista de holgura por empresa (plazas individuales), 
           # lista con la cantidad de plazas por asignar por empresa, suma total de holgura (sum(can_send))


def _remove_random_block_from_company(selected_blocks, k, rng):
                                     # Diccionario de la selección actual de bloques de dependencias por empresa, empresa k, generador de números aleatorios
    """
    Desactiva aleatoriamente un bloque de dependencias seleccionado de la empresa k,
    permitiendo probar variaciones en la selección
    """
    # Obtener bloques seleccionados de la empresa
    blocks = selected_blocks.get(k, [])
    if not blocks:
        return False # si no había bloques para eliminar
    
    # Elegir un bloque al azar y quitarlo
    idx = rng.randrange(len(blocks))
    blocks.pop(idx)
    return True # se ha eliminado un bloque


def _add_random_block_from_company(pre, selected_blocks, k, rng):
                                  # Problema preprocesado, diccionario de la selección actual de bloques de dependencias por empresa, empresa k, generador de números aleatorios
    """
    Activa aleatoriamente un bloque de dependencias no seleccionado de la empresa k
    """
    # Ver cuáles están ya activos
    existing = selected_blocks.get(k, [])

    # Construir lista de bloques disponibles
    available = []
    for block in pre.dep_blocks_by_company[k]:
        if block not in existing:
            available.append(block)

    if not available:
        return False # No hay bloques disponibles para añadir

    # Elegir uno al azar y activarlo
    block = rng.choice(available)
    selected_blocks.setdefault(k, []).append(list(block))
    return True # Añade el bloque nuevo


def _remove_random_block_any(selected_blocks, rng):
                            # Diccionario de la selección actual de bloques de dependencias por empresa, generador de números aleatorios
    """
    Quita aleatoriamente un bloque (a partir de la función anterior) de una empresa aleatoria
    """
    # Busca empresas con bloques activos
    companies_with_blocks = [k for k, bl in selected_blocks.items() if bl]
   
    if not companies_with_blocks:
        return False # No hay empresas con bloques activos
    
    # Elegir empresa al azar y quitar un bloque suyo (si es posible)
    k = rng.choice(companies_with_blocks)
    return _remove_random_block_from_company(selected_blocks, k, rng) # True/False, dependiendo de la empresa


def _fix_dependency_selection(problem, pre, rng, selected_blocks, max_iters = 5000):
                             # Problema original, Problema preprocesado, generador de números aleatorios, diccionario de la selección actual de bloques de dependencias por empresa, límite de iteraciones del fixing
    """
    Arreglo de las siguientes dependencias:
      - total_selected <= n_students
      - selected_from_company[k] <= company_max[k]
      - can_send[k] >= must_send[k]
      - total_selected + sum(can_send) >= n_students
    """
    for _ in range(max_iters):
        # Recalcular contadores
        selected_from_company, total_selected, must_send, can_send, _, total_can = _recompute_counters(problem, pre, selected_blocks)

        # Demasiadas plazas en dependencias
        if total_selected > problem.n_students:
            # Quitar un bloque cualquiera para bajar total_selected
            if not _remove_random_block_any(selected_blocks, rng):
                return None
            continue

        # Alguna empresa excede su máximo por dependencias
        over_max = [k for k in range(problem.n_companies) if selected_from_company[k] > problem.company_max[k]]
        if over_max:
            k = rng.choice(over_max)
            # Quitar un bloque cualquiera de alguna empresa con excedencia de cupo 
            if not _remove_random_block_from_company(selected_blocks, k, rng):
                return None
            continue

        # En alguna empresa no es posible alcanzar el mínimo con las no-deps restantes
        deficit = [k for k in range(problem.n_companies) if can_send[k] < must_send[k]]
        if deficit:
            k = rng.choice(deficit)

            # Intentar activar dependencias no seleccionadas
            if _add_random_block_from_company(pre, selected_blocks, k, rng):
                continue

            # Si no se puede activar ninguna, intentar eliminar alguna
            if _remove_random_block_from_company(selected_blocks, k, rng):
                continue

            # Si tampoco se puede eliminar, no es reparable
            return None

        # Revisar si, con lo que queda, no se llega a n_students
        if total_selected + total_can < problem.n_students:
            # Quitar un bloque en una empresa donde company_max - selected_from_company es pequeño (están "apretadas") y hay bloques individuales
            candidates = []
            for k in range(problem.n_companies):
                if selected_blocks.get(k, []) and len(pre.nondep_by_company[k]) > 0:
                    slack = problem.company_max[k] - selected_from_company[k]  # si slack es bajo, quitar ayuda más
                    candidates.append((slack, k))
            
            # Si no hay candidatos razonables, quitamos cualquiera
            if not candidates:
                if not _remove_random_block_any(selected_blocks, rng):
                    return None
            else:
                candidates.sort(key=lambda x: x[0])
                best_slack = candidates[0][0]
                best_ks = [k for slack, k in candidates if slack == best_slack]
                k = rng.choice(best_ks)
                if not _remove_random_block_from_company(selected_blocks, k, rng):
                    return None
            continue

        return selected_blocks, must_send, can_send # diccionario de bloques seleccionados, lo que se debe enviar y la holgura (en bloques individuales); todo ACTUALIZADO

    return None


def _random_partition_to_fill(need, must_send, can_send, rng):
                             # Plazas que faltan para llegar a n_students, lista de mínimo obligatorio por empresa, 
                             # lista de máxima holgura por empresa, generador de números aleatorios
    """   
    Decide cuántas plazas no-dep se eligen por empresa, respetando:
      - must_send[k] <= x[k] <= can_send[k]
      - sum_k x[k] = need
    """
    # Primero se cumplen todos los mínimos
    x = must_send[:]
    base = sum(x)
    if base > need:
        raise ValueError("Inconsistent: sum(must_send) > needed")
    
    surplus = need - base # Cuánto queda por repartir
    caps = [can_send[k] - must_send[k] for k in range(len(must_send))] # Margen por empresa
    
    # Orden aleatorio de empresas
    order = list(range(len(must_send)))
    rng.shuffle(order)
    for k in order:
        if surplus <= 0:
            break
        
        # Reparto aleatorio inicial
        take = rng.randint(0, min(caps[k], surplus))
        x[k] += take
        surplus -= take

    # Si todavía queda, repartir sin romper límites
    if surplus > 0:
        for k in order:
            if surplus <= 0:
                break
            room = can_send[k] - x[k]
            if room <= 0:
                continue
            take = min(room, surplus)
            x[k] += take
            surplus -= take

    if surplus != 0:
        raise ValueError("Could not partition to fill all needed placements within can_send limits")

    return x # [3, 6, 1, ...]; donde cada elemento corresponde a cuántas plazas no dependientes se deben asignar a cada empresa


def _choose_final_placements(problem, pre, rng):
                            # Problema original, Problema preprocesado, generador de números aleatorios
    """
    Devuelve una lista de n_students placements (con todas las plazas de bloques
    de dependencias activados y completado con plazas individuales)
    """
    # Selección inicial de dependencias
    selected_blocks = _random_initial_dep_selection(pre, rng)

    # Arreglar las dependencias
    fixed = _fix_dependency_selection(problem, pre, rng, selected_blocks)
    if fixed is None:
        raise ValueError("Failed to fix dependency selection")
    selected_blocks, must_send, can_send = fixed
    
    # Construir conjunto inicial de plazas
    chosen_set = set()
    selected_from_company = [0] * problem.n_companies
    total_selected = 0
    for k in range(problem.n_companies):
        for block in selected_blocks.get(k, []):
            for j in block:
                chosen_set.add(j)
            selected_from_company[k] += len(block)
            total_selected += len(block)

    # Calcular cuántas plazas faltan
    need = problem.n_students - total_selected
    if need < 0:
        raise ValueError("Internal error: selected more than students after fixing")

    # Elegir cuántas no-deps por empresa
    to_pick = _random_partition_to_fill(need, must_send, can_send, rng)

    # Seleccionar plazas individuales concretas
    for k in range(problem.n_companies):
        if to_pick[k] <= 0:
            continue
        pool = pre.nondep_by_company[k]
        if len(pool) < to_pick[k]:
            raise ValueError("Internal error: not enough non-dep placements to pick")
        chosen = rng.sample(pool, to_pick[k])
        chosen_set.update(chosen)
    chosen_list = list(chosen_set)

    # Por seguridad, aunque el diseño debe garantizar exactitud
    if len(chosen_list) != problem.n_students:
        raise ValueError(f"Expected {problem.n_students} placements, got {len(chosen_list)}")

    rng.shuffle(chosen_list)
    return chosen_list # Lista de plazas seleccionadas por empresa (cuya suma debe resultar en n_students)


# ----------------------------
# Asignación de profesores (constructivo aleatorizado + repair ligero)
# ----------------------------

def _assign_professors_with_repair(problem, sol, rng, max_repair_iters = 3000):
                                  # Problema original, objeto Solution que ya tiene las plazas de estudiantes asignadas, 
                                  # generador aleatorio, nº máximo de iteraciones del proceso de reparación
    """
    Asigna un profesor a cada plaza ocupada (1º por construccion + 2º reparación)

    True si se ha logrado asignar un profesor a todas las plazas ocupadas, False si no
    """

    # Comprobación de factibilidad
    if sum(problem.prof_capacity) < problem.n_students:
        return False

    # Obtener plazas ocupadas
    assigned_placements = [j for j in range(problem.n_placements) if sol.placement_filled[j]]
    rng.shuffle(assigned_placements)

    prof_to_pl = [[] for _ in range(problem.n_professors)] # Lista que guarda qué plazas tiene asignadas cada profesor
    unassigned = [] # Lista de plazas sin profesor

    # -------- Constructivo --------
    for j in assigned_placements:
        # Genera lista aleatoria de profesores
        cand = list(range(problem.n_professors))
        rng.shuffle(cand)

        # Filtrar profesores con algo de capacidad
        feasible = [t for t in cand if sol.professor_load[t] < problem.prof_capacity[t]]

        if not feasible:
            unassigned.append(j)
            continue

        # Se elige un profesor aleatorio y se asigna
        t = rng.choice(feasible)
        sol.placement_to_professor[j] = t
        sol.professor_load[t] += 1
        prof_to_pl[t].append(j)

    # Si todas las plazas tienen profesor
    if not unassigned:
        return True

    # -------- Reparación --------
    for _ in range(max_repair_iters):

        if not unassigned:
            return True

        # Tomar una plaza j sin profesor e intenta asignación directa
        j = unassigned[-1]
        cand = list(range(problem.n_professors))
        rng.shuffle(cand)

        # Filtrar profesores con algo de capacidad
        feasible = [t for t in cand if sol.professor_load[t] < problem.prof_capacity[t]]

        # Si hay alguno, la plaza queda asignada y se elimina de unassigned
        if feasible:
            t = rng.choice(feasible)

            sol.placement_to_professor[j] = t
            sol.professor_load[t] += 1
            prof_to_pl[t].append(j)

            unassigned.pop()
            continue
        
        # Si a ninguno le cabe j, se intenta liberar capacidad moviendo una plaza existente
        
        # Elige profesores a intentar liberar para que quepa j
        target_pool = cand[:]
        rng.shuffle(target_pool)
        moved = False
        for t_full in target_pool:
            if not prof_to_pl[t_full]: # Ignorar profesores sin plazas
                continue
            
            # Elegir una plaza j2 del profesor lleno para que a este le queja j
            rng.shuffle(prof_to_pl[t_full])
            for j2 in list(prof_to_pl[t_full]):
                cand2 = list(range(problem.n_professors))
                rng.shuffle(cand2)

                # Buscar un profesor alternativo para asignar la plaza nueva j2
                dests = [t2 for t2 in cand2 if t2 != t_full and sol.professor_load[t2] < problem.prof_capacity[t2]]
                if not dests:
                    continue
                
                # Swap parcial --> se mueve j2 y t_full ahora tiene hueco para j
                t2 = rng.choice(dests)
                sol.placement_to_professor[j2] = t2
                sol.professor_load[t_full] -= 1
                sol.professor_load[t2] += 1

                prof_to_pl[t_full].remove(j2)
                prof_to_pl[t2].append(j2)

                sol.placement_to_professor[j] = t_full
                sol.professor_load[t_full] += 1
                prof_to_pl[t_full].append(j)

                unassigned.pop()
                moved = True
                break

            if moved:
                break # Ya ha habido movimiento

        # Si no se pudo mover nada, se cambia el orden de las plazas pendientes para probar otra
        if not moved:
            rng.shuffle(unassigned)

    return False


# ----------------------------
# Construcción final de Solution
# ----------------------------

def generate_random_feasible_fixing(problem, seed = None, max_attempts = 50):
                                   # Problema original, semilla para reproducibilidad, nº máximo de iteraciones del proceso de reparación
    """
    Genera una Solution aleatoria y factible 
    """
    # Inicializar generador aleatorio y preprocesado de la instancia
    rng = random.Random(seed)
    pre = _preprocess(problem)

    # Bucle de intentos
    for _ in range(max_attempts):
        try:
            # Elegir plazas finales
            chosen_placements = _choose_final_placements(problem, pre, rng)

            # --- Estudiante-plaza ---
            students = list(range(problem.n_students))
            rng.shuffle(students)
            rng.shuffle(chosen_placements)

            sol = Solution(problem) # Creación del objeto solution

            # Asignar estudiantes a placements
            for i, j in zip(students, chosen_placements):
                sol.student_to_placement[i] = j
                sol.placement_filled[j] = True
                k = problem.placement_company[j]
                sol.company_load[k] += 1

            # Verificación rápida de mínimos/máximos de empresas antes de profes
            ok = True
            for k in range(problem.n_companies):
                if sol.company_load[k] < problem.company_min[k] or sol.company_load[k] > problem.company_max[k]:
                    ok = False
                    break
            if not ok or not sol.dependencies_ok():
                continue

            # --- Profesores-Plazas ---
            if not _assign_professors_with_repair(problem, sol, rng):
                continue

            # Validación final
            if sol.validate():
                return sol # Objeto Solution ya factible (asignaciones y cargas correctas)

        except ValueError:
            continue # Se prueba otra vez

    raise ValueError(f"No feasible random solution found after {max_attempts} attempts") # No se ha podido obtener una solución óptima tras todas las iteraciones