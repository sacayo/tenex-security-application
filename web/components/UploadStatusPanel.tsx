"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RotateCcw,
  UploadCloud,
} from "lucide-react";
import { formatBytes } from "@/lib/format";

export type UploadPanelState = "processing" | "success" | "failed";

const PROCESSING_MESSAGES = [
  "Parsing events…",
  "Normalizing fields…",
  "Running detection rules…",
  "Building the timeline…",
];

export default function UploadStatusPanel({
  state,
  filename,
  fileSize,
  eventCount,
  anomalyCount,
  message,
  onViewResults,
  onRetry,
  onUploadAnother,
}: {
  state: UploadPanelState;
  filename?: string;
  fileSize?: number;
  eventCount?: number;
  anomalyCount?: number;
  message?: string;
  onViewResults?: () => void;
  onRetry?: () => void;
  onUploadAnother?: () => void;
}) {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    if (state !== "processing") return;
    setMessageIndex(0);
    const timer = setInterval(
      () => setMessageIndex((i) => (i + 1) % PROCESSING_MESSAGES.length),
      1200,
    );
    return () => clearInterval(timer);
  }, [state]);

  const fileLine =
    filename &&
    (fileSize != null ? `${filename} · ${formatBytes(fileSize)}` : filename);

  return (
    <div
      className={`flex h-64 flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center backdrop-blur-sm ${
        state === "failed"
          ? "border-red-500/40 bg-red-500/5"
          : "border-gray-700 bg-gray-900/40"
      }`}
      aria-live="polite"
    >
      {state === "processing" && (
        <>
          <Loader2
            size={32}
            className="mb-3 animate-spin text-white/80"
            aria-hidden
          />
          <p className="font-medium text-white">Analyzing your log…</p>
          <p className="mt-1 text-sm text-white/60">
            {PROCESSING_MESSAGES[messageIndex]}
          </p>
          {fileLine && (
            <p className="mt-3 max-w-full truncate text-xs text-white/40">
              {fileLine}
            </p>
          )}
        </>
      )}

      {state === "success" && (
        <>
          <CheckCircle2 size={40} className="mb-3 text-emerald-400" aria-hidden />
          <p className="font-medium text-white">Analysis complete</p>
          <p className="mt-1 text-sm text-white/60">
            {(eventCount ?? 0).toLocaleString()} events ·{" "}
            {(anomalyCount ?? 0).toLocaleString()} anomalies
          </p>
          {onViewResults && (
            <button
              type="button"
              onClick={onViewResults}
              className="mt-5 inline-flex h-10 items-center justify-center rounded-md bg-white px-5 text-sm font-medium text-black transition-colors hover:bg-gray-100"
            >
              View results
            </button>
          )}
        </>
      )}

      {state === "failed" && (
        <>
          <AlertTriangle
            size={40}
            className="mb-3 text-red-400"
            aria-hidden
          />
          <p className="font-medium text-white">Could not process this file</p>
          <p className="mt-1 max-w-md text-sm text-white/60">
            {message ?? "Something went wrong while analyzing the upload."}
          </p>
          {fileLine && (
            <p className="mt-2 max-w-full truncate text-xs text-white/40">
              {fileLine}
            </p>
          )}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-white px-5 text-sm font-medium text-black transition-colors hover:bg-gray-100"
              >
                <RotateCcw size={16} aria-hidden />
                Try again
              </button>
            )}
            {onUploadAnother && (
              <button
                type="button"
                onClick={onUploadAnother}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-gray-700 px-5 text-sm font-medium text-white transition-colors hover:bg-gray-800"
              >
                <UploadCloud size={16} aria-hidden />
                Upload another
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
