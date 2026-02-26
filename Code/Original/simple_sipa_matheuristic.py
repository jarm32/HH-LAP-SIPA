
import heapq
import numpy as np
from numpy import mean, array, fromiter, zeros, uint8, uint16, matrix, bitwise_and, bitwise_or, any
from array import array as parray
from numpy.random import choice
from numpy.random import shuffle as np_shuffle
from random import randint, shuffle, sample
from deap import base, creator, tools, algorithms
from math import comb
from lapjv import lapjv
from .simple_sipa_milp import solve_simple_sipa_milp
from ..problems.simple_sipa import SimpleSIPA
import umap
from sklearn.cluster import dbscan
from ortools.linear_solver import pywraplp
import itertools
from sklearn.decomposition import SparsePCA, PCA
import pacmap
import ot
import time


class DependencyGAFitness(base.Fitness):

    weights = (1.0, )

    def __init__(self, values=()):
        super().__init__(values)
        

class DependencyGASetSolution():


    def __init__(self, problem: SimpleSIPA, quick=False):
        self._problem = problem
        if not quick:
            self.clear()

    def __copy__(self):
        c = DependencyGASetSolution(self._problem, quick=True)
        c._solution = self._solution.copy()
        c._selected_from_business = self._selected_from_business.copy()
        c._must_send = self._must_send.copy()
        c._total_in_dependencies = self._total_in_dependencies #Fast copy
        c._unassigned = self._unassigned #Fast copy
        c._can_send = self._can_send.copy()
        c._total_chosen = self._total_chosen #Fast copy
        c._total_need_to_assign = self._total_need_to_assign #Fast copy
        c._total_can_assign = self._total_can_assign #Fast copy
        c._dep_by_business = {key:self._dep_by_business[key][:] for key in self._dep_by_business} #Fast copy
        c._over_limit = self._over_limit.copy()
        c._needs_more = self._needs_more.copy()
        c.fitness = DependencyGAFitness(values=self.fitness.values) #Fast copy
        return c
        

    def __deepcopy__(self, memodict={}):
        return self.__copy__()


    def clear(self):
        self._solution = set()

        self._selected_from_business = np.zeros(self._problem.number_companies)
        self._must_send = self._problem._company_min.copy()
        self._total_in_dependencies = self._problem._total_placements_with_dependencies
 
        self._unassigned = self._problem._unassigned
        self._can_send = np.minimum(self._problem._company_max, self._unassigned)

        self._total_chosen = 0

        self._total_need_to_assign = np.sum(self._must_send)
        self._total_can_assign = np.sum(self._can_send)

        self._dep_by_business = dict()

        self._over_limit = set()
        self._needs_more = set(np.where(self._can_send < self._must_send)[0])
        self.fitness = DependencyGAFitness()



    def _update_send_vectors(self, b_id):
        new_must_send = max(self._problem._company_min[b_id] - self._selected_from_business[b_id], 0)
        change_must_send = new_must_send - self._must_send[b_id]
        self._must_send[b_id] = new_must_send
        self._total_need_to_assign = self._total_need_to_assign + change_must_send

        new_can_assign = min(max(self._problem._company_max[b_id] - self._selected_from_business[b_id], 0), self._unassigned[b_id])
        change_can_send = new_can_assign - self._can_send[b_id]
        self._can_send[b_id] = new_can_assign
        self._total_can_assign = self._total_can_assign + change_can_send


    def add_dependency(self, dep_idx):
        if not dep_idx in self._solution:
            s = len(self._problem.placement_dependencies_info[dep_idx])
            self._total_chosen = self._total_chosen + s
            b_id = self._problem._dependencies_business[dep_idx]
            self._dep_by_business[b_id] = self._dep_by_business.setdefault(b_id, list()) + [dep_idx]
            self._selected_from_business[b_id] = self._selected_from_business[b_id] + s
            
            
            self._update_send_vectors(b_id)
            self._solution.add(dep_idx)

            if self._selected_from_business[b_id] > self._problem._company_max[b_id]:
                self._over_limit.add(b_id)
            if b_id in self._needs_more and self._can_send[b_id] >= self._must_send[b_id]:
                self._needs_more.remove(b_id)

    def remove_dependency(self, dep_idx):
        if dep_idx in self._solution:
            s = len(self._problem.placement_dependencies_info[dep_idx])
            self._total_chosen = self._total_chosen - s
            b_id = self._problem._dependencies_business[dep_idx]
            self._dep_by_business[b_id].remove(dep_idx) #self._dep_by_business.setdefault(b_id, list()).append(dep_idx)
            self._selected_from_business[b_id] = self._selected_from_business[b_id] - s
            
            self._update_send_vectors(b_id)
            self._solution.remove(dep_idx)

            if self._can_send[b_id] < self._must_send[b_id]:
                self._needs_more.add(b_id)
            if b_id in self._over_limit and self._selected_from_business[b_id] < self._problem._company_max[b_id]:
                self._over_limit.remove(b_id)


    def generate_randomly(self):
        self.clear()

        n = randint(0, self._problem.number_placement_dependencies)
        chosen_idx = set(choice(self._problem.number_placement_dependencies, n, replace=False))

        for dep_idx in chosen_idx:
            self.add_dependency(dep_idx)

        self.fix_solution()
        return self

    

    def fix_solution(self):
        required_fixing = True
        while required_fixing:
            f1 = self._fix_over_limit()
            f2 = self._fix_must_send()
            f3 = self._fix_total_achievable()
            required_fixing = f1 or f2 or f3



    def _fix_over_limit(self):
        if self._over_limit:
            list_businesses = list(self._over_limit)
            for b_id in list_businesses:
                dependencies = list(self._dep_by_business[b_id])
                shuffle(dependencies)
                for dep_idx in dependencies:
                    self.remove_dependency(dep_idx)
                    if self._selected_from_business[b_id] <= self._problem._company_max[b_id]:
                        break
            return True
        return False
        
    
    def _fix_must_send(self):
        if self._needs_more:
            list_businesses = list(self._needs_more)
            for b_id in list_businesses:
                list_deps = self._problem._business_dependencies[b_id].copy()
                shuffle(list_deps)
                for dep_idx in list_deps:
                    self.add_dependency(dep_idx)
                    if not b_id in self._needs_more:
                        break
            return True
        return False
            
    def _fix_total_achievable(self):
        if self._total_can_assign + self._total_chosen < self._problem.number_students:
            difference = self._problem.number_students - self._total_can_assign - self._total_chosen
            dependencies = [dep_id for dep_id in range(self._problem.number_placement_dependencies) if not dep_id in self._solution ]
            shuffle(dependencies)
            while difference > 0:
                dep_idx = dependencies.pop()
                self.add_dependency(dep_idx)
                difference = difference - len(self._problem._placement_dependencies_info[dep_idx])
            return True
        return False
    
    def get_fitness(self):
        if self.fitness.valid:
            return self.fitness.values
        else:
            n_left = self._problem.number_students - self._total_chosen
            ut_current = np.einsum("i->", self._problem._greedy_ut_by_dependency[list(self._solution)])
            ut_others = sum( score for score,_ in self._problem._greedy_ut_by_placement_no_dep[0:n_left])
            self.fitness.setValues((ut_current + ut_others, ))
            return self.fitness.values
    
    def evaluate(cls, solution):
        return solution.get_fitness()
    
    def mutate(self, p_mut=0.3):
        indices = np.random.choice(self._problem.number_placement_dependencies, size=int(p_mut * self._problem.number_placement_dependencies), replace=False)
        for idx in indices:
            if idx in self._solution:
                self.remove_dependency(idx)
            else:
                self.add_dependency(idx)
        self.fix_solution()
        return self,
    
    def crossover(self, other_solution):
        not_shared1 = self._solution.difference(other_solution._solution)
        not_shared2 = other_solution._solution.difference(self._solution)
        not_shared = list(not_shared1 | not_shared2)
        for elem in not_shared1:
            self.remove_dependency(elem)
        for elem in not_shared2:
            other_solution.remove_dependency(elem)
        shuffle(not_shared)
        n_elements = len(not_shared)
        if n_elements > 0:
            n1 = np.random.randint(0, n_elements)
            elems1 = not_shared[0:n1]
            elems2 = not_shared[n1:]
            for elem in elems1:
                self.add_dependency(elem)
            for elem in elems2:
                other_solution.add_dependency(elem)
        self.fix_solution()
        other_solution.fix_solution()
        return self, other_solution
    
            
