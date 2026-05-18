"""
UK Premium Bond Draw Simulator (Pydroid friendly, stdlib only).
"""

import random
import math
import time
from collections import deque

# --- UK Premium Bond parameters -------------------------------------------

ODDS_DENOM = 22000

# Per-person NS&I holding cap. Joint pots scale with the number of holders.
PER_PERSON_CAP = 50000

EXTERNAL_RATE_ANNUAL = 0.08
EXTERNAL_RATE_MONTHLY = EXTERNAL_RATE_ANNUAL / 12.0

BIG_WIN_THRESHOLD = 500

# Luck presets -> a 0..100 score. 50 = neutral.
LUCK_PRESETS = [
    ("Very Unlucky", 10),
    ("Unlucky",      30),
    ("Average",      50),
    ("Lucky",        70),
    ("Very Lucky",   90),
]

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

# Prizes listed largest first, so small cumulative indexes => big prizes.
_CUMULATIVE = []
_running = 0
for _value, _count in PRIZES:
    _running += _count
    _CUMULATIVE.append((_running, _value))


def luck_multipliers(luck_score):
    """Turn a 0..100 luck score into a (freq_mult, skew_exp) pair.

    freq_mult scales the per-bond win probability (1.0 = unchanged).
    skew_exp powers the uniform [0,1) draw used to pick a prize. With
    prizes listed largest-first, exp > 1 biases samples toward small
    indices (= bigger prizes), exp < 1 toward small prizes.
    """
    # Centered exponential mapping: score 50 -> 1.0, 0 -> 0.5, 100 -> 2.0.
    factor = 2.0 ** ((luck_score - 50) / 50.0)
    return factor, factor


def draw_prize_value(skew_exp=1.0):
    u = random.random()
    if skew_exp != 1.0:
        u = u ** skew_exp
    r = int(u * TOTAL_PRIZES) + 1
    if r > TOTAL_PRIZES:
        r = TOTAL_PRIZES
    for cum, value in _CUMULATIVE:
        if r <= cum:
            return value
    return 0


def sample_winners(num_bonds, prob):
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


def simulate(starting_bonds, months, monthly_buy=0, cap=PER_PERSON_CAP,
             people=1, big_win_pause=2, luck_score=50, verbose=True):
    active = min(starting_bonds, cap)
    pending = deque([0, 0])
    external_pot = 0.0
    external_principal = 0
    total_winnings = 0
    total_bought = 0
    big_wins = []

    freq_mult, skew_exp = luck_multipliers(luck_score)
    base_prob = 1.0 / ODDS_DENOM
    prob = min(0.99, base_prob * freq_mult)

    if verbose:
        print("")
        print("People sharing pot:  {}".format(people))
        print("Starting holding:    GBP{:,}".format(active))
        print("Monthly purchase:    GBP{:,}".format(monthly_buy))
        print("Holding cap:         GBP{:,} ({} x GBP{:,})".format(
            cap, people, PER_PERSON_CAP))
        print("Side-pot rate:       {:.0%} per annum, monthly compounding".format(
            EXTERNAL_RATE_ANNUAL))
        print("Big-win pause:       {}s (for prizes >= GBP{:,})".format(
            big_win_pause, BIG_WIN_THRESHOLD))
        print("Luck score:          {} (freq x{:.2f}, prize skew x{:.2f})".format(
            luck_score, freq_mult, skew_exp))
        print("Effective odds:      1 in {:,.0f} per GBP1 per month".format(1.0 / prob))
        print("Simulating {} monthly draws".format(months))
        print("-" * 72)

    for month in range(1, months + 1):
        active += pending.popleft()
        external_pot *= (1.0 + EXTERNAL_RATE_MONTHLY)
        month_to_side = 0

        winners = sample_winners(active, prob)
        month_win = 0
        for _ in range(winners):
            value = draw_prize_value(skew_exp)
            month_win += value
            if value >= 1000:
                big_wins.append((month, value))
            if value >= BIG_WIN_THRESHOLD:
                if verbose:
                    print("  *** Month {}: prize of GBP{:,}! ***".format(month, value))
                    if big_win_pause > 0:
                        time.sleep(big_win_pause)
        total_winnings += month_win

        held = active + sum(pending)
        room = cap - held
        if month_win <= room:
            active += month_win
        else:
            if room > 0:
                active += room
            spilled = month_win - max(0, room)
            external_pot += spilled
            external_principal += spilled
            month_to_side += spilled

        held = active + sum(pending)
        room = max(0, cap - held)
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


def _ask_choice(prompt, choices):
    options = "/".join(str(c) for c in choices)
    while True:
        raw = input("{} ({}): ".format(prompt, options)).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter one of: {}".format(options))
            continue
        if value not in choices:
            print("Please enter one of: {}".format(options))
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


def _ask_luck():
    print("Luck level:")
    for i, (name, score) in enumerate(LUCK_PRESETS, start=1):
        print("  {}) {} (score {})".format(i, name, score))
    choice = _ask_choice("Pick a luck level",
                         list(range(1, len(LUCK_PRESETS) + 1)))
    name, score = LUCK_PRESETS[choice - 1]
    return name, score


def main():
    print("UK Premium Bond Draw Simulator")
    print("==============================")
    print("Odds: 1 in {:,} per GBP1 bond per month (at neutral luck)".format(ODDS_DENOM))
    print("Per-person holding cap: GBP{:,}".format(PER_PERSON_CAP))
    print("Side investment for prizes over cap: {:.0%} per annum".format(
        EXTERNAL_RATE_ANNUAL))

    last_params = None
    while True:
        if last_params is not None and _ask_yes_no(
            "Repeat the previous scenario with the same settings? (y/n): "
        ):
            (people, bonds, months, monthly_buy,
             big_win_pause, luck_name, luck_score) = last_params
            cap = PER_PERSON_CAP * people
            print("Reusing: {} people (cap GBP{:,}), bonds GBP{:,}, "
                  "{} months, monthly GBP{:,}, pause {}s, luck {}".format(
                      people, cap, bonds, months, monthly_buy,
                      big_win_pause, luck_name))
        else:
            people = _ask_int(
                "How many people own the bonds? (1 or more): ",
                minimum=1,
                maximum=20,
            )
            cap = PER_PERSON_CAP * people
            print("Joint holding cap: GBP{:,}".format(cap))

            bonds = _ask_int(
                "How many bonds do you hold? (GBP1 each, 25-{}): ".format(cap),
                minimum=25,
                maximum=cap,
            )
            months = _ask_int(
                "How many monthly draws to simulate? ",
                minimum=1,
            )
            monthly_buy = _ask_int(
                "How much to buy each month? (GBP, 0 for none): ",
                minimum=0,
                maximum=cap,
            )
            big_win_pause = _ask_choice(
                "Pause length on a big win (GBP{}+)".format(BIG_WIN_THRESHOLD),
                [0, 1, 2],
            )
            luck_name, luck_score = _ask_luck()
            last_params = (people, bonds, months, monthly_buy,
                           big_win_pause, luck_name, luck_score)

        simulate(
            bonds, months,
            monthly_buy=monthly_buy,
            cap=cap,
            people=people,
            big_win_pause=big_win_pause,
            luck_score=luck_score,
        )

        print("")
        if not _ask_yes_no("Run another simulation? (y/n): "):
            print("Goodbye.")
            break
        print("")


if __name__ == "__main__":
    main()
