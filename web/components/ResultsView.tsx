"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, getSummary } from "@/lib/api";
import { waitForUpload } from "@/lib/uploadStatus";
import { formatDateTime } from "@/lib/format";
import type { SummaryResponse, UploadStatus } from "@/lib/types";
import AnomalyList from "@/components/AnomalyList";
import EventsTable from "@/components/EventsTable";
import NarrativeCard from "@/components/NarrativeCard";
import StatCards from "@/components/StatCards";
import TimelineChart from "@/components/TimelineChart";
import UploadStatusPanel from "@/components/UploadStatusPanel";

type LoadError = { kind: "not-found" | "failed" | "error"; message: string };

export default function ResultsView({ uploadId }: { uploadId: number }) {
  const router = useRouter();
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [loadError, setLoadError] = useState<LoadError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setSummary(null);
    setStatus(null);
    setLoadError(null);

    (async () => {
      try {
        const upload = await waitForUpload(uploadId, {
          signal: controller.signal,
          onTick: (s) => {
            if (!controller.signal.aborted) setStatus(s);
          },
        });
        if (controller.signal.aborted) return;

        if (upload.status === "failed") {
          setLoadError({
            kind: "failed",
            message:
              upload.error_message ??
              "The backend could not process this file.",
          });
          return;
        }

        const data = await getSummary(uploadId);
        if (!controller.signal.aborted) setSummary(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const notFound = err instanceof ApiError && err.status === 404;
        setLoadError({
          kind: notFound ? "not-found" : "error",
          message:
            err instanceof Error ? err.message : "Failed to load this upload",
        });
      }
    })();

    return () => controller.abort();
  }, [uploadId, attempt]);

  const title = status?.filename ?? `Upload #${uploadId}`;

  if (loadError) {
    if (loadError.kind === "not-found") {
      return (
        <div className="animate-[fadeIn_0.4s_ease-out] rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-6 text-sm text-white/60">
          <p className="font-medium text-white">
            We couldn&apos;t find upload #{uploadId}.
          </p>
          <p className="mt-1">{loadError.message}</p>
          <Link href="/" className="mt-3 inline-block text-white underline">
            ← Upload a file
          </Link>
        </div>
      );
    }

    return (
      <UploadStatusPanel
        state="failed"
        filename={status?.filename}
        message={loadError.message}
        onRetry={
          loadError.kind === "error"
            ? () => setAttempt((n) => n + 1)
            : undefined
        }
        onUploadAnother={() => router.push("/")}
      />
    );
  }

  if (!summary) {
    return (
      <UploadStatusPanel
        state="processing"
        filename={status?.filename}
        message={`Upload #${uploadId}`}
      />
    );
  }

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-xl font-bold text-white">{title}</h2>
        <p className="mt-1 text-sm text-white/60">
          Upload #{summary.upload_id}
          {status?.uploaded_at &&
            ` · uploaded ${formatDateTime(status.uploaded_at)}`}
          {" — "}
          {summary.total_events.toLocaleString()} events across{" "}
          {summary.unique_clients} clients
          {summary.anomalies.length > 0 && (
            <>
              ; {summary.anomalies.length} anomalies
              {summary.anomalies.some((a) => a.severity === "high") && (
                <span className="font-medium text-red-400">
                  {" "}
                  (
                  {
                    summary.anomalies.filter((a) => a.severity === "high")
                      .length
                  }{" "}
                  high severity)
                </span>
              )}
            </>
          )}
          .
        </p>
      </div>
      <Link
        href="/"
        className="rounded-lg border border-gray-700 bg-gray-900/40 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-800"
      >
        ← New upload
      </Link>
    </div>
  );

  if (summary.total_events === 0) {
    return (
      <div className="animate-[fadeIn_0.4s_ease-out] space-y-6">
        {header}
        <div className="rounded-2xl border border-gray-800 bg-gray-900/40 p-10 text-center">
          <p className="font-medium text-white">No events found</p>
          <p className="mt-1 text-sm text-white/60">
            This file parsed successfully but contained no web-log events.
            Check that it&apos;s an NSS web-log export and try again.
          </p>
          <Link href="/" className="mt-4 inline-block text-sm text-white underline">
            Upload another file
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-[fadeIn_0.4s_ease-out] space-y-6">
      {header}

      <NarrativeCard uploadId={uploadId} />

      <StatCards summary={summary} />

      <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-5">
        <h3 className="mb-4 font-semibold text-white">Timeline</h3>
        <TimelineChart buckets={summary.timeline} />
      </section>

      <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-5">
        <h3 className="mb-4 font-semibold text-white">
          Anomalies{" "}
          <span className="ml-1 rounded-full bg-white/10 px-2 py-0.5 text-xs font-medium text-white/70">
            {summary.anomalies.length}
          </span>
        </h3>
        <AnomalyList anomalies={summary.anomalies} />
      </section>

      <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-5">
        <h3 className="mb-4 font-semibold text-white">Events</h3>
        <EventsTable uploadId={uploadId} />
      </section>
    </div>
  );
}
