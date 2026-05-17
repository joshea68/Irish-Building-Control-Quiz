"""
UK Premium Bond Draw Simulator (Pydroid friendly, stdlib only).

Models monthly NS&I Premium Bond prize draws using current published
odds (1 in 22,000 per GBP1 bond per month) and the May 2025 prize
fund distribution. Winnings are reinvested as additional bonds up to
the GBP50,000 holding cap; anything above the cap is treated as
"invested elsewhere" and tracked separately.
"""

import random
import math
from collections import deque

# --- UK Premium Bond parameters -------------------------------------------

# Odds: 1 in 22,000 per GBP1 bond per monthly draw.
ODDS_DENOM = 22000

# Maximum NS&I Premium Bond holding.
MAX_HOLDING = 50000

# Approximate prize structure (value in GBP, number of prizes).
# Based on a representative recent NS&I monthly draw (May 2025).
PRIZES = [
    (1_000_000,         2),
    (  100_000,        83),
    (   50_000,       166),
    (   25_000,       333),
    (   10_000,       832),
    (    5_000,     1_664),
    (    1_000,    17_420),
    (      500,    52_260),
    (      100, 1_994_851),
    (       50, 1_994_851),
    (       25, 1_392_936),
]

TOTAL_PRIZES = sum(count for _, count in PRIZES)

# Pre-built cumulative table for fast weighted sampling.
_CUMULATIVE = []
_running = 0
for _value, _count in PRIZES:
    _running += _count
    _CUMULATIVE.append((_running, _value))


# --- Probability helpers --------------------------------------------------

def draw_prize_value():
    """Return the value of a single prize, weighted by prize frequency."""
    r = random.randint(1, TOTAL_PRIZES)
    for cum, value in _CUMULATIVE:
        if r <= cum:
            return value
    return 0  # unreachable


def sample_winners(num_bonds, prob):
    """Sample how many bonds win in one monthly draw, ~ Binomial(n, p).

    Uses a direct Bernoulli loop for small expectations and a normal
    approximation once the expected number of wins is large enough to
    keep things fast on a phone.
    """
    expected = num_bonds * prob
    if expected < 40:
        wins = 0
        for _ in range(num_bonds):
            if random.random() < prob:
                wins += 1
        return wins
    mean = expected
    std = math.sqrt(num_bonds * prob * (1.0 - prob))
    sampled = int(round(random.gauss(mean, std)))
    if sampled < 0:
        sampled = 0
    if sampled > num_bonds:
        sampled = num_bonds
    return sampled


# --- Simulation -----------------------------------------------------------

def simulate(starting_bonds, months, monthly_buy=0, verbose=True):
    # Bonds bought this month aren't eligible until the draw two months
    # later (NS&I rule: a full clear calendar month must pass). We model
    # this with a two-slot pipeline: pending[0] = bought last month
    # (eligible next month), pending[1] = bought this month.
    active = min(starting_bonds, MAX_HOLDING)
    pending = deque([0, 0])
    overflow = 0
    total_winnings = 0
    total_bought = 0
    big_wins = []

    prob = 1.0 / ODDS_DENOM

    if verbose:
        print("")
        print("Starting holding:    GBP{:,}".format(active))
        print("Monthly purchase:    GBP{:,}".format(monthly_buy))
        print("Simulating {} monthly draws".format(months))
        print("-" * 70)

    for month in range(1, months + 1):
        # 1. Graduate the oldest pending tranche into the active pool.
        graduating = pending.popleft()
        active += graduating

        # 2. Run this month's draw on the active bonds.
        winners = sample_winners(active, prob)
        month_win = 0
        for _ in range(winners):
            value = draw_prize_value()
            month_win += value
            if value >= 1000:
                big_wins.append((month, value))
        total_winnings += month_win

        # 3. Reinvest winnings straight into active (existing behaviour),
        #    constrained by the GBP50,000 cap on total bond holding.
        held = active + sum(pending)
        room = MAX_HOLDING - held
        if month_win <= room:
            active += month_win
        else:
            if room > 0:
                active += room
            overflow += month_win - max(0, room)

        # 4. Buy this month's contribution into the pending pipeline,
        #    also constrained by the cap. Anything that can't fit goes
        #    "elsewhere".
        held = active + sum(pending)
        room = max(0, MAX_HOLDING - held)
        bought = min(monthly_buy, room)
        overflow += monthly_buy - bought
        total_bought += bought
        pending.append(bought)

        if verbose and (month_win > 0 or bought > 0):
            print(
                "M{:>3}: won GBP{:>7,}  bought GBP{:>5,}  "
                "active GBP{:>6,}  pending GBP{:>5,}  "
                "else GBP{:,}".format(
                    month, month_win, bought, active, sum(pending), overflow
                )
            )

    final_total = active + sum(pending)
    if verbose:
        print("-" * 70)
        print("Final active bonds:         GBP{:,}".format(active))
        print("Pending (not yet eligible): GBP{:,}".format(sum(pending)))
        print("Total bond holding:         GBP{:,}".format(final_total))
        print("Total bought from monthly:  GBP{:,}".format(total_bought))
        print("Invested elsewhere:         GBP{:,}".format(overflow))
        print("Total winnings:             GBP{:,}".format(total_winnings))
        print("Grand total (bonds + else): GBP{:,}".format(final_total + overflow))
        if big_wins:
            print("")
            print("Notable wins (GBP1,000+):")
            for m, v in big_wins:
                print("  Month {:>3}: GBP{:,}".format(m, v))
        else:
            print("")
            print("No prizes of GBP1,000 or more in this run.")

    return {
        "final_active": active,
        "final_pending": sum(pending),
        "final_total_bonds": final_total,
        "overflow": overflow,
        "total_winnings": total_winnings,
        "total_bought": total_bought,
        "big_wins": big_wins,
    }


# --- CLI ------------------------------------------------------------------

def _ask_int(prompt, minimum=None, maximum=None):
    while True:
        raw = input(prompt).strip().replace(",", "")
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print("Must be at least {}.".format(minimum))
            continue
        if maximum is not None and value > maximum:
            print("Must be at most {}.".format(maximum))
            continue
        return value


def _ask_yes_no(prompt):
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer yes or no.")


def main():
    print("UK Premium Bond Draw Simulator")
    print("==============================")
    print("Odds: 1 in {:,} per GBP1 bond per month".format(ODDS_DENOM))
    print("Holding cap: GBP{:,}".format(MAX_HOLDING))

    while True:
        bonds = _ask_int(
            "How many bonds do you hold? (GBP1 each, 25-50000): ",
            minimum=25,
            maximum=MAX_HOLDING,
        )
        months = _ask_int(
            "How many monthly draws to simulate? ",
            minimum=1,
        )
        monthly_buy = _ask_int(
            "How much to buy each month? (GBP, 0 for none): ",
            minimum=0,
            maximum=MAX_HOLDING,
        )

        simulate(bonds, months, monthly_buy=monthly_buy)

        print("")
        if not _ask_yes_no("Run another simulation? (y/n): "):
            print("Goodbye.")
            break
        print("")


if __name__ == "__main__":
    main()
