# Representación de una solución factible del modelo

class Solution:
    """
    Representa una solución del problema
    (Asignación estudiante -> plaza y plaza -> profesor)
    """

    def __init__(self, problem):
        # Instancia cargada
        self.problem = problem

        # Asignaciones principales
        self.student_to_placement = [-1] * problem.n_students # student_to_placement[i] = j
        self.placement_to_professor = [-1] * problem.n_placements # placement_to_professor[j] = t

        # Estructuras auxiliares
        self.company_load = [0] * problem.n_companies # Número actual de estudiantes asignados a cada empresa
        self.professor_load = [0] * problem.n_professors # Carga actual por profesor
        self.placement_filled = [False] * problem.n_placements # Marca si una plaza ya está ocupada

    # Métodos básicos
    def assign(self, student, placement, professor):
        """
        Asigna el estudiante i a la plaza j supervisada por el profesor t
        No valida restricciones, solo actualiza la estructura
        """

        self.student_to_placement[student] = placement # i → j
        self.placement_to_professor[placement] = professor # j → t

        company = self.problem.placement_company[placement] # empresa a la que pertenece la plaza j
        
        self.company_load[company] += 1 # actualiza la carga de la empresa
        self.professor_load[professor] += 1 # actualiza la carga del profesor
        self.placement_filled[placement] = True # marca la plaza como ocupada


    def unassign(self, student): 
        """
        Deshace la asignación de un estudiante
        (libera la plaza y al profesor)
        """

        placement = self.student_to_placement[student] # plaza a la que estaba asignado el estudiante
        professor = self.placement_to_professor[placement] # profesor que supervisaba esa plaza

        company = self.problem.placement_company[placement] # empresa a la que pertenece la plaza

        self.company_load[company] -= 1 # actualiza la carga de la empresa
        self.professor_load[professor] -= 1 # actualiza la carga del profeso
        self.placement_filled[placement] = False # marca la plaza como libre

        self.student_to_placement[student] = -1 # estudiante sin asignar
        self.placement_to_professor[placement] = -1 # plaza sin profesor asignado

    # Consultas sobre la solución
    def is_complete(self): # Devuelve True si todos los estudiantes están asignados
        return all(p != -1 for p in self.student_to_placement)

    def company_capacity_ok(self, company): # Comprueba si la empresa respeta el máximo
        return self.company_load[company] <= self.problem.company_max[company]

    def professor_capacity_ok(self, professor): # Comprueba si el profesor respeta su capacidad de supervisión
        return self.professor_load[professor] <= self.problem.prof_capacity[professor]


# Librerías
from problem import load_instance

problem = load_instance("Code/Teachers+Centers/inst_creator/output/problem_instance_ext_400_1.txt")
sol = Solution(problem)
print(sol.is_complete())  # debería ser False