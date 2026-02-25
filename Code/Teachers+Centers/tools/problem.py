# Representación interna del problema (loader de instancias .txt)

# Librerías

import numpy as np


# Cargador del problema

class Problem:
    """
    Representación en memoria de una instancia del problema
    (estudiantes, empresas, dependencias, centros y profesores)
    """
    def __init__(self):
        # Dimensiones
        self.n_students = 0 #S
        self.n_companies = 0 #B
        self.n_placements = 0 #P
        self.n_competences = 0 #C
        self.n_centers = 0 #E
        self.n_professors = 0 #T

        # Empresas
        self.company_min = [] #qk
        self.company_max = [] # Qk

        # Plazas
        self.placement_company = [] # empresa a la que pertenece cada plaza
        self.dependencies = [] # grupo de plazas que deben asignarse juntas

        # Estudiantes
        self.student_w_distance = [] # peso de i a la distancia
        self.student_w_dev = [] # peso de i al desarrollo profesional
        self.student_dev = [] # vector real de competencias de i
        self.student_pref = [] # vector de preferencias de i

        # Distancias
        self.student_company_dist = None # matriz distancia estudiante → empresa
        self.center_company_dist = None # matriz distancia centro → empresa
        self.company_company_dist = None # matriz distancia empresa → empresa

        # Centros y profesores
        self.centers_coords = [] # coordenadas del centro c
        self.prof_center = [] # centro al que pertenece el profesor t
        self.prof_capacity = [] # capacidad máxima de supervisión Ct

    # Métodos auxiliares útiles más adelante

    def total_company_capacity(self): # -
        return sum(self.company_max) # suma de las cuotas máximas de todas las empresas

    def total_professor_capacity(self): # -
        return sum(self.prof_capacity) # suma de las capacidades totales de supervisión de todos los profesores


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

    # Dimensiones faltantes (n_centers, n_professors)
    key, value = lines[idx].split("\t")
    if key == "n_centers":
        problem.n_centers = int(value)
    idx += 1

    key, value = lines[idx].split("\t")
    if key == "n_professors":
        problem.n_professors = int(value)
    idx += 1

    # Localización de los centros --> c | latitud | longitud
    idx += 1
    for _ in range(problem.n_centers):

        tokens = lines[idx].split("\t")

        lat = float(tokens[1])
        lon = float(tokens[2])
        problem.centers_coords.append((lat, lon))
        idx += 1

    # Información de los profesores --> t | e(t) | Ct
    idx += 1
    for _ in range(problem.n_professors):

        tokens = lines[idx].split("\t")
        
        problem.prof_center.append(int(tokens[1]))
        problem.prof_capacity.append(int(tokens[2]))
        idx += 1

    # Matriz de distancias: center → company (center_company_dist[c][k] del centro c a la empresa k)
    idx += 1
    center_company_matrix = [] # n_centers x n_companies

    for _ in range(problem.n_centers):
        row = list(map(float, lines[idx].split("\t")))
        center_company_matrix.append(row)
        idx += 1

    problem.center_company_dist = np.array(center_company_matrix)

    # Matriz de distancias: company → company (company_company_dist[k][k'] de la empresa k a la empresa k')
    idx += 1
    company_company_matrix = [] # n_companies x n_companies

    for _ in range(problem.n_companies):
        row = list(map(float, lines[idx].split("\t")))
        company_company_matrix.append(row)
        idx += 1

    problem.company_company_dist = np.array(company_company_matrix)

    return problem # Un objeto Problem con la información de la instancia (dimensiones, datos de estudiantes, empresas, plazas, dependencias, distancias, centros y profesores)