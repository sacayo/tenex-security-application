import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Security Anomaly Explorer",
  description:
    "Upload web logs in NSS output formatand see a human-readable timeline of events and anomalies.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="bg-slate-900 text-white shadow">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
            <span className="text-xl" aria-hidden>
              🛡️
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                Security Anomaly Explorer
              </h1>
              <p className="text-xs text-slate-400">
                Security web-log timeline &amp; anomaly viewer
              </p>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
