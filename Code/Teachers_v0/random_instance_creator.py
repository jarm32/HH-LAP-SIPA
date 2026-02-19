# ----------------------------
# Librerías
# ----------------------------

import random
import numpy as np
import json
import math
import sys
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

# ----------------------------
# Configuración inicial // helpers
# ----------------------------

# from openrouteservice import Client, distance_matrix
# ORS_AVAILABLE = True

ORS_AVAILABLE = False # Distancias sintéticas

@dataclass
class GeneratorConfig:
    # Configuración general
    result_path: str
    start_size: int
    end_size: int
    number_instances: int
    surplus: int
    placement_dep_prob: float
    number_competences: int
    most_important_competences: int

    # Profesores / centros
    n_centers_min: int = 2
    n_centers_max: int = 6
    profs_per_center_min: int = 3
    profs_per_center_max: int = 12

    # Capacidad por profesor (Ct)
    prof_capacity_min: int = 5
    prof_capacity_max: int = 25

    # ORS // Distancias sintéticas
    use_ors: bool = True
    ors_base_url: str = "http://localhost:8080/ors"

    synthetic_dist_mu: float = 1500.0
    synthetic_dist_sigma: float = 250.0


# En caso de que usemos ORS, esta función hace la matriz de tiempos con valores reales
def request_matrix_api(client, sources, destinations):
    resp = distance_matrix.distance_matrix(client, sources + destinations,
        sources=[i for i in range(len(sources))],
        destinations=[i for i in range(len(sources), len(sources) + len(destinations))]
    )
    return resp

# Crea una distancia sintética al no usar ORS
def synthetic_duration():
    return max(1.0, random.normalvariate(1500, 250))


# ----------------------------
# Competencias: necesidades (empresas) y perfiles (estudiantes)
# ----------------------------

def create_competence_need_vector(number_competences, most_important): 
                                  # nº de competencias y nº de competencias importantes (medianamente importante solo hay 1 siempre)
    """
    Genera el vector de necesidades de competencias de una plaza,
    con most_important competencias al 1.0, la medianamente importante al 0.5 y el resto a 0.0

    Resulta ordenado, pero se shuffleará luego para no tener siempre las mismas competencias importantes
    """
    if most_important + 1 > number_competences:
        raise ValueError("most_important must be <= n-1")
    competence_need = ([1.0] * most_important) + [0.5]
    if (most_important + 1) < number_competences:
        competence_need += [0.0 for _ in range(number_competences - most_important - 1)]
    return competence_need  # vector tipo: [1,1,...,0.5,0,0,...]. S


