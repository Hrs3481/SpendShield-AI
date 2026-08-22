import { useCallback, useEffect, useState } from "react";
import AddTransaction from "../components/AddTransaction";
import BudgetForm from "../components/BudgetForm";
import CategoryChart from "../components/CategoryChart";
import CopilotChat from "../components/CopilotChat";
import ForecastPanel from "../components/ForecastPanel";
import PurchaseEvaluator from "../components/PurchaseEvaluator";
import SafeToSpendGauge from "../components/SafeToSpendGauge";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/AuthContext";
import { ApiError, api, formatINR } from "../lib/api";
import type {
  Budget, CategorySpend, CurrentUser, Forecast, SafeToSpend, Transaction, Velocity,
} from "../lib/types";

interface DashboardData {
  sts: SafeToSpend;
  transactions: Transaction[];
  forecast: Forecast;
  velocity: Velocity;
  categories: CategorySpend[];
  budget: Budget | null;
  user: CurrentUser | null;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingBudget, setEditingBudget] = useState(false);
  const { logout } = useAuth();

  const load = useCallback(async () => {
    setError(null);
    try {
      // A missing budget is an expected state, not a failure, so its 404 is
      // caught here rather than taking down the whole dashboard.
      const [sts, transactions, forecast, velocity, categories, budget, user] = await Promise.all([
        api.getSafeToSpend(),
        api.listTransactions(10),
        api.getForecast(),
        api.getVelocity(),
        api.getCategories(),
        api.getCurrentBudget().catch(() => null),
        api.me().catch(() => null),
      ]);
      setData({ sts, transactions, forecast, velocity, categories, budget, user });
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Couldn't reach the SpendShield API. Is the backend running?",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen px-4 sm:px-6 py-8 max-w-3xl mx-auto">
      <header className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-paper">SpendShield AI</h1>
          <p className="text-paper/40 text-sm">Know before you spend.</p>
        </div>
        <div className="flex items-center gap-3">
          {data?.user?.is_demo && (
            <span className="text-xs text-marigold-500 border border-marigold-500/30 rounded-full px-2.5 py-1">
              Demo data
            </span>
          )}
          <button onClick={logout} className="text-paper/50 text-sm hover:text-paper">
            Log out
          </button>
        </div>
      </header>

      {loading && <p className="text-paper/50 text-sm">Loading your financial picture…</p>}

      {error && (
        <div
          role="alert"
          className="bg-sindoor-500/10 border border-sindoor-500/30 rounded-xl p-4 text-sm text-sindoor-500 mb-6"
        >
          {error}
          <button onClick={() => void load()} className="ml-3 underline hover:no-underline">
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          {/* Without a budget every figure below is zero. Ask for the missing input
              rather than rendering an empty gauge that looks like a broken app. */}
          {!data.sts.has_budget || editingBudget ? (
            <div className="mb-6">
              {!data.sts.has_budget && (
                <p className="text-paper/70 text-sm mb-3">
                  Set a budget to unlock your safe-to-spend number, forecast, and purchase checks.
                </p>
              )}
              <BudgetForm
                existing={data.budget}
                onSaved={() => {
                  setEditingBudget(false);
                  void load();
                }}
                onCancel={editingBudget ? () => setEditingBudget(false) : undefined}
              />
            </div>
          ) : (
            <>
              <div className="bg-ink-800 rounded-2xl p-6 mb-6">
                <SafeToSpendGauge data={data.sts} />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
                <StatCard label="Remaining budget" value={formatINR(data.sts.remaining_budget)} />
                <StatCard label="Days remaining" value={String(data.sts.days_remaining)} />
                <StatCard
                  label="Monthly budget"
                  value={formatINR(data.budget?.total_income ?? 0)}
                  onAction={() => setEditingBudget(true)}
                  actionLabel="Edit"
                />
              </div>

              <div className="bg-ink-800 rounded-xl p-5 mb-6">
                <p className="text-sm text-paper/60 mb-2">Why this number</p>
                <ul className="space-y-1.5">
                  {data.sts.explanation_factors.map((factor, i) => (
                    <li key={i} className="text-sm text-paper/70 flex gap-2">
                      <span className="text-marigold-500 shrink-0">•</span>
                      {factor}
                    </li>
                  ))}
                </ul>
              </div>

              <ForecastPanel forecast={data.forecast} velocity={data.velocity} />
            </>
          )}

          <CategoryChart categories={data.categories} />

          <div className="mb-6">
            <PurchaseEvaluator />
          </div>

          <div className="mb-6">
            <CopilotChat />
          </div>

          <div className="mb-6">
            <AddTransaction onAdded={() => void load()} />
          </div>

          {data.transactions.length > 0 && (
            <div className="bg-ink-800 rounded-xl p-5">
              <p className="text-sm text-paper/60 mb-3">Recent transactions</p>
              <div className="space-y-2">
                {data.transactions.map((t) => (
                  <div key={t.id} className="flex justify-between items-center text-sm gap-3">
                    <div className="min-w-0">
                      <p className="text-paper truncate">
                        {t.merchant ?? t.category.replace(/_/g, " ")}
                      </p>
                      <p className="text-paper/40 text-xs">
                        {t.transaction_date}
                        {t.is_recurring && " · recurring"}
                        {t.impulse_score >= 65 && " · high impulse"}
                      </p>
                    </div>
                    <span className="font-mono text-paper shrink-0">{formatINR(t.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
