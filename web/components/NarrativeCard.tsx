"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, RefreshCw, Sparkles } from "lucide-react";
import { ApiError, getNarrative, requestNarrative } from "@/lib/api";
import type { NarrativeResponse, RiskLevel } from "@/lib/types";

/**
 * AI-written brief for one upload.
 *
 * Flow: POST on mount (server is idempotent, so React's dev double-mount and
 * duplicate tabs are harmless) -> poll GET while `pending` -> render. The
 * model runs on a scale-to-zero GPU, so the first request after idle can
 * take a minute or two; copy escalates from skeleton to "warming up" to a
 * non-error "still generating" if we outlast the poll window.
 *
 * A 503 from POST means the feature is disabled on the backend: the card
 * renders nothing, and the rest of the dashboard is unaffected.
 */

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 5 * 60_000;
const WARMING_AFTER_MS = 15_000;

type Phase =
  | { kind: "loading" }
  | { kind: "ready"; data: NarrativeResponse }
  | { kind: "failed"; message: string }
  | { kind: "timeout" }
  | { kind: "cooldown"; message: string }
  | { kind: "error"; message: string }
  | { kind: "hidden" };

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

const RISK_STYLES: Record<RiskLevel, { label: string; className: string }> = {
  none: { label: "No anomalies", className: "bg-white/10 text-white/70" },
  low: { label: "Low risk", className: "bg-emerald-500/15 text-emerald-300" },
  medium: { label: "Medium risk", className: "bg-amber-500/15 text-amber-300" },
  high: { label: "High risk", className: "bg-red-500/15 text-red-300" },
};

export default function NarrativeCard({ uploadId }: { uploadId: number }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const refreshRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const refresh = refreshRef.current;
    refreshRef.current = false;
    const startedAt = Date.now();

    setPhase({ kind: "loading" });
    setElapsedMs(0);
    const ticker = setInterval(() => setElapsedMs(Date.now() - startedAt), 1_000);

    (async () => {
      try {
        let current = await requestNarrative(uploadId, { refresh, signal });
        const deadline = Date.now() + POLL_TIMEOUT_MS;
        while (current.status === "pending") {
          if (Date.now() >= deadline) {
            if (!signal.aborted) setPhase({ kind: "timeout" });
            return;
          }
          await sleep(POLL_INTERVAL_MS, signal);
          current = await getNarrative(uploadId, signal);
        }
        if (signal.aborted) return;
        if (current.status === "failed") {
          setPhase({
            kind: "failed",
            message:
              current.error_message ?? "The model could not produce a summary.",
          });
        } else {
          setPhase({ kind: "ready", data: current });
        }
      } catch (err) {
        if (isAbort(err) || signal.aborted) return;
        if (err instanceof ApiError && err.status === 503) {
          setPhase({ kind: "hidden" });
          return;
        }
        if (err instanceof ApiError && err.status === 429) {
          setPhase({ kind: "cooldown", message: err.message });
          return;
        }
        setPhase({
          kind: "error",
          message: err instanceof Error ? err.message : "Request failed",
        });
      } finally {
        clearInterval(ticker);
      }
    })();

    return () => {
      controller.abort();
      clearInterval(ticker);
    };
  }, [uploadId, attempt]);

  if (phase.kind === "hidden") return null;

  const rerun = (refresh: boolean) => {
    refreshRef.current = refresh;
    setAttempt((n) => n + 1);
  };

  return (
    <section
      className="rounded-2xl border border-gray-800 bg-gray-900/40 p-5"
      aria-live="polite"
      aria-busy={phase.kind === "loading"}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold text-white">
          <Sparkles size={16} className="text-white/60" aria-hidden="true" />
          Summary
          <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white/50">
            AI-generated
          </span>
        </h3>
        {phase.kind === "ready" && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${RISK_STYLES[phase.data.risk_level].className}`}
          >
            {RISK_STYLES[phase.data.risk_level].label}
          </span>
        )}
      </div>

      {phase.kind === "loading" && <Loading elapsedMs={elapsedMs} />}

      {phase.kind === "ready" && phase.data.sections && (
        <Brief data={phase.data} onRegenerate={() => rerun(true)} />
      )}

      {phase.kind === "timeout" && (
        <Notice
          tone="neutral"
          title="Still generating"
          body="The model is taking longer than usual. Check again in a minute — the summary is saved once it finishes."
          action={{ label: "Check again", onClick: () => rerun(false) }}
        />
      )}

      {phase.kind === "failed" && (
        <Notice
          tone="warn"
          title="Summary unavailable"
          body={phase.message}
          action={{ label: "Retry", onClick: () => rerun(true) }}
        />
      )}

      {phase.kind === "cooldown" && (
        <Notice
          tone="neutral"
          title="Recently generated"
          body={phase.message}
          action={{ label: "Show current", onClick: () => rerun(false) }}
        />
      )}

      {phase.kind === "error" && (
        <Notice
          tone="warn"
          title="Could not load the summary"
          body={phase.message}
          action={{ label: "Try again", onClick: () => rerun(false) }}
        />
      )}
    </section>
  );
}

function Loading({ elapsedMs }: { elapsedMs: number }) {
  const warming = elapsedMs >= WARMING_AFTER_MS;
  return (
    <div className="space-y-3">
      <div className="h-5 w-3/4 animate-pulse rounded bg-white/10" />
      <div className="h-4 w-full animate-pulse rounded bg-white/5" />
      <div className="h-4 w-11/12 animate-pulse rounded bg-white/5" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-white/5" />
      <p className="pt-1 text-xs text-white/50">
        {warming
          ? "Warming up the model — the first run after idle can take a minute or two."
          : "Writing a plain-language summary of this upload…"}
      </p>
    </div>
  );
}

function Brief({
  data,
  onRegenerate,
}: {
  data: NarrativeResponse;
  onRegenerate: () => void;
}) {
  const s = data.sections!;
  return (
    <div className="space-y-4">
      <p className="text-lg font-medium leading-snug text-white">{s.headline}</p>
      <p className="text-sm leading-relaxed text-white/75">{s.overview}</p>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-white/50">
            Key findings
          </h4>
          <ul className="space-y-1.5 text-sm text-white/80">
            {s.key_findings.map((item, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-white/40" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-white/50">
            Recommended actions
          </h4>
          <ul className="space-y-1.5 text-sm text-white/80">
            {s.recommended_actions.map((item, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-white/40" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-800 pt-3 text-xs text-white/40">
        <span>
          Written by a language model from the counts and rule findings above;
          verify before acting.
          {data.model && data.model !== "none" && (
            <> Model: {data.model.split("/").pop()}.</>
          )}
        </span>
        {data.model !== "none" && (
          <button
            type="button"
            onClick={onRegenerate}
            className="inline-flex items-center gap-1 text-white/60 transition-colors hover:text-white"
          >
            <RefreshCw size={12} aria-hidden="true" />
            Regenerate
          </button>
        )}
      </div>
    </div>
  );
}

function Notice({
  tone,
  title,
  body,
  action,
}: {
  tone: "neutral" | "warn";
  title: string;
  body: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 text-sm">
      <div className="flex gap-2">
        {tone === "warn" && (
          <AlertTriangle
            size={16}
            className="mt-0.5 shrink-0 text-amber-400"
            aria-hidden="true"
          />
        )}
        <div>
          <p className="font-medium text-white">{title}</p>
          <p className="mt-0.5 text-white/60">{body}</p>
        </div>
      </div>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="rounded-lg border border-gray-700 bg-gray-900/40 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-800"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
