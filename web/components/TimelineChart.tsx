"use client";

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import { formatUtcTick } from "@/lib/format";
import type { TimelineBucket } from "@/lib/types";

type ChartRow = {
  bucket_start: string;
  event_count: number;
  blocked: number;
  anomaly_count: number;
  /** Same as event_count when anomalies exist; omitted otherwise. */
  anomalyY?: number;
};

function toRows(buckets: TimelineBucket[]): ChartRow[] {
  return buckets.map((b) => {
    const row: ChartRow = {
      bucket_start: b.bucket_start,
      event_count: b.event_count,
      blocked: Math.min(b.blocked_count, b.event_count),
      anomaly_count: b.anomaly_count,
    };
    if (b.anomaly_count > 0 && b.event_count > 0) {
      row.anomalyY = b.event_count;
    }
    return row;
  });
}

function TimelineTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as ChartRow | undefined;
  if (!row) return null;

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1.5 font-medium text-white">
        {formatUtcTick(String(label))} UTC
      </p>
      <dl className="space-y-1 text-white/70">
        <div className="flex justify-between gap-6">
          <dt>Events</dt>
          <dd className="font-medium text-indigo-300">{row.event_count}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Blocked</dt>
          <dd className="font-medium text-red-400">{row.blocked}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Anomalies</dt>
          <dd className="font-medium text-amber-400">{row.anomaly_count}</dd>
        </div>
      </dl>
    </div>
  );
}

type DotProps = {
  cx?: number;
  cy?: number;
  payload?: ChartRow;
};

function AnomalyDot({ cx, cy, payload }: DotProps) {
  if (
    cx == null ||
    cy == null ||
    payload?.anomalyY == null ||
    !Number.isFinite(cx) ||
    !Number.isFinite(cy)
  ) {
    return null;
  }
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill="#fbbf24"
      stroke="#111827"
      strokeWidth={1}
    />
  );
}

/**
 * Timeline: event and blocked counts as lines, with anomaly markers on peaks.
 * Bucket contract comes from GET /summary — no API changes.
 */
export default function TimelineChart({ buckets }: { buckets: TimelineBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-sm text-white/50">No events to chart.</p>;
  }

  const data = toRows(buckets);
  const tickEvery = Math.max(1, Math.ceil(buckets.length / 8));
  const yMax = Math.max(
    ...data.map((r) => Math.max(r.event_count, r.blocked)),
    1,
  );

  return (
    <div className="h-[280px] w-full" role="img" aria-label="Events over time">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 16, right: 8, left: 0, bottom: 4 }}
        >
          <CartesianGrid
            stroke="#1f2937"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="bucket_start"
            tickFormatter={formatUtcTick}
            interval={tickEvery - 1}
            minTickGap={28}
            tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            domain={[0, yMax]}
            ticks={yMax <= 1 ? [0, 1] : undefined}
            width={40}
            tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<TimelineTooltip />}
            cursor={{
              stroke: "rgba(255,255,255,0.15)",
              strokeWidth: 1,
              strokeDasharray: "4 4",
            }}
          />
          <Legend
            verticalAlign="bottom"
            height={28}
            iconSize={10}
            wrapperStyle={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}
            formatter={(value) => (
              <span className="text-white/50">{value}</span>
            )}
          />
          <Line
            type="monotone"
            dataKey="event_count"
            name="Events"
            stroke="#818cf8"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#818cf8", stroke: "#111827", strokeWidth: 1 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="blocked"
            name="Blocked"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#ef4444", stroke: "#111827", strokeWidth: 1 }}
            isAnimationActive={false}
          />
          <Scatter
            dataKey="anomalyY"
            name="Anomalies"
            fill="#fbbf24"
            shape={<AnomalyDot />}
            legendType="circle"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
