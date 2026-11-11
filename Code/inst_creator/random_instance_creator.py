# Código generador de instancias SIPA con estudiantes, empresas, plazas y profesores de un único centro educativo.

# cd C:\Code\VRAIN-practicas\Code\inst_creator
# python random_instance_creator.py <result_path> <start_size> <end_size> <number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences> [seed]
# python random_instance_creator.py output 200 600 4 20 0.2 30 6 2 1234
# python random_instance_creator.py output 800 1000 4 20 0.2 30 6 2 1250


# ----------------------------
# Librerías
# ----------------------------

# from fileinput import filename
import random
# from openrouteservice import Client, distance_matrix
import numpy as np
import json
import math
import sys
from dataclasses import dataclass


# ----------------------------
# Configuración inicial // helpers
# ----------------------------

#from openrouteservice import Client, distance_matrix
#ORS_AVAILABLE = True

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
    slack_ratio: float = 0.0
    seed: int | None = None # Reproducibilidad

    # Capacidad por profesor (Ct)
    prof_capacity_min: int = 5
    prof_capacity_max: int = 25

    # ORS = False, uso de distancias sintéticas
    use_ors: bool = False 
    #ors_base_url: str = "http://localhost:8080/ors"


# En caso de usar ORS, esta función hace la matriz de tiempos con valores reales
def request_matrix_api(client, sources, destinations):
    resp = distance_matrix.distance_matrix(client, sources + destinations, sources=[i for i in range(len(sources))],
                                           destinations=[i for i in range(len(sources), len(sources) + len(destinations))])
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

    loc_file = open(f"data/points/{location_name}.geojson", "r")
    loc_obj = json.load(loc_file)
    (latitude, longitude) = random.choice(loc_obj["features"])["geometry"]["coordinates"]
    loc_file.close()

    return latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference 
           # Genera un vector con el perfil del estudiante: latitud y longitud de su casa, si tiene coche, el peso que le da el estudiante a la distancia y el que le da al desarrollo profesional,
           # su vector de desarrollo de competencias y su vector de preferencias de competencias (en ambos casos, solo el bloque de su perfil tiene valores; el resto son ceros)


# ----------------------------
# Hacer la instancia factible por construcción (se amolda a las restricciones de empresa y dependencias)
# ----------------------------

def number_placements_for_business(number_businesses, base_per_business, surplus, percentage=0.25, prob_major=0.8):
                                   # número de empresas, plazas por empresa (n_placements/n_companies), número de plazas sobrantes a repartir, 
                                   # porcentaje de empresas importantes para el reparto del surplus, probabilidad de que el surplus vaya a una empresa importante
    """ 
    Distribuye el total de plazas entre empresas (todas parten de un valor base
    y el surplus se reparte de forma sesgada para generar empresas más grandes que otras)
    """
    # Nº de plazas inicial
    placement_vec = np.full(number_businesses, base_per_business, dtype=int)
    businesses_to_consider = np.random.choice(number_businesses, max(1, int(number_businesses * percentage)), replace=False)
    
    # Reparte el surplus
    for _ in range(surplus):
        if random.random() <= prob_major:
            rnd_idx = int(random.choice(businesses_to_consider))
        else:
            rnd_idx = random.randint(0, number_businesses - 1)
        placement_vec[rnd_idx] += 1
    return placement_vec # [5, 8, 4, 6, 9, 3, ...]; Cada índice representa una empresa, y el valor en ese índice es el número de plazas que tiene esa empresa (sumará n_placements)


def create_dependencies(placements, percentage_dependencies):
                        # Lista de índices de plazas de la empresa, porcentaje de plazas que estarán involucradas en dependencias
    """
    Genera grupos de dependencias (tamaño >=2) entre plazas de una empresa.
    """
    # Selecciona las plazas que estarán en dependencias (no necesariamente entre ellas, sino que tendrán alguna)
    if len(placements) < 2:
        return []

    count = int(len(placements) * percentage_dependencies / 100.0)
    if count < 2:
        return []

    placements_in_dep = np.random.choice(placements, count, replace=False)
    n_dependent = len(placements_in_dep)

    # Divide las plazas dependientes en grupos de tamaño aleatorio (entre 2 y n_dependent-1) hasta que queden menos de 2 sin agrupar
    sizes = []
    while n_dependent >= 2:
        if n_dependent <= 3:
            s = n_dependent
        else:
            s = random.randint(2, n_dependent - 1)
        sizes.append(s)
        n_dependent -= s

    # Crea cada grupo de dependencias como lista de plazas
    deps = []
    k = 0
    for s in sizes:
        dep = [int(placements_in_dep[k + r]) for r in range(s)]
        k += s
        if len(dep) >= 2:
            deps.append(dep)
    return deps # [[3, 6], [4, 7, 5]]...; cada sublista representa un grupo de plazas que dependen entre sí


