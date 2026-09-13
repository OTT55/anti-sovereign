"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

async function sha256HexOfFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function RegisterWorkForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [aiDisclosure, setAiDisclosure] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const contentHash = await sha256HexOfFile(file);
      const res = await fetch("/api/provenance", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ contentHash, filename: file.name, title: title || undefined, aiDisclosure: aiDisclosure || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "registration failed");
      setFile(null);
      setTitle("");
      setAiDisclosure("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card space-y-4 p-6">
      <h2 className="font-display text-lg font-semibold text-text">Register a work</h2>
      <p className="text-xs text-muted">
        Hashed entirely in your browser — the file itself never leaves your device.
      </p>
      <input
        type="file"
        required
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block w-full text-sm text-text file:mr-4 file:rounded-sm file:border-0 file:bg-accent-subtle file:px-3 file:py-1.5 file:text-accent"
      />
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (optional)"
        className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
      />
      <input
        value={aiDisclosure}
        onChange={(e) => setAiDisclosure(e.target.value)}
        placeholder="AI disclosure (optional)"
        className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
      />
      {error && <p className="text-sm text-danger">{error}</p>}
      <button
        type="submit"
        disabled={!file || busy}
        className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? "Registering…" : "Register"}
      </button>
    </form>
  );
}
