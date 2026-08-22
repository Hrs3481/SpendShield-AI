import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.forecasting import (
    DailySpend,
    calculate_spending_velocity,
    detect_transaction_anomaly,
    forecast_month_end_spend,
)


class TestForecasting(unittest.TestCase):
    def test_matches_spec_direction(self):
        # spec section 10: current spend 8200, 11 days left, target 11000 -> HIGH risk overspend
        daily = [DailySpend(date(2026, 8, d), 400) for d in range(15, 20)]
        result = forecast_month_end_spend(
            daily_spend=daily, days_remaining=11, monthly_budget=11000, spent_so_far=8200,
        )
        self.assertGreater(result.predicted_total_month_spend, 11000)
        self.assertEqual(result.risk, "HIGH")
        self.assertGreater(result.projected_overspend, 0)

    def test_no_history_returns_zero_remaining(self):
        result = forecast_month_end_spend([], days_remaining=10, monthly_budget=10000, spent_so_far=2000)
        self.assertEqual(result.predicted_remaining_spend, 0.0)
        self.assertEqual(result.predicted_total_month_spend, 2000)

    def test_on_budget_is_low_risk(self):
        daily = [DailySpend(date(2026, 8, d), 100) for d in range(1, 6)]
        result = forecast_month_end_spend(daily, days_remaining=25, monthly_budget=15000, spent_so_far=1000)
        self.assertEqual(result.risk, "LOW")


class TestVelocity(unittest.TestCase):
    def test_ahead_of_pace(self):
        v = calculate_spending_velocity(
            spent_so_far=9000, elapsed_days=15, monthly_budget=15000, total_days_in_month=30
        )
        # current = 600/day, required = 500/day -> +20% -> AHEAD
        self.assertEqual(v.label, "AHEAD")
        self.assertGreater(v.deviation_pct, 10)

    def test_behind_pace_is_good(self):
        v = calculate_spending_velocity(
            spent_so_far=3000, elapsed_days=15, monthly_budget=15000, total_days_in_month=30
        )
        self.assertEqual(v.label, "BEHIND")

    def test_zero_days_does_not_crash(self):
        v = calculate_spending_velocity(
            spent_so_far=0, elapsed_days=0, monthly_budget=15000, total_days_in_month=30
        )
        self.assertEqual(v.current_velocity, 0.0)


class TestAnomalyDetection(unittest.TestCase):
    def test_flags_large_outlier(self):
        history = [200, 220, 180, 210, 195]
        flag = detect_transaction_anomaly(1500, history)
        self.assertTrue(flag.is_anomalous)

    def test_does_not_flag_normal_purchase(self):
        history = [200, 220, 180, 210, 195]
        flag = detect_transaction_anomaly(215, history)
        self.assertFalse(flag.is_anomalous)

    def test_insufficient_history_never_flags(self):
        flag = detect_transaction_anomaly(5000, [100, 100])
        self.assertFalse(flag.is_anomalous)


if __name__ == "__main__":
    unittest.main(verbosity=2)