class ProxyFitnessFunctionA():

    def __init__(self, problem: SimpleSIPA):
        self._problem = problem

        self._scores = {}
        for j in range(problem.number_placements):
            self._scores[j] = 0
            for i in range(problem.number_students):
                score = problem.get_utility_individual_assignment(i, j)
                self._scores[j] = max(self._scores[j], score)

    def evaluate(self, placements):
        return np.sum( self._scores[j] for j in placements )/self._problem.number_students

class ProxyFitnessFunctionB():

    def __init__(self, problem: SimpleSIPA, n):
        self._problem = problem
        self.n = n

        self._scores = {}
        for j in range(problem.number_placements):
            self._scores[j] = []
            heapq.heapify(self._scores[j])
            for i in range(problem.number_students):
                score = problem.get_utility_individual_assignment(i, j)
                heapq.heappush(self._scores[j], score)
                #self._scores[j] = max(self._scores[j], score)

    def evaluate(self, placements):
        return np.sum( np.mean(heapq.nlargest(self.n, self._scores[j])) for j in placements )/self._problem.number_students
    

class ProxyFitnessFunctionTransport():

    def __init__(self, problem: SimpleSIPA, n_components=2, n_neighbors=5):
        self._problem = problem
        self.number_placements = problem.number_placements

        student_data = []
        for i in range(problem.number_students):   
            student_data.append(problem.student_info[i]["preference_vector"] + problem.student_info[i]["development_vector"])

        embedding = pacmap.PaCMAP(n_components=n_components, n_neighbors=n_neighbors).fit_transform(student_data,init="pca")
        
        cluster_labels = dbscan(embedding)

        self._clusters = {}
        for i in range(problem.number_students):
            cluster_label = cluster_labels[1][i]
            cluster_label = cluster_label + 1
            if cluster_label in self._clusters:
                self._clusters[cluster_label].add(i)
            else:
                self._clusters[cluster_label] = set([i])
        
        self._scores = {}

        self._cost_matrix = np.zeros((self.number_placements, len(self._clusters)))
        self._placement_prod = np.ones(problem.number_placements)
        self._cluster_demand = np.array([len(self._clusters[c_id]) for c_id in range(len(self._clusters))])
        for c_id in range(len(self._clusters)):
            cluster_members = self._clusters[c_id]
            for j in range(self.number_placements):
                cluster_score = np.mean([problem._utility_matrix[i, j] for i in cluster_members])
                self._cost_matrix[j, c_id] = -cluster_score

    def evaluate(self, placements):
        M = self._cost_matrix[placements, : ]
        a = self._placement_prod[placements]
        b = self._cluster_demand
        res = ot.emd(a, b, M)
        return -np.sum(M.flatten()*res.flatten())/self._problem.number_students 

class RandomPlacementSelection():

    def __init__(self, problem: SimpleSIPA) -> None:
        self._problem = problem

    def run(self):
        solution = DependencyGASetSolution(self._problem)
        solution.generate_randomly()

        placements = random_choice_placements_np(self._problem, self._problem._assignments_no_deps, solution._total_chosen, solution._must_send, solution._can_send)

        placements_idx = list(np.where(placements == 1)[0])

        for dep_idx in solution._solution:
            for idx in self._problem._placement_dependencies_info[dep_idx]:
                placements_idx.append(idx)
                placements[idx] = 1

        return placements_idx, placements
    

class RandomSearch():

    def __init__(self, problem:SimpleSIPA):
        self._problem = problem
        self._best_solution = None
        self._best_fitness = float("-inf")      

    def run(self, deadline=180):
        t1 = time.time()
        while time.time() - t1 <= deadline:
            placement_choice_idx, placements = RandomPlacementSelection(self._problem).run()
            np.random.shuffle(placement_choice_idx)
            assignments = [ (i, placement_choice_idx[i]) for i in range(self._problem.number_students) ]
            ut = self._problem.get_utility_solution(assignments)
            is_valid = self._problem.is_valid_solution(assignments)
            if not is_valid:
                raise Exception("Problema gordo!!!!")
            if ut > self._best_fitness:
                self._best_fitness = ut
                self._best_solution = assignments
        return self._best_solution
    
class GreedyHeuristicSearch():

    def __init__(self, problem:SimpleSIPA):
        self._problem = problem
        self._best_solution = None
        self._best_fitness = float("-inf") 

    def _generate_greedy_placement_selection(self):
        solution = DependencyGASetSolution(self._problem)
        solution.generate_randomly()

        placements = greedy_choice_placements2_np(self._problem, self._problem._placements_no_deps_greedy, solution._total_chosen, solution._must_send, solution._can_send)

        placements_idx = list(np.where(placements == 1)[0])

        for dep_idx in solution._solution:
            for idx in self._problem._placement_dependencies_info[dep_idx]:
                placements_idx.append(idx)
                #placements[idx] = 1

        return placements_idx


    def run(self, deadline=180):
        t1 = time.time()
        while time.time() - t1 <= deadline:
            placement_choice_idx = set(self._generate_greedy_placement_selection())
            student_choice = set()
            assignments = []
            for (ut, s_id, p_id, b_id) in self._problem._assignments:
                if (s_id not in student_choice and p_id in placement_choice_idx):
                    assignments.append((s_id, p_id))
                    placement_choice_idx.remove(p_id)
                    student_choice.add(s_id)
                    if len(student_choice) == self._problem.number_students:
                        break
            ut = self._problem.get_utility_solution(assignments)
            if ut >= self._best_fitness:
                self._best_fitness = ut
                self._best_solution = assignments
        return self._best_solution

