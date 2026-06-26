from unittest import TestCase

from colette.solver import (
    Pair,
    Person,
    RoundConfig,
    Solution,
    find_optimal_pairs,
    solve_round,
)


def test_find_optimal_pairs_reports_optimality():
    # cheapest to pair person 0 with 1 (cross-pair weight 0)
    cost, pairs, optimal = find_optimal_pairs(2, {(0, 0): 50, (0, 1): 0, (1, 1): 50})
    assert optimal is True
    assert (0, 1) in pairs
    assert cost == 0


def test_find_optimal_pairs_accepts_max_seconds():
    weights = {(i, j): (0 if i != j else 50) for i in range(4) for j in range(i, 4)}
    cost, pairs, optimal = find_optimal_pairs(4, weights, max_seconds=5)
    assert len(pairs) == 2  # everyone paired
    assert optimal is True


def test_solve_round_returns_valid_pairing_when_time_limited(monkeypatch):
    """Regression for a hard round (like round 59 of a long-running roulette).

    The matching is a MIP the solver can't always prove optimal in time. When
    it hits its limit and returns a feasible-but-not-proven-optimal solution we
    must still get a complete, valid pairing flagged non-optimal — never hang or
    raise. Simulated by making the optimiser report FEASIBLE after solving.
    """
    import mip

    real_optimize = mip.Model.optimize

    def time_limited(self, *args, **kwargs):
        real_optimize(self, *args, **kwargs)  # really solve (sets variables)
        return mip.OptimizationStatus.FEASIBLE  # but pretend time ran out

    monkeypatch.setattr(mip.Model, "optimize", time_limited)

    people = {
        name: Person(name, f"Org{i % 2}", True, f"{name}@example.com")
        for i, name in enumerate(["A", "B", "C", "D", "E", "F"])
    }
    config = RoundConfig(number=1, people=people)

    solution = solve_round(config, previous_rounds=[])

    assert solution.optimal is False
    # every active person is still covered exactly once
    covered = set()
    for pair in solution.pairs:
        covered.add(pair.primary.name)
        covered.add(pair.secondary.name)
    assert covered == set(people)
    assert len(solution.pairs) == 3


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
