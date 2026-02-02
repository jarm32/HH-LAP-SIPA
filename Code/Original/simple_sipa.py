from tools.scaling import scale_rows_to_0_1
import numpy as np

class SimpleSIPA:

    def _calculate_placements_without_dep(self):

        no_deps = [1 for i in range(self.number_placements)]

        for dep in self._placement_dependencies_info:
            for p_id in dep:
                no_deps[p_id] = 0

        return np.array(no_deps, bool)
            
    def _create_company_placement_matrix(self):
        """
        Creates a dictionary with the placement ids of each company
        Args:
            data: The data employed to build the dictionary, which is a list of placements
        Returns:
            A dictionary with the company id as key, and a list of placements as value
        """
        # Create a dictionary to store placement_ids for each company_id
        company_placement_dict = {}

        # Iterate through the data and populate the dictionary
        for entry in self.placement_info:
            company_id = entry['company_id']
            placement_id = entry['placement_id']
            if company_id not in company_placement_dict:
                company_placement_dict[company_id] = []
            company_placement_dict[company_id].append(placement_id)

        # Create the resulting matrix
        max_company_id = max(company_placement_dict.keys())
        company_placement_matrix = [[] for _ in range(max_company_id + 1)]
        for company_id, placement_ids in company_placement_dict.items():
            company_placement_matrix[company_id] = placement_ids

        return company_placement_matrix


    def _calculate_eta(self):
        """
        Calculate eta_ij, which represents how good a student i is for placement j
        Returns:
            A matrix with eta_ij calculated for each prospective pair of i and j
        """

        m = np.matrix([
            [np.dot(self.placement_info[j]["competence_importance_vector"], self.student_info[i]["development_vector"]) for j in
            range(self.number_placements)] for i in range(self.number_students)])
        
        for j in range(self.number_placements):
            v = m[:,j]
            mu = v.mean()
            sigma = v.std()
            sigma = 1 if sigma == 0 else sigma
            m[:,j] = (v-mu)/(sigma)
        
        return m

    def _calculate_tao(self):
        """
        Calculate the tao_ij for each pair of student and placement. It represents how good a placement j is for a student i
        Returns:
            A matrix of tao_ij values for each pair of student and placement.
        """
        m = np.matrix([[self.student_info[i]['importance_distance'] * (
                    1 - self.distance_info[i][self.get_company_id(j)]) + \
                (self.student_info[i]['importance_competence_development'] * sum([a * b for a, b in zip(
                    self.placement_info[j]['competence_importance_vector'], self.student_info[i]['preference_vector'])])) \
                for j in range(self.number_placements)] for i in range(self.number_students)]) 
        
        for i in range(self.number_students):
            v = m[i, :]
            mu = v.mean()
            sigma = v.std()
            sigma = 1 if sigma == 0 else sigma
            m[i, :] = (v-mu)/(sigma)
        
        return m

    def __init__(self,path, alpha=0.5, beta=0.5):
            # Initialize variables to store metadata
        n_competences = None
        
        self._alpha = alpha
        self._beta = beta

        # Initialize empty lists to store student and company info
        self._student_info = []
        self._company_info = []
        self._placement_info = []
        self._placement_dependencies_info = []
        self._distance_info = []
        self._cache_utilities = dict()

        # Flags to indicate when to start reading student and company data
        start_reading_students = False
        start_reading_companies = False
        start_reading_placements = False
        start_reading_placements_dependencies = False
        start_reading_distances = False

        with open(path, "r") as file:
            for line in file:
                # Check if the line contains metadata and extract the values
                if line.startswith("n_students"):
                    n_students = int(line.split("\t")[1].strip())
                elif line.startswith("n_companies"):
                    n_companies = int(line.split("\t")[1].strip())
                elif line.startswith("n_placements"):
                    n_placements = int(line.split("\t")[1].strip())
                elif line.startswith("n_competences"):
                    n_competences = int(line.split("\t")[1].strip())
                elif line.startswith("n_dependent"):
                    n_dependent = int(line.split("\t")[1].strip())
                elif line.startswith("STUDENT_INFO"):
                    start_reading_students = True
                    continue  # Skip the line with student column names
                elif line.startswith("COMPANY_INFO"):
                    start_reading_students = False  # Stop reading students
                    start_reading_companies = True
                elif line.startswith("PLACEMENT_INFO"):
                    start_reading_companies = False  # Stop reading students
                    start_reading_placements = True
                elif line.startswith("PLACEMENT_DEPENDENCIES"):
                    start_reading_placements = False  # Stop reading students
                    start_reading_placements_dependencies = True
                elif line.startswith("DISTANCE_MATRIX"):
                    start_reading_placements_dependencies = False  # Stop reading students
                    start_reading_distances = True
                    continue  # Skip the line with company column names

                # If we're reading the student matrix, split the line into values
                if start_reading_students and not start_reading_companies:
                    values = line.strip().split()
                    if len(values) >= 13 and values[0].isdigit():  # Check if the first element is a valid integer
                        # Extract scalar values
                        student_id = int(values[0])
                        importance_distance = float(values[1])
                        importance_competence_development = float(values[2])
                        # Extract lists
                        development_vector = [float(val) for val in values[3:(3+n_competences)]]
                        preference_vector = [float(val) for val in values[(3+n_competences):(3+2*n_competences)]]

                        # Create a dictionary for each student
                        student_dict = {
                            "student_id": student_id,
                            "importance_distance": importance_distance,
                            "importance_competence_development": importance_competence_development,
                            "development_vector": development_vector,
                            "preference_vector": preference_vector
                        }

                        self.student_info.append(student_dict)

                # If we're reading the company matrix, split the line into values
                if start_reading_companies and line.strip():  # Check if the line is not empty
                    values = line.strip().split()
                    if len(values) >= 3 and values[0].isdigit():  # Check if the first element is a valid integer
                        # Extract company info
                        company_bounds = [int(val) for val in values]
                        self.company_info.append(company_bounds)

                # If we're reading the placement matrix, split the line into values
                if start_reading_placements:
                    values = line.strip().split()
                    if len(values) >= 4 and values[0].isdigit():  # Check if the first element is a valid integer
                        # Extract placement info
                        placement_id = int(values[0])
                        company_id = int(values[1])
                        competence_importance_vector = [float(val) for val in values[2:]]

                        # Create a dictionary for each placement
                        placement_dict = {
                            "placement_id": placement_id,
                            "company_id": company_id,
                            "competence_importance_vector": competence_importance_vector
                        }

                        self.placement_info.append(placement_dict)

                # If we're reading the related placement matrix, split the line into values
                if start_reading_placements_dependencies:
                    values = line.strip().split()
                    if len(values) >= 2 and values[0].isdigit():  # Check if the first element is a valid integer
                        # Extract interdependency placement info
                        interdependent_placements = [int(val) for val in values]
                        self.placement_dependencies_info.append(interdependent_placements)

                # If we're reading the distances matrix, split the line into values
                if start_reading_distances:
                    student_distances = [float(x) for x in line.split("\t")]
                    self.distance_info.append(student_distances)
                        

        self._distance_info = scale_rows_to_0_1(self._distance_info)

        self._eta = self._calculate_eta()
        self._tao = self._calculate_tao()

        self._company_placement_matrix = self._create_company_placement_matrix()
        self._placements_without_deps = self._calculate_placements_without_dep()

        


        self._utility_matrix = np.matrix( [ 
            [ self._alpha * self._get_utility_student_placement(s_id, p_id) + self._beta * self._get_utility_placement_student(p_id, s_id) for p_id in range(self.number_placements)] 
            for s_id in range(self.number_students) ] )
        


        self._assignments = [ (self.get_utility_individual_assignment(s_id, p_id), s_id, p_id, self.get_company_id(p_id)) for s_id in range(self.number_students) for p_id in range(self.number_placements) ]
        #self._utility_matrix = np.array( [ut for ut,_,_,_ in self._assignments] ).reshape((self.number_students, self.number_placements))
        
        self._assignments.sort(key=lambda x: x[0], reverse=True)

        self._total_placements_with_dependencies = np.array([0 for i in range(self.number_companies)], np.uint16)

        for dep in self.placement_dependencies_info:
            b_id = self.get_company_id(dep[0])
            self._total_placements_with_dependencies[b_id] = self._total_placements_with_dependencies[b_id] + len(dep)

        self._numpy_company_placement_matrix = np.zeros( (self.number_companies, self.number_placements) , bool)
        for p_id in range(self.number_placements):
            b_id = self.get_company_id(p_id)
            self._numpy_company_placement_matrix[b_id, p_id] = 1

        self._numpy_dependency_matrix = np.zeros( (self.number_placement_dependencies, self.number_placements), bool )
        for i, dep in enumerate(self.placement_dependencies_info):
            for j in dep:
                self._numpy_dependency_matrix[i, j] = 1

        self._company_min = np.array( [self.get_min_student_company(b_id) for b_id in range(self.number_companies)] , np.uint16)
        self._company_max = np.array( [self.get_max_student_company(b_id) for b_id in range(self.number_companies)] , np.uint16)


        self._assignments_no_deps = [  (ut, s_id, p_id, b_id) for (ut, s_id, p_id, b_id) in self._assignments if self._placements_without_deps[p_id] ]

        self._placements_no_deps_greedy = []
        
        chosen_placements = set()
        for (ut, s_id, p_id, b_id) in self._assignments_no_deps:
            if not p_id in chosen_placements:
                chosen_placements.add(p_id)
                self._placements_no_deps_greedy.append((ut, s_id, p_id, b_id))

        #self._best_student_by_placement = dict()
        #number_times_student = dict()
        #for (ut, s_id, p_id, b_id) in self._assignments:
        #    if not p_id in self._best_student_by_placement:
        #        self._best_student_by_placement[p_id] = (ut, s_id)
        #        number_times_student[s_id] = number_times_student.setdefault(s_id, 0) + 1
        #        if len(self._best_student_by_placement) == self.number_placements:
        #            break
        #for p_id in self._best_student_by_placement:
        #    ut, s_id = self._best_student_by_placement[p_id]
        #    pen = number_times_student[s_id]
        #    self._best_student_by_placement[p_id] = (ut/pen, s_id)
        scores = self._utility_percentile_heuristic(percentile=0.1)
        self._greedy_ut_by_placement = [(scores[p_id], p_id) for p_id in range(self.number_placements)]
        self._greedy_ut_by_placement_no_dep = [(scores[p_id], p_id) for p_id in range(self.number_placements) if self._placements_without_deps[p_id]]
        self._greedy_ut_by_placement_no_dep.sort(reverse=True)
        
        self._greedy_ut_by_dependency = np.array([ sum([self._greedy_ut_by_placement[p_id][0] for p_id in dep]) for dep in self._placement_dependencies_info ])
        
        


        self._dependencies_business = dict()
        self._business_dependencies = dict()
        for i, dep in enumerate(self._placement_dependencies_info):
            p_id = dep[0]
            b_id = self.get_company_id(p_id)
            self._dependencies_business[i] = b_id
            if not b_id in self._business_dependencies:
                self._business_dependencies[b_id] = [i]
            else :
                self._business_dependencies[b_id].append(i)

        self._unassigned = np.sum(self._numpy_company_placement_matrix, axis=1) - self._total_placements_with_dependencies
                
    def _utility_penalized_heuristic(self):
        scores = dict()
        number_times_student = dict()
        for (ut, s_id, p_id, b_id) in self._assignments:
            if not p_id in scores:
                scores[p_id] = (ut, s_id)
                number_times_student[s_id] = number_times_student.setdefault(s_id, 0) + 1
                if len(scores) == self.number_placements:
                    break
        for p_id in scores:
            ut, s_id = scores[p_id]
            pen = number_times_student[s_id]
            scores[p_id] = ut/pen

        return scores
    
    def _utility_percentile_heuristic(self, percentile=0.1):
        scores = { p_id:0 for p_id in range(self.number_placements) }
        total_assignments = len(self._assignments)

        for (ut, s_id, p_id, b_id) in self._assignments[ 0:int(total_assignments*percentile) ]:
            scores[p_id] = scores[p_id] + ut

        #l_values = list(scores.values())
        #mu = np.mean(l_values)
        #sd = np.std(l_values)

        #for p_id in scores:
        #    scores[p_id] = (scores[p_id] - mu)/sd

        return scores




    def get_placement_company_matrix(self):
        return self._numpy_company_placement_matrix.copy()
    
    def get_dependency_matrix(self):
        return self._numpy_dependency_matrix.copy()

    def get_total_dependent_placements_per_business(self):
        return self._total_placements_with_dependencies.copy()
      
    @property
    def student_info(self):
        return self._student_info

    @property
    def company_info(self):
        return self._company_info

    @property
    def placement_info(self):
        return self._placement_info
    
    @property
    def placement_dependencies_info(self):
        return self._placement_dependencies_info
    
    @property
    def distance_info(self):
        return self._distance_info

    @property
    def number_students(self):
        return len(self.student_info)
    
    @property
    def number_placements(self):
        return len(self.placement_info)
    
    @property
    def number_companies(self):
        return len(self.company_info)
    
    @property
    def number_placement_dependencies(self):
        return len(self.placement_dependencies_info)
    
    def clear_cache_utilities(self):
        self._cache_utilities = dict()

    def get_sorted_assignments(self):
        return self._assignments.copy(), self._assignments_no_deps.copy()

    def get_company_id(self, placement_id):
        """
        Given a list of information about placements, returns the id of the company that offers the placement
        Args:
            placement_info_list: The list of placements information
            placement_id: The position of the placement in the list whose company should be returned
        Returns:
            An integer that represents the id of the company of the given placement
        """
        return self.placement_info[placement_id]["company_id"]
    
    def get_unweighted_utility(self, assignments):
        """
        Calculates both sum terms in equation 3a. The first one is the average utility of students
        The second one is the average utility per placement
        Args:
            assignments: A list of tuples (i,j) that identify the assignments made by an algorithm
        Returns:
            A tuple with the first term of the sum and the second term of the sum. Unweighted (no alpha or beta)
        """
        n_students = self.number_students
        utility_students = 0
        utility_businesses = 0
        for (i,j) in assignments:
            utility_students = utility_students  +  ( (1/n_students)*self._tao[i, j] )
            utility_businesses = utility_businesses + (1/n_students)*self._eta[i, j] 

        return utility_students, utility_businesses
    
    def get_utility_individual_assignment(self, student_id, placement_id):
        return self._utility_matrix[student_id, placement_id]
        #value = None
        #if (student_id, placement_id) in self._cache_utilities:
        #    value = self._cache_utilities[student_id, placement_id]
        #else :
        #    value = self._alpha * self.get_utility_student_placement(student_id, placement_id) + self._beta * self.get_utility_placement_student(placement_id, student_id)
        #    self._cache_utilities[student_id, placement_id] = value
        #return value


    def _get_utility_student_placement(self, student_id, placement_id):
        """
        Returns the individual utility of the placement for the student
        Args:
            student_id: The student identifier
            placement_id: The placement identifier
        Returns: 
            A float number
        """
        return self._tao[student_id, placement_id]
    
    def _get_utility_placement_student(self, placement_id, student_id):
        """
        Returns the individual utility of the student for the placement
        Args:
            student_id: The student identifier
            placement_id: The placement identifier
        Returns:
            A float number
        """
        return self._eta[student_id, placement_id]
    
    def get_placements_for_company(self, company_id):
        """
        Returns a list of placements associated to a company
        Args:
            company_id: The identifier of the company
        Returns:
            A list of placement identifiers
        """
        return self._company_placement_matrix[company_id]
    
    def get_placements_for_company_no_deps(self, company_id):
        """
        Returns a list of placements associated to a company
        Args:
            company_id: The identifier of the company
        Returns:
            A list of placement identifiers
        """
        return self._placements_without_deps[company_id]
    
    def get_min_student_company(self, company_id):
        """
        Args:
            company_id: The identifier of the company
        Returns:
            An integer with the minimum number of students for the company
        """
        return self.company_info[company_id][1]
    
    def get_max_student_company(self, company_id):
        """
        Args:
            company_id: The identifier of the company
        Returns:
            An integer with the maximum number of students for the company
        """
        return self.company_info[company_id][2] 
    
    def get_placement_dependencies(self, dependency_id):
        """
        Args:
            dependency_id: Identifier of the dependency
        Returns:
            A list of placement ids with dependency
        """
        return self.placement_dependencies_info[dependency_id]
    
    def is_valid_solution(self, assignments):
        assigned_placements = set()
        assigned_students = set()
        total_per_company = [0 for i in range(self.number_companies)]
        valid = True
        for (s_id, p_id) in assignments:
            if s_id in assigned_students:
                print(f"Student {s_id} assigned twice!")
                valid = False
                break
            if p_id in assigned_placements:
                print(f"Placement {p_id} assigned twice!")
                valid = False
                break
            assigned_students.add(s_id)
            assigned_placements.add(p_id)
            c_id = self.get_company_id(p_id)
            total_per_company[c_id] = total_per_company[c_id] + 1
        
        if len(assigned_students) != self.number_students or len(assigned_placements) != self.number_students:
            print(f"ERROR: assigned students {assigned_students}-{self.number_students}  assigned_placements {assigned_placements}-{self.number_students}")
            valid = False
        
        for c_id in range(self.number_companies):
            if total_per_company[c_id] < self.get_min_student_company(c_id) or total_per_company[c_id] > self.get_max_student_company(c_id):
                print(f"total for company {c_id} is {total_per_company[c_id]} and limits are  {self.get_min_student_company(c_id)} and {self.get_max_student_company(c_id)}")
                valid = False
                break

        for dependency in self.placement_dependencies_info:
            n= len(assigned_placements.intersection(dependency))
            if n!=0 and n!=len(dependency):
                valid = False
                print(f"Placement dependenciy {dependency} has the following intersection {assigned_placements.intersection(dependency)}")
                break
        return valid
    
    def get_utility_solution(self, assignments):
        
        total_utility = 0

        for(s_id, p_id) in assignments:
            total_utility = total_utility + self.get_utility_individual_assignment(s_id, p_id)
        
        return total_utility/self.number_students
        