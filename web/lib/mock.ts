/**
 * Mock-mode data (NEXT_PUBLIC_MOCK_API=1).
 *
 * Mirrors tests/fixtures/sample_nss_web.json so the UI tells the same story
 * the backend's own test fixture does: one clean browse, a gambling block,
 * blocked malware, a big file-sharing upload, a DLP hit, and a 3 AM beacon.
 */

import type {
  AnomalyOut,
  EventOut,
  EventPage,
  SummaryResponse,
  UploadResponse,
} from "./types";
import type { EventQuery } from "./api";

const EVENTS: EventOut[] = [
  {
    id: 1,
    timestamp: "2026-09-10T09:15:23Z",
    client_ip: "10.1.2.15",
    username: "alice.smith",
    method: "GET",
    url: "https://www.google.com/search?q=standup notes",
    host: "www.google.com",
    status_code: 200,
    action: "Allow",
    url_category: "Search Engines",
    threat_name: null,
    risk_score: 5,
    bytes_sent: 512,
    bytes_received: 18432,
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0",
  },
  {
    id: 2,
    timestamp: "2026-09-10T09:47:02Z",
    client_ip: "10.1.3.44",
    username: "bob.jones",
    method: "GET",
    url: "https://www.online-casino.example/poker",
    host: "www.online-casino.example",
    status_code: 403,
    action: "Block",
    url_category: "Gambling",
    threat_name: null,
    risk_score: 41,
    bytes_sent: 480,
    bytes_received: 1024,
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
  },
  {
    id: 3,
    timestamp: "2026-09-10T10:03:41Z",
    client_ip: "10.1.4.22",
    username: "carol.davis",
    method: "GET",
    url: "http://cdn-update.example-bad.net/payload.exe",
    host: "cdn-update.example-bad.net",
    status_code: 200,
    action: "Block",
    url_category: "Miscellaneous",
    threat_name: "Trojan.Win32.FakeAV",
    risk_score: 92,
    bytes_sent: 640,
    bytes_received: 2048000,
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
  },
  {
    id: 4,
    timestamp: "2026-09-10T11:22:10Z",
    client_ip: "10.1.2.31",
    username: "dave.miller",
    method: "POST",
    url: "https://filedrop.example-share.com/upload",
    host: "filedrop.example-share.com",
    status_code: 200,
    action: "Allow",
    url_category: "File Sharing",
    threat_name: null,
    risk_score: 78,
    bytes_sent: 26214400,
    bytes_received: 2048,
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0",
  },
  {
    id: 5,
    timestamp: "2026-09-10T13:05:55Z",
    client_ip: "10.1.5.9",
    username: "erin.taylor",
    method: "POST",
    url: "https://webmail.example.com/compose",
    host: "webmail.example.com",
    status_code: 200,
    action: "Allow",
    url_category: "Webmail",
    threat_name: null,
    risk_score: 34,
    bytes_sent: 5242880,
    bytes_received: 4096,
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/128.0",
  },
  {
    id: 6,
    timestamp: "2026-09-10T03:12:47Z",
    client_ip: "10.1.9.99",
    username: null,
    method: "GET",
    url: "http://upd-svc.example-suspicious.net/beacon",
    host: "upd-svc.example-suspicious.net",
    status_code: 200,
    action: "Allow",
    url_category: "Miscellaneous",
    threat_name: null,
    risk_score: 66,
    bytes_sent: 256,
    bytes_received: 128,
    user_agent: null,
  },
];

