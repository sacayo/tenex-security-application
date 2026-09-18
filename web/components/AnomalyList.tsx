import { formatDateTime } from "@/lib/format";
import type { AnomalyOut, Severity } from "@/lib/types";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-red-500/15 text-red-300 border-red-500/30",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  low: "bg-blue-500/15 text-blue-300 border-blue-500/30",
};

const SEVERITY_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

export default function AnomalyList({ anomalies }: { anomalies: AnomalyOut[] }) {
  if (anomalies.length === 0) {
    return (
      <p className="text-sm text-white/50">
        No anomalies detected — this log looks clean.
      </p>
    );
  }

  const sorted = [...anomalies].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
  );

  return (
    <ul className="space-y-3">
      {sorted.map((a) => (
        <li
          key={a.id}
          className="rounded-lg border border-gray-800 p-4 transition-colors hover:bg-gray-900/60"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${SEVERITY_STYLES[a.severity]}`}
            >
              {a.severity}
            </span>
            <span className="font-medium text-white">{a.title}</span>
            <span className="ml-auto text-xs text-white/40">{a.rule}</span>
          </div>
          <p className="mt-1.5 text-sm text-white/60">{a.description}</p>
          {a.timestamp && (
            <p className="mt-1 text-xs text-white/40">
              {formatDateTime(a.timestamp)}
              {a.event_id != null && ` · event #${a.event_id}`}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
