# Constructor de soluciones aleatorias factibles mediante una heurística simple que, dado un "Problem", devuelve una "Solution" factible

import random
from tools.solution import Solution

def _build_company_blocks(problem): # objeto Problem
    """
    Construye bloques indivisibles por empresa a partir de dependencias
    """
    blocks_by_company = {k: [] for k in range(problem.n_companies)}

    # Dependencias como bloques (vienen como grupos de plazas)
    used = set()
    for dep in problem.dependencies:
        if not dep:
            continue
        
        # Todas las plazas del bloque deben pertenecer a la misma empresa
        companies = {problem.placement_company[j] for j in dep}

        if len(companies) != 1:
            raise ValueError(f"Dependency group {dep} spans multiple companies: {companies}")

        k = companies.pop()
        blocks_by_company[k].append(list(dep))
        used.update(dep)

    # Plazas sueltas (no dependientes) como bloques de tamaño 1
    for j in range(problem.n_placements):
        if j in used:
            continue
        k = problem.placement_company[j]
        blocks_by_company[k].append([j])

    return blocks_by_company # blocks_by_company[k] = lista de bloques, donde cada block es lista de plazas [j1, j2, ...]


def _pick_professor(sol, problem):
    """
    Elige un profesor con capacidad disponible
    """
    candidates = [p for p in range(problem.n_professors) if sol.professor_load[p] < problem.prof_capacity[p]]

    if not candidates:
        return None

    return max(candidates, key=lambda p: problem.prof_capacity[p] - sol.professor_load[p]) # Elige el profesor que más capacidad restante tenga


def _build_once(problem, seed=None): # objeto Problem ya cargado y una semilla para reproducibilidad
    """
    Construye una solución factible aleatoria (sin optimizar).
    Primero satisface los mínimos por empresa usando bloques (dependencias),
    luego completa hasta asignar a todos los estudiantes respetando 
    máximos de empresa, ocupación de plazas y capacidad de profesores
    """
    if seed is not None:
        random.seed(seed)

    sol = Solution(problem)
    blocks_by_company = _build_company_blocks(problem)

    # Satisfacer mínimos por empresa (asignar company_min[k])
    students = list(range(problem.n_students))
    random.shuffle(students)
    student_idx = 0

    for k in range(problem.n_companies):
        needed = problem.company_min[k]
        if needed <= 0:
            continue
        
        blocks = blocks_by_company[k][:]  
        random.shuffle(blocks)             # aleatoriza desempates
        blocks.sort(key=len, reverse=True) # grandes primero

        # Selecciona bloques hasta cubrir qk sin superar Qk
        for block in blocks:
            if needed <= 0:
                break

            block_size = len(block)

            # No exceder Qk
            if sol.company_load[k] + block_size > problem.company_max[k]:
                continue

            # Si no hay suficientes estudiantes restantes, no se puede completar
            if student_idx + block_size > problem.n_students:
                raise ValueError("Not enough students to satisfy company minimums")

            # Asignar cada plaza del bloque a un estudiante distinto
            for j in block:
                t = _pick_professor(sol, problem)
                if t is None:
                    raise ValueError("No professor capacity left while satisfying minimums")

                i = students[student_idx]
                student_idx += 1
                sol.assign(i, j, t)

            needed -= block_size

        if needed > 0:
            raise ValueError(f"Cannot satisfy minimum quota for company {k}")

    # Completar asignación del resto de estudiantes --> Construye una lista de plazas libres por empresa (en forma de bloques)
    all_blocks = []
    for k in range(problem.n_companies):
        for block in blocks_by_company[k]:
            # Si cualquier plaza del bloque ya está ocupada, el bloque ya está parcialmente usado, se salta
            # No debería ocurrir en en bloques dependientes
            if any(sol.placement_filled[j] for j in block):
                continue
            all_blocks.append((k, block))

    random.shuffle(all_blocks)

    # Asigna estudiantes restantes
    while student_idx < problem.n_students:
        assigned = False

        for (k, block) in all_blocks:
            if any(sol.placement_filled[j] for j in block):
                continue

            block_size = len(block)
            if sol.company_load[k] + block_size > problem.company_max[k]:
                continue

            if student_idx + block_size > problem.n_students:
                continue

            # Asignar bloque
            for j in block:
                t = _pick_professor(sol, problem)
                if t is None:
                    raise ValueError("No professor capacity left while completing assignment")

                i = students[student_idx]
                student_idx += 1
                sol.assign(i, j, t)

            assigned = True
            break

        if not assigned:
            raise ValueError("Cannot complete assignment with given quotas/capacities")

    return sol # objeto Solution factible (si se puede construir, si no, ValueError)


def generate_random_feasible(problem, seed=None, max_attempts=50):
    for attempt in range(max_attempts):
        try:
            s = None if seed is None else seed + attempt
            sol = _build_once(problem, s)
            if sol.validate():
                return sol
        except ValueError:
            continue
    raise RuntimeError("No feasible solution found after multiple attempts")