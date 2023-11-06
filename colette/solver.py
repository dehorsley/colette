from .models import Person, Pair, RoundConfig, Solution
import random

from itertools import chain
import mip


def solve_round(config: RoundConfig, previous_rounds: list[Solution]) -> Solution:
    """
    find_pairs finds the best (or a best) set of pairings based on the active players and
    the previous rounds.
    """

    def last_pairing(p: Person) -> Pair:
        """
        last_pairing finds the most recent pair person p participated in the
        list of previous_rounds, or None otherwise.
        """
        return next(
            (pairs[p] for pairs in reversed(previous_rounds) if p in pairs),
            None,
        )

    def assign_roles(p1: Person, p2: Person) -> Pair:
        """
        assign_roles makes a Pair object, assigning role "primary" or "secondary"
        to the players based on their previous assignments:

        - If the players were assigned a different role from each other last
          time they played, or one player hasn't played, they will swap roles.

        - If both were assigned the same role in their previous pairings, or
          neither have previously played, then they will be randomly assigned
          roles with equal probability.
        """

        if p1 == p2:
            # Player removed from the round
            return Pair(p1, p2)

        p1_last_pair = last_pairing(p1)
        p2_last_pair = last_pairing(p2)

        if p1_last_pair is None and p2_last_pair is None:
            if random.random() < 0.5:
                return Pair(primary=p1, secondary=p2)
            return Pair(primary=p2, secondary=p1)

        if (p1_last_pair is None or p1 == p1_last_pair.secondary) and (
            p2_last_pair is None or p2 == p2_last_pair.primary
        ):
            return Pair(primary=p1, secondary=p2)

        if (p1_last_pair is None or p1 == p1_last_pair.primary) and (
            p2_last_pair is None or p2 == p2_last_pair.secondary
        ):
            return Pair(primary=p2, secondary=p1)

        if random.random() < 0.5:
            return Pair(primary=p1, secondary=p2)

        return Pair(primary=p2, secondary=p1)

    # weights contains the "cost" to the final solution of pairing
    # player i and j together. Takes into account if players are in the same organisation,
    # were previously assigned the same role, and were previously paired together.
    weights = {}

    # whys contains the list of explanations for the "costs" in weights. This
    # allows for reporting of non-preferred matches in the optimal solution.
    caviats = {}

    players = [p for p in config.people.values() if p.active]

    N = len(players)
    for i in range(N):
        for j in range(i, N):
            p1 = players[i]
            p2 = players[j]
            cost = 0
            caviats[i, j] = []

            ##
            # overrides
            if (s := frozenset({p1, p2})) in config.overrides:
                cost += config.overrides[s]
                caviats[i, j].append(f"override values {config.overrides[s]}")

            ##
            # if partners were previously paired
            for n, solution in enumerate(reversed(previous_rounds)):
                if n >= config.cost_of_pairing_previous_partner_n:
                    break

                if {p1, p2} not in solution:
                    continue

                if i == j:
                    continue

                # TODO: maybe this should take into account the last time this pair
                # was *available* i.e. if someone goes in break, you don't want to
                # pair them up with the same person, when they came back even if
                # there was a large number of rounds between

                if n == 0:
                    cost += config.cost_of_pairing_previous_partner_one_round_ago
                    caviats[i, j].append(
                        "were paired last round" if i != j else "was removed last round"
                    )
                elif n < config.cost_of_pairing_previous_partner_n:
                    cost += config.cost_of_pairing_previous_partner_two_to_n_round_ago
                    caviats[i, j].append(
                        f"were paired less than {n+1} rounds ago"
                        if i != j
                        else f"was removed last less than {n+1} rounds ago"
                    )

            if i == j:
                cost += config.cost_of_not_pairing
                caviats[i, j].append("removed from round")
                weights[i, j] = cost
                continue

            ##
            # same org
            if p1.organisation == p2.organisation:
                cost += config.cost_of_pairing_within_org
                caviats[i, j].append("are in the same organisation")

            ##
            # if partners were of the same type in their last round
            p1_last_pair = last_pairing(p1)
            p2_last_pair = last_pairing(p2)

            if p1_last_pair is not None and p2_last_pair is not None:
                if (
                    p1 == p1_last_pair.primary
                    and p2 == p2_last_pair.primary
                    or p1 == p1_last_pair.secondary
                    and p2 == p2_last_pair.secondary
                ):
                    cost += config.cost_of_pairing_same_type
                    caviats[i, j].append("were the same role last round")

            weights[i, j] = cost

    cost, optimal_pair_indices = find_optimal_pairs(len(players), weights)

    caviats_in_solution = {}
    pairs = set()
    for i, j in optimal_pair_indices:
        pair = assign_roles(players[i], players[j])
        pairs.add(pair)
        if weights[i, j] > 0:
            caviats_in_solution[pair] = caviats[i, j]

    return Solution(
        cost=cost,
        round=config.number,
        pairs=frozenset(pairs),
        caviats=caviats_in_solution,
    )


def find_optimal_pairs(N, weights) -> (float, list[tuple[int, int]]):
    """
    find_optimal_pairs finds an optimal set of pairs of integers between 0 and
    N-1 (incl) that minimize the sum of the weights specified for each pair.

    Returns the objective value and list of pairs.
    """

    # List of possible pairings.
    # People are excluded from the round by pairing with themselves
    pairs = [(i, j) for i in range(N) for j in range(i, N)]

    def pairs_containing(k):
        return chain(((i, k) for i in range(k)), ((k, i) for i in range(k, N)))

    m = mip.Model()

    p = {pair: m.add_var(var_type=mip.BINARY) for pair in pairs}

    # Constraint: a person can only be in one pair,
    # so sum of all pairs with person k must be 1

    # TODO: this should use special ordred set type 1
    for k in range(N):
        m += mip.xsum(p[i, j] for i, j in pairs_containing(k)) == 1

    m.objective = mip.minimize(mip.xsum(weights[i, j] * p[i, j] for i, j in pairs))

    m.verbose = False
    status = m.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise Exception("not optimal")

    return m.objective_value, [(i, j) for i, j in pairs if p[i, j].x > 0.5]