class ClassicGA():

    def _generate_random_solution(self):
        placement_choice_idx, placements = RandomPlacementSelection(self._problem).run()
        np.random.shuffle(placement_choice_idx)
        selected = set(placement_choice_idx)

        s = placement_choice_idx + [j for j in range(self._problem.number_placements) if j not in selected]
        
        return s
    
    def _fix_solution(self, solution):
        cardinality_per_business = [0 for k in range(self._problem.number_companies)]
        placements = set()
        placements_no_deps = set()
        placements_per_business = {}
        not_used_placements = list(p_id for p_id in range(self._problem.number_placements))
        

        for s_id, p_id in enumerate(solution[0:self._problem.number_students]):
            c_id = self._problem.get_company_id(p_id)
            placements_per_business.setdefault(c_id, set()).add(p_id)
            cardinality_per_business[c_id] = cardinality_per_business[c_id] + 1
            placements.add(p_id)
            not_used_placements.remove(p_id)
        
        invalid = True
        while invalid:
            invalid = False
            np.random.shuffle(not_used_placements)
            for d_id, dep in enumerate(self._problem._placement_dependencies_info):
                b_id = self._problem.get_company_id(dep[0])
                common = placements.intersection(dep)
                l_common = len(common)
                if l_common > 0 and l_common < len(dep): #Decide to activate or deactivate
                    invalid = True
                    if np.random.random() < 0.5: #Deactivate
                        to_replace = not_used_placements[0:l_common]
                        not_used_placements = not_used_placements[l_common:]
                        placements.difference_update(common)
                        cardinality_per_business[b_id] = cardinality_per_business[b_id] - l_common
                        placements_per_business[b_id].difference_update(common)
                        not_used_placements.extend(common)
                        for p_id in to_replace:
                            n_b_id = self._problem.get_company_id(p_id)
                            cardinality_per_business[n_b_id] = cardinality_per_business[n_b_id] + 1
                            placements_per_business.setdefault(n_b_id, set()).add(p_id)
                    else: #Activate
                        to_be_replaced = np.random.choice(list(placements.difference(dep)), len(dep) - l_common)
                        for p_id in to_be_replaced:
                            n_b_id = self._problem.get_company_id(p_id)
                            placements.remove(p_id)
                            not_used_placements.append(p_id)
                            cardinality_per_business[n_b_id] = cardinality_per_business[n_b_id] - 1
                            placements_per_business[n_b_id].remove(p_id)
                        for p_id in set(dep).difference(common):
                            cardinality_per_business[b_id] = cardinality_per_business[b_id] + 1
                            placements.add(p_id)
                            not_used_placements.remove(p_id)
                            placements_per_business[n_b_id].add(p_id)
            if invalid:
                continue

            for b_id in range(self._problem.number_companies):
                c = cardinality_per_business[b_id]
                m = self._problem.get_min_student_company(b_id)
                M = self._problem.get_max_student_company(b_id)
                if c < m: #Invalid
                    invalid = True
                    need = m - c
                    not_added = list(set(self._problem.get_placements_for_company(b_id)).difference(placements_per_business[b_id]))
                    to_add = np.random.choice(not_added, need)
                    to_remove = np.random.choice(list(placements), need)
                    placements.update(to_add)
                    cardinality_per_business[b_id] = cardinality_per_business[b_id] + need
                    placements_per_business.setdefault(b_id, set()).update(to_add)
                    placements.difference_update(to_remove)
                    not_used_placements = [p_id for p_id in not_used_placements if not p_id in to_add]
                    for p_id in to_remove:
                        n_b_id = self._problem.get_company_id(p_id)
                        cardinality_per_business[n_b_id] = cardinality_per_business[n_b_id] - 1
                        not_used_placements.append(p_id)
                        placements.remove(p_id)
                elif c > M: #Invalid
                    invalid = True
                    

                        
                        





                

    def _fitness(self, solution):
        utility = 0
        cardinality_per_business = [0 for k in range(self._problem.number_companies)]
        placements = set()
        for s_id, p_id in enumerate(solution[0:self._problem.number_students]):
            c_id = self._problem.get_company_id(p_id)
            cardinality_per_business[c_id] = cardinality_per_business[c_id] + 1
            placements.add(p_id)
            utility = utility + self._problem.get_utility_individual_assignment(s_id, p_id)
        
        deviation_cardinality = 0
        for b_id, q in enumerate(cardinality_per_business):
            m = self._problem.get_min_student_company(b_id)
            M = self._problem.get_max_student_company(b_id)
            d = 0
            if q < m:
                d = m - q
            elif q > M:
                d = q - M
            if d:
                deviation_cardinality = deviation_cardinality + d/(1 if m==M else d/(M-m))
        
        deviation_dependency = 0
        for d_id, dep in enumerate(self._problem._placement_dependencies_info):
            l_common = len(placements.intersection(dep))
            if l_common > 0 and l_common < len(dep):
                deviation_dependency = deviation_dependency + (len(dep) - l_common)/len(dep)

        if deviation_dependency > 0 or deviation_cardinality > 0:
            return (-10 - ( deviation_cardinality/self._problem.number_companies + deviation_dependency/self._problem.number_placement_dependencies ),)
        else :
            return (utility/self._problem.number_students,)


    def run(self):
        population = self._toolbox.population(100)
        algorithms.eaSimple(population, self._toolbox, 0, 0.4, 100, self._stats, halloffame=self._hof)
        return self._hof[0]


    def __init__(self, problem:SimpleSIPA, tournsize=2, cx_indpb=0.5, mt_indpb=0.3):
        self._problem = problem
        self._best_solution = None
        self._best_fitness = float("-inf")

        creator.create("FitnessClassicGASIPA", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessClassicGASIPA)
        self._toolbox = base.Toolbox()

        self._toolbox.register("individual", lambda: creator.Individual(self._generate_random_solution()))
        self._toolbox.register("population", tools.initRepeat, list, self._toolbox.individual)
        self._toolbox.register("mate", tools.cxUniformPartialyMatched, indpb=cx_indpb)
        self._toolbox.register("mutate", tools.mutShuffleIndexes, indpb=mt_indpb)
        self._toolbox.register("select", tools.selTournament, tournsize=tournsize)
        self._toolbox.register("evaluate", self._fitness)

    
        self._stats = tools.Statistics(key= lambda ind: ind.fitness.values)
        self._stats.register("avg", np.mean)
        self._stats.register("min", np.min)
        self._stats.register("max", np.max)


        self._hof = tools.HallOfFame(1)            

    





def generate_random_dependency_selection_np(problem, placement_dependency_matrix):
    n = randint(0, problem.number_placement_dependencies)
    idx = choice(problem.number_placement_dependencies, n, replace=False)
    return np.sum(placement_dependency_matrix[i, :] for i in idx), idx

def generate_random_dependency_selection_set(problem):
    n = randint(0, problem.number_placement_dependencies)
    idx = set(choice(problem.number_placement_dependencies, n, replace=False))
    return idx

def generate_greedy_dependency_selection(problem, all_dependencies_weights):
    all_dependencies_idx = [i for i in range(problem.number_placement_dependencies)]
    n = randint(0, problem.number_placement_dependencies)
    return choice(all_dependencies_idx, n, replace=False, p=all_dependencies_weights)