def create_student_profile(p_excellence_students, number_competences, number_profiles, student_locations, profile_prob): 
                           # vector de dos elementos (prob de alumno excelente // prob de alumno notable), nº de competencias base a considerar (por perfil),
                           # número de perfiles académicos distintos (informático, industrial...) --> el nº de competencias se multiplica por este número para generar perfiles con diferentes competencias importantes,
                           # probs para decidir donde habita cada estudiante, y probs para decidir el perfil académico de cada estudiante
    """
    Genera un estudiante completo de forma aleatoria:
    decide su nivel académico, construye su vector de competencias y preferencias según un perfil específico, 
    y le asigna una localización y otros atributos
    """
    
    # Determina el tipo de estudiante
    p_excellent_student = p_excellence_students[0]
    p_notable_student = p_excellence_students[1]

    r = random.random()
    if r <= p_excellent_student:
        n_excellent = int(0.8 * number_competences)
        n_notable = number_competences - n_excellent
        competence_development = [random.random() * (1 - 0.7) + 0.7 for _ in range(n_excellent)] + \
                                 [random.random() * (0.7 - 0.4) + 0.4 for _ in range(n_notable)]
    elif r <= (p_excellent_student + p_notable_student):
        n_excellent = int(0.1 * number_competences)
        n_notable = int(0.3 * number_competences)
        n_low = number_competences - n_excellent - n_notable
        competence_development = [random.random() * (1 - 0.7) + 0.7 for _ in range(n_excellent)] + \
                                 [random.random() * (0.7 - 0.4) + 0.4 for _ in range(n_notable)] + \
                                 [random.random() * 0.4 for _ in range(n_low)]
    else:
        n_notable = int(0.2 * number_competences)
        n_low = number_competences - n_notable
        competence_development = [random.random() * (0.7 - 0.4) + 0.4 for _ in range(n_notable)] + \
                                 [random.random() * 0.4 for _ in range(n_low)]

    random.shuffle(competence_development)

    # Elige una competencia fuerte del estudiante
    comp_idx = np.random.choice(number_competences, 1, p=np.array(competence_development) / np.sum(competence_development))
    competence_preference = [random.random() * 0.3 for _ in range(number_competences)]
    competence_preference[int(comp_idx[0])] = 1.0
    random.shuffle(competence_preference)

    # Elige el perfil académico
    profile = int(np.random.choice(number_profiles, 1, p=profile_prob)[0])

    # Expande a number_profiles * number_competences (solo su bloque de perfil tiene valores)
    competence_development = ([0.0] * (profile * number_competences)) + competence_development + \
                             ([0.0] * ((number_profiles - profile - 1) * number_competences))
    competence_preference = ([0.0] * (profile * number_competences)) + competence_preference + \
                            ([0.0] * ((number_profiles - profile - 1) * number_competences))

    # Asigna localización (dónde vive) y otros atributos (tiene coche y cuánto le importa la distancia vs. el desarrollo profesional)
    r_loc = random.random()
    acum = 0.0
    location_name = None
    for (location, prob) in student_locations:
        acum += prob
        if r_loc <= acum:
            location_name = location
            break
    if location_name is None:
        location_name = student_locations[-1][0]

    has_car = True if random.random() <= 0.65 else False
    w_distance = round(random.random() * 0.5, 2)
    w_dev = round(1 - w_distance, 2)

    loc_file = open(f"../data/points/{location_name}.geojson", "r")
    loc_obj = json.load(loc_file)
    (latitude, longitude) = random.choice(loc_obj["features"])["geometry"]["coordinates"]
    loc_file.close()

    return latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference 
           # Genera un vector con el perfil del estudiante: latitud y longitud de su casa, si tiene coche, el peso que le da el estudiante a la distancia y el que le da al desarrollo profesional,
           # su vector de desarrollo de competencias y su vector de preferencias de competencias (en ambos casos, solo el bloque de su perfil tiene valores; el resto son ceros)



##################################################

# ----------------------------
# Bloque: empresas, plazas y dependencias (ajustado para factibilidad)
# ----------------------------

def number_placements_for_business(number_businesses, base_per_business, surplus, percentage=0.25, prob_major=0.8):
    placement_vec = np.full(number_businesses, base_per_business, dtype=int)
    businesses_to_consider = np.random.choice(number_businesses, max(1, int(number_businesses * percentage)), replace=False)
    for _ in range(surplus):
        if random.random() <= prob_major:
            rnd_idx = int(random.choice(businesses_to_consider))
        else:
            rnd_idx = random.randint(0, number_businesses - 1)
        placement_vec[rnd_idx] += 1
    return placement_vec


def create_dependencies(placements: List[int], percentage_dependencies: float) -> List[List[int]]:
    """
    Genera grupos de dependencias (tamaño >=2) dentro de una lista de plazas.
    """
    if len(placements) < 2:
        return []

    count = int(len(placements) * percentage_dependencies / 100.0)
    if count < 2:
        return []

    placements_in_dep = np.random.choice(placements, count, replace=False)
    n_dependent = len(placements_in_dep)

    sizes = []
    while n_dependent >= 2:
        if n_dependent <= 3:
            s = n_dependent
        else:
            s = random.randint(2, n_dependent - 1)
        sizes.append(s)
        n_dependent -= s

    deps = []
    k = 0
    for s in sizes:
        dep = [int(placements_in_dep[k + r]) for r in range(s)]
        k += s
        if len(dep) >= 2:
            deps.append(dep)
    return deps


