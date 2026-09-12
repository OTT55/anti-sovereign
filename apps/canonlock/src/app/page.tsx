"use client";

import type { Certificate } from "@/lib/registry";
import { sha256HexOfFile } from "@/lib/hash-file.client";
import { useEffect, useState } from "react";

interface Stats {
  count: number;
  merkleRoot: string | null;
}

export default function RegisterPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileHash, setFileHash] = useState<string | null>(null);
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [certificate, setCertificate] = useState<Certificate | null>(null);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => setStats(null));
  }, [certificate]);

  async function handleFileChange(selected: File | null) {
    setFile(selected);
    setFileHash(null);
    setCertificate(null);
    setError(null);
    if (selected) {
      const hash = await sha256HexOfFile(selected);
      setFileHash(hash);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !fileHash) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          handle,
          displayName,
          fileHash,
          filename: file.name,
          description: description || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "registration failed");
      }
      setCertificate(data as Certificate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="vibe-eyebrow font-mono text-xs uppercase tracking-widest text-accent">
          SHA-256 IP Registry
        </p>
        <h1 className="font-display text-3xl font-semibold text-text">Register a work</h1>
        <p className="mt-2 text-muted">
          Your file never leaves this device — only its SHA-256 hash is registered, sealed with a
          Merkle inclusion proof and a signed certificate.
        </p>
        {stats && (
          <p className="mt-4 font-mono text-xs text-muted">
            {stats.count} works registered · current root{" "}
            <span className="text-text">{stats.merkleRoot?.slice(0, 16) ?? "—"}…</span>
          </p>
        )}
      </section>

      {!certificate ? (
        <form onSubmit={handleSubmit} className="glass-card space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm text-muted">File</label>
            <input
              type="file"
              required
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
            />
            {fileHash && <p className="mt-2 break-all font-mono text-xs text-muted">{fileHash}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
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
            <div>
              <label className="mb-1 block text-sm text-muted">Display name</label>
              <input
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your Name"
                className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={!fileHash || busy}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-bg transition-colors duration-fast disabled:opacity-50"
          >
            {busy ? "Registering…" : "Register"}
          </button>
        </form>
      ) : (
        <CertificateCard certificate={certificate} onReset={() => setCertificate(null)} />
      )}
    </div>
  );
}

function CertificateCard({
  certificate,
  onReset,
}: {
  certificate: Certificate;
  onReset: () => void;
}) {
  return (
    <div className="glass-card space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold text-text">{certificate.registryId}</h2>
        <span className="rounded-pill bg-ok/10 px-2 py-0.5 font-mono text-xs text-ok">
          Registered
        </span>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 font-mono text-xs">
        <dt className="text-muted">File</dt>
        <dd className="text-text">{certificate.filename}</dd>
        <dt className="text-muted">Hash</dt>
        <dd className="break-all text-text">{certificate.fileHash}</dd>
        <dt className="text-muted">Signature</dt>
        <dd className="break-all text-text">{certificate.signature}</dd>
        <dt className="text-muted">Merkle root</dt>
        <dd className="break-all text-text">{certificate.merkleRoot}</dd>
        <dt className="text-muted">Leaf index</dt>
        <dd className="text-text">{certificate.leafIndex}</dd>
        <dt className="text-muted">Timestamp</dt>
        <dd className="text-text">
          {certificate.tsa.status === "granted" ? (
            <>
              {certificate.tsa.grantedAt ?? "granted"} via {certificate.tsa.server}
            </>
          ) : (
            <span className="text-warn">unavailable — {certificate.tsa.reason}</span>
          )}
        </dd>
      </dl>
      <button
        onClick={onReset}
        className="rounded-sm border border-border px-4 py-2 text-sm text-text hover:border-accent"
      >
        Register another
      </button>
    </div>
  );
}