def remove_dependency(problem, dep_idx, b_id, base_solution, selected_from_business, must_send, can_send, unassigned):
    s = len(problem.placemenent_dependencies_info[dep_idx])
    base_solution.remove(dep_idx)                 
    selected_from_business[b_id] = selected_from_business[b_id] - s

    new_must_send = max(problem.company_min[b_id] - selected_from_business[b_id], 0)
    change_must_send = new_must_send - must_send[b_id]
    must_send[b_id] = new_must_send
    total_need_to_assign = total_need_to_assign + change_must_send

    new_can_assign = min(max(problem.company_max[b_id] - selected_from_business[b_id], 0), unassigned[b_id])
    change_can_send = new_can_assign - can_send[b_id]
    can_send[b_id] = new_can_assign
    total_can_assign = total_can_assign + change_can_send

    return s, change_can_send, change_must_send


    
    company_min = problem._company_min
    company_max = problem._company_max
    placement_matrix = problem._numpy_company_placement_matrix
    total_in_dependencies = problem._total_placements_with_dependencies
    valid = False

    base_solution = chosen_dependencies

    unassigned = np.sum(placement_matrix, axis=1) - total_in_dependencies

    total_chosen = 0
    selected_from_business = zeros(problem.number_companies, uint16) #[0 for i in range(problem.number_companies)]
        
    must_send = company_min.copy()
    can_send = company_max.copy()

    over_company_max = set()
    need_to_send_more = set()

    dep_by_business = dict()

    for dep_idx in chosen_dependencies:
        s = len(problem.placement_dependencies_info[dep_idx])
        total_chosen = total_chosen + s
        b_id = problem._dependencies_business[dep_idx]
        dep_by_business[b_id] = dep_by_business.setdefault(b_id, list()).append(dep_idx)
        selected_from_business[b_id] = selected_from_business[b_id] + s
        if selected_from_business[b_id] > company_max:
            over_company_max.add(b_id)
        must_send[b_id] = max(must_send[b_id] - s, 0)
        can_send[b_id] = max( can_send[b_id] - s, 0 ) 

    can_send = np.minimum(can_send, unassigned)
    need_to_send_more.update(np.where(can_send < must_send))
    total_need_to_assign = np.sum(must_send)
    total_can_assign = np.sum(can_send)

    ok_companies = set([b_id for b_id in range(problem.number_companies)]).difference(need_to_send_more).difference(over_company_max)
    
    while not valid:
        if total_chosen > problem.number_students or over_company_max:

            total_to_reduce = total_chosen - problem.number_students

            while over_company_max:
                b_id = over_company_max.pop()
                deps = dep_by_business[b_id]
                shuffle(deps)
                while deps:
                    dep_idx = deps.pop()
                    
                    s=remove_dependency(problem, dep_idx, b_id, base_solution, selected_from_business)


                    total_chosen = total_chosen - s
                    total_to_reduce = total_to_reduce - s

                    if selected_from_business[b_id] <= company_max[b_id]:
                        break
                
                if not deps:
                    dep_by_business.pop(b_id)
                
                


                if can_send[b_id] >= must_send[b_id]:
                    need_to_send_more.remove(b_id)
                    ok_companies.add(b_id)
                else:
                    need_to_send_more.add(b_id)
                
            #Solved over capacity problems. Try to solve with businesses that have no problems
            list_businesses = [b_id for b_id in dep_by_business]
            shuffle(list_businesses) 
            while list_businesses:
                b_id = over_company_max.pop()
                deps = dep_by_business[b_id]
                shuffle(deps) 

                while deps:
                    dep_idx = deps.pop()
                    s = len(problem.placemenent_dependencies_info[dep_idx])
                    base_solution.remove(dep_idx)
                    
                    selected_from_business[b_id] = selected_from_business[b_id] - s

                    total_chosen = total_chosen - s
                    total_to_reduce = total_to_reduce - s

                    if total_to_reduce <= 0:
                        break
                new_must_send = max(company_min[b_id] - selected_from_business[b_id], 0)
                change_must_send = new_must_send - must_send[b_id]
                must_send[b_id] = new_must_send
                total_need_to_assign = total_need_to_assign + change_must_send

                new_can_assign = min(max(company_max[b_id] - selected_from_business[b_id], 0), unassigned[b_id])
                change_can_send = new_can_assign - can_send[b_id]
                can_send[b_id] = new_can_assign
                total_can_assign = total_can_assign + change_can_send

                if not deps:
                    dep_by_business.pop(b_id)

                if total_to_reduce <= 0:
                    break
        elif np.any(can_send < must_send) :
            need_additional = must_send - can_send
            to_activate = [i for i in range(len(base_solution)) if base_solution[i] == 0]
            np.random.shuffle(to_activate)
            how_many = len(np.where(need_additional > 0))
            for dep_idx in to_activate:
                dep = problem.placement_dependencies_info[dep_idx]
                p_id = dep[0]
                c_id = problem.get_company_id(p_id)
                if need_additional[c_id] > 0:
                    dep_size = len(dep)
                    need_additional[c_id] = need_additional[c_id] - dep_size
                    base_solution[dep_idx] = 1
                    if need_additional[c_id] <= 0:
                        how_many = how_many - 1
                        if how_many == 0:
                            break
        elif (total_chosen + total_can_assign) < problem.number_students:
            difference = problem.number_students - total_chosen - total_can_assign
            non_active = [i for i in range(len(base_solution)) if base_solution[i] == 0]
            np.random.shuffle(non_active)
            for dep_idx in non_active:
                dep_s = len(problem.placement_dependencies_info[dep_idx])
                difference = difference - dep_s
                base_solution[dep_idx] = 1
                if difference <= 0:
                    break
        else:
            valid = True




        #ut1 =  ((total_chosen-problem.number_students)/problem.number_students if total_chosen > problem.number_students else 0)
        #ut2 = np.sum(selected_from_business > company_max )/problem.number_companies
        #ut3 = np.sum(can_send < must_send)/problem.number_companies
        #ut4 = ((problem.number_students-total_chosen-total_can_assign)/problem.number_students if (total_chosen+total_can_assign)<problem.number_students else 0)

        #count_invalid = ut1 + ut2 + ut3 + ut4

    #if ut4 and not (ut1+ut2+ut3):
    #    print(chosen_dependencies, len(chosen_dependencies), np.where(np.array(chosen_dependencies)==1), total_chosen)
    #    input()
        
    

        #(1 if total_can_assign < total_need_to_assign else 0) + \
        
    
    #if total_chosen+total_can_assign < problem.number_students:
    #    print(total_chosen, total_can_assign, total_chosen + total_can_assign)

    #    input()

    return base_solution, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business

