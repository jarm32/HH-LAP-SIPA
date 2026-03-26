from tools.problem import load_instance

p = load_instance("Code/Teachers+Centers/inst_creator/output/problem_instance_ext_400_1.txt")

print("Students:", p.n_students)
print("Companies:", p.n_companies)
print("Centers:", p.n_centers)
print("Professors:", p.n_professors)
print("Total company capacity:", p.total_company_capacity())
print("Total professor capacity:", p.total_professor_capacity())