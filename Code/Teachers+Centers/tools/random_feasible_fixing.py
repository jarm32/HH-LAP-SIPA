# Generador de soluciones aleatorias factibles (random + fixing) --> 1º Asignación estudiante-plaza (con dependencias y cuotas por empresa) / 2º Asignación plaza-profesor (con capacidades y centros)

# ----------------------------
# Imports
# ----------------------------
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional

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

##############################


def _fix_dependency_selection(problem, pre, rng, selected_blocks, max_iters = 5000):
    """
    Arregla selección de dependencias para que:
      - total_selected <= n_students
      - selected_from_company[k] <= company_max[k]
      - para cada empresa: can_send[k] >= must_send[k]
      - global: total_selected + sum(can_send) >= n_students (posible completar con no-deps)
    Devuelve (selected_blocks_fixed, must_send, can_send) o None si no converge.
    """
    for _ in range(max_iters):
        selected_from_company, total_selected, must_send, can_send, _, total_can = _recompute_counters(problem, pre, selected_blocks)

        # Caso 1: demasiadas plazas en dependencias
        if total_selected > problem.n_students:
            # quitar un bloque cualquiera para bajar total_selected
            if not _remove_random_block_any(selected_blocks, rng):
                return None
            continue

        # Caso 2: alguna empresa excede su máximo por dependencias
        over_max = [k for k in range(problem.n_companies) if selected_from_company[k] > problem.company_max[k]]
        if over_max:
            k = rng.choice(over_max)
            if not _remove_random_block_from_company(selected_blocks, k, rng):
                return None
            continue

        # Caso 3: en alguna empresa no es posible alcanzar el mínimo con las no-deps restantes
        deficit = [k for k in range(problem.n_companies) if can_send[k] < must_send[k]]
        if deficit:
            k = rng.choice(deficit)

            # 1) intentar activar dependencias no seleccionadas
            if _add_random_block_from_company(pre, selected_blocks, k, rng):
                continue

            # 2) si no se puede activar ninguna, intentar eliminar alguna
            if _remove_random_block_from_company(selected_blocks, k, rng):
                continue

            # 3) si tampoco se puede eliminar, no es reparable
            return None

        # Caso 4: aunque todo lo anterior esté OK, globalmente no hay plazas alcanzables para n_students
        if total_selected + total_can < problem.n_students:
            # quitar un bloque en una empresa donde eso aumente "achievable" lo más probable:
            # preferimos empresas donde max-selected es pequeño (están "apretadas") y hay no-deps.
            candidates = []
            for k in range(problem.n_companies):
                if selected_blocks.get(k, []) and len(pre.nondep_by_company[k]) > 0:
                    slack = problem.company_max[k] - selected_from_company[k]  # si slack es bajo, quitar ayuda más
                    candidates.append((slack, k))
            if not candidates:
                # si no hay candidatos razonables, quitamos cualquiera
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

        # Si llegamos aquí, ya es completables
        return selected_blocks, must_send, can_send

    return None


def _random_partition_to_fill(need: int, must_send: List[int], can_send: List[int], rng: random.Random) -> List[int]:
    """
    Decide cuántas plazas no-dep se eligen por empresa, respetando:
      must_send[k] <= x[k] <= can_send[k]
      sum_k x[k] = need
    """
    x = must_send[:]
    base = sum(x)
    if base > need:
        raise ValueError("Inconsistent: sum(must_send) > needed")

    surplus = need - base
    caps = [can_send[k] - must_send[k] for k in range(len(must_send))]
    order = list(range(len(must_send)))
    rng.shuffle(order)

    for k in order:
        if surplus <= 0:
            break
        take = rng.randint(0, min(caps[k], surplus))
        x[k] += take
        surplus -= take

    # Si todavía queda, repartir de manera determinista (sin romper límites)
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

    return x


def _choose_final_placements(problem, pre: _Preproc, rng: random.Random) -> List[int]:
    """
    Devuelve una lista de exactamente n_students placements:
      - incluye todos los placements de los bloques de dependencias seleccionados (tras fixing)
      - completa con placements no-dep para cumplir mínimos/máximos
    """
    selected_blocks = _random_initial_dep_selection(pre, rng)
    fixed = _fix_dependency_selection(problem, pre, rng, selected_blocks)
    if fixed is None:
        raise ValueError("Failed to fix dependency selection")
    selected_blocks, must_send, can_send = fixed

    chosen_set: Set[int] = set()
    selected_from_company = [0] * problem.n_companies
    total_selected = 0
    for k in range(problem.n_companies):
        for block in selected_blocks.get(k, []):
            for j in block:
                chosen_set.add(j)
            selected_from_company[k] += len(block)
            total_selected += len(block)

    need = problem.n_students - total_selected
    if need < 0:
        raise ValueError("Internal error: selected more than students after fixing")

    # Elegir cuántas no-deps por empresa
    to_pick = _random_partition_to_fill(need, must_send, can_send, rng)

    # Seleccionar placements no-dep concretos
    for k in range(problem.n_companies):
        if to_pick[k] <= 0:
            continue
        pool = pre.nondep_by_company[k]
        if len(pool) < to_pick[k]:
            raise ValueError("Internal error: not enough non-dep placements to pick")
        chosen = rng.sample(pool, to_pick[k])
        chosen_set.update(chosen)

    chosen_list = list(chosen_set)
    if len(chosen_list) != problem.n_students:
        # Por seguridad, aunque el diseño debe garantizar exactitud
        raise ValueError(f"Expected {problem.n_students} placements, got {len(chosen_list)}")

    rng.shuffle(chosen_list)
    return chosen_list


