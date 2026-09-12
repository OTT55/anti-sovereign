"use client";

import { APPS } from "@anti-sovereign/design-system/apps-registry";
import type { HealthStatus } from "@/lib/health";
import { useEffect, useState } from "react";

const POLL_INTERVAL_MS = 5000;

export default function GatewayPage() {
  const [health, setHealth] = useState<Record<string, HealthStatus>>({});

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.error("service worker registration failed", err);
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch("/api/health");
        const data = await res.json();
        if (!cancelled) setHealth(data);
      } catch {
        // leave the previous state in place; the next poll will retry
      }
    }
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-10">
        <p className="font-mono text-xs uppercase tracking-widest text-muted">Anti-Sovereign</p>
        <h1 className="font-display text-3xl font-semibold text-text">Gateway</h1>
        <p className="mt-2 text-muted">Live status for every app in the portfolio.</p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {APPS.map((app) => {
          const status = health[app.id];
          return (
            <a
              key={app.id}
              href={`http://localhost:${app.port}`}
              target="_blank"
              rel="noreferrer"
              className="glass-card block p-5 transition-transform duration-fast hover:-translate-y-0.5"
              style={{ borderColor: status?.online ? `${app.accent}55` : undefined }}
            >
              <div className="flex items-center justify-between">
                <h2 className="font-display text-lg font-semibold" style={{ color: app.accent }}>
                  {app.name}
                </h2>
                <StatusBadge status={status} />
              </div>
              <p className="mt-1 text-sm text-muted">{app.description}</p>
              <p className="mt-3 font-mono text-xs text-muted">
                {app.category} · :{app.port}
              </p>
            </a>
          );
        })}
      </div>
    </main>
  );
}

function StatusBadge({ status }: { status?: HealthStatus }) {
  if (!status) {
    return <span className="font-mono text-xs text-muted">checking…</span>;
  }
  const color = status.status === "Healthy" ? "text-ok" : status.status === "Port Open" ? "text-warn" : "text-muted";
  return <span className={`font-mono text-xs ${color}`}>{status.status}</span>;
}
