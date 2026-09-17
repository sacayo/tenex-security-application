"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { uploadLog } from "@/lib/api";

const MAX_BYTES = 25 * 1024 * 1024; // keep in sync with spec.md §5
const ALLOWED_EXTENSIONS = [".json", ".log", ".txt"];
const MOCK = process.env.NEXT_PUBLIC_MOCK_API === "1";

export default function FileUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function validate(file: File): string | null {
    const name = file.name.toLowerCase();
    if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size === 0) return "The file is empty.";
    if (file.size > MAX_BYTES) return "File is over the 25 MB limit.";
    return null;
  }

  async function handleFile(file: File) {
    setError(null);
    const problem = validate(file);
    if (problem) {
      setError(problem);
      return;
    }
    setUploading(true);
    try {
      const result = await uploadLog(file);
      router.push(`/uploads/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
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
          const file = e.dataTransfer.files?.[0];
          if (file) void handleFile(file);
        }}
        className={`flex h-56 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-white px-6 text-center transition-colors ${
          dragOver
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 hover:border-indigo-400 hover:bg-slate-50"
        }`}
      >
        {uploading ? (
          <>
            <div className="mb-3 h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" />
            <p className="font-medium text-slate-700">
              Uploading &amp; analyzing…
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Parsing events and running detection rules
            </p>
          </>
        ) : (
          <>
            <div className="mb-3 text-4xl" aria-hidden>
              📄
            </div>
            <p className="font-medium text-slate-700">
              Drag &amp; drop your log file here
            </p>
            <p className="mt-1 text-sm text-slate-500">
              or click to browse — .json / .log / .txt, up to 25 MB
            </p>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />

      {error && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {MOCK && !uploading && (
        <p className="mt-3 text-center text-xs text-slate-400">
          Mock mode is on (NEXT_PUBLIC_MOCK_API=1) — no backend needed.
        </p>
      )}
    </div>
  );
}
