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
      <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Invalid upload id.
      </p>
    );
  }

  return <ResultsView uploadId={uploadId} />;
}
