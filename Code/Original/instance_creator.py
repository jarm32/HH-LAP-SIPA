import random
import numpy as np
import json
import math
import time
import sys
import heapq


from openrouteservice import Client, distance_matrix
from simple_sipa_milp import solve_simple_sipa_milp
from simple_sipa import SimpleSIPA

client = Client(base_url="http://localhost:8080/ors")

def request_matrix_api(sources, destinations):
    
    response = distance_matrix.distance_matrix(client, sources + destinations, sources=[i for i in range(len(sources))], 
                    destinations=[i for i in range(len(sources), len(sources)+ len(destinations))])
    return response

def create_competence_need_vector(number_competences, most_important):
    if most_important + 1 > number_competences:
        raise Exception("The number of most important competences must be n-1")
    competence_need = ([1] * most_important) + [0.5]
    if (most_important + 1) < number_competences:
        competence_need = competence_need + [0 for k in range(number_competences-most_important-1)]
    return competence_need
    

def create_min_cardinality_vector(number_businesses, number_placements, number_students):
    vec = None
    while True:
        vec = np.random.choice(2, size=number_businesses, p=[0.8, 0.2]) + 1
        total = np.sum(vec)
        if total <= number_placements and total <= number_students:
            break
    return vec

def number_placements_for_business(number_businesses, number_placements_per_business, surplus, percentage=0.25, prob_major = 0.8):
    placement_vec = np.full(number_businesses, number_placements_per_business)
    businesses_to_consider = np.random.choice(number_businesses, int(number_businesses*percentage), replace=False)
    for i in range(surplus):
        r = random.random()
        if r <= prob_major:
            rnd_idx = random.choice(businesses_to_consider)
        else:
            rnd_idx = random.randint(0, number_businesses - 1)
        
        placement_vec[rnd_idx] = placement_vec[rnd_idx] + 1
    return placement_vec


def create_max_cardinality_vector(number_businesses, number_students, placements_per_business):
    students_per_business = int(math.ceil(number_students/number_businesses))
    vec = np.zeros(number_businesses)
    for i in range(number_businesses):
        m = max(students_per_business, placements_per_business[i] - 2)
        vec[i] = random.randint(students_per_business, m) if m != students_per_business else m
    return vec

def create_dependencies(placements, percentage_dependencies):
    placements_in_dependencies = np.random.choice(placements, int(len(placements)*percentage_dependencies/100), replace=False)
    n_dependent = len(placements_in_dependencies)
    print(n_dependent, placements_in_dependencies)
    sizes = []
    while n_dependent >= 2:
        if n_dependent - 2 < 2:
            s = n_dependent
        else :
            max_size = n_dependent - 2 
            min_size = 2
            s = random.randint(min_size, max_size) if min_size != max_size else 2
        sizes.append(s)
        n_dependent = n_dependent - s

    dependencies = []
    k = 0
    for i in range(len(sizes)):
        dep = []
        for j in range(sizes[i]):
            dep.append(placements_in_dependencies[k])
            k = k + 1
        dependencies.append(dep)
    return dependencies
        




    



