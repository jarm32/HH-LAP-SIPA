import random
import numpy as np
import json
import math
import time


from openrouteservice import Client, distance_matrix

client = Client(base_url="http://localhost:8080/ors")

def request_matrix_api(sources, destinations):
    
    response = distance_matrix.distance_matrix(client, sources + destinations, sources=[i for i in range(len(sources))], 
                    destinations=[i for i in range(len(sources), len(sources)+ len(destinations))])
    return response
    #return [ [random.random() for j in range(len(destinations))] for i in range(len(destinations))  ]


p_excellent_student = 0.05
p_notable_student = 0.45
p_pass_student = 0.5

all_student_locations_prop = []
all_business_locations = []

number_competences = 6

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

for n_students in range(100, 1100, 100):
    for n_instance in range(20):
        student_info = []
        placement_info = []
        print("COMENZANDO", flush=True)
        
        #Code to create the problem instance
        for i in range(n_students):
            r = random.random()
            if r <= p_excellent_student:
                avg = 7
                sd = 2
                competence_development = [ round((max(min(9 + random.normalvariate(0, 1), 10), 5) -5)/5, 2) for i in range(2) ] + [round((max(min(random.normalvariate(mu=avg, sigma=sd),10),5) - 5)/5,2) for j in range(number_competences - 2)]
            elif r <= (p_excellent_student + p_notable_student):
                avg = 6
                sd = 0.5
                competence_development = [ round((max(min(9 + random.normalvariate(0, 1), 10), 5) -5)/5, 2) for i in range(1) ] + [round((max(min(random.normalvariate(mu=avg, sigma=sd),10),5) - 5)/5,2) for j in range(number_competences - 1)]
                
            else :
                avg = 5
                sd = 0.5
                competence_development = [round((max(min(random.normalvariate(mu=avg, sigma=sd),10),5) - 5)/5,2) for j in range(number_competences)]
            
            random.shuffle(competence_development)

            #competence_development = [ round((max(min(random.normalvariate(mu=avg, sigma=sd),10),5) - 5)/5,2) for j in range(number_competences) ]
            sd_preference = 2
            #competence_preference = np.array([ (competence_development[j]+random.normalvariate(mu=0, sigma=sd_preference)) for j in range(number_competences) ]).argsort() + 1
            competence_preference = [1, 0.5] + [random.random()*0.3 for i in range(number_competences - 2 ) ]
            random.shuffle(competence_preference) 
            #competence_preference = competence_preference/max(competence_preference)

            r_loc = random.random()
            acum = 0
            location_name = None
            for (location, prob) in all_student_locations_prop:
                acum = acum + prob
                if r_loc <= acum:
                    location_name = location
                    break
            
            has_car = True if random.random() <= 0.65 else False
            w_distance = round(random.random(), 2)
            w_dev = round(1 - w_distance, 2)

            loc_file = open("../data/points/{}.geojson".format(location_name), "r")
            loc_obj = json.load(loc_file)
            (latitude, longitude) = random.choice(loc_obj["features"])["geometry"]["coordinates"]
            loc_file.close()
            student_info.append((latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference))
        n_placements = int(math.ceil(n_students*1.20))
        for j in range(n_placements):
            competence_needs = [1, 0.5 ] + [random.random()*0.3 for k in range(number_competences-2)]
            random.shuffle(competence_needs)
            total = sum(competence_needs)
            competence_needs = [competence_needs[k]/total for k in range(number_competences)]
            placement_info.append(competence_needs)

        
        n_businesses = min(math.ceil(n_placements/5), len(all_business_locations)) 

        business_locations = random.sample(all_business_locations,n_businesses)

        business_assignments = [k for k in range(n_businesses)]
        
        while len(business_assignments) < n_placements:
            b = random.randint(0, n_businesses-1)
            business_assignments.append(b)

        random.shuffle(business_assignments)

        business_placements = {}
        placements_business = {}
        for j in range(len(business_assignments)):
            b = business_assignments[j]
            business_placements.setdefault(b, list()).append(j)

        cardinality_business_placements = [(0,0) for i in range(n_businesses)]
        dependencies_placements = []
        surplus_placements = n_placements - n_students
        minimum_set = 0
        b_indices = [j for j in range(n_businesses)]
        random.shuffle(b_indices)
        for i in b_indices:
            p = len(business_placements[i])
            minimum = 0
            maximum = p
            dependencies = []
            
            if p <= 1:
                maximum = 1
            else : #p >= 2
                if minimum_set < n_students:
                    r = random.random()
                    if r <= 0.25:
                        minimum = 1
                    
                if surplus_placements >= 1:
                    r = random.random()
                    if r <= 0.45:
                        surplus_placements = surplus_placements - 1
                        maximum = p - 1
                    elif r <= 0.65 and (p - 2 > 0) and surplus_placements >= 2:
                        surplus_placements = surplus_placements - 2
                        maximum = p - 2
            
            r = random.random()
            if r <= 0.3 and p >= 2:
                n_dep = random.randint(2, max(2,maximum - 1))
                dependencies = random.sample(business_placements[i], n_dep)
                n_diff = max(n_dep - minimum, 0)
                minimum_set = minimum_set + n_diff

            if dependencies:
                dependencies_placements.append(dependencies)

            minimum_set = minimum_set + minimum
            cardinality_business_placements[i] = (minimum, maximum)

        filename = "../data/problems/problem_instance_{}_{}.txt".format(n_students, n_instance)
        fd=open(filename,"w")
        fd.write("n_students\t{}\n".format(n_students))
        fd.write("n_companies\t{}\n".format(n_businesses))
        fd.write("n_placements\t{}\n".format(n_placements))
        fd.write("n_competences\t{}\n".format(number_competences))
        fd.write("n_dependent\t{}\n".format(len(dependencies_placements)))

        fd.write("STUDENT_INFO\n")

        for i in range(n_students):
            (latitude, longitude, has_car, w_distance, w_dev, competence_development, competence_preference) = student_info[i]
            fd.write("{}\t{}\t{}\t{}\t{}\n".format(i,w_distance, w_dev, "\t".join([str(round(x,2)) for x in competence_development]), "\t".join([str(round(x,2)) for x in competence_preference])))
            
        
        fd.write("COMPANY_INFO\n")
        for j in range(n_businesses):
            (minimum, maximum) = cardinality_business_placements[j]
            fd.write("{}\t{}\t{}\n".format(j, minimum, maximum))
            
        fd.write("PLACEMENT_INFO\n")
        for k in range(n_placements):
            fd.write("{}\t{}\t{}\n".format(k, business_assignments[k], "\t".join([str(round(x,2)) for x in placement_info[k]])))

        fd.write("PLACEMENT_DEPENDENCIES\n")
        for dep in dependencies_placements:
            fd.write("\t".join(str(x) for x in dep)+"\n")

        fd.write("DISTANCE_MATRIX\n")
        print("VAMOS A COMENZAR", flush=True)
        resp = request_matrix_api([(x[0], x[1]) for x in student_info],
                                  [(x[0], x[1]) for x in business_locations])
        
        durations = resp["durations"]
        #durations = resp
        for row in durations:
            fd.write("\t".join(str(d) if d else str(max(1,round(random.normalvariate(1500, 250),2))) for d in row)+"\n")
        
        print("WRITTEN STUDENT MATRIX ", flush=True)
        time.sleep(1)
            
        fd.close()
        
        
        

        
            