def fix_dependency_solution(problem, chosen_dependencies):
    
    company_min = problem._company_min
    company_max = problem._company_max
    placement_matrix = problem._numpy_company_placement_matrix
    total_in_dependencies = problem._total_placements_with_dependencies
    valid = False

    base_solution = chosen_dependencies
    while not valid:
        chosen_placements = binary_dependency_vector_to_np(base_solution, problem)
        
        total_chosen = 0
        selected_from_business = zeros(problem.number_companies, uint16) #[0 for i in range(problem.number_companies)]

        zerosv = np.zeros(problem.number_companies)

        total_chosen = sum(problem.placement_dependencies_info)

        selected_from_business = np.sum(bitwise_and(chosen_placements, placement_matrix), axis=1)
        

        must_send = np.maximum( company_min - selected_from_business, zerosv )
        total_need_to_assign = np.sum(must_send)


        #d_diff = np.maximum( company_min - selected_from_business, zerosv)
        unassigned = np.sum(placement_matrix, axis=1) - total_in_dependencies

        can_send = np.maximum( company_max - selected_from_business, zerosv)
        can_send = np.minimum(can_send, unassigned)
        total_can_assign = np.sum(can_send)
        
        if total_chosen > problem.number_students:
            to_reduce = total_chosen - problem.number_students
            active_dep = [i for i in range(len(base_solution)) if base_solution[i] == 1]
            np.random.shuffle(active_dep)
            for dep_idx in active_dep:
                dep_size = len(problem.placement_dependencies_info[dep_idx])
                base_solution[dep_idx] = 0
                to_reduce = to_reduce - dep_size
                if to_reduce <= 0:
                    break
        elif np.sum(selected_from_business > company_max) > 0:
            to_reduce = selected_from_business - company_max
            how_many = len(np.where(to_reduce>0))
            active_dep = [i for i in range(len(base_solution)) if base_solution[i] == 1]
            np.random.shuffle(active_dep)
            for dep_idx in active_dep:
                dep = problem.placement_dependencies_info[dep_idx]
                p_id = dep[0]
                c_id = problem.get_company_id(p_id)
                if to_reduce[c_id] > 0:
                    dep_size = len(dep)
                    to_reduce[c_id] = to_reduce[c_id] - dep_size
                    base_solution[dep_idx] = 0
                    if to_reduce[c_id] <= 0:
                        how_many = how_many - 1
                        if how_many == 0:
                            break
        elif np.any(can_send < must_send) :
            need_additional = must_send - can_send
            to_activate = [i for i in range(len(base_solution)) if base_solution[i] == 0]
            np.random.shuffle(to_activate)
            how_many = len(np.where(need_additional > 0))
            for dep_idx in to_activate:
                dep = problem.placement_dependencies_info[dep_idx]
                p_id = dep[0]
                c_id = problem.get_company_id(p_id)
                if need_additional[c_id] > 0:
                    dep_size = len(dep)
                    need_additional[c_id] = need_additional[c_id] - dep_size
                    base_solution[dep_idx] = 1
                    if need_additional[c_id] <= 0:
                        how_many = how_many - 1
                        if how_many == 0:
                            break
        elif (total_chosen + total_can_assign) < problem.number_students:
            difference = problem.number_students - total_chosen - total_can_assign
            non_active = [i for i in range(len(base_solution)) if base_solution[i] == 0]
            np.random.shuffle(non_active)
            for dep_idx in non_active:
                dep_s = len(problem.placement_dependencies_info[dep_idx])
                difference = difference - dep_s
                base_solution[dep_idx] = 1
                if difference <= 0:
                    break
        else:
            valid = True




        #ut1 =  ((total_chosen-problem.number_students)/problem.number_students if total_chosen > problem.number_students else 0)
        #ut2 = np.sum(selected_from_business > company_max )/problem.number_companies
        #ut3 = np.sum(can_send < must_send)/problem.number_companies
        #ut4 = ((problem.number_students-total_chosen-total_can_assign)/problem.number_students if (total_chosen+total_can_assign)<problem.number_students else 0)

        #count_invalid = ut1 + ut2 + ut3 + ut4

    #if ut4 and not (ut1+ut2+ut3):
    #    print(chosen_dependencies, len(chosen_dependencies), np.where(np.array(chosen_dependencies)==1), total_chosen)
    #    input()
        
    

        #(1 if total_can_assign < total_need_to_assign else 0) + \
        
    
    #if total_chosen+total_can_assign < problem.number_students:
    #    print(total_chosen, total_can_assign, total_chosen + total_can_assign)

    #    input()

    return base_solution, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business
    
def is_valid_dependency_selection(problem, chosen_dependencies, total_in_dependencies):
    valid = True
    total_chosen = 0
    selected_from_business = [0 for i in range(problem.number_companies)]
    must_send = [ 0 for i in range(problem.number_companies)]
    can_send = [0 for i in range(problem.number_companies)]

    for d_idx in chosen_dependencies:
            dep_info = problem.get_placement_dependencies(d_idx)
            n_dep = len(dep_info)
            c_id = problem.get_company_id(dep_info[0])
            selected_from_business[c_id] = selected_from_business[c_id] + n_dep
            total_chosen + n_dep
    
    if total_chosen <= problem.number_students:
        total_need_to_assign = 0
        total_can_assign = 0
        for b_id in range(problem.number_companies):
            total_assigned=selected_from_business[b_id]
            b_min = problem.get_min_student_company(b_id)
            b_max = problem.get_max_student_company(b_id)
            if total_assigned>b_max:
                return (False, [], [])
            d_diff = max(b_min - total_assigned, 0)
            unassigned = len(problem.get_placements_for_company(b_id)) - total_in_dependencies[b_id]
            
            m_assign = max(b_max - selected_from_business[b_id], 0)
            if unassigned < d_diff or m_assign < d_diff:
                return (False, [], [])
            total_need_to_assign = total_need_to_assign + d_diff
            total_can_assign = total_can_assign + m_assign
            must_send[b_id] = d_diff
            can_send[b_id] = m_assign
        if valid and total_can_assign>=total_need_to_assign:
            return (True, must_send,  can_send) 
    else:
        return False, [], []
    
def random_choice_partition(problem, total_assigned, must_assign, can_assign, total_in_dependencies):
    b_indices = [b_id for b_id in range(problem.number_companies)]
    shuffle(b_indices)

    cardinalities = must_assign.copy()

    total_can_assign = sum(can_assign)
    total_must_assign = sum(must_assign)

    to_assign = problem.number_students - total_assigned
    surplus_to_assign = to_assign - total_must_assign
    surplus_left = total_can_assign - total_must_assign
    if surplus_to_assign < 0:
        raise Exception("IMPORTANT ERROR, THIS SHOULD HAVE NEVER HAPPENED")

    for b_id in b_indices:
        business_surplus = can_assign[b_id] - must_assign[b_id]
        min_surplus = max(0, surplus_to_assign - surplus_left + business_surplus)
        s = randint(min_surplus, business_surplus)
        surplus_to_assign = surplus_to_assign - s
        surplus_left = surplus_left - business_surplus
        cardinalities[b_id] = cardinalities[b_id] + s

            

    return cardinalities

def greedy_choice_placements2_np(problem, sorted_assignments, total_assigned, must_assign, can_assign):
    assigned_placements = set() # zeros(problem.number_placements, bool)
    assigned_student = set() # zeros(problem.number_students, bool)
    total_must_assign = np.sum(must_assign)
    total_to_assign = problem.number_students - total_assigned

    for i, (ut, s_id, p_id, b_id) in enumerate(sorted_assignments):
        if (not p_id in assigned_placements): # and (must_assign[b_id] > 0 or (can_assign[b_id]>0 and total_to_assign > total_must_assign)):
            if must_assign[b_id]>0:
                assigned_placements.add(p_id)
                assigned_student.add(s_id)
                can_assign[b_id] = can_assign[b_id] - 1
                total_must_assign = total_must_assign - 1
                must_assign[b_id] = must_assign[b_id] - 1  
                total_to_assign = total_to_assign - 1
                if total_must_assign == 0:
                    break
    for i, (ut, s_id, p_id, b_id) in enumerate(sorted_assignments):
        if (not p_id in assigned_placements): # and (must_assign[b_id] > 0 or (can_assign[b_id]>0 and total_to_assign > total_must_assign)):
            if can_assign[b_id]>0:
                assigned_placements.add(p_id)
                assigned_student.add(s_id)
                can_assign[b_id] = can_assign[b_id] - 1
                total_to_assign = total_to_assign - 1
                if total_to_assign == 0:
                    break
        
    assignment_vector = np.zeros(problem.number_placements, bool)
    assignment_vector[list(assigned_placements)] = 1
    return assignment_vector

