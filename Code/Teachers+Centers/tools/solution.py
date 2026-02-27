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
        Asigna el estudiante i a la plaza j supervisada por el profesor t.
        Valida, también, restricciones básicas (ocupación y capacidades) antes de actualizar la estructura
        """
        # Validaciones

        # Índices válidos
        if not (0 <= student < self.problem.n_students):
            raise ValueError("Invalid student index")
        if not (0 <= placement < self.problem.n_placements):
            raise ValueError("Invalid placement index")
        if not (0 <= professor < self.problem.n_professors):
            raise ValueError("Invalid professor index")
        
        if self.student_to_placement[student] != -1: 
            raise ValueError("Student already assigned") # El estudiante ya está asignado

        if self.placement_filled[placement]:
            raise ValueError("Placement already filled") # La plaza ya está ocupada

        company = self.problem.placement_company[placement] # empresa a la que pertenece la plaza j

        if self.company_load[company] + 1 > self.problem.company_max[company]:
            raise ValueError("Company capacity exceeded") # Capacidad de empresa excedida
        
        if self.professor_load[professor] + 1 > self.problem.prof_capacity[professor]:
            raise ValueError("Professor capacity exceeded") # Capacidad de profesor excedida
        

        # Asignaciones

        self.student_to_placement[student] = placement # i → j
        self.placement_to_professor[placement] = professor # j → t
        
        self.company_load[company] += 1 # actualiza la carga de la empresa
        self.professor_load[professor] += 1 # actualiza la carga del profesor
        self.placement_filled[placement] = True # marca la plaza como ocupada


    def unassign(self, student): 
        """
        Deshace la asignación de un estudiante
        (libera la plaza y al profesor)
        """
        # Validación de índices
        if not (0 <= student < self.problem.n_students):
            raise ValueError("Invalid student index")

        placement = self.student_to_placement[student] # plaza a la que estaba asignado el estudiante
        if placement == -1:
            raise ValueError(f"Student {student} is not assigned to any placement")
    
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
    
    def dependencies_ok(self): # Comprueba que se respetan las dependencias (si un bloque de plazas dependientes está parcialmente asignado, devuelve False)
        for dep in self.problem.dependencies:
            if not dep:
                continue
            assigned = [self.placement_filled[j] for j in dep]
            if any(assigned) and not all(assigned):
                return False
        return True
    
    def validate(self):
        # Todos los estudiantes asignados
        if not self.is_complete():
            return False

        # Mínimos y máximos por empresa
        for k in range(self.problem.n_companies):
            if self.company_load[k] < self.problem.company_min[k]:
                return False
            if self.company_load[k] > self.problem.company_max[k]:
                return False

        # Capacidad de profesores
        for t in range(self.problem.n_professors):
            if self.professor_load[t] > self.problem.prof_capacity[t]:
                return False

        # Dependencias
        if not self.dependencies_ok():
            return False

        return True