const ANOMALIES: AnomalyOut[] = [
  {
    id: 1,
    rule: "threat-detected",
    severity: "high",
    title: "Malware blocked: Trojan.Win32.FakeAV",
    description:
      "carol.davis (10.1.4.22) downloaded payload.exe — detected as Trojan.Win32.FakeAV (risk 92). The proxy blocked it.",
    event_id: 3,
    timestamp: "2026-09-10T10:03:41Z",
  },
  {
    id: 2,
    rule: "large-upload",
    severity: "high",
    title: "25.0 MB uploaded to filedrop.example-share.com",
    description:
      "dave.miller (10.1.2.31) sent 25.0 MB to a File Sharing site. Large outbound transfers can indicate data exfiltration.",
    event_id: 4,
    timestamp: "2026-09-10T11:22:10Z",
  },
  {
    id: 3,
    rule: "dlp-violation",
    severity: "high",
    title: "DLP match: Credit Cards",
    description:
      "erin.taylor (10.1.5.9) triggered the Credit Cards DLP dictionary via webmail.example.com.",
    event_id: 5,
    timestamp: "2026-09-10T13:05:55Z",
  },
  {
    id: 4,
    rule: "high-risk-score",
    severity: "medium",
    title: "High-risk destination (score 78)",
    description:
      "dave.miller (10.1.2.31) visited filedrop.example-share.com, risk score 78/100.",
    event_id: 4,
    timestamp: "2026-09-10T11:22:10Z",
  },
  {
    id: 5,
    rule: "suspicious-url-category",
    severity: "medium",
    title: "Visit to Gambling site",
    description:
      "bob.jones (10.1.3.44) attempted to browse a Gambling category site; the proxy blocked it.",
    event_id: 2,
    timestamp: "2026-09-10T09:47:02Z",
  },
  {
    id: 6,
    rule: "off-hours",
    severity: "low",
    title: "Activity at 03:12",
    description:
      "Unauthenticated request from 10.1.9.99 to upd-svc.example-suspicious.net outside business hours.",
    event_id: 6,
    timestamp: "2026-09-10T03:12:47Z",
  },
];

const SUMMARY: SummaryResponse = {
  upload_id: 1,
  time_range_start: "2026-09-10T03:12:47Z",
  time_range_end: "2026-09-10T13:05:55Z",
  total_events: 6,
  unique_clients: 6,
  unique_users: 5,
  blocked_count: 2,
  allowed_count: 4,
  top_categories: [
    { category: "Miscellaneous", count: 2 },
    { category: "Search Engines", count: 1 },
    { category: "Gambling", count: 1 },
    { category: "File Sharing", count: 1 },
    { category: "Webmail", count: 1 },
  ],
  top_hosts: [
    { host: "www.google.com", count: 1 },
    { host: "www.online-casino.example", count: 1 },
    { host: "cdn-update.example-bad.net", count: 1 },
    { host: "filedrop.example-share.com", count: 1 },
    { host: "webmail.example.com", count: 1 },
  ],
  timeline: [
    { bucket_start: "2026-09-10T03:00:00Z", event_count: 1, blocked_count: 0, anomaly_count: 1 },
    { bucket_start: "2026-09-10T09:00:00Z", event_count: 2, blocked_count: 1, anomaly_count: 1 },
    { bucket_start: "2026-09-10T10:00:00Z", event_count: 1, blocked_count: 1, anomaly_count: 1 },
    { bucket_start: "2026-09-10T11:00:00Z", event_count: 1, blocked_count: 0, anomaly_count: 2 },
    { bucket_start: "2026-09-10T13:00:00Z", event_count: 1, blocked_count: 0, anomaly_count: 1 },
  ],
  anomalies: ANOMALIES,
};

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function mockUpload(): Promise<UploadResponse> {
  await delay(1200); // pretend to parse
  return {
    id: 1,
    filename: "sample_nss_web.json",
    status: "completed",
    event_count: 6,
    anomaly_count: 6,
  };
}

export async function mockGetSummary(_uploadId: number): Promise<SummaryResponse> {
  await delay(400);
  return SUMMARY;
}

export async function mockGetEvents(
  _uploadId: number,
  query: EventQuery,
): Promise<EventPage> {
  await delay(300);
  const filtered = query.action
    ? EVENTS.filter((e) => e.action === query.action)
    : EVENTS;
  const offset = query.offset ?? 0;
  const limit = query.limit ?? 25;
  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
    limit,
    offset,
  };
}