def build_company_blocks(placements_of_company: List[int], dep_groups_in_company: List[List[int]]) -> List[List[int]]:
    """
    Convierte "dependencias" en bloques indivisibles (cada grupo es un bloque),
    y añade como bloques singleton las plazas que no están en ningún grupo.
    """
    used = set()
    blocks = []
    for g in dep_groups_in_company:
        blocks.append(list(g))
        used.update(g)

    for j in placements_of_company:
        if j not in used:
            blocks.append([j])
    return blocks


def choose_min_quota_from_blocks(blocks: List[List[int]], max_students: int) -> int:
    """
    El mínimo de empresa se construye como suma de bloques completos.
    Así evitamos pedir "1 plaza" que pertenezca a un grupo de tamaño 3.
    """
    # Elegimos cuántos bloques exigir (al azar), sin pasarnos de max_students
    sizes = [len(b) for b in blocks]
    order = list(range(len(blocks)))
    random.shuffle(order)

    min_q = 0
    for idx in order:
        if min_q + sizes[idx] <= max_students and random.random() <= 0.35:
            min_q += sizes[idx]

    # Asegura al menos 0 o 1 bloque a veces (si cabe)
    if min_q == 0 and blocks and random.random() <= 0.25:
        # mete un bloque pequeño si cabe
        smallest = min(sizes)
        if smallest <= max_students:
            min_q = smallest

    return min_q


def adjust_max_quotas(max_q: List[int], placements_per_company: List[int], n_students: int) -> List[int]:
    """
    Garantiza: max_q[k] <= plazas_empresa[k] y sum(max_q) >= n_students.
    Si sum(max_q) es pequeño, incrementa (sin pasar de plazas).
    """
    max_q = [min(max_q[k], placements_per_company[k]) for k in range(len(max_q))]
    total = sum(max_q)
    if total >= n_students:
        return max_q

    # Reparte incrementos donde haya margen
    idxs = list(range(len(max_q)))
    while total < n_students:
        random.shuffle(idxs)
        progressed = False
        for k in idxs:
            if max_q[k] < placements_per_company[k]:
                max_q[k] += 1
                total += 1
                progressed = True
                if total >= n_students:
                    break
        if not progressed:
            # No hay más margen, debería no ocurrir si n_placements >= n_students
            break
    return max_q


# ----------------------------
# Bloque: centros y profesores (nuevo, factible por construcción)
# ----------------------------

def sample_geo_points_from_locations(n: int, location_names: List[str]) -> List[Tuple[float, float]]:
    """
    Toma puntos (lat,lon) de los geojson de locations.
    """
    points = []
    for _ in range(n):
        loc = random.choice(location_names)
        with open(f"../data/points/{loc}.geojson", "r") as f:
            obj = json.load(f)
        (lat, lon) = random.choice(obj["features"])["geometry"]["coordinates"]
        points.append((lat, lon))
    return points


def create_centers_and_professors(n_students: int,
                                 location_names: List[str],
                                 cfg: GeneratorConfig) -> Tuple[List[Tuple[float, float]], List[int], List[int]]:
    """
    Devuelve:
      - centers_coords: [(lat,lon) por centro]
      - prof_center: center_id de cada profesor
      - prof_capacity: Ct de cada profesor
    Factibilidad: sum(Ct) >= n_students.
    """
    n_centers = random.randint(cfg.n_centers_min, cfg.n_centers_max)
    centers_coords = sample_geo_points_from_locations(n_centers, location_names)

    prof_center = []
    prof_capacity = []

    # Genera un nº de profes por centro
    for c in range(n_centers):
        n_profs_c = random.randint(cfg.profs_per_center_min, cfg.profs_per_center_max)
        for _ in range(n_profs_c):
            prof_center.append(c)
            prof_capacity.append(random.randint(cfg.prof_capacity_min, cfg.prof_capacity_max))

    # Asegura capacidad total
    total_cap = sum(prof_capacity)
    if total_cap < n_students:
        # Sube capacidades hasta cubrir
        need = n_students - total_cap
        i = 0
        while need > 0:
            add = min(need, 5)
            prof_capacity[i] += add
            need -= add
            i = (i + 1) % len(prof_capacity)

    return centers_coords, prof_center, prof_capacity


# ----------------------------
# Escritura de instancia (backward-friendly)
# ----------------------------