def build_company_blocks(placements_of_company, dep_groups_in_company):
                        # Lista de índices de plazas de la empresa, lista de grupos de dependencias (lista de listas de índices de plazas)
    """
    Convierte las dependencias en bloques indivisibles (cada grupo es un bloque),
    y añade como bloques aislados las plazas que no están en ningún grupo.
    """
    used = set()
    blocks = []
    for g in dep_groups_in_company:
        blocks.append(list(g))
        used.update(g)

    for j in placements_of_company:
        if j not in used:
            blocks.append([j])
    return blocks # [[3, 6], [4, 7, 5], [2], [8], ...]; cada sublista representa un bloque de plazas que deben asignarse juntas)


def choose_min_quota_from_blocks(blocks, max_students):
                                # lista de bloques de una empresa, número máximo de estudiantes que la empresa puede aceptar
    """
    Construye la cuota mínima de estudiantes para una empresa como suma de bloques completos
    (dependencias o plazas individuales), garantizando que nunca se exija una parte de un bloque dependiente,
    y que no se supere el máximo permitido por la empresa
    """
    # Elige cuántos bloques exigir (al azar), sin pasarnos de max_students
    sizes = [len(b) for b in blocks]
    order = list(range(len(blocks)))
    random.shuffle(order)

    min_q = 0
    for idx in order:
        if min_q + sizes[idx] <= max_students and random.random() <= 0.35:
            min_q += sizes[idx]

    # Asegura al menos 0 o 1 bloque, a veces, si cabe
    if min_q == 0 and blocks and random.random() <= 0.25:
        smallest = min(sizes)
        if smallest <= max_students:
            min_q = smallest

    return min_q # número entero que representa el mínimo de estudiantes exigidos para la empresa

def adjust_max_quotas(max_q, placements_per_company, n_students, slack_ratio=0.0):
                      # nº máximo de estudiantes por empresa (preliminar, nº de plazas reales de la empresa), número de plazas por empresa, número total de estudiantes a asignarse
    """
    Ajusta las cuotas máximas por empresa garantizando que no superen
    las plazas reales disponibles y que la suma total permita asignar
    a todos los estudiantes.
    """    
    # Objetivo con holgura, pero nunca podemos superar plazas reales totales
    max_q = [min(max_q[k], placements_per_company[k]) for k in range(len(max_q))]
    total = sum(max_q)

    total_placements = sum(placements_per_company)
    target = int(math.ceil(n_students * (1.0 + slack_ratio)))
    target = min(target, total_placements)
    target = max(target, n_students)

    if total >= target:
        return max_q

    # Reparte incrementos donde haya margen si no hay capacidad suficiente
    idxs = list(range(len(max_q)))
    while total < target:
        random.shuffle(idxs)
        progressed = False
        for k in idxs:
            if max_q[k] < placements_per_company[k]:
                max_q[k] += 1
                total += 1
                progressed = True
                if total >= target:
                    break
        if not progressed:
            # No hay más margen, debería no ocurrir si n_placements >= n_students
            break

    return max_q # [5, 10, 4, 9]; lista de máximos ajustados y factibles


# ----------------------------
# Hacer la instancia factible por construcción (capacidades de profesores)
# ----------------------------

