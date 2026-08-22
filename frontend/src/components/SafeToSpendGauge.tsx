import { formatINR } from "../lib/api";
import type { SafeToSpend } from "../lib/types";

const RADIUS = 76;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const RISK_COLOR: Record<SafeToSpend["overspend_risk"], string> = {
  LOW: "#4CAF7D",
  MEDIUM: "#F5A623",
  HIGH: "#D94A4A",
};

interface Props {
  data: SafeToSpend;
}

export default function SafeToSpendGauge({ data }: Props) {
  // The ring tracks financial_health_score, a genuine 0-100 metric from the engine.
  // It previously scaled safe-to-spend against a hard-coded ₹500 "reference ceiling",
  // so the same rupee amount filled the ring differently for different budgets and
  // the arc meant nothing you could point at.
  const fillRatio = Math.min(Math.max(data.financial_health_score / 100, 0), 1);
  const dashOffset = CIRCUMFERENCE * (1 - fillRatio);
  const color = RISK_COLOR[data.overspend_risk];

  return (
    <div className="flex items-center gap-6 flex-wrap">
      <svg
        width={180}
        height={180}
        viewBox="0 0 180 180"
        role="img"
        aria-label={
          `Safe to spend today: ${Math.round(data.safe_to_spend_today)} rupees. ` +
          `Financial health ${data.financial_health_score} out of 100. ` +
          `Overspend risk ${data.overspend_risk.toLowerCase()}.`
        }
      >
        <circle cx={90} cy={90} r={RADIUS} fill="none" stroke="#272B54" strokeWidth={12} />
        <circle
          cx={90} cy={90} r={RADIUS} fill="none" stroke={color} strokeWidth={12}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          transform="rotate(-90 90 90)"
        />
        <text
          x={90} y={82} textAnchor="middle" fontFamily="IBM Plex Mono, monospace"
          fontSize={data.safe_to_spend_today >= 10000 ? 24 : 30} fontWeight={500} fill="#F1EEE6"
        >
          {formatINR(data.safe_to_spend_today)}
        </text>
        <text x={90} y={104} textAnchor="middle" fontSize={11} fill="#9C9AB0">
          safe to spend today
        </text>
      </svg>

      <div>
        <p className="text-sm text-paper/60">Overspend risk</p>
        <p className="text-lg font-display font-semibold" style={{ color }}>
          {data.overspend_risk}
        </p>
        <p className="text-sm text-paper/60 mt-3">Financial health</p>
        <p className="text-lg font-display font-semibold text-paper">
          {data.financial_health_score}/100
        </p>
        <p className="text-xs text-paper/40 mt-1">shown by the ring</p>
      </div>
    </div>
  );
}
