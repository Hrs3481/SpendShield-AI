import os
import sys
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.impulse_score import ImpulseInput
from app.services.impulse_score import evaluate as evaluate_impulse
from app.services.intervention import InterventionInput, InterventionLevel, decide
from app.services.safe_to_spend import (
    SafeToSpendInput,
    calculate_financial_runway,
    calculate_safe_to_spend,
    evaluate_purchase,
)


class TestSafeToSpend(unittest.TestCase):
    def test_matches_spec_scenario_structure(self):
        # Uses the same inputs as the product spec's worked example (section 4).
        # Note: the spec's illustrative ₹287 figure isn't algebraically derivable
        # from its own stated inputs (5740 - 2100 - 1900 = 1740, not ~3444), so this
        # test asserts the engine's actual, internally-consistent arithmetic instead
        # of the marketing copy's number.
        inp = SafeToSpendInput(
            monthly_budget=15000,
            spent_so_far=9260,
            upcoming_obligations=2100,
            predicted_essential_spend=1900,
            today=date(2026, 8, 20),
            month_start=date(2026, 8, 1),
            month_end=date(2026, 8, 31),
            savings_target=0,
        )
        result = calculate_safe_to_spend(inp)
        self.assertEqual(result.remaining_budget, 5740)
        self.assertEqual(result.days_remaining, 12)
        # free pool = 5740 - 2100 - 1900 = 1740 -> 1740/12 = 145/day
        self.assertAlmostEqual(result.safe_to_spend_today, 145, delta=1)
        self.assertIn(result.overspend_risk, {"LOW", "MEDIUM", "HIGH"})
        self.assertTrue(0 <= result.financial_health_score <= 100)
        self.assertTrue(len(result.explanation_factors) >= 3)

    def test_zero_days_remaining_does_not_crash(self):
        inp = SafeToSpendInput(
            monthly_budget=10000, spent_so_far=9000, upcoming_obligations=0,
            predicted_essential_spend=0, today=date(2026, 8, 31),
            month_start=date(2026, 8, 1), month_end=date(2026, 8, 31),
        )
        result = calculate_safe_to_spend(inp)
        self.assertEqual(result.days_remaining, 1)
        self.assertGreaterEqual(result.safe_to_spend_today, 0)

    def test_overbudget_triggers_high_risk(self):
        inp = SafeToSpendInput(
            monthly_budget=10000, spent_so_far=11000, upcoming_obligations=500,
            predicted_essential_spend=500, today=date(2026, 8, 15),
            month_start=date(2026, 8, 1), month_end=date(2026, 8, 31),
        )
        result = calculate_safe_to_spend(inp)
        self.assertEqual(result.safe_to_spend_today, 0)
        self.assertEqual(result.overspend_risk, "HIGH")

    def test_savings_target_reduces_free_pool(self):
        base = dict(  # noqa: C408
            monthly_budget=15000, spent_so_far=5000, upcoming_obligations=0,
            predicted_essential_spend=0, today=date(2026, 8, 5),
            month_start=date(2026, 8, 1), month_end=date(2026, 8, 31),
        )
        no_savings = calculate_safe_to_spend(SafeToSpendInput(**base, savings_target=0))
        with_savings = calculate_safe_to_spend(SafeToSpendInput(**base, savings_target=2000))
        self.assertLess(with_savings.safe_to_spend_today, no_savings.safe_to_spend_today)


class TestRunway(unittest.TestCase):
    def test_basic_runway(self):
        r = calculate_financial_runway(4200, 280, target_runway_days=21)
        self.assertAlmostEqual(r.estimated_runway_days, 15.0, delta=0.1)

    def test_zero_spend_is_infinite_runway(self):
        r = calculate_financial_runway(4200, 0, target_runway_days=21)
        self.assertEqual(r.estimated_runway_days, float("inf"))


class TestPurchaseEvaluation(unittest.TestCase):
    def test_small_purchase_buy_now(self):
        r = evaluate_purchase(price=200, remaining_discretionary_budget=5000, days_remaining=10,
                               recent_category_spend=500)
        self.assertEqual(r.recommendation, "BUY_NOW")

    def test_large_purchase_recommends_wait(self):
        r = evaluate_purchase(price=2499, remaining_discretionary_budget=6000, days_remaining=12,
                               recent_category_spend=2100)
        self.assertEqual(r.recommendation, "WAIT")
        self.assertGreaterEqual(r.budget_impact_pct, 40)

    def test_over_category_budget_skips(self):
        r = evaluate_purchase(price=1500, remaining_discretionary_budget=10000, days_remaining=10,
                               recent_category_spend=2000, category_budget=2500)
        self.assertIn(r.recommendation, {"WAIT", "SKIP"})


class TestImpulseScore(unittest.TestCase):
    def test_recurring_is_never_impulse(self):
        r = evaluate_impulse(ImpulseInput(
            amount=199, category="subscriptions_impulse", timestamp=datetime(2026, 8, 20, 23, 0),
            category_spend_this_week=0, category_weekly_budget=200,
            transactions_same_category_last_7d=1, is_recurring=True,
        ))
        self.assertEqual(r.score, 0)

    def test_late_night_shopping_high_impulse(self):
        r = evaluate_impulse(ImpulseInput(
            amount=599, category="shopping", timestamp=datetime(2026, 8, 20, 23, 30),
            category_spend_this_week=1800, category_weekly_budget=1500,
            transactions_same_category_last_7d=6, is_recurring=False,
        ))
        self.assertEqual(r.label, "HIGH")
        self.assertGreaterEqual(r.score, 65)


class TestIntervention(unittest.TestCase):
    def test_zero_budget_is_emergency(self):
        d = decide(InterventionInput(
            impulse_score=10, budget_impact_pct=5, overspend_risk="LOW", remaining_budget=0
        ))
        self.assertEqual(d.level, InterventionLevel.EMERGENCY_ALERT)

    def test_low_risk_low_impulse_is_none_or_simple(self):
        d = decide(InterventionInput(
            impulse_score=5, budget_impact_pct=2, overspend_risk="LOW", remaining_budget=5000
        ))
        self.assertIn(d.level, {InterventionLevel.NONE, InterventionLevel.SIMPLE_INSIGHT})

    def test_high_everything_is_strong_or_worse(self):
        d = decide(InterventionInput(
            impulse_score=90, budget_impact_pct=60, overspend_risk="HIGH", remaining_budget=1000
        ))
        self.assertGreaterEqual(d.level, InterventionLevel.STRONG_WAIT_RECOMMENDATION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
