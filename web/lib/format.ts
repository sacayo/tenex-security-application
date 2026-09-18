/** Small display helpers shared by the results components. */

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Axis/tooltip labels for timeline buckets — always UTC to match NSS times. */
export function formatUtcTick(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const month = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const day = d.getUTCDate();
  const hour = String(d.getUTCHours()).padStart(2, "0");
  const minute = String(d.getUTCMinutes()).padStart(2, "0");
  return `${month} ${day}, ${hour}:${minute}`;
}

/** Human label for the gap between adjacent timeline buckets. */
export function describeBucketWidth(buckets: { bucket_start: string }[]): string | null {
  if (buckets.length < 2) return null;
  const ms =
    new Date(buckets[1].bucket_start).getTime() -
    new Date(buckets[0].bucket_start).getTime();
  if (!Number.isFinite(ms) || ms <= 0) return null;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}-second buckets`;
  if (seconds < 3600) {
    const minutes = Math.round(seconds / 60);
    return `${minutes}-minute buckets`;
  }
  if (seconds < 86400) {
    const hours = Math.round(seconds / 3600);
    return `${hours}-hour buckets`;
  }
  const days = Math.round(seconds / 86400);
  return `${days}-day buckets`;
}
