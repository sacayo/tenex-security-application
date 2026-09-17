import type { SummaryResponse } from "@/lib/types";

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-bold ${accent ?? "text-slate-900"}`}>
        {value}
      </p>
    </div>
  );
}

export default function StatCards({ summary }: { summary: SummaryResponse }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <StatCard label="Events" value={summary.total_events.toLocaleString()} />
      <StatCard
        label="Blocked"
        value={summary.blocked_count.toLocaleString()}
        accent={summary.blocked_count > 0 ? "text-red-600" : undefined}
      />
      <StatCard label="Allowed" value={summary.allowed_count.toLocaleString()} />
      <StatCard
        label="Anomalies"
        value={summary.anomalies.length.toLocaleString()}
        accent={summary.anomalies.length > 0 ? "text-amber-600" : undefined}
      />
      <StatCard label="Clients" value={summary.unique_clients.toLocaleString()} />
      <StatCard label="Users" value={summary.unique_users.toLocaleString()} />
    </div>
  );
}
