import ResultsView from "@/components/ResultsView";

export default async function ResultsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const uploadId = Number(id);

  if (!Number.isInteger(uploadId) || uploadId <= 0) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          Invalid upload id.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black px-4 py-8">
      <div className="mx-auto max-w-6xl">
        <ResultsView uploadId={uploadId} />
      </div>
    </div>
  );
}
