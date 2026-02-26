import numpy as np
from tools.scaling import scale_rows_to_0_1


class SimpleSIPAWithTeachers:
    """
    Extended SIPA model including teachers (supervisors).

    A solution is a set of tuples (i, j, t):
        student i assigned to placement j supervised by teacher t
    """

    def __init__(self, path, alpha=0.5, beta=0.5, gamma=0.2):

        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

        # Base SIPA data
        self.student_info = []
        self.company_info = []
        self.placement_info = []
        self.placement_dependencies_info = []
        self.distance_info = []
        self.teacher_info = []

        # Parse instance file
        self._parse_instance(path)

        # Normalization & utilities
        self.distance_info = scale_rows_to_0_1(self.distance_info)

        self._tao = self._calculate_tao()   # student → placement
        self._eta = self._calculate_eta()   # placement → student
        self._mu  = self._calculate_mu()    # placement → teacher
   

    # Basic properties
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
    def number_teachers(self):
        return len(self.teacher_info)

    @property
    def number_placement_dependencies(self):
        return len(self.placement_dependencies_info)
    

    # Utilities
    def _calculate_tao(self):
        """
        Utility of placement j for student i
        """
        m = np.zeros((self.number_students, self.number_placements))

        for i in range(self.number_students):
            for j in range(self.number_placements):
                m[i, j] = (
                    self.student_info[i]["importance_distance"]
                    * (1 - self.distance_info[i][self.get_company_id(j)])
                    +
                    self.student_info[i]["importance_competence_development"]
                    * np.dot(
                        self.placement_info[j]["competence_importance_vector"],
                        self.student_info[i]["preference_vector"]
                    )
                )

        return self._zscore_rows(m)

    def _calculate_eta(self):
        """
        Utility of student i for placement j
        """
        m = np.zeros((self.number_students, self.number_placements))

        for i in range(self.number_students):
            for j in range(self.number_placements):
                m[i, j] = np.dot(
                    self.placement_info[j]["competence_importance_vector"],
                    self.student_info[i]["development_vector"]
                )

        return self._zscore_columns(m)

    def _calculate_mu(self):
        """
        Utility of teacher t supervising placement j (μ_jt)
        """
        m = np.zeros((self.number_placements, self.number_teachers))

        for j in range(self.number_placements):
            for t in range(self.number_teachers):
                m[j, t] = np.dot(
                    self.teacher_info[t]["competence_preference_vector"],
                    self.placement_info[j]["competence_importance_vector"]
                )

        return self._zscore_rows(m)


    # Public utility getters (contract for solvers)
    def get_student_utility(self, i, j):
        return self._tao[i, j]

    def get_business_utility(self, i, j):
        return self._eta[i, j]

    def get_teacher_utility(self, j, t):
        return self._mu[j, t]


    # Solution evaluation
    def evaluate_solution(self, assignments_ijt):
        """
        Computes all utilities of a solution.

        Args:
            assignments_ijt: list of (i, j, t)

        Returns:
            (U_students, U_businesses, U_teachers, U_joint)
        """
        n = self.number_students
        U_s, U_b, U_t = 0, 0, 0

        for (i, j, t) in assignments_ijt:
            U_s += self._tao[i, j]
            U_b += self._eta[i, j]
            U_t += self._mu[j, t]

        U_s /= n
        U_b /= n
        U_t /= n

        U_joint = (
            self.alpha * U_s +
            self.beta  * U_b +
            self.gamma * U_t
        )

        return U_s, U_b, U_t, U_joint


    # Constraints helpers
    def get_teacher_capacity(self, t):
        return self.teacher_info[t]["capacity"]

    def get_company_id(self, placement_id):
        return self.placement_info[placement_id]["company_id"]


    # Internal helpers
    def _zscore_rows(self, m):
        for i in range(m.shape[0]):
            mu = m[i, :].mean()
            sigma = m[i, :].std() or 1
            m[i, :] = (m[i, :] - mu) / sigma
        return m

    def _zscore_columns(self, m):
        for j in range(m.shape[1]):
            mu = m[:, j].mean()
            sigma = m[:, j].std() or 1
            m[:, j] = (m[:, j] - mu) / sigma
        return m