def write_instance_file(filename: str,
                        n_students: int,
                        n_companies: int,
                        n_placements: int,
                        n_competences_total: int,
                        dependencies_all: List[List[int]],
                        student_info_rows: List[Tuple],
                        company_min: List[int],
                        company_max: List[int],
                        placement_company: List[int],
                        placement_comp_needs: List[List[float]],
                        student_company_matrix: List[List[float]],
                        # Nuevos: companies coords
                        company_coords: List[Tuple[float, float]],
                        # Nuevos: centers/profs
                        centers_coords: List[Tuple[float, float]],
                        prof_center: List[int],
                        prof_capacity: List[int],
                        # Nuevo: matriz centro->empresa
                        center_company_matrix: List[List[float]]):
    with open(filename, "w") as fd:
        fd.write(f"n_students\t{n_students}\n")
        fd.write(f"n_companies\t{n_companies}\n")
        fd.write(f"n_placements\t{n_placements}\n")
        fd.write(f"n_competences\t{n_competences_total}\n")
        fd.write(f"n_dependent\t{len(dependencies_all)}\n")

        # --- Original blocks ---
        fd.write("STUDENT_INFO\n")
        for row in student_info_rows:
            # row: (i, w_distance, w_dev, dev_vec, pref_vec)
            i, w_dist, w_dev, dev_vec, pref_vec = row
            fd.write(
                "{}\t{}\t{}\t{}\t{}\n".format(
                    i,
                    w_dist,
                    w_dev,
                    "\t".join([str(round(x, 2)) for x in dev_vec]),
                    "\t".join([str(round(x, 2)) for x in pref_vec]),
                )
            )

        fd.write("COMPANY_INFO\n")
        for k in range(n_companies):
            fd.write(f"{k}\t{int(company_min[k])}\t{int(company_max[k])}\n")

        fd.write("PLACEMENT_INFO\n")
        for j in range(n_placements):
            needs = placement_comp_needs[j]
            fd.write(f"{j}\t{placement_company[j]}\t" + "\t".join([str(round(x, 2)) for x in needs]) + "\n")

        fd.write("PLACEMENT_DEPENDENCIES\n")
        for dep in dependencies_all:
            fd.write("\t".join(str(x) for x in dep) + "\n")

        fd.write("DISTANCE_MATRIX\n")
        for row in student_company_matrix:
            fd.write("\t".join(str(d) for d in row) + "\n")

        # --- New blocks (Extended model) ---
        fd.write("COMPANY_LOCATIONS\n")
        for k, (lat, lon) in enumerate(company_coords):
            fd.write(f"{k}\t{lat}\t{lon}\n")

        fd.write("n_centers\t{}\n".format(len(centers_coords)))
        fd.write("n_professors\t{}\n".format(len(prof_center)))

        fd.write("CENTER_LOCATIONS\n")
        for c, (lat, lon) in enumerate(centers_coords):
            fd.write(f"{c}\t{lat}\t{lon}\n")

        fd.write("PROFESSOR_INFO\n")
        for t in range(len(prof_center)):
            fd.write(f"{t}\t{prof_center[t]}\t{prof_capacity[t]}\n")

        fd.write("CENTER_COMPANY_DISTANCE\n")
        for row in center_company_matrix:
            fd.write("\t".join(str(d) for d in row) + "\n")


# ----------------------------
# Main generator (factible por construcción)
# ----------------------------

