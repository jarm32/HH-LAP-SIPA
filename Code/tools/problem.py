# Representación interna del problema (loader de instancias .txt)

import numpy as np

class Problem:
    """
    Representación en memoria de una instancia del problema
    (estudiantes, empresas, dependencias y profesores del centro educativo)
    """
    def __init__(self):
        # Dimensiones
        self.n_students = 0 #S
        self.n_companies = 0 #B
        self.n_placements = 0 #P
        self.n_competences = 0 #C
        self.n_professors = 0 #T

        # Empresas
        self.company_min = [] #qk
        self.company_max = [] # Qk

        # Plazas
        self.placement_company = [] # empresa a la que pertenece cada plaza
        self.dependencies = [] # grupo de plazas que deben asignarse juntas
        self.placement_comp_needs = []  # vector competencias por plaza

        # Estudiantes
        self.student_w_distance = [] # peso de i a la distancia
        self.student_w_dev = [] # peso de i al desarrollo profesional
        self.student_dev = [] # vector real de competencias de i
        self.student_pref = [] # vector de preferencias de i
        
        # Distancias
        self.student_company_dist = None # matriz distancia estudiante → empresa
        self.center_company_dist = None # vector distancia centro → empresa
        self.company_company_dist = None # matriz distancia empresa → empresa

        # Centro y profesores
        self.center_coords = None # (latitud, longitud) del centro educativo
        self.prof_capacity = [] # capacidad máxima de supervisión Ct

    # Métodos auxiliares útiles más adelante

    def total_company_capacity(self): # -
        return int(np.sum(self.company_max)) # suma de las cuotas máximas de todas las empresas

    def total_professor_capacity(self): # -
        return int(np.sum(self.prof_capacity)) # suma de las capacidades totales de supervisión de todos los profesores


def load_instance(filename): # ruta del archivo .txt que contiene la instancia
    """
    Lee un archivo .txt generado por random_instance_creator y construye un objeto Problem
    """
    # Creación del objeto y lectura del archivo
    problem = Problem()

    with open(filename, "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    idx = 0

    # Cabecera con las dimensiones
    while not lines[idx].startswith("STUDENT_INFO"):
        key, value = lines[idx].split("\t")

        if key == "n_students":
            problem.n_students = int(value)
        elif key == "n_companies":
            problem.n_companies = int(value)
        elif key == "n_placements":
            problem.n_placements = int(value)
        elif key == "n_competences":
            problem.n_competences = int(value)

        idx += 1

    # Información de los estudiantes --> id | w_dist | w_dev | dev_vector | pref_vector
    idx += 1
    for _ in range(problem.n_students):
        
        tokens = lines[idx].split("\t")

        # Pesos (distancia y desarrollo)
        problem.student_w_distance.append(float(tokens[1]))
        problem.student_w_dev.append(float(tokens[2]))

        start_dev = 3
        end_dev = start_dev + problem.n_competences

        dev_vector = list(map(float, tokens[start_dev:end_dev])) # Vector de desarrollo
        pref_vector = list(map(float, tokens[end_dev:end_dev + problem.n_competences])) # Vector de preferencias

        problem.student_dev.append(dev_vector)
        problem.student_pref.append(pref_vector)

        idx += 1

    # Información de las empresas --> id | qk | Qk
    idx += 1
    for _ in range(problem.n_companies):

        tokens = lines[idx].split("\t")

        # Cuotas mínimas y máximas de cada empresa
        problem.company_min.append(int(tokens[1]))
        problem.company_max.append(int(tokens[2]))
        idx += 1

    # Información de las plazas --> id | empresa a la que pertenece cada plaza
    idx += 1
    for _ in range(problem.n_placements):

        tokens = lines[idx].split("\t")

        # Empresa a la que pertenece cada plaza
        problem.placement_company.append(int(tokens[1]))

        needs = list(map(float, tokens[2:]))
        if len(needs) != problem.n_competences:
            raise ValueError(f"PLACEMENT_INFO row has {len(needs)} needs, expected {problem.n_competences}")
        problem.placement_comp_needs.append(needs)

        idx += 1

    # Dependencias entre plazas (lista de listas)
    idx += 1
    while not lines[idx].startswith("DISTANCE_MATRIX"):
        dep_group = list(map(int, lines[idx].split("\t")))
        problem.dependencies.append(dep_group)
        idx += 1

    # Matriz de distancias: student → company (student_company_dist[i][k] del estudiante i a la empresa k)
    idx += 1
    student_company_matrix = [] # n_students x n_companies

    for _ in range(problem.n_students):
        row = list(map(float, lines[idx].split("\t")))
        student_company_matrix.append(row)
        idx += 1

    problem.student_company_dist = np.array(student_company_matrix)

    # Localización de las empresas (no se guarda y solo se usa para avanzar en la instancia)
    idx += 1
    idx += problem.n_companies
    
    # Número de profesores
    key, value = lines[idx].split("\t")
    if key == "n_professors":
        problem.n_professors = int(value)
    idx += 1

    # Localización del centro educativo --> latitud | longitud
    idx += 1
    tokens = lines[idx].split("\t")
    lat = float(tokens[0])
    lon = float(tokens[1])

    problem.center_coords = (lat, lon)
    idx += 1

    # Información de los profesores --> t | Ct
    idx += 1
    for _ in range(problem.n_professors):

        tokens = lines[idx].split("\t")

        problem.prof_capacity.append(int(tokens[1]))
        idx += 1

    # Vector de distancias: centro → empresa
    idx += 1
    center_company_vector = list(map(float, lines[idx].split("\t")))
    problem.center_company_dist = np.array(center_company_vector)
    idx += 1

    # Matriz de distancias: empresa → empresa
    idx += 1
    company_company_matrix = [] # n_companies x n_companies

    for _ in range(problem.n_companies):
        row = list(map(float, lines[idx].split("\t")))
        company_company_matrix.append(row)
        idx += 1

    problem.company_company_dist = np.array(company_company_matrix)

    # Una vez cargados todos los datos, se convierten a arrays NumPy para mejorar el rendimiento en operaciones vectorizadas
    problem.company_min = np.asarray(problem.company_min, dtype=np.int32)
    problem.company_max = np.asarray(problem.company_max, dtype=np.int32)

    problem.placement_company = np.asarray(problem.placement_company, dtype=np.int32)
    problem.placement_comp_needs = np.asarray(problem.placement_comp_needs, dtype=np.float64)

    problem.student_w_distance = np.asarray(problem.student_w_distance, dtype=np.float64)
    problem.student_w_dev = np.asarray(problem.student_w_dev, dtype=np.float64)
    problem.student_dev = np.asarray(problem.student_dev, dtype=np.float64)
    problem.student_pref = np.asarray(problem.student_pref, dtype=np.float64)

    problem.prof_capacity = np.asarray(problem.prof_capacity, dtype=np.int32)

    return problem # Un objeto Problem con la información de la instancia (dimensiones, estudiantes, empresas, plazas, dependencias, distancias, centro y profesores)