"use client";

import Link from "next/link";
import { useState } from "react";

interface SearchResult {
  handle: string;
  displayName: string;
}

export default function HomePage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    setResults(await res.json());
    setSearched(true);
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">CreativeOS</p>
        <h1 className="font-display text-3xl font-semibold text-text">FrameVault</h1>
        <p className="mt-2 text-muted">
          Dailies and asset vault, and the identity + reputation hub for the whole CreativeOS
          suite — one account, one portfolio, one reputation across every product.
        </p>
      </section>

      <form onSubmit={handleSearch} className="glass-card flex gap-2 p-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search creators by handle or skill…"
          className="flex-1 rounded-sm border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
        />
        <button type="submit" className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white">
          Search
        </button>
      </form>

      {searched && (
        <div className="space-y-2">
          {results.map((r) => (
            <Link
              key={r.handle}
              href={`/@${r.handle}`}
              className="glass-card block p-4 text-sm hover:border-accent-border"
            >
              <p className="text-text">{r.displayName}</p>
              <p className="font-mono text-xs text-muted">@{r.handle}</p>
            </Link>
          ))}
          {results.length === 0 && <p className="text-sm text-muted">No creators matched.</p>}
        </div>
      )}
    </div>
  );
}
