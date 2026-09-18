import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import FileUpload from "@/components/FileUpload";
import Hero from "@/components/ui/hero";
import { SESSION_COOKIE, isAuthEnabled, verifySessionValue } from "@/lib/auth";

// Auth state is per-request; never bake it (or the env lookups) at build time.
export const dynamic = "force-dynamic";

const STEPS = [
  "The file is parsed into normalized events.",
  "Rule-based detection flags threats, DLP hits, bursts, and more.",
  "You get a timeline, summary stats, and a filterable event table.",
];

export default async function UploadPage() {
  const authEnabled = isAuthEnabled();
  const loggedIn = authEnabled
    ? await verifySessionValue((await cookies()).get(SESSION_COOKIE)?.value)
    : true;

  if (!loggedIn) redirect("/login");

  return (
    <div className="min-h-screen bg-black text-white">
      <Hero>
        <FileUpload />
      </Hero>

      <section id="how-it-works" className="mx-auto max-w-3xl px-6 pb-24">
        <div className="rounded-2xl border border-gray-800 bg-gray-900/40 p-6 backdrop-blur-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-white/60">
            What happens next
          </h2>
          <ol className="space-y-3">
            {STEPS.map((step, i) => (
              <li key={step} className="flex gap-3 text-sm text-white/70">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
