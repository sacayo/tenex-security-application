import Hero from "@/components/ui/hero";

/**
 * Landing-page composition adapted from the original `saa-s-template`.
 *
 * The fixed site navigation now lives in `app/layout.tsx` (it applies to the
 * whole app), so this component is just the page shell + hero. It is used by
 * the `/demo` route as an isolated preview of the template styling.
 */
export default function LandingPage({
  children,
}: {
  children?: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-black text-white">
      <Hero>{children}</Hero>
    </div>
  );
}
