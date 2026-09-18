export default function Loading() {
  return (
    <div className="min-h-screen bg-black px-4 py-8">
      <div className="mx-auto max-w-6xl space-y-4" aria-busy="true">
        <div className="h-16 animate-pulse rounded-xl bg-gray-800/60" />
        <div className="h-24 animate-pulse rounded-xl bg-gray-800/60" />
        <div className="h-48 animate-pulse rounded-xl bg-gray-800/60" />
        <div className="h-64 animate-pulse rounded-xl bg-gray-800/60" />
      </div>
    </div>
  );
}
