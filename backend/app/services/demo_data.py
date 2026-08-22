"""
Synthetic demo data generator.

Produces a plausible month of spending for an Indian student/PG resident so a
fresh deployment can be explored without manual data entry. Deterministic given
a seed, so a demo always looks the same when you show it to someone.

Nothing here touches the financial engines — it only creates input rows. The
numbers on the dashboard are still computed by the same tested code that runs
on real data.
"""
import calendar
import random
from dataclasses import dataclass
from datetime import date, timedelta

MONTHLY_INCOME = 18000.0
SAVINGS_TARGET = 2000.0

CATEGORY_RULES: dict[str, float] = {
    "rent": 6500.0,
    "groceries": 2200.0,
    "food_delivery": 2000.0,
    "transport": 1200.0,
    "shopping": 1800.0,
    "entertainment": 900.0,
    "coffee_snacks": 700.0,
    "utilities": 800.0,
}


@dataclass
class DemoTransaction:
    amount: float
    merchant: str
    category: str
    transaction_date: date
    payment_method: str
    is_essential: bool
    is_recurring: bool
    notes: str | None = None


# (category, merchants, amount range, essential, avg times per month)
_PATTERNS: list[tuple[str, list[str], tuple[int, int], bool, int]] = [
    ("food_delivery", ["Swiggy", "Zomato", "Behrouz Biryani"], (140, 380), False, 7),
    ("coffee_snacks", ["Chaayos", "Campus Canteen", "Blue Tokai"], (40, 160), False, 8),
    ("groceries",     ["BigBasket", "Local Kirana", "DMart"],     (180, 700), True,  4),
    ("transport",     ["Uber", "Rapido", "Metro Card"],           (30, 220), True,  6),
    ("shopping",      ["Myntra", "Amazon", "Decathlon"],          (350, 1400), False, 2),
    ("entertainment", ["BookMyShow", "Spotify Top-up", "PVR"],    (150, 550), False, 2),
]

# Fixed costs. These carry is_recurring=True, which is what lets the
# safe-to-spend engine reserve next month's rent as an upcoming obligation.
_RECURRING: list[tuple[str, str, float, int, bool]] = [
    ("rent", "PG Rent - Sharma Residency", 6500.0, 3, True),
    ("utilities", "Electricity + Wifi", 780.0, 5, True),
    ("entertainment", "Netflix Mobile", 199.0, 8, False),
]


def generate_transactions(today: date, seed: int = 20260822) -> list[DemoTransaction]:
    """
    Two months of history: last month in full (so recurring costs have a template
    to project from) and the current month up to `today`.
    """
    rng = random.Random(seed)
    txns: list[DemoTransaction] = []

    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    for period_start, period_end in (
        (last_month_start, last_month_end),
        (this_month_start, today),
    ):
        span_days = (period_end - period_start).days + 1
        days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]
        # How much of this month the period covers: 1.0 for a full past month,
        # a fraction for the current month up to today.
        month_fraction = span_days / days_in_month

        for category, merchant, amount, day_of_month, essential in _RECURRING:
            when = period_start.replace(day=min(day_of_month, span_days))
            if when > period_end:
                continue
            txns.append(
                DemoTransaction(
                    amount=amount,
                    merchant=merchant,
                    category=category,
                    transaction_date=when,
                    payment_method="upi",
                    is_essential=essential,
                    is_recurring=True,
                )
            )

        for category, merchants, (low, high), essential, per_month in _PATTERNS:
            count = max(1, round(per_month * min(month_fraction, 1.0)))
            for _ in range(count):
                offset = rng.randint(0, span_days - 1)
                txns.append(
                    DemoTransaction(
                        amount=float(rng.randint(low, high)),
                        merchant=rng.choice(merchants),
                        category=category,
                        transaction_date=period_start + timedelta(days=offset),
                        payment_method=rng.choice(["upi", "upi", "upi", "card", "cash"]),
                        is_essential=essential,
                        is_recurring=False,
                    )
                )

    txns.sort(key=lambda t: t.transaction_date)
    return txns
