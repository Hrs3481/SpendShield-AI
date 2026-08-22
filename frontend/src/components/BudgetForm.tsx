import { useState, type FormEvent } from "react";
import { ApiError, api, formatINR } from "../lib/api";
import type { Budget, BudgetRule } from "../lib/types";

const SUGGESTED_CATEGORIES = [
  "rent", "groceries", "food_delivery", "transport",
  "shopping", "entertainment", "coffee_snacks", "utilities",
];

interface Props {
  existing: Budget | null;
  onSaved: (budget: Budget) => void;
  onCancel?: () => void;
}

/**
 * Sets the monthly budget — the input every other number depends on. Without it
 * safe-to-spend, forecast and velocity are all zero, and the app had no UI (and
 * no API) for entering one.
 */
export default function BudgetForm({ existing, onSaved, onCancel }: Props) {
  const [totalIncome, setTotalIncome] = useState(existing ? String(existing.total_income) : "15000");
  const [savingsTarget, setSavingsTarget] = useState(existing ? String(existing.savings_target) : "2000");
  const [rules, setRules] = useState<BudgetRule[]>(existing?.rules ?? []);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const allocated = rules.reduce((sum, r) => sum + (Number(r.allocated_amount) || 0), 0);
  const income = Number(totalIncome) || 0;

  function updateRule(index: number, patch: Partial<BudgetRule>) {
    setRules(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (income <= 0) {
      setError("Enter your total money available this month.");
      return;
    }
    if (Number(savingsTarget) > income) {
      setError("Savings target can't be more than your total budget.");
      return;
    }
    if (allocated > income) {
      setError(`Category allocations total ${formatINR(allocated)}, more than your ${formatINR(income)} budget.`);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const saved = await api.saveBudget({
        total_income: income,
        savings_target: Number(savingsTarget) || 0,
        rules: rules.filter((r) => r.category && r.allocated_amount > 0),
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your budget. Try again.");
    } finally {
      setSaving(false);
    }
  }

  const field =
    "bg-ink-900 rounded-lg px-3 py-2 text-sm text-paper outline-none border border-ink-700 focus:border-marigold-500";

  return (
    <form onSubmit={handleSubmit} className="bg-ink-800 rounded-xl p-5">
      <p className="text-sm text-paper/60 mb-4">
        {existing ? "Edit this month's budget" : "Set this month's budget"}
      </p>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <label className="block">
          <span className="text-xs text-paper/50 mb-1 block">Money available this month</span>
          <input
            type="number" min="1" value={totalIncome}
            onChange={(e) => setTotalIncome(e.target.value)}
            className={`${field} w-full`} required
          />
        </label>
        <label className="block">
          <span className="text-xs text-paper/50 mb-1 block">Savings goal</span>
          <input
            type="number" min="0" value={savingsTarget}
            onChange={(e) => setSavingsTarget(e.target.value)}
            className={`${field} w-full`}
          />
        </label>
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-paper/50">Category limits (optional)</span>
          <span className="text-xs font-mono text-paper/40">
            {formatINR(allocated)} of {formatINR(income)} allocated
          </span>
        </div>

        <div className="space-y-2">
          {rules.map((rule, i) => (
            <div key={i} className="flex gap-2">
              <select
                value={rule.category}
                onChange={(e) => updateRule(i, { category: e.target.value })}
                className={`${field} flex-1`}
              >
                {SUGGESTED_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
              <input
                type="number" min="0" value={rule.allocated_amount}
                onChange={(e) => updateRule(i, { allocated_amount: Number(e.target.value) })}
                className={`${field} w-28`}
              />
              <button
                type="button"
                onClick={() => setRules(rules.filter((_, idx) => idx !== i))}
                className="text-paper/40 hover:text-sindoor-500 px-2"
                aria-label={`Remove ${rule.category} limit`}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={() => {
            const unused = SUGGESTED_CATEGORIES.find((c) => !rules.some((r) => r.category === c));
            if (unused) setRules([...rules, { category: unused, allocated_amount: 1000 }]);
          }}
          className="text-marigold-500 text-xs mt-2 hover:text-marigold-400"
        >
          + Add a category limit
        </button>
      </div>

      {error && <p role="alert" className="text-sindoor-500 text-sm mb-3">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit" disabled={saving}
          className="bg-marigold-500 hover:bg-marigold-600 disabled:opacity-50 text-ink-950 font-medium text-sm rounded-lg px-4 py-2"
        >
          {saving ? "Saving…" : "Save budget"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-paper/50 text-sm px-3 hover:text-paper">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
