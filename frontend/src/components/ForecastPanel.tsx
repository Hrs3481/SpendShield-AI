import { formatINR } from "../lib/api";
import type { Forecast, Velocity } from "../lib/types";

const RISK_STYLE: Record<Forecast["risk"], string> = {
  LOW: "text-tulsi-500",
  MEDIUM: "text-marigold-500",
  HIGH: "text-sindoor-500",
};

const VELOCITY_LABEL: Record<Velocity["label"], string> = {
  AHEAD: "Spending faster than planned",
  BEHIND: "Spending slower than planned",
  ON_PACE: "Right on pace",
};

const VELOCITY_STYLE: Record<Velocity["label"], string> = {
  AHEAD: "text-sindoor-500",
  BEHIND: "text-tulsi-500",
  ON_PACE: "text-paper/70",
};

interface Props {
  forecast: Forecast;
  velocity: Velocity;
}

export default function ForecastPanel({ forecast, velocity }: Props) {
  return (
    <div className="bg-ink-800 rounded-xl p-5 mb-6">
      <p className="text-sm text-paper/60 mb-3">End-of-month projection</p>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <p className="text-xs text-paper/50 mb-1">Predicted total spend</p>
          <p className="font-mono text-lg font-medium text-paper">
            {formatINR(forecast.predicted_total_month_spend)}
          </p>
          <p className="text-xs text-paper/40 mt-0.5">
            against {formatINR(forecast.target_budget)} budget
          </p>
        </div>
        <div>
          <p className="text-xs text-paper/50 mb-1">Projected overspend</p>
          <p className={`font-mono text-lg font-medium ${RISK_STYLE[forecast.risk]}`}>
            {forecast.projected_overspend > 0 ? formatINR(forecast.projected_overspend) : "None"}
          </p>
          <p className="text-xs text-paper/40 mt-0.5">{forecast.risk.toLowerCase()} risk</p>
        </div>
      </div>

      <div className="border-t border-ink-700 pt-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <p className={`text-sm ${VELOCITY_STYLE[velocity.label]}`}>
            {VELOCITY_LABEL[velocity.label]}
          </p>
          <p className="font-mono text-sm text-paper/80">
            {formatINR(velocity.current_velocity)}/day vs {formatINR(velocity.required_velocity)}/day target
          </p>
        </div>
      </div>

      <p className="text-xs text-paper/30 mt-3">
        Projection from {forecast.method.replace(/_/g, " ")}. A prediction, not a promise.
      </p>
    </div>
  );
}
