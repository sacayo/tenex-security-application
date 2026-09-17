import { formatDateTime } from "@/lib/format";
import type { AnomalyOut, Severity } from "@/lib/types";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-red-100 text-red-800 border-red-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
};

const SEVERITY_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

export default function AnomalyList({ anomalies }: { anomalies: AnomalyOut[] }) {
  if (anomalies.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No anomalies detected — this log looks clean. ✅
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
          className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${SEVERITY_STYLES[a.severity]}`}
            >
              {a.severity}
            </span>
            <span className="font-medium text-slate-900">{a.title}</span>
            <span className="ml-auto text-xs text-slate-400">{a.rule}</span>
          </div>
          <p className="mt-1.5 text-sm text-slate-600">{a.description}</p>
          {a.timestamp && (
            <p className="mt-1 text-xs text-slate-400">
              {formatDateTime(a.timestamp)}
              {a.event_id != null && ` · event #${a.event_id}`}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
