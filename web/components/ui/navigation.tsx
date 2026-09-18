"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, ShieldAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/upload", label: "Upload" },
  { href: "/demo", label: "Template" },
];

export default function Navigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="fixed top-0 z-50 w-full border-b border-gray-800/50 bg-black/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 text-white">
          <ShieldAlert size={20} className="text-white/80" aria-hidden />
          <span className="text-base font-semibold sm:text-lg">
            Security Anomaly Explorer
          </span>
        </Link>

        <div className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 items-center gap-8 md:flex">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm transition-colors",
                isActive(link.href)
                  ? "text-white"
                  : "text-white/60 hover:text-white",
              )}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <Link
          href="/upload"
          className="hidden rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100 md:inline-flex"
        >
          Analyze a log
        </Link>

        <button
          type="button"
          className="text-white md:hidden"
          onClick={() => setMobileMenuOpen((open) => !open)}
          aria-label="Toggle menu"
          aria-expanded={mobileMenuOpen}
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </nav>

      {mobileMenuOpen && (
        <div className="animate-[slideDown_0.3s_ease-out] border-t border-gray-800/50 bg-black/95 backdrop-blur-md md:hidden">
          <div className="flex flex-col gap-4 px-6 py-4">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "py-2 text-sm transition-colors",
                  isActive(link.href)
                    ? "text-white"
                    : "text-white/60 hover:text-white",
                )}
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <div className="border-t border-gray-800/50 pt-4">
              <Link
                href="/upload"
                className="inline-flex rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-gray-100"
                onClick={() => setMobileMenuOpen(false)}
              >
                Analyze a log
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
