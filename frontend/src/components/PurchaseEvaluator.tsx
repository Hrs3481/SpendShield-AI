import { useState } from "react";
import { ApiError, api, formatINR } from "../lib/api";
import type { PurchaseEvaluation } from "../lib/types";

const CATEGORIES = [
  "shopping", "food_delivery", "entertainment", "transport", "coffee_snacks", "groceries",
];

const RECOMMENDATION_STYLE: Record<PurchaseEvaluation["recommendation"], string> = {
  BUY_NOW: "bg-tulsi-500/20 text-tulsi-500",
  WAIT: "bg-marigold-500/20 text-marigold-500",
  SKIP: "bg-sindoor-500/20 text-sindoor-500",
};

const RECOMMENDATION_LABEL: Record<PurchaseEvaluation["recommendation"], string> = {
  BUY_NOW: "Go ahead",
  WAIT: "Maybe wait",
  SKIP: "Better to skip",
};

// Copy is deliberately non-judgemental; the engine returns a level, the UI
// chooses the tone (see services/intervention.py).
const INTERVENTION_COPY: Record<number, string> = {
  0: "",
  1: "Worth a quick look before you buy.",
  2: "This one's worth a second thought.",
  3: "This would take a real bite out of what's left.",
  4: "Sleeping on this one is probably the better call.",
  5: "There's nothing left in this month's budget to cover it.",
};

export default function PurchaseEvaluator() {
  const [price, setPrice] = useState("2499");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [result, setResult] = useState<PurchaseEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleEvaluate() {
    const parsed = Number(price);
    if (!price || Number.isNaN(parsed) || parsed <= 0) {
      setError("Enter a price greater than 0.");
      setResult(null);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      setResult(await api.evaluatePurchase(parsed, category));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't evaluate this purchase. Try again.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const field =
    "bg-ink-900 rounded-lg px-3 py-2 text-sm text-paper outline-none border border-ink-700 focus:border-marigold-500";

  return (
    <div className="bg-ink-800 rounded-xl p-5">
      <p className="text-sm text-paper/60 mb-3">Should I buy this?</p>

      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="number" min="1" value={price}
          onChange={(e) => setPrice(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleEvaluate()}
          placeholder="Price ₹" className={`${field} w-32`}
          aria-label="Price in rupees"
        />
        <select
          value={category} onChange={(e) => setCategory(e.target.value)}
          className={field} aria-label="Category"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
        <button
          onClick={handleEvaluate} disabled={loading}
          className="bg-marigold-500 hover:bg-marigold-600 disabled:opacity-50 text-ink-950 font-medium text-sm rounded-lg px-4 py-2"
        >
          {loading ? "Checking…" : "Check"}
        </button>
      </div>

      {error && <p role="alert" className="text-sindoor-500 text-sm mt-2">{error}</p>}

      {result && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`text-xs font-medium rounded-full px-3 py-1 ${RECOMMENDATION_STYLE[result.recommendation]}`}>
              {RECOMMENDATION_LABEL[result.recommendation]}
            </span>
            <span className="font-mono text-sm text-paper">
              Affordability {result.affordability_score}/100
            </span>
            <span className="font-mono text-xs text-paper/50">
              {result.budget_impact_pct}% of what's left
            </span>
          </div>

          <p className="text-sm text-paper/70">{result.reason}</p>

          {INTERVENTION_COPY[result.intervention_level] && (
            <p className="text-sm text-marigold-400 mt-2">
              {INTERVENTION_COPY[result.intervention_level]}
            </p>
          )}

          {result.impulse_reasons.length > 0 && (
            <div className="mt-3 border-t border-ink-700 pt-3">
              <p className="text-xs text-paper/50 mb-1.5">
                Impulse signals — {result.impulse_score}/100 ({result.impulse_label.toLowerCase()})
              </p>
              <ul className="space-y-1">
                {result.impulse_reasons.map((reason, i) => (
                  <li key={i} className="text-xs text-paper/60 flex gap-2">
                    <span className="text-marigold-500">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-paper/30 mt-3">
            {formatINR(Number(price))} in {category.replace(/_/g, " ")} · it's your call, always.
          </p>
        </div>
      )}
    </div>
  );
}
