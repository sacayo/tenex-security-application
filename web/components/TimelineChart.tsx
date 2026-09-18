import { formatDateTime } from "@/lib/format";
import type { TimelineBucket } from "@/lib/types";

/**
 * Dependency-free timeline bar chart: one bar per time bucket.
 * Indigo = events, red bottom segment = blocked, dot on top = anomalies.
 */
export default function TimelineChart({ buckets }: { buckets: TimelineBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-sm text-white/50">No events to chart.</p>;
  }

  const max = Math.max(...buckets.map((b) => b.event_count), 1);
  // Show at most ~8 x-axis labels so they stay readable on small screens.
  const labelEvery = Math.max(1, Math.ceil(buckets.length / 8));

  return (
    <div>
      <div className="flex h-40 items-end gap-[2px]">
        {buckets.map((b, i) => {
          const heightPct = (b.event_count / max) * 100;
          const blockedPct =
            b.event_count > 0 ? (b.blocked_count / b.event_count) * 100 : 0;
          return (
            <div
              key={b.bucket_start}
              className="relative flex-1"
              title={`${formatDateTime(b.bucket_start)} — ${b.event_count} events, ${b.blocked_count} blocked, ${b.anomaly_count} anomalies`}
            >
              {b.anomaly_count > 0 && (
                <span
                  className="absolute -top-2 left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-amber-400"
                  aria-label={`${b.anomaly_count} anomalies`}
                />
              )}
              <div
                className="flex w-full flex-col justify-end overflow-hidden rounded-t bg-indigo-500/40"
                style={{ height: `${Math.max(heightPct, 4)}%` }}
              >
                <div
                  className="w-full bg-red-500/80"
                  style={{ height: `${blockedPct}%` }}
                />
              </div>
              {i % labelEvery === 0 && (
                <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-white/40">
                  {formatDateTime(b.bucket_start)}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-8 flex flex-wrap gap-4 text-xs text-white/50">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-indigo-500/40" /> events
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-red-500/80" /> blocked
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> anomalies
        </span>
      </div>
    </div>
  );
}
