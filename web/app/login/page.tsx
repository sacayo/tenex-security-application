import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import ModernLoginSignup from "@/components/ui/modern-login-signup";
import { SESSION_COOKIE, isAuthEnabled, verifySessionValue } from "@/lib/auth";

// Auth state is per-request; never bake it (or the env lookups) at build time.
export const dynamic = "force-dynamic";

function safeNext(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/upload";
  return raw;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  // Without configured credentials there is nothing to sign in to.
  if (!isAuthEnabled()) redirect("/");

  const next = safeNext((await searchParams).next);
  const loggedIn = await verifySessionValue(
    (await cookies()).get(SESSION_COOKIE)?.value,
  );
  if (loggedIn) redirect(next);

  return <ModernLoginSignup next={next} />;
}
