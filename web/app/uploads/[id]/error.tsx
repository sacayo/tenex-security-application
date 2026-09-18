"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function ResultsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-black px-4 py-8">
      <div className="mx-auto max-w-2xl rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300">
        <p className="font-medium">Something went wrong loading this upload.</p>
        <p className="mt-1">{error.message}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100"
          >
            Try again
          </button>
          <Link
            href="/"
            className="rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800"
          >
            Upload another
          </Link>
        </div>
      </div>
    </div>
  );
}
