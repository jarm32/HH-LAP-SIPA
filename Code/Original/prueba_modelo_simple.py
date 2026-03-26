from simple_sipa import SimpleSIPA
from simple_sipa_milp import solve_simple_sipa_milp

# Ruta a la instancia
path = "C:/Code/VRAIN-practicas/Code/Original/problem_instance_600_0.txt"

# Construir el modelo
problem = SimpleSIPA(path)

# Ejecutar el ILP
status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(
    problem,
    solver_name="CBC",
    time_limit=300000
)

# Mostrar resultados
print("Status:", status)
print("Utility students:", utility_students)
print("Utility businesses:", utility_businesses)
print("Joint utility:", joint_utility)
print("Time (s):", t)