def sample_geo_points_from_locations(n, location_names):
                                    # nº de puntos a generar, lista de nombres de localizaciones disponibles (cada nombre corresponde a un archivo geojson)
    """
    Genera n coordenadas geográficas aleatorias a partir 
    de los geojson de las localizaciones disponibles
    """
    # Cargar todos los puntos disponibles (únicos)
    pool = []
    seen = set()
    for loc in location_names:
        with open(f"data/points/{loc}.geojson", "r") as f:
            obj = json.load(f)
        for feat in obj.get("features", []):
            coords = feat["geometry"]["coordinates"]
            # coords viene como (lat, lon) en tu código actual
            p = (float(coords[0]), float(coords[1]))
            if p not in seen:
                seen.add(p)
                pool.append(p)

    if not pool:
        raise ValueError("No se han encontrado puntos en los geojson de data/points/")

    # Muestreo sin repetición si se puede
    if n <= len(pool):
        return random.sample(pool, n)

    # Si se piden más de los que hay, devuelve todos y completa con reemplazo
    points = list(pool)
    points.extend(random.choice(pool) for _ in range(n - len(pool)))
    return points # [(lat1, lon1), (lat2, lon2), ...]; lista de coordenadas


def create_center_and_professors(n_students, location_names, cfg):
                                # Nº total de estudiantes, localizaciones disponibles y configuración del generador
    """
    Genera la ubicación del centro educativo y a los profesores con
    cantidades y capacidades aleatorias, garantizando la capacidad total
    necesaria y respetando los límites individuales
    """
    center_coords = sample_geo_points_from_locations(1, location_names)[0] # (lat, lon) del centro educativo
    target_cap = int(math.ceil(n_students * (1.0 + cfg.slack_ratio))) # Capacidad total necesaria, incluyendo holgura
    min_cap, max_cap = cfg.prof_capacity_min, cfg.prof_capacity_max
    
    # Límites que garantizan que existe una distribución factible
    feasible_min = math.ceil(target_cap / max_cap)
    feasible_max = target_cap // min_cap
    
    # Intervalo
    min_professors = max(feasible_min, math.ceil(target_cap / 22))
    max_professors = min(feasible_max, target_cap // 10)
    if min_professors > max_professors:
        min_professors = feasible_min
        max_professors = feasible_max

    # Favorecer ligeramente los extremos del intervalo
    count = max_professors - min_professors + 1
    if count < 3:
        n_professors = random.randint(min_professors, max_professors)
    else:
        cut1 = min_professors + count // 3
        cut2 = min_professors + (2 * count) // 3
        ranges = (range(min_professors, cut1), range(cut1, cut2), range(cut2, max_professors + 1))

        # Probabilidades: 35 %, 30 %, 35 %
        selected_range = random.choices(ranges, weights=(35, 30, 35), k=1)[0]
        n_professors = random.choice(selected_range)

    # ----------------------------------------
    # Capacidades individuales heterogéneas
    # ----------------------------------------

    mean_capacity = target_cap / n_professors

    # Intensidad aleatoria de la dispersión
    # Valores bajos: capacidades más similares
    # Valores altos: mayor amplitud de capacidades
    dispersion = random.uniform(0.35, 1.0)

    # Intervalo aleatorio de capacidades alrededor de la media
    lower = max(
        min_cap,
        math.floor(mean_capacity - dispersion * (mean_capacity - min_cap))
    )

    upper = min(
        max_cap,
        math.ceil(mean_capacity + dispersion * (max_cap - mean_capacity))
    )

    # Capacidades iniciales aleatorias
    prof_capacity = [
        random.randint(lower, upper)
        for _ in range(n_professors)
    ]

    # ----------------------------------------
    # Ajuste de la capacidad total
    # ----------------------------------------

    # Diferencia entre la capacidad necesaria y la generada
    difference = target_cap - sum(prof_capacity)

    # Ajustar aleatoriamente sin superar límites individuales
    while difference != 0:

        if difference > 0:
            candidates = [t for t, cap in enumerate(prof_capacity) if cap < upper]
        else:
            candidates = [t for t, cap in enumerate(prof_capacity) if cap > lower]

        if not candidates:
            raise ValueError("No se puede ajustar la capacidad total")

        t = random.choice(candidates)

        step = 1 if difference > 0 else -1

        prof_capacity[t] += step
        difference -= step

    return center_coords, prof_capacity # (lat, lon) del centro educativo, [Ct1, Ct2, Ct3, ...]; capacidades individuales


# ----------------------------
# Escritura de instancia
# ----------------------------

def write_instance_file(filename, n_students, n_companies, n_placements, n_competences_total, dependencies_all, 
                        # nombre del archivo, número de estudiantes, de empresas, de plazas, total de competencias (nº competencias * nº de perfiles), lista de dependencias (lista de listas de índices de plazas),
                        student_info_rows, company_min, company_max, placement_company, 
                        # info de cada estudiante (id, pesos de distancia/desarrollo, vectores de competencias y preferencias), cuota mínima y máxima de estudiantes por empresa, lista que indica la empresa a la que pertenece cada plaza
                        placement_comp_needs, student_company_matrix, company_coords, center_coords, 
                        # vector de necesidades de competencias asociado a cada plaza, matriz de distancias/tiempos entre estudiantes y empresas, coordenadas de las empresas y coordenadas del centro educativo,
                        prof_capacity, center_company_dist, company_company_matrix):
                        # lista que indica la capacidad de cada profesor (Ct), lista de distancias/tiempos el centro y empresas, y matriz de distancias/tiempos entre las empresas
    """
    Crea un archivo .txt con la instancia completa del problema
    """
    # Cabecera 
    with open(filename, "w") as fd:
        fd.write(f"n_students\t{n_students}\n")
        fd.write(f"n_companies\t{n_companies}\n")
        fd.write(f"n_placements\t{n_placements}\n")
        fd.write(f"n_competences\t{n_competences_total}\n")
        fd.write(f"n_dependent\t{len(dependencies_all)}\n")

        # Pesos y vectores de competencias de cada estudiante.
        fd.write("STUDENT_INFO\n")
        for row in student_info_rows:
            # row --> (id, w_distance, w_development, development_vector_real, development_vector_preference)
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

        # Cuotas mínima y máxima por empresa.
        fd.write("COMPANY_INFO\n")
        for k in range(n_companies):
            fd.write(f"{k}\t{int(company_min[k])}\t{int(company_max[k])}\n")

        # Empresa asociada y necesidades de competencias de cada plaza
        fd.write("PLACEMENT_INFO\n")
        for j in range(n_placements):
            needs = placement_comp_needs[j]
            fd.write(f"{j}\t{placement_company[j]}\t" + "\t".join([str(round(x, 2)) for x in needs]) + "\n")

        # Grupos de plazas dependientes
        fd.write("PLACEMENT_DEPENDENCIES\n")
        for dep in dependencies_all:
            fd.write("\t".join(str(x) for x in dep) + "\n")

        # Matriz distancia estudiante → empresa
        fd.write("DISTANCE_MATRIX\n")
        for row in student_company_matrix:
            fd.write("\t".join(str(d) for d in row) + "\n")

        # Coordenadas de cada empresa
        fd.write("COMPANY_LOCATIONS\n")
        for k, (lat, lon) in enumerate(company_coords):
            fd.write(f"{k}\t{lat}\t{lon}\n")
       
        # Número de profesores
        fd.write("n_professors\t{}\n".format(len(prof_capacity)))

        # Coordenadas del centro
        fd.write("CENTER_LOCATION\n")
        lat, lon = center_coords
        fd.write(f"{lat}\t{lon}\n")

        # Para cada profesor (t, Ct)
        fd.write("PROFESSOR_INFO\n")
        for t in range(len(prof_capacity)):
            fd.write(f"{t}\t{prof_capacity[t]}\n")

        # Distancias del centro → empresa
        fd.write("CENTER_COMPANY_DISTANCE\n")
        fd.write("\t".join(str(d) for d in center_company_dist) + "\n")

        # Matriz distancia empresa → empresa
        fd.write("COMPANY_COMPANY_DISTANCE\n")
        for row in company_company_matrix:
            fd.write("\t".join(str(d) for d in row) + "\n")


# ----------------------------
# Generador de instancias
# ----------------------------

def generate_instances(cfg): # Configuración global del generador (tamaños, nº de instancias, parámetros de competencias, cuotas, dependencias y rutas de salida)
    """
    Genera archivos .txt de instancias factibles por construcción.
    Además, calcula las matrices de distancia
    """
    # Reproducibilidad --> cfg.seed + global_instance_idx = semilla de la instancia
    global_instance_idx = 0

    # Carga distribuciones de localización
    all_student_locations_prop = []
    with open("data/proportion_home.csv", "r") as f: # distribución de vivienda estudiantes
        for line in f.readlines():
            line = line.strip().lstrip("\ufeff")  # quita BOM si existe
            tokens = line.split(";")
            all_student_locations_prop.append((tokens[0].strip(), float(tokens[1].strip())))

    all_business_locations = []
    with open("data/placement_locations.csv", "r") as f: # coordenadas posibles de empresas
        for line in f.readlines():
            line = line.strip().lstrip("\ufeff")  # quita BOM si existe
            tokens = line.split(";")
            all_business_locations.append((float(tokens[1].strip()), float(tokens[0].strip())))

    location_names = [x[0] for x in all_student_locations_prop]

    # ORS client (en caso de usarse) // Si no, se usan distancias sintéticas
    client = None
    use_ors = cfg.use_ors and ORS_AVAILABLE
    if use_ors:
        client = Client(base_url=cfg.ors_base_url)
    
    # Genera instancias para distintos tamaños de estudiantes dados unos parámetros
    number_profiles = 8
    p_excellent_student = 0.05
    p_notable_student = 0.25

    for n_students in range(cfg.start_size, cfg.end_size + 100, 200):
        n_instance = 0


        # Para cada tamaño n_students, genera varias instancias distintas
        while n_instance < cfg.number_instances:
            # Semilla específica de la instancia actual
            instance_seed = None
            if cfg.seed is not None:
                instance_seed = cfg.seed + global_instance_idx
                random.seed(instance_seed)
                np.random.seed(instance_seed)

            # perfiles (probabilidad aleatoria de cada uno)
            profile_prob = np.random.random(number_profiles)
            profile_prob = profile_prob / np.sum(profile_prob)

            # estudiantes (localización, coche, peso distancia/desarrollo, vector de desarrollo, vector de preferencias)
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

            # nº plazas (más plazas que estudiantes por el surplus)
            n_placements = int(math.ceil(n_students * (1.0 + cfg.surplus / 100.0)))
            placement_comp_needs = []

            # vector de necesidades de las plazas (reutiliza perfiles ligeramente modificados o crea nuevos aleatorios)
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

            # Elige número de empresas en rango razonable
            lower = max(2, n_placements // 10)
            upper = max(2, int(cfg.placement_dep_prob / 100 * n_placements / 2))
            upper = max(upper, lower)

            n_companies = random.randint(lower, upper)

            # Distribuye las plazas entre empresas
            base = n_placements // n_companies
            surplus_placements = n_placements % n_companies
            placements_per_company = number_placements_for_business(n_companies, base, surplus_placements)

            # Construye el vector que asigna cada plaza a una empresa
            placement_company = []
            for k in range(n_companies):
                placement_company.extend([k] * int(placements_per_company[k]))
            placement_company = placement_company[:n_placements]

            # Construye, para cada empresa, la lista de plazas que le pertenecen
            company_placements = {k: [] for k in range(n_companies)}
            for j, k in enumerate(placement_company):
                company_placements[int(k)].append(j)

            # Genera los grupos de plazas dependientes por empresa y construye la lista global de dependencias
            dependencies_all = []
            dep_groups_per_company = {k: [] for k in range(n_companies)}
            for k in range(n_companies):
                deps = create_dependencies(company_placements[k], cfg.placement_dep_prob)
                # filtra grupos tamaño 1
                deps = [d for d in deps if len(d) >= 2]
                dep_groups_per_company[k] = deps
                dependencies_all.extend(deps)

            # Inicializa las cuotas mínimas y máximas por empresa
            company_min = [0] * n_companies
            company_max = [0] * n_companies

            # Ajusta las cuotas máximas para garantizar que sea posible asignar a todos los estudiantes
            for k in range(n_companies):
                # max al menos 1 y como mucho plazas de empresa
                cap = len(company_placements[k])
                company_max[k] = random.randint(max(1, cap // 2), cap) if cap > 1 else 1

            company_max = adjust_max_quotas(company_max, [len(company_placements[k]) for k in range(n_companies)], n_students, cfg.slack_ratio)

            # Calcula la cuota mínima de cada empresa respetando bloques de dependencias y la cota máxima
            for k in range(n_companies):
                blocks = build_company_blocks(company_placements[k], dep_groups_per_company[k])
                company_min[k] = choose_min_quota_from_blocks(blocks, company_max[k])

            # Verifica que la suma de cuotas mínimas no supere el número de estudiantes y reduce si es necesario
            total_min = sum(company_min)
            if total_min > n_students:
                # reduce mins aleatoriamente (quitando bloques completos implícitamente al bajar el mínimo)
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

            # Asigna coordenadas geográficas a cada empresa seleccionándolas del conjunto disponible (si n_companies > len(list), usamos choice con replacement)
            company_coords = [all_business_locations[i] for i in np.random.choice(len(all_business_locations), n_companies, replace=True)]

            # Genera el centro educativo y sus profesores, garantizando capacidad total suficiente
            center_coords, prof_capacity = create_center_and_professors(n_students, location_names, cfg)

            # Extrae coordenadas de estudiantes y empresas para calcular matrices de distancia
            student_coords = [(x[0], x[1]) for x in student_info]
            company_coords_ors = [(x[0], x[1]) for x in company_coords]

            # Construye la matriz de distancias estudiante → empresa
            student_company_matrix = []
            if use_ors:
                # pedimos fila a fila como en tu original para evitar tamaños enormes
                for i in range(len(student_coords)):
                    resp = request_matrix_api(client, [student_coords[i]], company_coords_ors)
                    durations = resp["durations"][0]
                    student_company_matrix.append([float(d) if d else float(synthetic_duration()) for d in durations])
            else:
                for _ in range(n_students):
                    student_company_matrix.append([float(synthetic_duration()) for _ in range(n_companies)])

            # Construye el vector de distancias centro → empresa
            if use_ors:
                resp = request_matrix_api(client, [center_coords], company_coords_ors)
                durations = resp["durations"][0]
                center_company_dist = [float(d) if d is not None else float(synthetic_duration()) for d in durations]
            else:
                center_company_dist = [float(synthetic_duration()) for _ in range(n_companies)]

            # Construye el vector de distancias empresa → empresa
            company_company_matrix = []
            if use_ors:
                for k in range(len(company_coords)):
                    resp = request_matrix_api(client, [company_coords_ors[k]], company_coords_ors)
                    durations = resp["durations"][0]
                    company_company_matrix.append(
                        [float(d) if d else float(synthetic_duration()) for d in durations]
                    )
            else:
                for _ in range(n_companies):
                    row = []
                    for _ in range(n_companies):
                        row.append(float(synthetic_duration()))
                    company_company_matrix.append(row)

            # Archivo de salida
            out = f"{cfg.result_path}/problem_instance_ext_{n_students}_{n_instance}.txt"

            # Extrae la información de cada estudiante para escribirla en el fichero
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
                center_coords=center_coords,
                prof_capacity=prof_capacity,
                center_company_dist=center_company_dist,
                company_company_matrix=company_company_matrix
            )

            # Incrementa los contadores de instancias generadas
            n_instance += 1
            global_instance_idx += 1

            if instance_seed is None:
                print(f"[OK] written: {out}", flush=True)
            else:
                print(f"[OK] written: {out} | seed={instance_seed}", flush=True)


def parse_args_to_config(argv): # Lista de argumentos pasados por línea de comandos
    """
    Valida que se hayan proporcionado todos los argumentos necesarios por línea de comandos, 
    convierte cada uno al tipo correspondiente (int o float) y construye el objeto GeneratorConfig
    que contiene la configuración global utilizada por el generador de instancias

    python random_instance_creator.py <result_path> <start_size> <end_size> <number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences> [seed]
    """
    # Comprueba que se han pasado todos los argumentos necesarios
    if len(argv) < 10:
        raise SystemExit(
            "Usage: python random_instance_creator.py <result_path> <start_size> <end_size> "
            "<number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> "
            "<most_important_competences> [seed]"
        )
    
    seed = int(argv[10]) if len(argv) > 10 else None

    return GeneratorConfig(result_path=argv[1], start_size=int(argv[2]), end_size=int(argv[3]), number_instances=int(argv[4]), surplus=int(argv[5]),
            slack_ratio=float(argv[6]), placement_dep_prob=float(argv[7]), number_competences=int(argv[8]), most_important_competences=int(argv[9]), use_ors=False, seed=seed)
                          # Convierte los argumentos recibidos a sus tipos adecuados y construye el objeto de configuración que usará el generador de instancias


if __name__ == "__main__":
    cfg = parse_args_to_config(sys.argv)
    generate_instances(cfg)