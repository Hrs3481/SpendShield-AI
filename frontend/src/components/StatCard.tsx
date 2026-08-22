interface Props {
  label: string;
  value: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function StatCard({ label, value, actionLabel, onAction }: Props) {
  return (
    <div className="bg-ink-800 rounded-xl px-4 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs text-paper/50 mb-1">{label}</p>
        {actionLabel && onAction && (
          <button onClick={onAction} className="text-xs text-marigold-500 hover:text-marigold-400">
            {actionLabel}
          </button>
        )}
      </div>
      <p className="font-mono text-lg font-medium text-paper">{value}</p>
    </div>
  );
}