def random_choice_placements_np(problem, sorted_assignments, total_assigned, must_assign, can_assign):
    assigned_placements = set() # zeros(problem.number_placements, bool)
    random_order = [i for i in range(len(sorted_assignments))]
    np_shuffle(random_order)
    total_must_assign = np.sum(must_assign)
    total_to_assign = problem.number_students - total_assigned
    
    assigned_per_business = np.zeros(problem.number_companies) 
    for idx in random_order:
        (ut, s_id, p_id, b_id) = sorted_assignments[idx]
        if (not p_id in assigned_placements): # and (must_assign[b_id] > 0 or (can_assign[b_id]>0 and total_to_assign > total_must_assign)):
            if must_assign[b_id]>0:
                assigned_per_business[b_id] = assigned_per_business[b_id] + 1
                assigned_placements.add(p_id)
                can_assign[b_id] = can_assign[b_id] - 1
                total_must_assign = total_must_assign - 1
                must_assign[b_id] = must_assign[b_id] - 1  
                total_to_assign = total_to_assign - 1
                if total_must_assign == 0:
                    break
    
    for idx in random_order:
        (ut, s_id, p_id, b_id) = sorted_assignments[idx]
        if (not p_id in assigned_placements): # and (must_assign[b_id] > 0 or (can_assign[b_id]>0 and total_to_assign > total_must_assign)):
            if can_assign[b_id]>0:
                assigned_per_business[b_id] = assigned_per_business[b_id] + 1
                assigned_placements.add(p_id)
                can_assign[b_id] = can_assign[b_id] - 1
                total_to_assign = total_to_assign - 1
                if total_to_assign == 0:
                    break
            
        
    assignment_vector = np.zeros(problem.number_placements, bool)
    assignment_vector[list(assigned_placements)] = 1
    return assignment_vector


def greedy_choice_placements2(problem, sorted_assignments, total_assigned, must_assign, can_assign):

    
    assigned_placements = set()
    assigned_student = set()
    #added_per_business = [0 for i in range(problem.number_companies)]
    total_must_assign = sum(must_assign)
    total_to_assign = problem.number_students - total_assigned

    for (ut, s_id, p_id, b_id) in sorted_assignments:
        if (not p_id in assigned_placements) and (not s_id in assigned_student) and must_assign[b_id] and can_assign[b_id]:
            assigned_placements.add(p_id)
            assigned_student.add(s_id)
            must_assign[b_id] = must_assign[b_id] - 1
            can_assign[b_id] = can_assign[b_id] - 1
            total_must_assign = total_must_assign - 1
            total_to_assign = total_to_assign - 1
            if not total_must_assign:
                break
    if total_to_assign:
        for (ut, s_id, p_id, b_id) in sorted_assignments:
            if (not p_id in assigned_placements) and (not s_id in assigned_student) and can_assign[b_id]:
                assigned_placements.add(p_id)
                assigned_student.add(s_id)
                can_assign[b_id] = can_assign[b_id] - 1
                total_to_assign = total_to_assign - 1
                if not total_to_assign:
                    break
    #print(sum(must_assign), sum(can_assign), len(assigned_placements), len(assigned_student))

    return assigned_placements


def random_choice_placements(problem, to_be_assigned):
    chosen_placements = []
    for b_id in range(problem.number_companies):
        chosen_placements.append(choice(problem.get_placements_for_company_no_deps(b_id), to_be_assigned[b_id], replace=False ))
    return chosen_placements

def greedy_choice_placements(problem, to_be_assigned, utilities):
    chosen_placements = []
    for b_id in range(problem.number_companies):
        if to_be_assigned[b_id]:
            no_dep_placements = problem.get_placements_for_company_no_deps(b_id)
            weights = array( [max(utilities[j]) for j in no_dep_placements] )
            weights = weights/sum(weights)
            chosen_placements.append(choice(problem.get_placements_for_company_no_deps(b_id), to_be_assigned[b_id], replace=False, p=weights ))
            #print(chosen_placements)
        else:
            chosen_placements.append([])
    return chosen_placements

def local_improvement(problem, assignments, no_dep_placements, sorted_assignments, alpha, beta):

    no_deps = set(no_dep_placements)
    no_deps_not_assigned = set(no_dep_placements)

    assignments_per_business = [0 for i in range(problem.number_companies)]
    can_send = set()
    can_receive = set()
    in_current_solution = set() 
    assigned_placement = set()

    student_assignments = dict()

    for (s_id, p_id) in assignments:
        b_id = problem.get_company_id(p_id)
        assignments_per_business[b_id] = assignments_per_business[b_id] + 1
        in_current_solution.add((s_id, p_id))
        assigned_placement.add(p_id)
        student_assignments[s_id] = ( p_id, problem.get_utility_individual_assignment(s_id, p_id) )
        if p_id in no_deps:
            no_deps_not_assigned.remove(p_id)

    for b_id in range(problem.number_companies):
        t = assignments_per_business[b_id]
        if t < problem.get_max_student_company(b_id):
            can_receive.add(b_id)
        if t > problem.get_min_student_company(b_id):
            can_send.add(b_id)

    s_order = [s_id for s_id in range(problem.number_students)]
    shuffle(s_order)

    while 1:
        improvement = False
        for s_id in s_order:
            (p_id, ut) = student_assignments[s_id]
            b_id = problem.get_company_id(p_id)
            if p_id in no_deps:
                for new_p_id in no_deps_not_assigned:
                    n_ut = problem.get_utility_individual_assignment(s_id,new_p_id) 
                    b_id2 = problem.get_company_id(new_p_id)
                    if b_id == b_id2 and n_ut > ut:
                        improvement = True
                        student_assignments[s_id] = (new_p_id, n_ut)
                        no_deps_not_assigned.add(p_id)
                        no_deps_not_assigned.remove(new_p_id)
                        p_id = new_p_id
                        ut = n_ut
                    elif n_ut > ut and b_id in can_send and b_id2 in can_receive:
                        improvement = True
                        student_assignments[s_id] = (new_p_id, n_ut)
                        no_deps_not_assigned.add(p_id)
                        no_deps_not_assigned.remove(new_p_id)
                        p_id = new_p_id
                        ut = n_ut
                        assignments_per_business[b_id] = assignments_per_business[b_id] - 1
                        t = assignments_per_business[b_id]
                        if t == problem.get_min_student_company(b_id):
                            can_send.remove(b_id)
                        assignments_per_business[b_id2] = assignments_per_business[b_id2] + 1
                        t = assignments_per_business[b_id2]
                        if t == problem.get_max_student_company(b_id2):
                            can_receive.remove(b_id2)
        if not improvement:
            break

    return [ (s_id, student_assignments[s_id][0]) for s_id in range(problem.number_students) ]



