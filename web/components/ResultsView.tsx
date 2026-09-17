"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSummary } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { SummaryResponse } from "@/lib/types";
import AnomalyList from "@/components/AnomalyList";
import EventsTable from "@/components/EventsTable";
import StatCards from "@/components/StatCards";
import TimelineChart from "@/components/TimelineChart";

export default function ResultsView({ uploadId }: { uploadId: number }) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSummary(uploadId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load summary");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [uploadId]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        <p className="font-medium">Could not load this upload.</p>
        <p className="mt-1">{error}</p>
        <Link href="/" className="mt-2 inline-block text-indigo-600 underline">
          ← Upload another file
        </Link>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="h-24 animate-pulse rounded-xl bg-slate-200" />
        <div className="h-48 animate-pulse rounded-xl bg-slate-200" />
        <div className="h-64 animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  const highCount = summary.anomalies.filter((a) => a.severity === "high").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Analysis of upload #{summary.upload_id}</h2>
          <p className="mt-1 text-sm text-slate-600">
            Activity from{" "}
            <span className="font-medium">{formatDateTime(summary.time_range_start)}</span>{" "}
            to{" "}
            <span className="font-medium">{formatDateTime(summary.time_range_end)}</span>{" "}
            — {summary.total_events.toLocaleString()} events across{" "}
            {summary.unique_clients} clients; {summary.anomalies.length} anomalies
            {highCount > 0 && (
              <span className="font-medium text-red-600"> ({highCount} high severity)</span>
            )}
            .
          </p>
        </div>
        <Link
          href="/"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          ← New upload
        </Link>
      </div>

      <StatCards summary={summary} />

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="mb-4 font-semibold">Timeline</h3>
        <TimelineChart buckets={summary.timeline} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="mb-4 font-semibold">
          Anomalies{" "}
          <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
            {summary.anomalies.length}
          </span>
        </h3>
        <AnomalyList anomalies={summary.anomalies} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="mb-4 font-semibold">Events</h3>
        <EventsTable uploadId={uploadId} />
      </section>
    </div>
  );
}
