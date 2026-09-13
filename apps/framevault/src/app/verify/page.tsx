"use client";

import Link from "next/link";
import { useState } from "react";

async function sha256HexOfFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

interface VerifyResult {
  registered: boolean;
  registryId?: string;
  filename?: string;
  title?: string | null;
  createdAt?: string;
  signatureValid?: boolean;
  owner?: { handle: string; displayName: string };
}

export default function VerifyPage() {
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(file: File | null) {
    if (!file) return;
    setBusy(true);
    try {
      const hash = await sha256HexOfFile(file);
      const res = await fetch("/api/verify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ hash }),
      });
      setResult(await res.json());
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Verify</p>
        <h1 className="font-display text-3xl font-semibold text-text">Check a work's provenance</h1>
        <p className="mt-2 text-muted">Hashed entirely in your browser — the file itself never leaves your device.</p>
      </section>

      <div className="glass-card space-y-4 p-6">
        <input
          type="file"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
        />
        {busy && <p className="text-sm text-muted">Checking…</p>}
        {result && !result.registered && <p className="text-sm text-muted">Not registered with FrameVault.</p>}
        {result?.registered && (
          <div
            className={`space-y-2 rounded-sm border px-4 py-3 text-sm ${
              result.signatureValid ? "border-ok/30 bg-ok/10 text-ok" : "border-danger/30 bg-danger/10 text-danger"
            }`}
          >
            <p>{result.signatureValid ? "Registered — signature verified." : "Registered, but the signature does not check out."}</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-xs text-text/80">
              <dt>Registry</dt>
              <dd>{result.registryId}</dd>
              <dt>Title</dt>
              <dd>{result.title ?? result.filename}</dd>
              {result.owner && (
                <>
                  <dt>Owner</dt>
                  <dd>
                    <Link href={`/@${result.owner.handle}`} className="underline">
                      @{result.owner.handle}
                    </Link>
                  </dd>
                </>
              )}
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
