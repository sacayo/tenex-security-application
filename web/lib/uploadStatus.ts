/**
 * Poll an upload until it reaches a terminal state.
 *
 * The backend processes synchronously in the happy path, so the very first
 * call usually returns `completed` and we return immediately. This exists for
 * the async case (`uploaded` / `parsing`) and, importantly, for refreshes on
 * `/uploads/[id]` while a file is still being processed.
 */

import { getUploadStatus } from "./api";
import type { UploadStatus } from "./types";

export const POLL_INTERVAL_MS = 1000;
export const POLL_TIMEOUT_MS = 60_000;

export class ProcessingTimeoutError extends Error {
  constructor() {
    super("Processing is taking longer than expected. Please try again.");
    this.name = "ProcessingTimeoutError";
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export interface WaitForUploadOptions {
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Called on every poll with the latest status (handy for progress UI). */
  onTick?: (status: UploadStatus) => void;
}

export async function waitForUpload(
  uploadId: number,
  options: WaitForUploadOptions = {},
): Promise<UploadStatus> {
  const {
    intervalMs = POLL_INTERVAL_MS,
    timeoutMs = POLL_TIMEOUT_MS,
    signal,
    onTick,
  } = options;
  const deadline = Date.now() + timeoutMs;

  for (;;) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

    const status = await getUploadStatus(uploadId);
    onTick?.(status);

    if (status.status === "completed" || status.status === "failed") {
      return status;
    }
    if (Date.now() >= deadline) throw new ProcessingTimeoutError();

    await sleep(intervalMs, signal);
  }
}
