/**
 * TypeScript mirrors of the API contract (spec.md §5).
 *
 * These must stay in sync with `app/model/` on the backend — if one side
 * changes, change the other AND spec.md. See AGENTS.md "Division of labor".
 */

/** Lifecycle of an upload, shared by POST /api/logs and GET /api/uploads/{id}. */
export type UploadState = "uploaded" | "parsing" | "completed" | "failed";

export interface UploadResponse {
  id: number;
  filename: string;
  status: UploadState;
  event_count: number;
  anomaly_count: number;
}

export interface UploadStatus {
  id: number;
  filename: string;
  status: UploadState;
  uploaded_at: string;
  processed_at: string | null;
  event_count: number;
  anomaly_count: number;
  error_message: string | null;
}

export interface EventOut {
  id: number;
  timestamp: string;
  client_ip: string;
  username: string | null;
  method: string | null;
  url: string;
  host: string | null;
  status_code: number | null;
  action: string;
  url_category: string | null;
  threat_name: string | null;
  risk_score: number;
  bytes_sent: number;
  bytes_received: number;
  user_agent: string | null;
}

export interface EventPage {
  items: EventOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface TimelineBucket {
  bucket_start: string;
  event_count: number;
  blocked_count: number;
  anomaly_count: number;
}

export type Severity = "low" | "medium" | "high";

export interface AnomalyOut {
  id: number;
  rule: string;
  severity: Severity;
  title: string;
  description: string;
  event_id: number | null;
  timestamp: string | null;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface HostCount {
  host: string;
  count: number;
}

export interface SummaryResponse {
  upload_id: number;
  time_range_start: string;
  time_range_end: string;
  total_events: number;
  unique_clients: number;
  unique_users: number;
  blocked_count: number;
  allowed_count: number;
  top_categories: CategoryCount[];
  top_hosts: HostCount[];
  timeline: TimelineBucket[];
  anomalies: AnomalyOut[];
}

/** LLM narrative brief — mirrors app/model/narrative.py. */
export type NarrativeStatus = "pending" | "ready" | "failed";
export type RiskLevel = "none" | "low" | "medium" | "high";

export interface NarrativeSections {
  headline: string;
  overview: string;
  key_findings: string[];
  recommended_actions: string[];
}

export interface NarrativeResponse {
  upload_id: number;
  status: NarrativeStatus;
  /** Computed by the backend from anomaly severities, never by the model. */
  risk_level: RiskLevel;
  sections: NarrativeSections | null;
  model: string | null;
  prompt_version: string | null;
  generated_at: string | null;
  error_message: string | null;
}
