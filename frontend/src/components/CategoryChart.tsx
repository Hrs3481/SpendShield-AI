import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatINR } from "../lib/api";
import type { CategorySpend } from "../lib/types";

// One accent per rank, darkening down the list — the ordering already encodes
// magnitude, so colour only needs to separate adjacent bars.
const BAR_COLORS = ["#F5A623", "#E39A2E", "#C98A34", "#A87A38", "#8A6A38", "#6E5B36"];

interface Props {
  categories: CategorySpend[];
}

export default function CategoryChart({ categories }: Props) {
  if (categories.length === 0) return null;

  const data = categories.slice(0, 6).map((c) => ({
    ...c,
    label: c.category.replace(/_/g, " "),
  }));
  const total = categories.reduce((sum, c) => sum + c.total, 0);

  return (
    <div className="bg-ink-800 rounded-xl p-5 mb-6">
      <div className="flex items-baseline justify-between mb-4">
        <p className="text-sm text-paper/60">Where your money went this month</p>
        <p className="font-mono text-sm text-paper/80">{formatINR(total)}</p>
      </div>

      <div style={{ width: "100%", height: Math.max(data.length * 38, 120) }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 56, top: 0, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={96}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#F1EEE6", fontSize: 12, opacity: 0.7 }}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{
                background: "#12142B",
                border: "1px solid #272B54",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#F1EEE6" }}
              formatter={(value: number, _name, entry) => [
                `${formatINR(value)} · ${entry.payload.transaction_count} txns`,
                "Spent",
              ]}
            />
            <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={18}>
              {data.map((_, i) => (
                <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
