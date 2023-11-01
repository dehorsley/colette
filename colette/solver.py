from .data import Person, Pair, RoundConfig, Solution
import random

from itertools import chain
import mip

# NB: these must all be integers!
COST_OF_NOT_PAIRING = 50
COST_OF_PAIRING_WITHIN_ORG = 10

COST_OF_PAIRING_SAME_TYPE = 1  # as in role in pair: orgraniser or coffee buyer

# Should be a big number. Really don't want to pair people together *just* after
# they paired
COST_OF_PAIRING_PREVIOUS_PARTNER_ONE_ROUND_AGO = 1_000_000
# Cost of pairing players that were previously paired between 2 to N rounds ago
COST_OF_PAIRING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO = 50
# Number of round before a previous pairing doesn't matter anymore
COST_OF_PAIRING_PREVIOUS_PARTNER_N = 10


def solve_round(config: RoundConfig) -> Solution:
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
            (pairs[p] for pairs in reversed(config.previous_rounds) if p in pairs),
            None,
        )

    def assign_roles(p1: Person, p2: Person) -> Pair:
        """
        assign_roles makes a Pair object, assigning role "organiser" or "buyer"
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
                return Pair(organiser=p1, buyer=p2)
            return Pair(organiser=p2, buyer=p1)

        if (p1_last_pair is None or p1 == p1_last_pair.buyer) and (
            p2_last_pair is None or p2 == p2_last_pair.organiser
        ):
            return Pair(organiser=p1, buyer=p2)

        if (p1_last_pair is None or p1 == p1_last_pair.organiser) and (
            p2_last_pair is None or p2 == p2_last_pair.buyer
        ):
            return Pair(organiser=p2, buyer=p1)

        if random.random() < 0.5:
            return Pair(organiser=p1, buyer=p2)

        return Pair(organiser=p2, buyer=p1)

    # weights contains the "cost" to the final solution of pairing
    # player i and j together. Takes into account if players are in the same organisation,
    # were previously assigned the same role, and were previously paired together.
    weights = {}

    # whys contains the list of explanations for the "costs" in weights. This
    # allows for reporting of non-preferred matches in the optimal solution.
    whys = {}

    N = len(config.people)
    for i in range(N):
        for j in range(i, N):
            p1 = config.people[i]
            p2 = config.people[j]
            cost = 0
            whys[i, j] = []

            ##
            # overrides
            if (s := frozenset({p1, p2})) in config.overrides:
                cost += config.overrides[s]
                whys[i, j].append(f"override values {config.overrides[s]}")

            ##
            # if partners were previously paired
            for n, pairing in enumerate(reversed(config.previous_rounds)):
                if n >= COST_OF_PAIRING_PREVIOUS_PARTNER_N:
                    break

                if p1 not in pairing:
                    continue
                if p2 not in pairing[p1]:
                    continue

                if i == j and pairing[p1].organiser != pairing[p1].buyer:
                    continue

                # TODO: maybe this should take into account the last time this pair
                # was *available* i.e. if someone goes in break, you don't want to
                # pair them up with the same person, when they came back even if
                # there was a large number of rounds between

                if n == 0:
                    cost += COST_OF_PAIRING_PREVIOUS_PARTNER_ONE_ROUND_AGO
                    whys[i, j].append(
                        "were paired last round" if i != j else "was removed last round"
                    )
                elif n < COST_OF_PAIRING_PREVIOUS_PARTNER_N:
                    cost += COST_OF_PAIRING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO
                    whys[i, j].append(
                        f"were paired less than {n+1} rounds ago"
                        if i != j
                        else f"was removed last less than {n+1} rounds ago"
                    )

            if i == j:
                cost += COST_OF_NOT_PAIRING
                whys[i, j].append("removed from round")
                weights[i, j] = cost
                continue

            ##
            # same org
            if p1.organisation == p2.organisation:
                cost += COST_OF_PAIRING_WITHIN_ORG
                whys[i, j].append("are in the same organisation")

            ##
            # if partners were of the same type in their last round
            p1_last_pair = last_pairing(p1)
            p2_last_pair = last_pairing(p2)

            if p1_last_pair is not None and p2_last_pair is not None:
                if (
                    p1 == p1_last_pair.organiser
                    and p2 == p2_last_pair.organiser
                    or p1 == p1_last_pair.buyer
                    and p2 == p2_last_pair.buyer
                ):
                    cost += COST_OF_PAIRING_SAME_TYPE
                    whys[i, j].append("were the same role last round")

            weights[i, j] = cost

    pairs = []
    cost, optimal_pair_indices = find_optimal_pairs(len(players), weights)
    for i, j in optimal_pair_indices:
        if weights[i, j] > 0:
            # TODO: something better than this, option to turn off or something
            if i == j:
                print(players[i].name, ", ".join(whys[i, j]))
            else:
                print(
                    f"{players[i].name} paired with {players[j].name} but players",
                    " and ".join(whys[i, j]),
                )
        pair = assign_roles(players[i], players[j])
        pairs.append(pair)

    return pairs


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
    for k in range(N):
        m += mip.xsum(p[i, j] for i, j in pairs_containing(k)) == 1

    m.objective = mip.minimize(mip.xsum(weights[i, j] * p[i, j] for i, j in pairs))

    m.verbose = False
    status = m.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise Exception("not optimal")

    return m.objective_value, [(i, j) for i, j in pairs if p[i, j].x > 0.5]
