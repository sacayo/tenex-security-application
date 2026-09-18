"use client";

import { useCallback, useEffect, useState } from "react";
import { getEvents } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { EventPage } from "@/lib/types";

const PAGE_SIZE = 10;

export default function EventsTable({ uploadId }: { uploadId: number }) {
  const [page, setPage] = useState<EventPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (nextOffset: number, action: string) => {
      getEvents(uploadId, {
        limit: PAGE_SIZE,
        offset: nextOffset,
        action: action || undefined,
      })
        .then((data) => {
          setPage(data);
          setError(null);
        })
        .catch((err: unknown) =>
          setError(err instanceof Error ? err.message : "Failed to load events"),
        );
    },
    [uploadId],
  );

  useEffect(() => {
    setOffset(0);
    load(0, actionFilter);
  }, [load, actionFilter]);

  if (error) {
    return (
      <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-300">
        {error}
      </p>
    );
  }

  if (!page) {
    return <div className="h-48 animate-pulse rounded-lg bg-gray-800/60" />;
  }

  const canPrev = page.offset > 0;
  const canNext = page.offset + page.limit < page.total;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="text-sm text-white/60">
          Action:{" "}
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-white/20"
          >
            <option value="">All</option>
            <option value="Allow">Allow</option>
            <option value="Block">Block</option>
          </select>
        </label>
        <span className="ml-auto text-xs text-white/50">
          {page.total.toLocaleString()} event{page.total === 1 ? "" : "s"}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-xs uppercase tracking-wide text-white/50">
              <th className="py-2 pr-3">Time</th>
              <th className="py-2 pr-3">Client</th>
              <th className="py-2 pr-3">User</th>
              <th className="py-2 pr-3">Destination</th>
              <th className="py-2 pr-3">Action</th>
              <th className="py-2 pr-3">Category</th>
              <th className="py-2 pr-3 text-right">Risk</th>
              <th className="py-2 text-right">Sent</th>
            </tr>
          </thead>
          <tbody>
            {page.items.map((e) => (
              <tr key={e.id} className="border-b border-gray-800/60 last:border-0">
                <td className="whitespace-nowrap py-2 pr-3 text-white/60">
                  {formatDateTime(e.timestamp)}
                </td>
                <td className="py-2 pr-3 font-mono text-xs text-white/80">
                  {e.client_ip}
                </td>
                <td className="py-2 pr-3 text-white/80">{e.username ?? "—"}</td>
                <td className="max-w-[16rem] py-2 pr-3">
                  <span className="block truncate text-white/80" title={e.url}>
                    {e.host ?? e.url}
                  </span>
                </td>
                <td className="py-2 pr-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      e.action === "Block"
                        ? "bg-red-500/15 text-red-300"
                        : "bg-emerald-500/15 text-emerald-300"
                    }`}
                  >
                    {e.action}
                  </span>
                </td>
                <td className="py-2 pr-3 text-white/60">
                  {e.url_category ?? "—"}
                </td>
                <td className="py-2 pr-3 text-right">
                  <span
                    className={
                      e.risk_score >= 75
                        ? "font-semibold text-red-400"
                        : e.risk_score >= 50
                          ? "text-amber-400"
                          : "text-white/60"
                    }
                  >
                    {e.risk_score}
                  </span>
                </td>
                <td className="py-2 text-right text-white/60">
                  {formatBytes(e.bytes_sent)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {page.total > PAGE_SIZE && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <button
            disabled={!canPrev}
            onClick={() => {
              const next = Math.max(0, page.offset - PAGE_SIZE);
              setOffset(next);
              load(next, actionFilter);
            }}
            className="rounded-lg border border-gray-700 px-3 py-1.5 font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="text-xs text-white/50">
            {page.offset + 1}–{Math.min(page.offset + PAGE_SIZE, page.total)} of{" "}
            {page.total}
          </span>
          <button
            disabled={!canNext}
            onClick={() => {
              const next = offset + PAGE_SIZE;
              setOffset(next);
              load(next, actionFilter);
            }}
            className="rounded-lg border border-gray-700 px-3 py-1.5 font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
