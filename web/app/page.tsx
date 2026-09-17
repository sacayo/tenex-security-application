import FileUpload from "@/components/FileUpload";

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold">Upload a web-log file</h2>
        <p className="mt-1 text-sm text-slate-600">
          Drop a NSS web-log export (JSON) and get a timeline of what
          happened, with anomalies flagged.
        </p>
      </div>
      <FileUpload />
      <div className="mt-8 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <h3 className="mb-2 font-semibold text-slate-800">What happens next</h3>
        <ol className="list-decimal space-y-1 pl-5">
          <li>The file is parsed into normalized events.</li>
          <li>Rule-based detection flags threats, DLP hits, bursts, and more.</li>
          <li>You get a timeline, summary stats, and a filterable event table.</li>
        </ol>
      </div>
    </div>
  );
}
