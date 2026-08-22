import { useState, type FormEvent } from "react";
import { ApiError, api } from "../lib/api";
import type { Transaction } from "../lib/types";

const CATEGORIES = [
  "food_delivery", "groceries", "rent", "transport",
  "shopping", "entertainment", "coffee_snacks", "utilities",
];

interface Props {
  onAdded: (txn: Transaction) => void;
}

export default function AddTransaction({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [isEssential, setIsEssential] = useState(false);
  const [isRecurring, setIsRecurring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("Enter an amount greater than 0.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const txn = await api.createTransaction({
        amount: parsed,
        merchant: merchant || undefined,
        category,
        transaction_date: date,
        is_essential: isEssential,
        is_recurring: isRecurring,
      });
      onAdded(txn);
      setAmount("");
      setMerchant("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save that transaction.");
    } finally {
      setSaving(false);
    }
  }

  const field =
    "bg-ink-900 rounded-lg px-3 py-2 text-sm text-paper outline-none border border-ink-700 focus:border-marigold-500";

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full border border-dashed border-ink-700 text-paper/50 hover:text-paper hover:border-ink-700/80 text-sm rounded-xl py-3"
      >
        + Log a transaction
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-ink-800 rounded-xl p-5">
      <p className="text-sm text-paper/60 mb-3">Log a transaction</p>

      <div className="grid grid-cols-2 gap-2 mb-2">
        <input
          type="number" min="1" step="1" value={amount} autoFocus
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Amount ₹" className={field} required
        />
        <input
          value={merchant} onChange={(e) => setMerchant(e.target.value)}
          placeholder="Merchant (optional)" className={field}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={field}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} />
      </div>

      <div className="flex gap-4 mb-3 text-sm text-paper/70">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={isEssential} onChange={(e) => setIsEssential(e.target.checked)} />
          Essential
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={isRecurring} onChange={(e) => setIsRecurring(e.target.checked)} />
          Recurring
        </label>
      </div>

      {error && <p role="alert" className="text-sindoor-500 text-sm mb-2">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit" disabled={saving}
          className="bg-marigold-500 hover:bg-marigold-600 disabled:opacity-50 text-ink-950 font-medium text-sm rounded-lg px-4 py-2"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-paper/50 text-sm px-3 hover:text-paper">
          Cancel
        </button>
      </div>
    </form>
  );
}
