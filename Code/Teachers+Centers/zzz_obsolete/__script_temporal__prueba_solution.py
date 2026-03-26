from tools.problem import load_instance
from tools.solution import Solution

# 1) Cargar instancia
problem = load_instance("Code/Teachers+Centers/inst_creator/output/problem_instance_ext_200_0.txt")

# 2) Crear solución vacía
sol = Solution(problem)
print("Initially complete?", sol.is_complete())  # False

# 3) Elegir una plaza libre y un profesor (t=0) y asignar estudiante 0
j = 0
t = 0
k = problem.placement_company[j]

print("Before assign:",
      "company_load[k]=", sol.company_load[k],
      "prof_load[t]=", sol.professor_load[t],
      "filled[j]=", sol.placement_filled[j])

sol.assign(0, j, t)

print("After assign:",
      "student_to_placement[0]=", sol.student_to_placement[0],
      "placement_to_professor[j]=", sol.placement_to_professor[j],
      "company_load[k]=", sol.company_load[k],
      "prof_load[t]=", sol.professor_load[t],
      "filled[j]=", sol.placement_filled[j])

# 4) Probar que no deja reasignar el mismo estudiante
try:
    sol.assign(0, j + 1, t)
except ValueError as e:
    print("Expected error (student already assigned):", e)

# 5) Probar que no deja ocupar la misma plaza con otro estudiante
try:
    sol.assign(1, j, t)
except ValueError as e:
    print("Expected error (placement already filled):", e)

# 6) Desasignar y comprobar que revierte todo
sol.unassign(0)

print("After unassign:",
      "student_to_placement[0]=", sol.student_to_placement[0],
      "placement_to_professor[j]=", sol.placement_to_professor[j],
      "company_load[k]=", sol.company_load[k],
      "prof_load[t]=", sol.professor_load[t],
      "filled[j]=", sol.placement_filled[j])

# 7) Probar que unassign de un estudiante no asignado lanza error
try:
    sol.unassign(0)
except ValueError as e:
    print("Expected error (student not assigned):", e)