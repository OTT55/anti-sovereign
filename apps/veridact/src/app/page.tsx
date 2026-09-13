"use client";

import { exportPublicKeySpkiBase64, generateDeviceKeyPair } from "@/lib/browser-crypto.client";
import { saveKeyPair } from "@/lib/keystore.client";
import Link from "next/link";
import { useEffect, useState } from "react";

interface Stats {
  deviceCount: number;
  manifestCount: number;
}

export default function EnrollPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrolled, setEnrolled] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => setStats(null));
  }, [enrolled]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const keyPair = await generateDeviceKeyPair();
      const publicKeySpki = await exportPublicKeySpkiBase64(keyPair.publicKey);

      const res = await fetch("/api/enroll", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ handle, publicKeySpki }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "enrollment failed");

      // The private key stays non-extractable end to end — only IndexedDB's
      // structured clone can move it, and even that never exposes raw bytes.
      await saveKeyPair(handle, keyPair);
      setEnrolled(handle);
    } catch (err) {
      setError(err instanceof Error ? err.message : "enrollment failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Capture Attestation</p>
        <h1 className="font-display text-3xl font-semibold text-text">Enrol a device</h1>
        <p className="mt-2 text-muted">
          Generates a real ECDSA P-256 keypair in your browser. The private key is
          non-extractable — it never leaves this device, not even in principle.
        </p>
        {stats && (
          <p className="mt-4 font-mono text-xs text-muted">
            {stats.deviceCount} devices enrolled · {stats.manifestCount} captures attested
          </p>
        )}
      </section>

      {!enrolled ? (
        <form onSubmit={handleSubmit} className="glass-card space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm text-muted">Handle</label>
            <input
              required
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="yourhandle"
              className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white transition-colors duration-fast disabled:opacity-50"
          >
            {busy ? "Generating key…" : "Enrol"}
          </button>
        </form>
      ) : (
        <div className="glass-card space-y-4 p-6">
          <p className="text-sm text-ok">Enrolled as @{enrolled}.</p>
          <Link
            href="/authenticate"
            className="inline-block rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white"
          >
            Go capture something →
          </Link>
        </div>
      )}
    </div>
  );
}
