import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Hero({ children }: { children?: React.ReactNode }) {
  return (
    <section className="relative isolate flex min-h-screen flex-col items-center justify-start px-6 py-20 md:py-24">
      <div
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        aria-hidden
      >
        <div className="absolute inset-x-0 top-0 h-[50vh] bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.06),transparent_60%)]" />
      </div>

      <div className="mb-8 inline-flex max-w-full flex-wrap items-center justify-center gap-2 rounded-full border border-gray-700 bg-gray-800/50 px-4 py-2 backdrop-blur-sm">
        <span className="whitespace-nowrap text-center text-xs text-gray-400">
          Rule-based detection: threats, DLP hits, data exfiltration
        </span>
        <Link
          href="#how-it-works"
          className="flex items-center gap-1 whitespace-nowrap text-xs text-gray-400 transition-all hover:text-white active:scale-95"
        >
          How it works
          <ArrowRight size={12} />
        </Link>
      </div>

      <h1
        className="mb-6 max-w-3xl px-6 text-center text-4xl font-medium leading-tight md:text-5xl lg:text-6xl"
        style={{
          background:
            "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255, 255, 255, 0.6))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          letterSpacing: "-0.05em",
        }}
      >
        Give your web logs <br />
        the timeline they deserve
      </h1>

      <p className="mb-10 max-w-2xl px-6 text-center text-sm text-gray-400 md:text-base">
        Drop in a Zscaler NSS web-log export and get parsed events, a
        human-readable timeline, and rule-based anomalies flagged for you.
      </p>

      {!children && (
        <div className="relative z-10 mb-16 flex items-center gap-4">
          <Link href="/upload">
            <Button
              type="button"
              variant="gradient"
              size="lg"
              className="rounded-lg"
              aria-label="Upload a log file"
            >
              Get started
            </Button>
          </Link>
        </div>
      )}

      {children && (
        <div className="relative z-10 w-full max-w-2xl pb-10">{children}</div>
      )}
    </section>
  );
}
