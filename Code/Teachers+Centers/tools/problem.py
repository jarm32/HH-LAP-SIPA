# Representación interna del problema (loader de instancias .txt)
# Ni genera soluciones, ni evalúa la función objetivo, ni optimiza

import numpy as np


class Problem:
    """
    Representación en memoria de una instancia del SIPA ampliado
    (estudiantes, empresas, dependencias, centros y profesores).
    """

    def __init__(self):

        # -----------------
        # Dimensiones
        # -----------------
        self.n_students = 0
        self.n_companies = 0
        self.n_placements = 0
        self.n_competences = 0
        self.n_centers = 0
        self.n_professors = 0

        # -----------------
        # Empresas
        # -----------------
        self.company_min = []
        self.company_max = []

        # -----------------
        # Plazas
        # -----------------
        self.placement_company = []
        self.dependencies = []

        # -----------------
        # Estudiantes
        # -----------------
        self.student_w_distance = []
        self.student_w_dev = []
        self.student_dev = []
        self.student_pref = []

        # -----------------
        # Distancias
        # -----------------
        self.student_company_dist = None
        self.center_company_dist = None
        self.company_company_dist = None

        # -----------------
        # Centros y profesores
        # -----------------
        self.centers_coords = []
        self.prof_center = []
        self.prof_capacity = []

    # -------------------------------------------------
    # Métodos auxiliares útiles más adelante
    # -------------------------------------------------

    def total_company_capacity(self):
        return sum(self.company_max)

    def total_professor_capacity(self):
        return sum(self.prof_capacity)


def load_instance(filename):
    """
    Lee un archivo .txt generado por random_instance_creator
    y construye un objeto Problem.
    """

    problem = Problem()

    with open(filename, "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    idx = 0

    # =============================
    # CABECERA
    # =============================
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

    # =============================
    # STUDENT_INFO
    # =============================
    idx += 1
    for _ in range(problem.n_students):

        tokens = lines[idx].split("\t")

        problem.student_w_distance.append(float(tokens[1]))
        problem.student_w_dev.append(float(tokens[2]))

        start_dev = 3
        end_dev = start_dev + problem.n_competences

        dev_vector = list(map(float, tokens[start_dev:end_dev]))
        pref_vector = list(map(float, tokens[end_dev:end_dev + problem.n_competences]))

        problem.student_dev.append(dev_vector)
        problem.student_pref.append(pref_vector)

        idx += 1

    # =============================
    # COMPANY_INFO
    # =============================
    idx += 1
    for _ in range(problem.n_companies):
        tokens = lines[idx].split("\t")
        problem.company_min.append(int(tokens[1]))
        problem.company_max.append(int(tokens[2]))
        idx += 1

    # =============================
    # PLACEMENT_INFO
    # =============================
    idx += 1
    for _ in range(problem.n_placements):
        tokens = lines[idx].split("\t")
        problem.placement_company.append(int(tokens[1]))
        idx += 1

    # =============================
    # DEPENDENCIES
    # =============================
    idx += 1
    while not lines[idx].startswith("DISTANCE_MATRIX"):
        dep_group = list(map(int, lines[idx].split("\t")))
        problem.dependencies.append(dep_group)
        idx += 1

    # =============================
    # DISTANCE_MATRIX (student → company)
    # =============================
    idx += 1
    student_company_matrix = []

    for _ in range(problem.n_students):
        row = list(map(float, lines[idx].split("\t")))
        student_company_matrix.append(row)
        idx += 1

    problem.student_company_dist = np.array(student_company_matrix)

    # =============================
    # COMPANY_LOCATIONS (no necesario guardarlas)
    # =============================
    idx += 1
    idx += problem.n_companies

    # =============================
    # n_centers / n_professors
    # =============================
    key, value = lines[idx].split("\t")
    if key == "n_centers":
        problem.n_centers = int(value)
    idx += 1

    key, value = lines[idx].split("\t")
    if key == "n_professors":
        problem.n_professors = int(value)
    idx += 1

    # =============================
    # CENTER_LOCATIONS
    # =============================
    idx += 1
    for _ in range(problem.n_centers):
        tokens = lines[idx].split("\t")
        lat = float(tokens[1])
        lon = float(tokens[2])
        problem.centers_coords.append((lat, lon))
        idx += 1

    # =============================
    # PROFESSOR_INFO
    # =============================
    idx += 1
    for _ in range(problem.n_professors):
        tokens = lines[idx].split("\t")
        problem.prof_center.append(int(tokens[1]))
        problem.prof_capacity.append(int(tokens[2]))
        idx += 1

    # =============================
    # CENTER_COMPANY_DISTANCE
    # =============================
    idx += 1
    center_company_matrix = []

    for _ in range(problem.n_centers):
        row = list(map(float, lines[idx].split("\t")))
        center_company_matrix.append(row)
        idx += 1

    problem.center_company_dist = np.array(center_company_matrix)

    # =============================
    # COMPANY_COMPANY_DISTANCE
    # =============================
    idx += 1
    company_company_matrix = []

    for _ in range(problem.n_companies):
        row = list(map(float, lines[idx].split("\t")))
        company_company_matrix.append(row)
        idx += 1

    problem.company_company_dist = np.array(company_company_matrix)

    return problem