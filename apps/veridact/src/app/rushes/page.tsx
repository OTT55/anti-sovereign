"use client";

import { sha256HexOfBlob } from "@/lib/browser-crypto.client";
import { useEffect, useState } from "react";

interface Rush {
  rushId: string;
  production: string;
  rollNumber: string | null;
  sceneTake: string | null;
  fileName: string;
  mediaHash: string;
  framerate: string | null;
  ditNotes: string | null;
  capturedAt: string;
  createdAt: string;
}

export default function RushesPage() {
  const [rushes, setRushes] = useState<Rush[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [production, setProduction] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [sceneTake, setSceneTake] = useState("");
  const [framerate, setFramerate] = useState("");
  const [ditNotes, setDitNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const res = await fetch("/api/rushes/list");
    setRushes(await res.json());
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleFile(selected: File | null) {
    setFile(selected);
    setHash(selected ? await sha256HexOfBlob(selected) : null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !hash) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/rushes/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          production,
          rollNumber: rollNumber || undefined,
          sceneTake: sceneTake || undefined,
          fileName: file.name,
          mediaHash: hash,
          framerate: framerate || undefined,
          ditNotes: ditNotes || undefined,
          capturedAt: new Date().toISOString(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "registration failed");
      setFile(null);
      setHash(null);
      setRollNumber("");
      setSceneTake("");
      setFramerate("");
      setDitNotes("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Film Rushes</p>
        <h1 className="font-display text-3xl font-semibold text-text">DIT camera-card log</h1>
        <p className="mt-2 text-muted">
          A simpler hash registry for production rushes — no signature, just a SHA-256
          fingerprint against roll/scene/take metadata.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="glass-card space-y-4 p-6">
        <input
          type="file"
          required
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
        />
        {hash && <p className="break-all font-mono text-xs text-muted">{hash}</p>}
        <div className="grid grid-cols-2 gap-4">
          <input
            required
            value={production}
            onChange={(e) => setProduction(e.target.value)}
            placeholder="Production"
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <input
            value={rollNumber}
            onChange={(e) => setRollNumber(e.target.value)}
            placeholder="Roll number"
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <input
            value={sceneTake}
            onChange={(e) => setSceneTake(e.target.value)}
            placeholder="Scene/Take"
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <input
            value={framerate}
            onChange={(e) => setFramerate(e.target.value)}
            placeholder="Framerate"
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
        </div>
        <textarea
          value={ditNotes}
          onChange={(e) => setDitNotes(e.target.value)}
          placeholder="DIT notes"
          rows={2}
          className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={!hash || busy}
          className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Logging…" : "Log rush"}
        </button>
      </form>

      <div className="space-y-2">
        {rushes.map((r) => (
          <div key={r.rushId} className="glass-card flex items-center justify-between p-4 text-sm">
            <div>
              <p className="font-mono text-text">{r.rushId}</p>
              <p className="text-xs text-muted">
                {r.production} · {r.rollNumber ?? "—"}/{r.sceneTake ?? "—"} · {r.fileName}
              </p>
            </div>
            <p className="font-mono text-xs text-muted">{r.framerate ?? ""}</p>
          </div>
        ))}
        {rushes.length === 0 && <p className="text-sm text-muted">No rushes logged yet.</p>}
      </div>
    </div>
  );
}