# ----------------------------
# Asignación de profesores (constructivo aleatorizado + repair ligero)
# ----------------------------

def _assign_professors_with_repair(problem, sol: Solution, rng: random.Random,
                                   max_repair_iters: int = 3000) -> bool:
    """
    Asigna placement -> professor para todas las plazas ocupadas.
    """

    # quick infeasibility check
    if sum(problem.prof_capacity) < problem.n_students:
        return False

    assigned_placements = [j for j in range(problem.n_placements) if sol.placement_filled[j]]
    rng.shuffle(assigned_placements)

    prof_to_pl: List[List[int]] = [[] for _ in range(problem.n_professors)]
    unassigned: List[int] = []

    # -------- Constructivo --------
    for j in assigned_placements:
        cand = list(range(problem.n_professors))
        rng.shuffle(cand)

        feasible = [t for t in cand if sol.professor_load[t] < problem.prof_capacity[t]]

        if not feasible:
            unassigned.append(j)
            continue

        t = rng.choice(feasible)

        sol.placement_to_professor[j] = t
        sol.professor_load[t] += 1
        prof_to_pl[t].append(j)

    if not unassigned:
        return True

    # -------- Repair --------
    for _ in range(max_repair_iters):

        if not unassigned:
            return True

        j = unassigned[-1]

        cand = list(range(problem.n_professors))
        rng.shuffle(cand)

        feasible = [t for t in cand if sol.professor_load[t] < problem.prof_capacity[t]]

        if feasible:
            t = rng.choice(feasible)

            sol.placement_to_professor[j] = t
            sol.professor_load[t] += 1
            prof_to_pl[t].append(j)

            unassigned.pop()
            continue

        target_pool = cand[:]
        rng.shuffle(target_pool)

        moved = False

        for t_full in target_pool:

            if not prof_to_pl[t_full]:
                continue

            rng.shuffle(prof_to_pl[t_full])

            for j2 in list(prof_to_pl[t_full]):

                k2 = problem.placement_company[j2]

                cand2 = list(range(problem.n_professors))
                rng.shuffle(cand2)

                dests = [
                    t2 for t2 in cand2
                    if t2 != t_full and sol.professor_load[t2] < problem.prof_capacity[t2]
                ]

                if not dests:
                    continue

                t2 = rng.choice(dests)

                # mover j2
                sol.placement_to_professor[j2] = t2
                sol.professor_load[t_full] -= 1
                sol.professor_load[t2] += 1

                prof_to_pl[t_full].remove(j2)
                prof_to_pl[t2].append(j2)

                # asignar j
                sol.placement_to_professor[j] = t_full
                sol.professor_load[t_full] += 1
                prof_to_pl[t_full].append(j)

                unassigned.pop()
                moved = True
                break

            if moved:
                break

        if not moved:
            rng.shuffle(unassigned)

    return False

# ----------------------------
# Construcción final de Solution
# ----------------------------

def generate_random_feasible_fixing(problem, seed = None, max_attempts = 50):
    """
    Genera una Solution aleatoria y factible usando:
      A) random + fixing para dependencias y cuotas empresa, luego completar con no-deps
      B) asignación de profesores dependiente de A: constructivo aleatorizado + repair

    Nota: max_attempts se mantiene como "paracaídas" por robustez.
    """
    rng = random.Random(seed)
    pre = _preprocess(problem)

    for _ in range(max_attempts):
        try:
            chosen_placements = _choose_final_placements(problem, pre, rng)

            # Construir asignación estudiante->placement (aleatoria)
            students = list(range(problem.n_students))
            rng.shuffle(students)
            rng.shuffle(chosen_placements)

            sol = Solution(problem)

            # Asignamos student->placement sin profesor todavía, actualizando estructuras coherentes
            # (usamos las estructuras internas de Solution)
            for i, j in zip(students, chosen_placements):
                sol.student_to_placement[i] = j
                sol.placement_filled[j] = True
                k = problem.placement_company[j]
                sol.company_load[k] += 1

            # Verificación rápida de mínimos/máximos empresa antes de profes
            ok = True
            for k in range(problem.n_companies):
                if sol.company_load[k] < problem.company_min[k] or sol.company_load[k] > problem.company_max[k]:
                    ok = False
                    break
            if not ok or not sol.dependencies_ok():
                continue

            # Asignar profesores + repair
            if not _assign_professors_with_repair(problem, sol, rng):
                continue

            # Validación final
            if sol.validate():
                return sol

        except ValueError:
            continue

    raise ValueError(f"No feasible random solution found after {max_attempts} attempts")


# Alias si quieres mantener naming similar a tu módulo anterior
generate_random_feasible = generate_random_feasible_fixing