def create_student_profile(p_excellence_students, number_competences, number_profiles, student_locations):
    p_excellent_student = p_excellence_students[0]
    p_notable_student = p_excellence_students[1]
    
    r = random.random()
    if r <= p_excellent_student:
        n_excellent = int(0.8 * number_competences)
        n_notable = number_competences - n_excellent
        competence_development = [random.random() * (1-0.7) + 0.7 for j in range(n_excellent)] + [random.random() * (0.7-0.4) + 0.4 for j in range(n_notable)]
    elif r <= (p_excellent_student + p_notable_student):
        n_excellent = int(0.1 * number_competences)
        n_notable = int(0.3 * number_competences)
        n_low = number_competences - n_excellent - n_notable
        competence_development =  [random.random() * (1-0.7) + 0.7 for j in range(n_excellent)] + [random.random() * (0.7-0.4) + 0.4 for j in range(n_notable)] + [random.random() * 0.4 for j in range(n_low)]
    else :
        n_excellent = 0
        n_notable = int(0.2 * number_competences)
        n_low = number_competences - n_excellent - n_notable
        competence_development =  [random.random() * (1-0.7) + 0.7 for j in range(n_excellent)] + [random.random() * (0.7-0.4) + 0.4 for j in range(n_notable)] + [random.random() * 0.4 for j in range(n_low)]
            
    random.shuffle(competence_development)

    comp_idx = np.random.choice(number_competences, 1, p=competence_development/np.sum(competence_development))
    competence_preference = [ random.random()*0.3 for i in range(number_competences) ]
    competence_preference[comp_idx[0]] = 1
    #competence_preference[comp_idx[1]] = 0.5
    random.shuffle(competence_preference)

    profile = np.random.choice(number_profiles, 1, p=profile_prob)[0]
    competence_development = [0 for i in range(profile*number_competences)] + competence_development + [0 for i  in range((profile+1)*number_competences, number_profiles*number_competences)]
    competence_preference = [0 for i in range(profile*number_competences)] + competence_preference + [0 for i  in range((profile+1)*number_competences, number_profiles*number_competences)]

    r_loc = random.random()
    acum = 0
    location_name = None
    for (location, prob) in student_locations:
        acum = acum + prob
        if r_loc <= acum:
            location_name = location
            break
            
    has_car = True if random.random() <= 0.65 else False
    w_distance = round(random.random()*0.5, 2)
    w_dev = round(1 - w_distance, 2)

    loc_file = open("../data/points/{}.geojson".format(location_name), "r")
    loc_obj = json.load(loc_file)
    (latitude, longitude) = random.choice(loc_obj["features"])["geometry"]["coordinates"]
    loc_file.close()
    return latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference
    


    #return [ [random.random() for j in range(len(destinations))] for i in range(len(destinations))  ]

result_path = sys.argv[1]
start_size = int(sys.argv[2])
end_size = int(sys.argv[3])
number_instances = int(sys.argv[4])
surplus = int(sys.argv[5])
placement_dep_prob = float(sys.argv[6])
number_competences = int(sys.argv[7])
most_important_competences = int(sys.argv[8])
number_profiles = 8



p_excellent_student = 0.05
p_notable_student = 0.25
p_pass_student = 0.7

all_student_locations_prop = []
all_business_locations = []


f = open("../data/proportion_home.csv", "r")
for line in f.readlines():
    tokens = line.split("\t")
    all_student_locations_prop.append((tokens[0], float(tokens[1])))
f.close()

f = open("../data/placement_locations.csv", "r")
for line in f.readlines():
    tokens = line.split("\t")
    all_business_locations.append((float(tokens[1]), float(tokens[0])))
f.close()

