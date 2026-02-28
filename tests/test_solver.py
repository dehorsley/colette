from unittest import TestCase

from colette.solver import Pair, Person, RoundConfig, Solution, solve_round


class TestSolver(TestCase):
    def test_solve_round(self):
        # Create a RoundConfig object with some test data
        people = {
            "Alice": Person("Alice", "Org1", True, "blag@example.com"),
            "Bob": Person("Bob", "Org2", True, "blag@example.com"),
            "Charlie": Person("Charlie", "Org1", True, "blag@example.com"),
            "Dave": Person("Dave", "Org2", True, "blag@example.com"),
        }

        previous_rounds = [
            Solution(
                0,
                1,
                frozenset(
                    {
                        Pair(people["Alice"], people["Bob"]),
                        Pair(people["Charlie"], people["Dave"]),
                    }
                ),
                caviats={},
            ),
            Solution(
                0,
                2,
                frozenset(
                    {
                        Pair(people["Alice"], people["Charlie"]),
                        Pair(people["Bob"], people["Dave"]),
                    }
                ),
                caviats={},
            ),
        ]

        overrides = {}
        config = RoundConfig(
            number=3,
            people=people,
            overrides=overrides,
        )

        # Call the solve_round function and check the output
        solution = solve_round(config, previous_rounds=previous_rounds)
        self.assertIsInstance(solution, Solution)
        self.assertEqual(len(solution.pairs), 2)
        self.assertEqual(solution.cost, 0)
        self.assertIn({people["Alice"], people["Dave"]}, solution)
        self.assertIn({people["Bob"], people["Charlie"]}, solution)

        # Alice should be secondary
        alice_pair = next(pair for pair in solution.pairs if people["Alice"] in pair)
        self.assertEqual(alice_pair.secondary, people["Alice"])
        self.assertNotEqual(alice_pair.primary, people["Alice"])
