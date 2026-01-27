import unittest

from simple_sipa import SimpleSIPA
from simple_sipa_milp import solve_simple_sipa_milp

class TestSolveSimpleSIPAMILP(unittest.TestCase):

    def test_instance_1(self):
        path = "data/SAC/problems_0/problem_instance_100_0.txt"
        p = SimpleSIPA(path)
        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.6915555319995197)
        self.assertAlmostEqual(utility_businesses, 0.27637899999999993)
        self.assertAlmostEqual(joint_utility, 0.4839672659997598)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=1, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.7275444693230401)
        self.assertAlmostEqual(utility_businesses, 0.19332399999999997)
        self.assertAlmostEqual(joint_utility, 0.46043423466152)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=2, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.46789738919021673)
        self.assertAlmostEqual(utility_businesses, 0.31897999999999993)
        self.assertAlmostEqual(joint_utility, 0.39343869459510833)
        self.assertGreater(t, 0)


    def test_instance_2(self):
        path = "data/SAC/problems_10/problem_instance_100_0.txt"
        p = SimpleSIPA(path)
        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.7144850316130307)
        self.assertAlmostEqual(utility_businesses, 0.26465)
        self.assertAlmostEqual(joint_utility, 0.48956751580651536)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=1, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.7450200553034706)
        self.assertAlmostEqual(utility_businesses, 0.189315)
        self.assertAlmostEqual(joint_utility, 0.4671675276517353)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=2, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.4912897318270711)
        self.assertAlmostEqual(utility_businesses, 0.31672999999999996)
        self.assertAlmostEqual(joint_utility, 0.4040098659135355)
        self.assertGreater(t, 0)


    def test_instance_3(self):
        path = "data/SAC/problems_20/problem_instance_100_0.txt"
        p = SimpleSIPA(path)
        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.7479351683961596)
        self.assertAlmostEqual(utility_businesses, 0.277991)
        self.assertAlmostEqual(joint_utility, 0.5129630841980798)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=1, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.78938197259172)
        self.assertAlmostEqual(utility_businesses, 0.18083299999999997)
        self.assertAlmostEqual(joint_utility, 0.48510748629586)
        self.assertGreater(t, 0)

        status, utility_students, utility_businesses, joint_utility, t = solve_simple_sipa_milp(p, "SCIP", mode=2, time_limit=300000)
        self.assertEqual(status, 0)
        self.assertAlmostEqual(utility_students, 0.5654672001297881)
        self.assertAlmostEqual(utility_businesses, 0.32399299999999986)
        self.assertAlmostEqual(joint_utility, 0.444730100064894)
        self.assertGreater(t, 0)
