"use client";

import { useEffect, useState } from "react";

interface Stats {
  count: number;
  merkleRoot: string | null;
}

/** Renders nothing on failure or before load — never a stuck placeholder. */
export function LiveRoot() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/stats")
      .then((r) => r.json())
      .then((data: Stats) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!stats?.merkleRoot) return null;

  return (
    <p className="font-mono text-step--1 text-muted">
      {stats.count} {stats.count === 1 ? "work" : "works"} sealed · root{" "}
      <span className="tabular-nums text-text">{stats.merkleRoot.slice(0, 16)}…</span>
    </p>
  );
}
