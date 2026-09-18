"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UploadCloud } from "lucide-react";
import { uploadLog } from "@/lib/api";
import { waitForUpload } from "@/lib/uploadStatus";
import UploadStatusPanel from "@/components/UploadStatusPanel";

const MAX_BYTES = 25 * 1024 * 1024; // keep in sync with spec.md §5
const ALLOWED_EXTENSIONS = [
  ".json",
  ".jsonl",
  ".ndjson",
  ".log",
  ".txt",
  ".csv",
  ".tsv",
];
const SUCCESS_DWELL_MS = 1200;

type Phase = "idle" | "uploading" | "processing" | "success" | "failed" | "error";

interface SuccessInfo {
  id: number;
  eventCount: number;
  anomalyCount: number;
}

export default function FileUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const navigateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [dragOver, setDragOver] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [success, setSuccess] = useState<SuccessInfo | null>(null);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      if (navigateTimer.current) clearTimeout(navigateTimer.current);
    },
    [],
  );

  function validate(file: File): string | null {
    const name = file.name.toLowerCase();
    if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size === 0) return "The file is empty.";
    if (file.size > MAX_BYTES) return "File is over the 25 MB limit.";
    return null;
  }

  const goToResults = useCallback(
    (id: number) => {
      if (navigateTimer.current) clearTimeout(navigateTimer.current);
      router.push(`/uploads/${id}`);
    },
    [router],
  );

  function reset() {
    abortRef.current?.abort();
    abortRef.current = null;
    if (navigateTimer.current) clearTimeout(navigateTimer.current);
    navigateTimer.current = null;
    setPhase("idle");
    setFile(null);
    setError(null);
    setFailure(null);
    setSuccess(null);
  }

  function finishSuccess(id: number, eventCount: number, anomalyCount: number) {
    setSuccess({ id, eventCount, anomalyCount });
    setPhase("success");
    navigateTimer.current = setTimeout(() => goToResults(id), SUCCESS_DWELL_MS);
  }

  async function handleFile(selected: File) {
    setError(null);
    setFailure(null);
    setSuccess(null);

    const problem = validate(selected);
    if (problem) {
      setFile(selected);
      setError(problem);
      setPhase("error");
      return;
    }

    setFile(selected);
    setPhase("uploading");

    const controller = new AbortController();
    abortRef.current = controller;

    let uploaded;
    try {
      uploaded = await uploadLog(selected);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Upload failed");
      setPhase("error");
      return;
    }
    if (controller.signal.aborted) return;

    // Synchronous backends answer `completed` immediately — no polling needed.
    if (uploaded.status === "completed") {
      finishSuccess(uploaded.id, uploaded.event_count, uploaded.anomaly_count);
      return;
    }

    setPhase("processing");
    try {
      const status = await waitForUpload(uploaded.id, {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (status.status === "failed") {
        setFailure(
          status.error_message ?? "The backend could not process this file.",
        );
        setPhase("failed");
        return;
      }
      finishSuccess(uploaded.id, status.event_count, status.anomaly_count);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setFailure(err instanceof Error ? err.message : "Processing failed");
      setPhase("failed");
    }
  }

  if (phase === "processing" || phase === "success" || phase === "failed") {
    return (
      <UploadStatusPanel
        state={phase}
        filename={file?.name}
        fileSize={file?.size}
        eventCount={success?.eventCount}
        anomalyCount={success?.anomalyCount}
        message={failure ?? undefined}
        onViewResults={
          success ? () => goToResults(success.id) : undefined
        }
        onRetry={file ? () => void handleFile(file) : undefined}
        onUploadAnother={reset}
      />
    );
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a log file"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) void handleFile(dropped);
        }}
        className={`flex h-64 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center backdrop-blur-sm transition-colors ${
          dragOver
            ? "border-white bg-white/10"
            : "border-gray-700 bg-gray-900/40 hover:border-white/40 hover:bg-gray-900/60"
        }`}
      >
        {phase === "uploading" ? (
          <>
            <Loader2
              size={32}
              className="mb-3 animate-spin text-white/80"
              aria-hidden
            />
            <p className="font-medium text-white">Uploading…</p>
            <p className="mt-1 text-sm text-white/50">
              Sending the file to the analyzer
            </p>
            {file && (
              <p className="mt-3 max-w-full truncate text-xs text-white/40">
                {file.name}
              </p>
            )}
          </>
        ) : (
          <>
            <UploadCloud size={40} className="mb-3 text-white/70" aria-hidden />
            <p className="font-medium text-white">
              Drag &amp; drop your log file here
            </p>
            <p className="mt-1 text-sm text-white/50">
              or click to browse — .json / .log / .txt / .csv, up to 25 MB
            </p>
            <span className="mt-5 inline-flex h-10 items-center justify-center rounded-md bg-white px-5 text-sm font-medium text-black transition-colors">
              Browse files
            </span>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const selected = e.target.files?.[0];
          if (selected) void handleFile(selected);
          e.target.value = "";
        }}
      />

      {error && (
        <p className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
