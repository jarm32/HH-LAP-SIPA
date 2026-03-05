# Generador de soluciones aleatorias factibles (random + fixing) --> 1º Asignación estudiante -> plaza (con dependencias y cuotas por empresa) / 2º Asignación plaza -> profesor (con capacidades y centros)

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional

from tools.solution import Solution


# ----------------------------
# Utilidades: preprocesado de bloques y listas por empresa
# ----------------------------

@dataclass
class _Preproc:
    placements_by_company: List[List[int]]
    nondep_by_company: List[List[int]]
    dep_blocks_by_company: List[List[List[int]]]  # company -> list of blocks (each block is list of placements)
    placement_in_any_dep: List[bool]
    total_in_deps_by_company: List[int]


def _preprocess(problem: Problem) -> _Preproc:
    placements_by_company = [[] for _ in range(problem.n_companies)]
    for j in range(problem.n_placements):
        placements_by_company[problem.placement_company[j]].append(j)

    placement_in_any_dep = [False] * problem.n_placements
    dep_blocks_by_company = [[] for _ in range(problem.n_companies)]
    total_in_deps_by_company = [0] * problem.n_companies

    for dep in problem.dependencies:
        if not dep:
            continue
        k = problem.placement_company[dep[0]]
        block = list(dep)
        dep_blocks_by_company[k].append(block)
        for j in block:
            placement_in_any_dep[j] = True
        total_in_deps_by_company[k] += len(block)

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
    )


# ----------------------------
# Fase A: random + fixing de dependencias, y completar con no-deps
# ----------------------------

def _random_initial_dep_selection(pre: _Preproc, rng: random.Random) -> Dict[int, List[List[int]]]:
    """
    Selección completamente aleatoria de bloques de dependencia por empresa.
    Devuelve un dict: company -> lista de blocks seleccionados (cada block: lista de placements).
    """
    selected: Dict[int, List[List[int]]] = {k: [] for k in range(len(pre.dep_blocks_by_company))}
    for k, blocks in enumerate(pre.dep_blocks_by_company):
        if not blocks:
            continue
        # elige n bloques aleatorios (n puede ser 0..len(blocks))
        n = rng.randint(0, len(blocks))
        if n > 0:
            chosen = rng.sample(blocks, n)
            selected[k] = [list(b) for b in chosen]
    return selected


def _recompute_counters(problem: Problem, pre: _Preproc, selected_blocks: Dict[int, List[List[int]]]):
    selected_from_company = [0] * problem.n_companies
    total_selected = 0

    for k in range(problem.n_companies):
        s = sum(len(b) for b in selected_blocks.get(k, []))
        selected_from_company[k] = s
        total_selected += s

    unassigned_nondep = [len(pre.nondep_by_company[k]) for k in range(problem.n_companies)]

    must_send = [0] * problem.n_companies
    can_send = [0] * problem.n_companies
    for k in range(problem.n_companies):
        must_send[k] = max(problem.company_min[k] - selected_from_company[k], 0)
        can_send[k] = min(max(problem.company_max[k] - selected_from_company[k], 0), unassigned_nondep[k])

    total_can = sum(can_send)
    return selected_from_company, total_selected, must_send, can_send, unassigned_nondep, total_can


def _remove_random_block_from_company(selected_blocks: Dict[int, List[List[int]]], k: int, rng: random.Random) -> bool:
    blocks = selected_blocks.get(k, [])
    if not blocks:
        return False
    idx = rng.randrange(len(blocks))
    blocks.pop(idx)
    return True

def _add_random_block_from_company(pre, selected_blocks, k, rng):
    """
    Activa aleatoriamente un bloque de dependencias no seleccionado de la empresa k.
    """
    existing = selected_blocks.get(k, [])
    available = []

    for block in pre.dep_blocks_by_company[k]:
        if block not in existing:
            available.append(block)

    if not available:
        return False

    block = rng.choice(available)
    selected_blocks.setdefault(k, []).append(list(block))
    return True


def _remove_random_block_any(selected_blocks: Dict[int, List[List[int]]], rng: random.Random) -> bool:
    companies_with_blocks = [k for k, bl in selected_blocks.items() if bl]
    if not companies_with_blocks:
        return False
    k = rng.choice(companies_with_blocks)
    return _remove_random_block_from_company(selected_blocks, k, rng)


def _fix_dependency_selection(problem: Problem, pre: _Preproc, rng: random.Random,
                            selected_blocks: Dict[int, List[List[int]]],
                            max_iters: int = 5000) -> Optional[Tuple[Dict[int, List[List[int]]], List[int], List[int]]]:
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
                k = candidates[0][1]
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


def _choose_final_placements(problem: Problem, pre: _Preproc, rng: random.Random) -> List[int]:
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
# Fase B: asignación de profesores (constructivo aleatorizado + repair ligero)
# ----------------------------