for n_students in range(start_size, end_size+100, 200):

    n_instance = 0
    while n_instance < number_instances:

        profile_prob = np.random.random(number_profiles)
        s = np.sum(profile_prob)
        profile_prob = profile_prob/s

        student_info = []
        placement_info = []
        print("COMENZANDO", flush=True)

        profiles_used = []
        
        #Code to create the problem instance
        for i in range(n_students):
            latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference = create_student_profile([p_excellent_student, p_notable_student], number_competences, number_profiles, all_student_locations_prop)
            profiles_used.append(competence_preference)
            student_info.append((latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference))



        n_placements = int(math.ceil(n_students*(1.00 + surplus/100 )))

        np.random.shuffle(profiles_used)
        for j in range(n_placements):
            if j < len(profiles_used):
                competence_needs = profiles_used[j].copy()
                competence_needs = [competence_needs[i] if competence_needs[i]==0 else max(min(competence_needs[i] + random.normalvariate(0, sigma=0.1), 1), 0) for i in range(len(competence_needs)) ]
                competence_needs = [elem/sum(competence_needs) for elem in competence_needs]
            else :
                competence_needs = create_competence_need_vector(number_competences, most_important_competences)
                profile = np.random.choice(number_profiles, 1, p=profile_prob)[0]
                np.random.shuffle(competence_needs)
                competence_needs = [0 for i in range(profile*number_competences)] + competence_needs + [0 for i  in range((profile+1)*number_competences, number_profiles*number_competences)]

            #random.shuffle(competence_needs)
            #total = sum(competence_needs)
            #competence_needs = [competence_needs[k]/total for k in range(number_competences)]
            placement_info.append(competence_needs)

        

        while True:

            dependencies_placements = list()
            
            n_businesses = random.randint(math.floor(n_placements/10), math.floor(placement_dep_prob/100 * n_placements/2))

            n_placements_per_business = n_placements//n_businesses
            surplus_placements = n_placements % n_businesses

            min_cardinality = create_min_cardinality_vector(n_businesses, n_placements, n_students)
            total_placement_per_business = number_placements_for_business(n_businesses, n_placements_per_business, surplus_placements)
            max_cardinality = create_max_cardinality_vector(n_businesses, n_students, total_placement_per_business)

            business_locations_idx = np.random.choice(len(all_business_locations),n_businesses, replace=True)
            business_locations = [all_business_locations[i] for i in business_locations_idx]

            student_data_ors = None
            business_data_ors = None
            durations_m = []

            business_assignments = []
            for b_id in range(n_businesses):
                business_assignments.extend([b_id for j in range(total_placement_per_business[b_id])])

            business_placements = {}
            for j in range(len(business_assignments)):
                b_id = business_assignments[j]
                business_placements[b_id] = business_placements.setdefault(b_id, list()) + [j]

            for b_id in range(n_businesses):
                placements = business_placements[b_id]
                dependencies = create_dependencies(placements, placement_dep_prob)
                for dep in dependencies:
                    if len(dep) == 1:
                        continue
                dependencies_placements.extend(dependencies)



            filename = f"{result_path}/problem_instance_{n_students}_{n_instance}.txt"
            fd=open(filename,"w")
            fd.write("n_students\t{}\n".format(n_students))
            fd.write("n_companies\t{}\n".format(n_businesses))
            fd.write("n_placements\t{}\n".format(n_placements))
            fd.write("n_competences\t{}\n".format(number_competences*number_profiles))
            fd.write("n_dependent\t{}\n".format(len(dependencies_placements)))

            fd.write("STUDENT_INFO\n")

            for i in range(n_students):
                (latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference) = student_info[i]
                fd.write("{}\t{}\t{}\t{}\t{}\n".format(i,w_distance, w_dev, "\t".join([str(round(x,2)) for x in competence_development]), "\t".join([str(round(x,2)) for x in competence_preference])))
                
            
            fd.write("COMPANY_INFO\n")
            for j in range(n_businesses):
                minimum = int(min_cardinality[j])
                maximum = int(max_cardinality[j])
                fd.write("{}\t{}\t{}\n".format(j, minimum, maximum))
                
            fd.write("PLACEMENT_INFO\n")
            for k in range(n_placements):
                fd.write("{}\t{}\t{}\n".format(k, business_assignments[k], "\t".join([str(round(x,2)) for x in placement_info[k]])))

            fd.write("PLACEMENT_DEPENDENCIES\n")
            for dep in dependencies_placements:
                fd.write("\t".join(str(x) for x in dep)+"\n")

            fd.write("DISTANCE_MATRIX\n")
            print("VAMOS A COMENZAR", flush=True)
            student_data_ors = [(x[0], x[1]) for x in student_info]
            business_data_ors = [(x[0], x[1]) for x in business_locations]
            
            if not durations_m:
                for i in range(len(student_data_ors)):
                
                    resp = request_matrix_api([student_data_ors[i]],
                                    business_data_ors)
                    durations = resp["durations"]
                    durations_m.append(durations)
            for durations in durations_m:
                for row in durations:
                    fd.write("\t".join(str(d) if d else str(max(1,round(random.normalvariate(1500, 250),2))) for d in row)+"\n")
                
            
            print("WRITTEN STUDENT MATRIX ", flush=True)
                
            fd.close()

            problem = SimpleSIPA(filename)
            status, ut_students, ut_businesses, ut, t = solve_simple_sipa_milp(problem, "GUROBI")
            if status == 0 or status == 1:
                n_instance=n_instance+1
                break
            print(status, t, filename)
        
        
        

        
            





