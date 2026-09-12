"use client";

import type { VerifyResult } from "@/lib/registry";
import { sha256HexOfFile } from "@/lib/hash-file.client";
import { useState } from "react";

export default function VerifyPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);

  async function handleFile(file: File | null) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const hash = await sha256HexOfFile(file);
      const res = await fetch(`/api/verify?hash=${hash}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "verification failed");
      setResult(data as VerifyResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "verification failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Verify</p>
        <h1 className="font-display text-3xl font-semibold text-text">Check a registration</h1>
        <p className="mt-2 text-muted">
          Choose a file to check whether it — or rather its SHA-256 hash — is registered, and
          confirm its certificate and Merkle inclusion proof independently.
        </p>
      </section>

      <div className="glass-card space-y-4 p-6">
        <input
          type="file"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
        />
        {busy && <p className="text-sm text-muted">Verifying…</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
        {result && <VerifyOutcome result={result} />}
      </div>
    </div>
  );
}

function VerifyOutcome({ result }: { result: VerifyResult }) {
  if (!result.registered) {
    return (
      <p className="rounded-sm border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-warn">
        Not registered — this exact file hash has no entry in Canonlock.
      </p>
    );
  }

  const allValid = result.signatureValid && result.inclusionValid;

  return (
    <div className="space-y-4">
      <p
        className={`rounded-sm border px-4 py-3 text-sm ${
          allValid ? "border-ok/30 bg-ok/10 text-ok" : "border-danger/30 bg-danger/10 text-danger"
        }`}
      >
        {allValid ? "Verified — signature and inclusion proof both check out." : "Registered, but verification failed — see details below."}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 font-mono text-xs">
        <dt className="text-muted">Registry ID</dt>
        <dd className="text-text">{result.registryId}</dd>
        <dt className="text-muted">Owner</dt>
        <dd className="text-text">@{result.handle}</dd>
        <dt className="text-muted">Filename</dt>
        <dd className="text-text">{result.filename}</dd>
        <dt className="text-muted">Registered</dt>
        <dd className="text-text">{result.createdAt}</dd>
        <dt className="text-muted">Signature</dt>
        <dd className={result.signatureValid ? "text-ok" : "text-danger"}>
          {result.signatureValid ? "valid" : "INVALID"}
        </dd>
        <dt className="text-muted">Inclusion proof</dt>
        <dd className={result.inclusionValid ? "text-ok" : "text-danger"}>
          {result.inclusionValid ? `valid against root ${result.merkleRoot.slice(0, 16)}…` : "INVALID"}
        </dd>
        <dt className="text-muted">Timestamp</dt>
        <dd className="text-text">
          {result.tsa.status === "granted" ? (
            <>
              {result.tsa.grantedAt ?? "granted"} via {result.tsa.server}
            </>
          ) : (
            <span className="text-warn">unavailable</span>
          )}
        </dd>
      </dl>
    </div>
  );
}
