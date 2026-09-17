/**
 * Typed API client — the ONLY place that talks to the backend.
 *
 * Set NEXT_PUBLIC_API_URL to point at a non-default backend, or
 * NEXT_PUBLIC_MOCK_API=1 to run the whole UI against local fixture data
 * (no backend needed — handy while the API is still being built).
 */

import type { EventPage, SummaryResponse, UploadResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USE_MOCK = process.env.NEXT_PUBLIC_MOCK_API === "1";

/** FastAPI errors look like {"detail": "..."} — surface that message. */
async function toError(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return new Error(body.detail);
  } catch {
    // fall through to the generic message
  }
  return new Error(`Request failed: ${res.status} ${res.statusText}`);
}

export async function uploadLog(file: File): Promise<UploadResponse> {
  if (USE_MOCK) return (await import("./mock")).mockUpload();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/logs`, { method: "POST", body: form });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function getSummary(uploadId: number): Promise<SummaryResponse> {
  if (USE_MOCK) return (await import("./mock")).mockGetSummary(uploadId);
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}/summary`, {
    cache: "no-store",
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export interface EventQuery {
  limit?: number;
  offset?: number;
  action?: string;
}

export async function getEvents(
  uploadId: number,
  query: EventQuery = {},
): Promise<EventPage> {
  if (USE_MOCK) return (await import("./mock")).mockGetEvents(uploadId, query);
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 25));
  params.set("offset", String(query.offset ?? 0));
  if (query.action) params.set("action", query.action);
  const res = await fetch(
    `${API_BASE}/api/uploads/${uploadId}/events?${params.toString()}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw await toError(res);
  return res.json();
}
