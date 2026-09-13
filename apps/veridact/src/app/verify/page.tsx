"use client";

import { useState } from "react";

interface VerifyResponse {
  fileHash: string;
  verdict: "VERIFIED_CAPTURE" | "SIGNATURE_INVALID" | "RECOMPRESSED" | "ALTERED" | "UNVERIFIED";
  manifestId?: string;
  handle?: string;
  capturedAt?: string;
  label?: string | null;
}

const VERDICT_COPY: Record<VerifyResponse["verdict"], { label: string; tone: string }> = {
  VERIFIED_CAPTURE: { label: "Verified capture — hash and signature both check out.", tone: "text-ok border-ok/30 bg-ok/10" },
  SIGNATURE_INVALID: { label: "Hash matches, but the signature is invalid.", tone: "text-danger border-danger/30 bg-danger/10" },
  RECOMPRESSED: {
    label: "Recompressed — bytes changed, but the embedded watermark traces back to a real capture.",
    tone: "text-warn border-warn/30 bg-warn/10",
  },
  ALTERED: { label: "Altered — this doesn't match the capture it claims to be.", tone: "text-danger border-danger/30 bg-danger/10" },
  UNVERIFIED: { label: "Unverified — no record of this file.", tone: "text-muted border-border bg-surface" },
};

export default function VerifyPage() {
  const [manifestId, setManifestId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  async function handleFile(file: File | null) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.set("file", file);
      if (manifestId.trim()) form.set("manifestId", manifestId.trim());
      const res = await fetch("/api/verify", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "verification failed");
      setResult(data as VerifyResponse);
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
        <h1 className="font-display text-3xl font-semibold text-text">Check a capture</h1>
        <p className="mt-2 text-muted">
          Upload a file to check it against Veridact's records — by exact hash, embedded
          watermark, or a manifest ID you believe it should match.
        </p>
      </section>

      <div className="glass-card space-y-4 p-6">
        <div>
          <label className="mb-1 block text-sm text-muted">Manifest ID (optional)</label>
          <input
            value={manifestId}
            onChange={(e) => setManifestId(e.target.value)}
            placeholder="VD-XXXXXXXX"
            className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
        </div>
        <input
          type="file"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
        />
        {busy && <p className="text-sm text-muted">Verifying…</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
        {result && (
          <div className={`space-y-3 rounded-sm border px-4 py-3 text-sm ${VERDICT_COPY[result.verdict].tone}`}>
            <p>{VERDICT_COPY[result.verdict].label}</p>
            {result.manifestId && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-xs text-text/80">
                <dt>Manifest</dt>
                <dd>{result.manifestId}</dd>
                {result.handle && (
                  <>
                    <dt>Device</dt>
                    <dd>@{result.handle}</dd>
                  </>
                )}
                {result.capturedAt && (
                  <>
                    <dt>Captured</dt>
                    <dd>{result.capturedAt}</dd>
                  </>
                )}
              </dl>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