def _prof_candidates_sorted(problem: Problem, company_k: int) -> List[int]:
    """
    Devuelve profesores ordenados por distancia centro->empresa (menor es mejor).
    """
    # distancia del centro del profesor t a la empresa k
    # center_company_dist[center][k]
    d = []
    for t in range(problem.n_professors):
        c = problem.prof_center[t]
        d.append((problem.center_company_dist[c][company_k], t))
    d.sort(key=lambda x: x[0])
    return [t for _, t in d]


def _assign_professors_with_repair(problem: Problem, sol: Solution, rng: random.Random, 
                                   max_repair_iters: int = 3000, top_k = None) -> bool:
    """
    Asigna placement->professor para todos los placements ocupados en sol.
    - Constructivo: placements en orden aleatorio; elige prof aleatorio entre top_k candidatos con capacidad.
    - Repair: si quedan sin asignar, intenta liberar capacidad mediante moves simples.
    """

    # quick infeasibility check
    if sum(problem.prof_capacity) < problem.n_students:
        return False

    # placements asignados (ocupados por estudiantes)
    assigned_placements = [j for j in range(problem.n_placements) if sol.placement_filled[j]]
    rng.shuffle(assigned_placements)

    prof_to_pl: List[List[int]] = [[] for _ in range(problem.n_professors)]
    unassigned: List[int] = []

    # Constructivo
    for j in assigned_placements:
        k = problem.placement_company[j]
        
        # Candidatos
        if top_k is None:
            cand_sorted = list(range(problem.n_professors))
        else:
            cand_sorted = _prof_candidates_sorted(problem, k)

        # Filtra por capacidad disponible
        feasible = [t for t in cand_sorted if sol.professor_load[t] < problem.prof_capacity[t]]
        if not feasible:
            unassigned.append(j)
            continue
        
        # Elige aleatoriamente entre los candidatos
        if top_k is None:
            chosen_pool = feasible
        else:
            chosen_pool = feasible[:min(top_k, len(feasible))]
        t = rng.choice(chosen_pool)

        sol.placement_to_professor[j] = t
        sol.professor_load[t] += 1
        prof_to_pl[t].append(j)

    if not unassigned:
        return True

    # Repair ligero
    # Idea: para cada placement sin profesor, intentar:
    #  - asignarlo a un prof "preferido" que está lleno
    #  - mover 1 placement "movible" de ese prof a otro prof con hueco, y así liberar
    for _ in range(max_repair_iters):
        if not unassigned:
            return True

        j = unassigned[-1]
        k = problem.placement_company[j]
        cand_sorted = _prof_candidates_sorted(problem, k)

        # 1) si aparece alguno con hueco (por cambios previos), asignar directo
        feasible = [t for t in cand_sorted if sol.professor_load[t] < problem.prof_capacity[t]]
        if feasible:
            t = rng.choice(feasible[: min(top_k, len(feasible))])
            sol.placement_to_professor[j] = t
            sol.professor_load[t] += 1
            prof_to_pl[t].append(j)
            unassigned.pop()
            continue

        # 2) intentar liberar espacio en un candidato bueno "lleno"
        # elegimos un candidato dentro de top_k (o el primero) y tratamos de eyectar una plaza suya
        target_pool = cand_sorted[: min(top_k, len(cand_sorted))]
        rng.shuffle(target_pool)

        moved = False
        for t_full in target_pool:
            if not prof_to_pl[t_full]:
                continue

            # intenta mover una de sus plazas a otro profesor con capacidad
            rng.shuffle(prof_to_pl[t_full])
            for j2 in list(prof_to_pl[t_full]):
                k2 = problem.placement_company[j2]
                cand2 = _prof_candidates_sorted(problem, k2)
                dests = [t2 for t2 in cand2 if t2 != t_full and sol.professor_load[t2] < problem.prof_capacity[t2]]
                if not dests:
                    continue

                # mover j2 a t2
                t2 = rng.choice(dests[: min(top_k, len(dests))])

                sol.placement_to_professor[j2] = t2
                sol.professor_load[t_full] -= 1
                sol.professor_load[t2] += 1

                prof_to_pl[t_full].remove(j2)
                prof_to_pl[t2].append(j2)

                # ahora t_full tiene hueco, asignamos j a t_full
                sol.placement_to_professor[j] = t_full
                sol.professor_load[t_full] += 1
                prof_to_pl[t_full].append(j)

                unassigned.pop()
                moved = True
                break

            if moved:
                break

        if moved:
            continue

        # si no hemos podido mover nada en esta iteración, barajamos y seguimos
        rng.shuffle(unassigned)

    return False


# ----------------------------
# Construcción final de Solution
# ----------------------------

def generate_random_feasible_fixing(problem: Problem, seed: Optional[int] = None, max_attempts: int = 50) -> Solution:
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
            # (usamos las estructuras internas de Solution) :contentReference[oaicite:2]{index=2}
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