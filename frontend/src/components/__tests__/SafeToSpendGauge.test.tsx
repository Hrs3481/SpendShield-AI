import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SafeToSpendGauge from "../SafeToSpendGauge";
import type { SafeToSpend } from "../../lib/types";

const base: SafeToSpend = {
  safe_to_spend_today: 280,
  remaining_budget: 5631,
  days_remaining: 10,
  recommended_daily_discretionary: 280.22,
  overspend_risk: "LOW",
  financial_health_score: 61,
  explanation_factors: [],
  has_budget: true,
};

function ringOffset(container: HTMLElement): number {
  // Second circle is the progress arc; the first is the track.
  const arc = container.querySelectorAll("circle")[1];
  return Number(arc.getAttribute("stroke-dashoffset"));
}

describe("SafeToSpendGauge", () => {
  it("shows the amount with Indian formatting", () => {
    render(<SafeToSpendGauge data={{ ...base, safe_to_spend_today: 120000 }} />);
    expect(screen.getByText("₹1,20,000")).toBeInTheDocument();
  });

  it("fills the ring from financial_health_score, not from the rupee amount", () => {
    // The ring used to scale safe-to-spend against a hard-coded ₹500 ceiling,
    // so the arc meant nothing you could point at. Same health score must give
    // the same arc regardless of the amount.
    const { container: a } = render(
      <SafeToSpendGauge data={{ ...base, safe_to_spend_today: 50 }} />,
    );
    const { container: b } = render(
      <SafeToSpendGauge data={{ ...base, safe_to_spend_today: 5000 }} />,
    );
    expect(ringOffset(a)).toBeCloseTo(ringOffset(b), 5);
  });

  it("fills more of the ring for a healthier score", () => {
    const { container: low } = render(
      <SafeToSpendGauge data={{ ...base, financial_health_score: 10 }} />,
    );
    const { container: high } = render(
      <SafeToSpendGauge data={{ ...base, financial_health_score: 90 }} />,
    );
    // Larger offset = less of the ring drawn.
    expect(ringOffset(low)).toBeGreaterThan(ringOffset(high));
  });

  it("colours by risk level", () => {
    const { container } = render(<SafeToSpendGauge data={{ ...base, overspend_risk: "HIGH" }} />);
    expect(container.querySelectorAll("circle")[1].getAttribute("stroke")).toBe("#D94A4A");
  });

  it("exposes the numbers to screen readers", () => {
    render(<SafeToSpendGauge data={base} />);
    const label = screen.getByRole("img").getAttribute("aria-label") ?? "";
    expect(label).toMatch(/280 rupees/);
    expect(label).toMatch(/61 out of 100/);
    expect(label).toMatch(/low/);
  });
});
