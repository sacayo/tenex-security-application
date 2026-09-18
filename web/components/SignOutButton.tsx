"use client";

import { useState } from "react";

export default function SignOutButton({ className }: { className?: string }) {
  const [pending, setPending] = useState(false);

  async function signOut() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      // Full-document navigation so the cleared cookie takes effect and the
      // middleware gate re-evaluates on a fresh request.
      window.location.assign("/login");
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={signOut}
      disabled={pending}
      className={className}
    >
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}
