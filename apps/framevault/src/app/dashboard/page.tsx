import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import { db } from "@/db";
import { users } from "@/db/schema";
import { listProvenanceForUser } from "@/lib/provenance";
import { getDashboardStats } from "@/lib/profile";
import { getSessionUserId } from "@/lib/session";
import { RegisterWorkForm } from "./register-work-form";

export default async function DashboardPage() {
  const userId = await getSessionUserId();
  if (!userId) redirect("/login");

  const [user, stats, provenance] = await Promise.all([
    db.select().from(users).where(eq(users.id, userId)).get(),
    getDashboardStats(userId),
    listProvenanceForUser(userId),
  ]);

  return (
    <div className="space-y-8">
      <section>
        <p className="font-mono text-xs uppercase tracking-widest text-accent">Dashboard</p>
        <h1 className="font-display text-3xl font-semibold text-text">@{user!.handle}</h1>
        <div className="mt-4 grid grid-cols-3 gap-4">
          <Stat label="Reputation" value={stats.reputation} />
          <Stat label="Portfolio pieces" value={stats.provenanceCount} />
          <Stat label="Total spend" value={`£${(stats.spendPence / 100).toFixed(2)}`} />
        </div>
      </section>

      <RegisterWorkForm />

      <section className="space-y-2">
        <h2 className="font-display text-lg font-semibold text-text">Your portfolio</h2>
        {provenance.map((p) => (
          <div key={p.registryId} className="glass-card p-4 text-sm">
            <p className="font-mono text-text">{p.registryId}</p>
            <p className="text-xs text-muted">{p.title ?? p.filename}</p>
          </div>
        ))}
        {provenance.length === 0 && <p className="text-sm text-muted">Nothing registered yet.</p>}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="glass-card p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="font-display text-2xl font-semibold text-text">{value}</p>
    </div>
  );
}
