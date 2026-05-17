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

def simulate(starting_bonds, months, verbose=True):
    bonds = min(starting_bonds, MAX_HOLDING)
    overflow = 0          # winnings that couldn't fit under the cap
    total_winnings = 0
    big_wins = []         # remember prizes of GBP1,000+

    prob = 1.0 / ODDS_DENOM

    if verbose:
        print("")
        print("Starting holding: GBP{:,}".format(bonds))
        print("Simulating {} monthly draws".format(months))
        print("-" * 56)

    for month in range(1, months + 1):
        winners = sample_winners(bonds, prob)
        month_win = 0
        for _ in range(winners):
            value = draw_prize_value()
            month_win += value
            if value >= 1000:
                big_wins.append((month, value))

        total_winnings += month_win

        # Reinvest up to the cap, push the rest to "elsewhere".
        room = MAX_HOLDING - bonds
        if month_win <= room:
            bonds += month_win
            spilled = 0
        else:
            bonds = MAX_HOLDING
            spilled = month_win - room
            overflow += spilled

        if verbose and month_win > 0:
            print(
                "Month {:>3}: won GBP{:>7,}  bonds GBP{:>6,}  "
                "elsewhere GBP{:,}".format(month, month_win, bonds, overflow)
            )

    if verbose:
        print("-" * 56)
        print("Final bond holding:        GBP{:,}".format(bonds))
        print("Invested elsewhere:        GBP{:,}".format(overflow))
        print("Total winnings over period: GBP{:,}".format(total_winnings))
        print("Total pot (bonds + else):  GBP{:,}".format(bonds + overflow))
        if big_wins:
            print("")
            print("Notable wins (GBP1,000+):")
            for m, v in big_wins:
                print("  Month {:>3}: GBP{:,}".format(m, v))
        else:
            print("")
            print("No prizes of GBP1,000 or more in this run.")

    return {
        "final_bonds": bonds,
        "overflow": overflow,
        "total_winnings": total_winnings,
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


def main():
    print("UK Premium Bond Draw Simulator")
    print("==============================")
    print("Odds: 1 in {:,} per GBP1 bond per month".format(ODDS_DENOM))
    print("Holding cap: GBP{:,}".format(MAX_HOLDING))

    bonds = _ask_int(
        "How many bonds do you hold? (GBP1 each, 25-50000): ",
        minimum=25,
        maximum=MAX_HOLDING,
    )
    months = _ask_int(
        "How many monthly draws to simulate? ",
        minimum=1,
    )

    simulate(bonds, months)


if __name__ == "__main__":
    main()
