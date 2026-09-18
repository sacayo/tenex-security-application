import FileUpload from "@/components/FileUpload";

export default function UploadPage() {
  return (
    <div className="min-h-screen bg-black px-6 py-16 text-white">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 text-center">
          <h1
            className="text-3xl font-medium leading-tight md:text-4xl"
            style={{
              background:
                "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255, 255, 255, 0.6))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              letterSpacing: "-0.03em",
            }}
          >
            Upload a web-log file
          </h1>
          <p className="mt-3 text-sm text-gray-400">
            Drop a NSS web-log export and get a timeline of what happened,
            with anomalies flagged.
          </p>
        </div>
        <FileUpload />
      </div>
    </div>
  );
}