def deap_generate_random_dependency_selection(problem):
    n = randint(0, problem.number_placement_dependencies)
    idx = set(choice(problem.number_placement_dependencies, n, replace=False))
    #print(np.sum(problem._numpy_dependency_matrix[i, :] for i in idx))
    return [1 if i in idx else 0 for i in range(problem.number_placement_dependencies) ]



def deap_dependency_GA(problem, number_iterations=100, hof_size=10, p_cx=0.14, p_mut=0.2, cxpb=0.15, mpb=0.22, tourn_size=7, pop_size=100, lambda_=5, verbosity=False):

    def crossover(solution1, solution2):
        return solution1.crossover(solution2)
    
    def mutation(solution):
        return solution.mutate(p_mut=mpb)
    
    def fitness(solution):
        return solution.get_fitness()

    toolbox = base.Toolbox()

    toolbox.register("individual", lambda: DependencyGASetSolution(problem))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("mate", crossover )
    toolbox.register("mutate", mutation )
    toolbox.register("select", tools.selTournament, tournsize=tourn_size)
    toolbox.register("evaluate", fitness )

    if verbosity:
        stats = tools.Statistics(key= lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("min", np.min)
        stats.register("max", np.max)


    hof = tools.HallOfFame(hof_size)            

    population = [DependencyGASetSolution(problem).generate_randomly() for i in range(pop_size)]
    print("POP CREATED")
    algorithms.eaSimple(population, toolbox, p_cx, p_mut, number_iterations, stats=stats, halloffame=hof, verbose=verbosity)
    #if verbosity:
    #    algorithms.eaMuPlusLambda(population, toolbox, len(population), lambda_, p_cx, p_mut, ngen=number_iterations, stats=stats, halloffame=hof, verbose=verbosity)
    #else:
    #    algorithms.eaMuPlusLambda(population, toolbox, len(population), lambda_, p_cx, p_mut, ngen=number_iterations, halloffame=hof, verbose=verbosity)
 
    return hof

#def greedy_randomized_valid_dependency(problem):
#    solution = [0 for i in range(problem.number_placement_dependencies)]
#    order = choice(problem.number_placement_dependencies, problem.number_placement_dependencies, p=problem._greedy_ut_by_dependency)
#    for idx in order:
#        solution[idx] = 1
#        valid, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business, company_max, company_min = is_valid_dependency_selection_np(problem, binary_dependency_vector_to_np(solution, problem))
#        if not valid:
#            solution[idx] = 0

    

def binary_dependency_vector_to_np(solution, problem):
    return np.sum((problem._numpy_dependency_matrix[i] for i in range(problem.number_placement_dependencies) if solution[i]==1), axis=1)

def solve_assignment(placements, problem):
    cost_matrix = - problem._utility_matrix[:, placements==1]

            
    row_ind, _, _ = lapjv(cost_matrix)

    col_idx = np.where(placements)[0]

    assignments = [ (i, col_idx[row_ind[i]]) for i in range(problem.number_students) ]

    return assignments

def heuristicB(problem):
    
    sorted_assignments_no_deps =  problem._placements_no_deps_greedy

    solution = DependencyGASetSolution(problem)
    solution.generate_randomly()

    chosen_placements = np.sum(problem._numpy_dependency_matrix[list(solution._solution), ], axis=0)
        
    total_assigned = solution._total_chosen 
    must_send = solution._must_send
    can_send = solution._can_send

    chosen_placements2 = random_choice_placements_np(problem, sorted_assignments_no_deps, total_assigned, must_send, can_send)  #greedy_choice_placements2_np(problem, sorted_assignments_no_deps, total_assigned, must_send, can_send)

    final_placements = chosen_placements + chosen_placements2
        
    cost_matrix = - problem._utility_matrix[:, final_placements==1]

            
    row_ind, _, _ = lapjv(cost_matrix)

    col_idx = np.where(final_placements)[0]

    assignments = [ (i, col_idx[row_ind[i]]) for i in range(problem.number_students) ]

    was_valid = problem.is_valid_solution(assignments)

    if not was_valid:
        raise Exception("Invalid solution for heuristic B")

    utility = problem.get_utility_solution(assignments)
        
    return utility

def heuristicA(problem, number_iterations=100, hof_size=10, p_cx=0.7, p_mut=0.2, cxpb=0.6, mpb=0.1, tourn_size=4, pop_size=100, lambda_=50, alpha=0.5, beta=0.5, time_limit=900000, verbosity=False):
    
    number_dependencies = problem.number_placement_dependencies
    number_companies = problem.number_companies
    number_students = problem.number_students

    company_placement_matrix = problem.get_placement_company_matrix()

    placement_dependency_matrix = problem.get_dependency_matrix()

    total_in_dependencies = problem.get_total_dependent_placements_per_business()
    #print("**************", total_in_dependencies)
    no_dep_placements = problem._calculate_placements_without_dep()

    sorted_assignments, _ = problem.get_sorted_assignments()

    sorted_assignments_no_deps =  problem._placements_no_deps_greedy

    #hof = deap_dependency_GA(problem, number_iterations=number_iterations, hof_size=hof_size, p_cx=p_cx, p_mut=p_mut, cxpb=cxpb, mpb=mpb, tourn_size=tourn_size, pop_size=pop_size, lambda_=lambda_, verbosity=verbosity)

    best_fitness = 0 

    solution = DependencyGASetSolution(problem)
    solution.generate_randomly()
    hof = [solution]

    for solution in hof:
        chosen_placements = np.sum(problem._numpy_dependency_matrix[list(solution._solution), ], axis=0)
        #chosen_placements = binary_dependency_vector_to_np(solution, problem)
        total_assigned = solution._total_chosen #np.sum(chosen_placements)
        must_send = solution._must_send
        can_send = solution._can_send
        #_, must_send, can_send, _, _, _  = fix_dependency_solution(problem, solution)

        chosen_placements2 = random_choice_placements_np(problem, sorted_assignments_no_deps, total_assigned, must_send, can_send)  #greedy_choice_placements2_np(problem, sorted_assignments_no_deps, total_assigned, must_send, can_send)

        final_placements = chosen_placements + chosen_placements2
        
        cost_matrix = - problem._utility_matrix[:, final_placements==1]

        print("************************", cost_matrix.shape)
            
        row_ind, _, _ = lapjv(cost_matrix)

        col_idx = np.where(final_placements)[0]

        assignments = [ (i, col_idx[row_ind[i]]) for i in range(problem.number_students) ]

        was_valid = problem.is_valid_solution(assignments)

        if not was_valid:
            continue

        utility = problem.get_utility_solution(assignments)
        if utility > best_fitness:
            best_fitness = utility

        
        
    return best_fitness


    #print("RANDOM + ASSIGNMENT-----------------------")
    #for i in range(10):
    #    valid = False
    #    while not valid:
    #        chosen_placements, chosen_dependencies = generate_random_dependency_selection_np(problem, placement_dependency_matrix)
    #        valid, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business, company_max, company_min  = is_valid_dependency_selection_np(problem, chosen_placements)
    #    total_assigned = np.sum(chosen_placements)
    #    chosen_placements2 = greedy_choice_placements2_np(problem, sorted_assignments_no_deps, total_assigned, must_send, can_send)

    #    final_placements = chosen_placements + chosen_placements2
        
    #    cost_matrix = - problem._utility_matrix[:, final_placements==1]

    #    row_ind, _, _ = lapjv(cost_matrix)

    #    col_idx = np.where(final_placements)[0]

    #    assignments = [ (i, col_idx[row_ind[i]]) for i in range(problem.number_students) ]

    #    was_valid = problem.is_valid_solution(assignments)
    #    print(was_valid, problem.get_utility_solution(assignments))






    #creator.create("MaxDependency", base.Fitness, weights=(1.0, ))
    #creator.create("Individual", parray, fitness=creator.MaxDependency)
    #toolbox = base.Toolbox()

    #toolbox.register("population", tools.initRepeat, list, lambda x: deap_generate_random_dependency_selection(number_dependencies))
    #toolbox.register("mate", tools.cxUniform)
    #toolbox.register("mutate", tools.mutFlipBit, indpb=0.1)
    #toolbox.register("select", tools.selTournament, tournsize=3)
    #toolbox


    #for i in range(100):
    #    solutiodeap_generate_random_dependency_selection(number_dependencies)
        #generate_random_dependency_selection_np(problem, placement_dependency_matrix)


    #valid = False
    #while not valid:
    #    chosen_placements, chosen_dependencies = generate_random_dependency_selection_np(problem, placement_dependency_matrix)
    #    valid, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business, company_max, company_min  = is_valid_dependency_selection_np(problem, company_placement_matrix, min_companies, max_companies, chosen_placements, total_in_dependencies)

    #total_assigned = np.sum(chosen_placements)
    #chosen_placements2 = greedy_choice_placements2_np(problem, no_dep_placements, sorted_assignments_no_deps, total_assigned, must_send, can_send)

    #final_placements = chosen_placements + chosen_placements2
        
    #cost_matrix = - problem._utility_matrix[:, final_placements==1]

    #row_ind, _, _ = lapjv(cost_matrix)

    #col_idx = np.where(final_placements)[0]

    #assignments = [ (i, col_idx[row_ind[i]]) for i in range(problem.number_students) ]

    #was_valid = problem.is_valid_solution(assignments)

    #if not was_valid:
    #    print("ERROR")
    #    break

    #list_chosen_placements_dependencies = []

    #while len(list_chosen_placements_dependencies) < 100:
        #chosen_placements, chosen_dependencies = generate_random_dependency_selection_np(problem, placement_dependency_matrix)
        #valid, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business, company_max, company_min  = is_valid_dependency_selection_np(problem, company_placement_matrix, min_companies, max_companies, chosen_placements, total_in_dependencies)

        #if valid:
        #    list_chosen_placements_dependencies.append( (chosen_placements, chosen_dependencies, must_send, can_send, total_can_assign, total_need_to_assign, selected_from_business, company_max, company_min) )

    #for it in range(number_iterations):
    #    chosen_placements, chosen_dependencies = generate_random_dependency_selection_np(problem, placement_dependency_matrix)
    #    valid, must_send, can_send1 = is_valid_dependency_selection_np(problem, company_placement_matrix, min_companies, max_companies, chosen_placements, total_in_dependencies)
        #valid2, must_send2, can_send2 = is_valid_dependency_selection(problem, chosen_dependencies, total_in_dependencies)
        #if valid1 != valid2:
        #    print(valid1, valid2, chosen_dependencies, [ i for i in range(problem.number_placements) if chosen_placements[i] == 1 ], 
        #          [ problem.get_placement_dependencies(j) for j in chosen_dependencies ],
        #          [ problem.get_min_student_company(problem.get_company_id(problem.get_placement_dependencies(j)[0])) for j in chosen_dependencies ],
        #          [ problem.get_max_student_company(problem.get_company_id(problem.get_placement_dependencies(j)[0])) for j in chosen_dependencies ]
        #          )
        #    return
            
        
        
    

    return

    sorted_assignments = [ (alpha*problem.get_utility_student_placement(i,j) + beta*problem.get_utility_placement_student(j,i), i, j, problem.get_company_id(j)) for i in range(problem.number_students) for j in no_dep_placements ]
    sorted_assignments.sort(key=lambda t: t[0], reverse=True)

    
    for it in range(1):
        chosen_dependencies = None
        invalid_choice = False
        must_send = []
        can_send = []
        while not invalid_choice:
            chosen_dependencies = generate_random_dependency_selection(problem)#, all_dependencies_weights)
            invalid_choice, must_send, can_send = is_valid_dependency_selection(problem, chosen_dependencies, total_in_dependencies)

        sent_by_business = [0 for i in range(problem.number_companies)]
        for i in chosen_dependencies:
            b_id = problem.get_company_id(problem.placement_dependencies_info[i][0])
            sent_by_business[b_id] = sent_by_business[b_id] + len(problem.placement_dependencies_info[i])
        total_assigned = sum( [len(problem.placement_dependencies_info[i]) for i in chosen_dependencies] )
        
        #cardinalities = random_choice_partition(problem, total_assigned, must_send, can_send, total_in_dependencies)
        #total = 0
        #for j in range(problem.number_companies):
        #    t = cardinalities[j] + sent_by_business[j]
        #    total = total + t
        #    if t < problem.get_min_student_company(j) or t>problem.get_max_student_company(j):
        #        raise Exception("WTFFFFFF!!!!")
        #if total != problem.number_students:
        #    raise Exception(f"{total} {problem.number_students} ASDASDADASDASD")
        
        placement_idx = []
        #chosen_placements = greedy_choice_placements(problem, cardinalities, all_utilities)

        chosen_placements = greedy_choice_placements2(problem, sorted_assignments, total_assigned, must_send, can_send)

        #print(cho)

        #for p in chosen_placements:
        placement_idx.extend(chosen_placements)
        
        for idx in chosen_dependencies:
            placement_idx.extend(problem.placement_dependencies_info[idx])

        placement_idx.sort()

        cost_matrix = [ [] for i in range(problem.number_students) ]

        for i in range(problem.number_students):
            for j in range(len(placement_idx)):
                jp = placement_idx[j]
                a=problem.get_utility_student_placement(i,jp)
                b=problem.get_utility_placement_student(jp,i)
                cost_matrix[i].append(-alpha*a - beta*b)

        mat = matrix(cost_matrix)

        #print(mat.shape)
        row_ind, col_ind, algo = lapjv(mat)

        assignments = [ (i, placement_idx[row_ind[i]] ) for i in range(problem.number_students) ]

        utility_students, utility_businesses = problem.get_utility(assignments)

        #print(assignments)

        #for s_id in range(problem.number_students):
        #    for p_id in range(problem.number_placements):
        #        ut_s = problem.get_utility_student_placement(s_id, p_id)
        #        ut_p = problem.get_utility_placement_student(p_id, s_id)
        #        t_ut = alpha*ut_s + beta*ut_p
                


        was_valid = problem.is_valid_solution(assignments)
        ut = alpha*utility_students+beta*utility_businesses

        new_assignments = local_improvement(problem, assignments, no_dep_placements, sorted_assignments, alpha, beta)
        
        is_valid = problem.is_valid_solution(new_assignments)
        utility_students, utility_businesses = problem.get_utility(new_assignments)
        ut2 = alpha*utility_students+beta*utility_businesses

        print(ut, ut2, ut2-ut, was_valid, is_valid)

        

        

        
        

        
    return None


    





