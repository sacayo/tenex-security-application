/**
 * Typed API client — the ONLY place that talks to the backend.
 *
 * Set NEXT_PUBLIC_API_URL to point at a non-default backend
 * (default: http://localhost:8000).
 */

import type {
  EventPage,
  SummaryResponse,
  UploadResponse,
  UploadStatus,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Error carrying the HTTP status so callers can special-case e.g. 404. */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** FastAPI errors look like {"detail": "..."} — surface that message. */
async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") {
      return new ApiError(body.detail, res.status);
    }
  } catch {
    // fall through to the generic message
  }
  return new ApiError(
    `Request failed: ${res.status} ${res.statusText}`,
    res.status,
  );
}

export async function uploadLog(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/logs`, { method: "POST", body: form });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function getUploadStatus(uploadId: number): Promise<UploadStatus> {
  const res = await fetch(`${API_BASE}/api/uploads/${uploadId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function getSummary(uploadId: number): Promise<SummaryResponse> {
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
