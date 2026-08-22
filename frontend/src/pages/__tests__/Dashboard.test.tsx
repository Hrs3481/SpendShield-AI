/**
 * The dashboard's job when a user has no budget is the thing most worth pinning:
 * every figure is zero, and a zeroed gauge is indistinguishable from "you're
 * broke". It must ask for the missing input instead.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "../Dashboard";
import { AuthProvider } from "../../context/AuthContext";
import { api } from "../../lib/api";
import type { SafeToSpend } from "../../lib/types";

const withBudget: SafeToSpend = {
  safe_to_spend_today: 280,
  remaining_budget: 5631,
  days_remaining: 10,
  recommended_daily_discretionary: 280.22,
  overspend_risk: "LOW",
  financial_health_score: 61,
  explanation_factors: ["Remaining monthly budget is ₹5631.", "10 day(s) remain."],
  has_budget: true,
};

const withoutBudget: SafeToSpend = {
  ...withBudget,
  safe_to_spend_today: 0,
  remaining_budget: 0,
  financial_health_score: 0,
  explanation_factors: [],
  has_budget: false,
};

function stubApi(sts: SafeToSpend) {
  vi.spyOn(api, "getSafeToSpend").mockResolvedValue(sts);
  vi.spyOn(api, "listTransactions").mockResolvedValue([]);
  vi.spyOn(api, "getForecast").mockResolvedValue({
    predicted_total_month_spend: 16278, predicted_remaining_spend: 3900,
    target_budget: 18000, projected_overspend: 0, risk: "LOW",
    method: "exponential_smoothing_v1",
  });
  vi.spyOn(api, "getVelocity").mockResolvedValue({
    current_velocity: 562, required_velocity: 516, deviation_pct: 8.9, label: "ON_PACE",
  });
  vi.spyOn(api, "getCategories").mockResolvedValue([]);
  vi.spyOn(api, "getCurrentBudget").mockResolvedValue({
    id: "1", month: 8, year: 2026, total_income: 18000, savings_target: 2000, rules: [],
  });
  vi.spyOn(api, "me").mockResolvedValue({
    id: "1", email: "a@b.com", full_name: null, is_demo: false,
  });
}

function renderDashboard() {
  return render(
    <AuthProvider>
      <Dashboard />
    </AuthProvider>,
  );
}

describe("Dashboard", () => {
  beforeEach(() => localStorage.clear());

  it("asks for a budget instead of showing a gauge full of zeros", async () => {
    stubApi(withoutBudget);
    renderDashboard();

    expect(await screen.findByText(/set a budget to unlock/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save budget/i })).toBeInTheDocument();
    // No misleading ₹0 headline.
    expect(screen.queryByText("safe to spend today")).not.toBeInTheDocument();
  });

  it("shows the gauge and the explanation once a budget exists", async () => {
    stubApi(withBudget);
    renderDashboard();

    expect(await screen.findByText("safe to spend today")).toBeInTheDocument();
    expect(screen.getByText("₹280")).toBeInTheDocument();
    expect(screen.getByText(/why this number/i)).toBeInTheDocument();
    expect(screen.getByText(/Remaining monthly budget is ₹5631/)).toBeInTheDocument();
    expect(screen.queryByText(/set a budget to unlock/i)).not.toBeInTheDocument();
  });

  it("treats a missing budget as an expected state, not a page failure", async () => {
    // getCurrentBudget 404s for a new user; that must not blank the dashboard.
    stubApi(withBudget);
    vi.spyOn(api, "getCurrentBudget").mockRejectedValue(
      Object.assign(new Error("No budget set for this month yet."), { status: 404 }),
    );
    renderDashboard();

    expect(await screen.findByText("safe to spend today")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an actionable error with a retry when the API is unreachable", async () => {
    stubApi(withBudget);
    vi.spyOn(api, "getSafeToSpend").mockRejectedValue(
      Object.assign(new Error("Couldn't reach the SpendShield API. Is the backend running?"), {
        name: "ApiError", status: 0,
      }),
    );
    renderDashboard();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/backend running/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("marks a demo account so the data is never mistaken for real", async () => {
    stubApi(withBudget);
    vi.spyOn(api, "me").mockResolvedValue({
      id: "1", email: "demo-x@spendshield.local", full_name: "Demo User", is_demo: true,
    });
    renderDashboard();
    await waitFor(() => expect(screen.getByText(/demo data/i)).toBeInTheDocument());
  });
});