def generate_instances(cfg: GeneratorConfig):
    # Carga distribuciones de localización (igual que original)
    all_student_locations_prop = []
    with open("../data/proportion_home.csv", "r") as f:
        for line in f.readlines():
            tokens = line.split("\t")
            all_student_locations_prop.append((tokens[0], float(tokens[1])))

    all_business_locations = []
    with open("../data/placement_locations.csv", "r") as f:
        for line in f.readlines():
            tokens = line.split("\t")
            all_business_locations.append((float(tokens[1]), float(tokens[0])))

    location_names = [x[0] for x in all_student_locations_prop]

    # ORS client (si procede)
    client = None
    use_ors = cfg.use_ors and ORS_AVAILABLE
    if use_ors:
        client = Client(base_url=cfg.ors_base_url)

    number_profiles = 8
    p_excellent_student = 0.05
    p_notable_student = 0.25

    for n_students in range(cfg.start_size, cfg.end_size + 100, 200):
        n_instance = 0

        while n_instance < cfg.number_instances:
            # perfiles
            profile_prob = np.random.random(number_profiles)
            profile_prob = profile_prob / np.sum(profile_prob)

            # ---- Students ----
            student_info = []
            profiles_used = []
            for i in range(n_students):
                lat, lon, has_car, w_dist, w_dev, dev_vec, pref_vec = create_student_profile(
                    [p_excellent_student, p_notable_student],
                    cfg.number_competences,
                    number_profiles,
                    all_student_locations_prop,
                    profile_prob
                )
                profiles_used.append(pref_vec)
                student_info.append((lat, lon, has_car, w_dist, w_dev, dev_vec, pref_vec))

            # ---- Placements ----
            n_placements = int(math.ceil(n_students * (1.0 + cfg.surplus / 100.0)))
            placement_comp_needs = []

            np.random.shuffle(profiles_used)
            for j in range(n_placements):
                if j < len(profiles_used):
                    needs = profiles_used[j].copy()
                    needs = [
                        needs[i] if needs[i] == 0 else max(min(needs[i] + random.normalvariate(0, sigma=0.1), 1), 0)
                        for i in range(len(needs))
                    ]
                    s = sum(needs)
                    needs = [x / s for x in needs] if s > 0 else needs
                else:
                    needs = create_competence_need_vector(cfg.number_competences, cfg.most_important_competences)
                    profile = int(np.random.choice(number_profiles, 1, p=profile_prob)[0])
                    np.random.shuffle(needs)
                    needs = ([0.0] * (profile * cfg.number_competences)) + needs + \
                            ([0.0] * ((number_profiles - profile - 1) * cfg.number_competences))
                placement_comp_needs.append(needs)

            # ---- Companies ----
            # Elegimos nº empresas en rango razonable (como original)
            n_companies = random.randint(max(2, n_placements // 10), max(2, int(cfg.placement_dep_prob / 100 * n_placements / 2)))

            base = n_placements // n_companies
            surplus_placements = n_placements % n_companies
            placements_per_company = number_placements_for_business(n_companies, base, surplus_placements)

            # asignación empresa por plaza
            placement_company = []
            for k in range(n_companies):
                placement_company.extend([k] * int(placements_per_company[k]))
            placement_company = placement_company[:n_placements]

            # --- company placements list
            company_placements: Dict[int, List[int]] = {k: [] for k in range(n_companies)}
            for j, k in enumerate(placement_company):
                company_placements[int(k)].append(j)

            # --- dependencies per company
            dependencies_all: List[List[int]] = []
            dep_groups_per_company: Dict[int, List[List[int]]] = {k: [] for k in range(n_companies)}
            for k in range(n_companies):
                deps = create_dependencies(company_placements[k], cfg.placement_dep_prob)
                # filtra grupos tamaño 1
                deps = [d for d in deps if len(d) >= 2]
                dep_groups_per_company[k] = deps
                dependencies_all.extend(deps)

            # ---- Quotas factibles por construcción ----
            company_min = [0] * n_companies
            company_max = [0] * n_companies

            # Primero max = algo razonable, luego ajustamos para sumar >= n_students
            for k in range(n_companies):
                # max al menos 1 y como mucho plazas de empresa
                cap = len(company_placements[k])
                company_max[k] = random.randint(max(1, cap // 2), cap) if cap > 1 else 1

            company_max = adjust_max_quotas(company_max, [len(company_placements[k]) for k in range(n_companies)], n_students)

            # Ahora min se elige en función de bloques (dep grupos + singletons), y respetando max
            for k in range(n_companies):
                blocks = build_company_blocks(company_placements[k], dep_groups_per_company[k])
                company_min[k] = choose_min_quota_from_blocks(blocks, company_max[k])

            # Asegura suma(min) <= n_students (si no, reduce)
            total_min = sum(company_min)
            if total_min > n_students:
                # reduce mins aleatoriamente (quitando bloques completos implícitamente al bajar el mínimo)
                # (En la práctica, solo necesitamos que la cota no haga imposible asignar todos.)
                excess = total_min - n_students
                idxs = list(range(n_companies))
                random.shuffle(idxs)
                for k in idxs:
                    if excess <= 0:
                        break
                    if company_min[k] > 0:
                        dec = min(company_min[k], excess)
                        company_min[k] -= dec
                        excess -= dec

            # ---- Locations companies ----
            # Tomamos coords de placement_locations.csv
            # (repetimos si n_companies > len(list), usamos choice con replacement)
            company_coords = [all_business_locations[i] for i in np.random.choice(len(all_business_locations), n_companies, replace=True)]

            # ---- Centers / Professors (nuevo) ----
            centers_coords, prof_center, prof_capacity = create_centers_and_professors(n_students, location_names, cfg)

            # ---- Distance matrices ----
            # Student -> Company
            student_coords = [(x[0], x[1]) for x in student_info]
            company_coords_ors = [(x[0], x[1]) for x in company_coords]

            student_company_matrix: List[List[float]] = []
            if use_ors:
                # pedimos fila a fila como en tu original para evitar tamaños enormes
                for i in range(len(student_coords)):
                    resp = request_matrix_api(client, [student_coords[i]], company_coords_ors)
                    durations = resp["durations"][0]
                    student_company_matrix.append([float(d) if d else float(synthetic_duration()) for d in durations])
            else:
                for _ in range(n_students):
                    student_company_matrix.append([float(synthetic_duration()) for _ in range(n_companies)])

            # Center -> Company (nuevo)
            center_company_matrix: List[List[float]] = []
            if use_ors:
                for c in range(len(centers_coords)):
                    resp = request_matrix_api(client, [centers_coords[c]], company_coords_ors)
                    durations = resp["durations"][0]
                    center_company_matrix.append([float(d) if d else float(synthetic_duration()) for d in durations])
            else:
                for _ in range(len(centers_coords)):
                    center_company_matrix.append([float(synthetic_duration()) for _ in range(n_companies)])

            # ---- Write file ----
            out = f"{cfg.result_path}/problem_instance_ext_{n_students}_{n_instance}.txt"

            student_rows = []
            for i in range(n_students):
                (_, _, _, w_dist, w_dev, dev_vec, pref_vec) = student_info[i]
                student_rows.append((i, w_dist, w_dev, dev_vec, pref_vec))

            write_instance_file(
                filename=out,
                n_students=n_students,
                n_companies=n_companies,
                n_placements=n_placements,
                n_competences_total=cfg.number_competences * 8,
                dependencies_all=dependencies_all,
                student_info_rows=student_rows,
                company_min=company_min,
                company_max=company_max,
                placement_company=placement_company,
                placement_comp_needs=placement_comp_needs,
                student_company_matrix=student_company_matrix,
                company_coords=company_coords,
                centers_coords=centers_coords,
                prof_center=prof_center,
                prof_capacity=prof_capacity,
                center_company_matrix=center_company_matrix
            )

            n_instance += 1
            print(f"[OK] written: {out}", flush=True)


def parse_args_to_config(argv) -> GeneratorConfig:
    """
    Mantiene la interfaz similar a tu instance_creator.py original:
      python extended_instance_creator.py <result_path> <start> <end> <num_instances> <surplus> <dep_prob> <n_comp> <most_important>
    """
    if len(argv) < 9:
        raise SystemExit(
            "Usage: python extended_instance_creator.py <result_path> <start_size> <end_size> "
            "<number_instances> <surplus> <placement_dep_prob> <number_competences> <most_important_competences>"
        )

    return GeneratorConfig(
        result_path=argv[1],
        start_size=int(argv[2]),
        end_size=int(argv[3]),
        number_instances=int(argv[4]),
        surplus=int(argv[5]),
        placement_dep_prob=float(argv[6]),
        number_competences=int(argv[7]),
        most_important_competences=int(argv[8]),
        # Si no tienes ORS levantado, pon use_ors=False aquí o modifica el default
        use_ors=True
    )


if __name__ == "__main__":
    cfg = parse_args_to_config(sys.argv)
    generate_instances(cfg)