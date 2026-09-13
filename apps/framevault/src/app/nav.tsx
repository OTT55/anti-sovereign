"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface Identity {
  handle: string;
  displayName: string;
  verified: boolean;
}

export function AuthNav() {
  const [identity, setIdentity] = useState<Identity | null | undefined>(undefined);

  useEffect(() => {
    fetch("/api/me")
      .then((r) => r.json())
      .then((d) => setIdentity(d.identity))
      .catch(() => setIdentity(null));
  }, []);

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/";
  }

  return (
    <nav className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
      <Link href="/" className="font-display text-lg font-semibold text-text">
        Frame<span className="text-accent">Vault</span>
      </Link>
      <div className="flex items-center gap-6 font-mono text-sm text-muted">
        <Link href="/verify" className="hover:text-text">
          Verify
        </Link>
        {identity === undefined ? null : identity ? (
          <>
            <Link href="/dashboard" className="hover:text-text">
              Dashboard
            </Link>
            <Link href="/settings" className="hover:text-text">
              Settings
            </Link>
            <button onClick={handleLogout} className="hover:text-text">
              Log out
            </button>
          </>
        ) : (
          <>
            <Link href="/login" className="hover:text-text">
              Log in
            </Link>
            <Link href="/signup" className="rounded-sm bg-accent px-3 py-1.5 text-white">
              Sign up
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
