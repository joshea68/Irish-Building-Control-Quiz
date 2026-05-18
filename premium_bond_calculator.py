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
import time
from collections import deque

# --- UK Premium Bond parameters -------------------------------------------

# Odds: 1 in 22,000 per GBP1 bond per monthly draw.
ODDS_DENOM = 22000

# Combined holding cap (two joint holders, GBP50,000 each).
MAX_HOLDING = 100000

# Side-investment rate for prizes that exceed the bond cap.
EXTERNAL_RATE_ANNUAL = 0.08
EXTERNAL_RATE_MONTHLY = EXTERNAL_RATE_ANNUAL / 12.0

# Pause for this many seconds whenever a single prize of >= GBP500 hits.
BIG_WIN_THRESHOLD = 500
BIG_WIN_PAUSE_SECS = 2

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
    external_pot = 0.0           # value of side investment (compounds monthly)
    external_principal = 0       # cumulative GBP redirected to side pot
    total_winnings = 0
    total_bought = 0
    big_wins = []

    prob = 1.0 / ODDS_DENOM

    if verbose:
        print("")
        print("Starting holding:    GBP{:,}".format(active))
        print("Monthly purchase:    GBP{:,}".format(monthly_buy))
        print("Holding cap:         GBP{:,} (joint)".format(MAX_HOLDING))
        print("Side-pot rate:       {:.0%} per annum, monthly compounding".format(
            EXTERNAL_RATE_ANNUAL))
        print("Simulating {} monthly draws".format(months))
        print("-" * 72)

    for month in range(1, months + 1):
        # 1. Graduate the oldest pending tranche into the active pool.
        active += pending.popleft()

        # 2. Apply this month's growth to the existing side-pot balance
        #    BEFORE adding any new contributions for this month.
        external_pot *= (1.0 + EXTERNAL_RATE_MONTHLY)

        month_to_side = 0  # GBP added to side pot this month

        # 3. Run this month's draw on the active bonds.
        winners = sample_winners(active, prob)
        month_win = 0
        for _ in range(winners):
            value = draw_prize_value()
            month_win += value
            if value >= 1000:
                big_wins.append((month, value))
            if value >= BIG_WIN_THRESHOLD:
                if verbose:
                    print("  *** Month {}: prize of GBP{:,}! ***".format(month, value))
                    time.sleep(BIG_WIN_PAUSE_SECS)
        total_winnings += month_win

        # 4. Reinvest winnings into active up to the cap; anything that
        #    doesn't fit goes into the external 8%/yr side pot.
        held = active + sum(pending)
        room = MAX_HOLDING - held
        if month_win <= room:
            active += month_win
        else:
            if room > 0:
                active += room
            spilled = month_win - max(0, room)
            external_pot += spilled
            external_principal += spilled
            month_to_side += spilled

        # 5. Try to buy this month's monthly contribution into the
        #    pending pipeline. If the cap is full (or partly so), the
        #    leftover keeps flowing -- it just goes into the side pot
        #    instead.
        held = active + sum(pending)
        room = max(0, MAX_HOLDING - held)
        bought = min(monthly_buy, room)
        unbuilt = monthly_buy - bought
        if unbuilt > 0:
            external_pot += unbuilt
            external_principal += unbuilt
            month_to_side += unbuilt
        total_bought += bought
        pending.append(bought)

        if verbose and (month_win > 0 or bought > 0 or month_to_side > 0):
            print(
                "M{:>3}: won GBP{:>7,}  bought GBP{:>5,}  "
                "to side GBP{:>5,}  "
                "active GBP{:>7,}  pending GBP{:>5,}  "
                "side GBP{:>10,.0f}".format(
                    month, month_win, bought, month_to_side,
                    active, sum(pending), external_pot,
                )
            )

    final_total_bonds = active + sum(pending)
    external_growth = external_pot - external_principal
    grand_total = final_total_bonds + external_pot

    if verbose:
        print("-" * 72)
        print("Final active bonds:           GBP{:,}".format(active))
        print("Pending (not yet eligible):   GBP{:,}".format(sum(pending)))
        print("Total bond holding:           GBP{:,}".format(final_total_bonds))
        print("Total bought from monthly:    GBP{:,}".format(total_bought))
        print("Total winnings:               GBP{:,}".format(total_winnings))
        print("")
        print("Side investment ({:.0%}/yr):".format(EXTERNAL_RATE_ANNUAL))
        print("  Principal added:            GBP{:,}".format(external_principal))
        print("  Cumulative growth:          GBP{:,.2f}".format(external_growth))
        print("  Current value:              GBP{:,.2f}".format(external_pot))
        print("")
        print("Grand total (bonds + side):   GBP{:,.2f}".format(grand_total))
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
        "final_total_bonds": final_total_bonds,
        "external_principal": external_principal,
        "external_growth": external_growth,
        "external_value": external_pot,
        "total_winnings": total_winnings,
        "total_bought": total_bought,
        "big_wins": big_wins,
        "grand_total": grand_total,
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
    print("UK Premium Bond Draw Simulator (joint holding)")
    print("==============================================")
    print("Odds: 1 in {:,} per GBP1 bond per month".format(ODDS_DENOM))
    print("Joint holding cap: GBP{:,} (two holders)".format(MAX_HOLDING))
    print("Side investment for prizes over cap: {:.0%} per annum".format(
        EXTERNAL_RATE_ANNUAL))

    last_params = None
    while True:
        if last_params is not None and _ask_yes_no(
            "Repeat the previous scenario with the same settings? (y/n): "
        ):
            bonds, months, monthly_buy = last_params
            print("Reusing: bonds GBP{:,}, {} months, monthly GBP{:,}".format(
                bonds, months, monthly_buy))
        else:
            bonds = _ask_int(
                "How many bonds do you hold? (GBP1 each, 25-{}): ".format(MAX_HOLDING),
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
            last_params = (bonds, months, monthly_buy)

        simulate(bonds, months, monthly_buy=monthly_buy)

        print("")
        if not _ask_yes_no("Run another simulation? (y/n): "):
            print("Goodbye.")
            break
        print("")


if __name__ == "__main__":
    main()
